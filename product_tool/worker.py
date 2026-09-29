"""Bounded background worker for LG official regions, the trusted LG
supplier (Sulpak), the HyperX official adapter (Stage 14), the Samsung
official adapter (Stage 26), and the DNS
dealer fallback (available for any brand/category, per explicit user
authorization -- Stage 11.3/11.4)."""
from __future__ import annotations
import argparse, json, logging, os, re, time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable
from . import bosch_pipeline, jobs, samsung_pipeline
from .adapters.common import ProductDocument, SourceDocument
from .adapters.dns import DnsAdapter
from .adapters.bosch_home import BoschHomeAdapter
from .adapters.hyperx import HyperXAdapter
from .adapters.lg import LGAdapter, LGRUAdapter, lg_article_components, lg_base_model, normalize_lg_sku
from .lg_identity import structured_sales_relation
from .adapters.lg_policy import default_lg_adapters
from .adapters.lg_support import LGSupportAdapter, is_official_support_url, observed_product_support_urls
from .adapters.samsung_source import default_samsung_adapter
from .fetch_history import latest_source_snapshot
from .readiness import card_readiness, readiness_text
from .adapters.sulpak import SulpakAdapter
from .resolution import SUPPLIERS

LOGGER=logging.getLogger(__name__)
PROJECT_DIR=Path(__file__).resolve().parents[1]
TOTAL_BUDGET_SECONDS=60
# Stage 43: was 20s; a row whose sitemap lookup does not reach full_sku now also gets one bounded LG
# site-search attempt (adapters/lg_browser_search.py) inside this same window -- a real browser render
# takes a few seconds per query, so the shared KZ+RU budget needed room for it. Rows the sitemap already
# resolves to full_sku are unaffected: find_source() returns before this budget is ever pressured.
OFFICIAL_BUDGET_SECONDS=45
FALLBACK_BUDGET_SECONDS=30
DNS_BUDGET_SECONDS=10
# Brand labels (case-folded) that select an adapter branch in run_once(). Exposed
# so the offline coverage planner reads the real dispatch table instead of a copy.
LG_BRAND_ALIASES=frozenset({"lg","lg electronics","лджи","элджи"})
HYPERX_BRAND_ALIASES=frozenset({"hyperx"})
BOSCH_HOME_BRAND_ALIASES=frozenset({"bosch"})
SAMSUNG_BRAND_ALIASES=frozenset({"samsung","samsung electronics","самсунг"})

def _save(database, product_id, document, stages):
    jobs.save_source_document(database,product_id,document,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)

def _model_tokens_from_name(name: str) -> list[str]:
    """Latin-script tokens from the catalog name (e.g. 'QuadCast', '2S',
    'Black' out of 'Микрофон для пк игровой QuadCast 2S Black') -- this
    catalog's convention keeps model/variant words in Latin script inside
    otherwise-Cyrillic descriptive names."""
    return [tok for tok in re.findall(r"[A-Za-z0-9]+", name or "") if len(tok) >= 2]


def _effective_product_name(product: dict) -> str:
    """Older imports sometimes put a descriptive name in 'alternate_code'."""
    name = (product.get("name") or "").strip()
    alternate = (product.get("alternate_code") or "").strip()
    if name:
        return name
    if len(alternate.split()) >= 2 and re.search(r"[А-Яа-яЁё]", alternate):
        return alternate
    return ""


def _lg_model_candidates_from_name(name: str, article: str) -> tuple[str, ...]:
    """A shorter code printed in the name may locate a page, never prove its variant."""
    components = lg_article_components(article)
    models = []
    for candidate in re.findall(r"(?<![A-Za-z0-9])([A-Za-z0-9][A-Za-z0-9-]{3,})(?![A-Za-z0-9])", name or ""):
        code = candidate.upper()
        if re.search(r"[A-Z]", code) and re.search(r"\d", code) and any(part.startswith(code) for part in components):
            models.append(code)
    return tuple(dict.fromkeys(models))

def _compute_missing_fields(database, product_id, stages: list[int]) -> list[str]:
    """Concrete, per-row check of which categories the job actually
    requested (stages) still have zero data from any source already saved
    for this product -- never a hardcoded assumption. Called AFTER any
    official/Sulpak stage-1 processing for this same run, so a field
    those already found is correctly excluded before DNS is even asked
    about it, and re-running the job for a row that has since been filled
    (by any source) stops asking about that field."""
    missing = []
    if 3 in stages and not jobs.get_facts(database, product_id):
        missing.append("характеристики")
    if 4 in stages and not jobs.get_photo_candidates(database, product_id, include_excluded=False):
        missing.append("фото")
    if 6 in stages and not jobs.get_documents(database, product_id):
        missing.append("инструкция")
    return missing

def _save_dns_documents(database, product_id, dns_documents: list[dict]) -> None:
    jobs.save_documents(database, product_id, "dns", [
        ProductDocument(
            title=d["title"], language=d["language"], document_date="", size="",
            direct_url=d["direct_url"], source_url=d["source_url"],
            product_model=d["product_model"], support_model=d["support_model"],
            relation_url=d["relation_url"], primary=bool(d.get("primary", False)),
        )
        for d in dns_documents
    ])

def _has_retained_documents(database: Path, product_id: int, source_key: str) -> bool:
    """A prior verified document remains tied to the same saved source page."""
    page = next((item for item in jobs.get_source_pages(database, product_id)
                 if item["source_key"] == source_key), None)
    return bool(page and page["url"] and not page["error"]
                and any(item["source_key"] == source_key
                        and item["relation_url"] == page["url"]
                        for item in jobs.get_documents(database, product_id)))


def run_once(
    database: Path, adapter_factory=None, *,
    clock: Callable[[],float]=time.monotonic,
    dns_adapter_factory: Callable[[], DnsAdapter] | None = None,
    hyperx_adapter_factory: Callable[[], HyperXAdapter] | None = None,
    samsung_adapter_factory: Callable[[], object] | None = None,
    bosch_adapter_factory: Callable[[], BoschHomeAdapter] | None = None,
    lg_support_adapter_factory: Callable[[], LGSupportAdapter] | None = None,
) -> bool:
    job=jobs.claim_next(database)
    if job is None: return False
    job_id,product_id=job["id"],job["product_id"]
    lg_browser_search = None  # Stage 43: initialized before every early return so the closing finally below is always safe
    try:
        product=jobs.get_product(database,product_id)
        if not product:
            jobs.finish(database,job_id,"error","Подтверждённый товар не найден."); return True
        if product["brand"].strip().casefold() in BOSCH_HOME_BRAND_ALIASES:
            bosch_pipeline.run_job(database, job_id, product_id, product, stages=job["stages"],
                                   adapter_factory=bosch_adapter_factory, clock=clock)
            return True
        is_lg = product["brand"].strip().casefold() in LG_BRAND_ALIASES
        is_hyperx = product["brand"].strip().casefold() in HYPERX_BRAND_ALIASES
        is_samsung = product["brand"].strip().casefold() in SAMSUNG_BRAND_ALIASES
        effective_name = _effective_product_name(product)
        start=clock(); total_deadline=start+TOTAL_BUDGET_SECONDS; stages=job["stages"]
        official_docs: list[SourceDocument] = []
        lg_ru = None
        lg_support = support_doc = None
        lg_browser_search = None
        base = ""
        hyperx_doc = None
        samsung_doc = samsung = samsung_code = samsung_budget = None

        if is_lg:
            full=normalize_lg_sku(product["search_code"]); base=lg_base_model(full)
            components=lg_article_components(full)
            name_models=_lg_model_candidates_from_name(effective_name,full)
            detail=(f"Комплект из {', '.join(components)}; общая модель {base}. Страница одной модели не подтверждает весь комплект."
                    if len(components)>1 else f"Полный артикул {full}; базовая модель {base}.")
            jobs.progress(database,job_id,1,f"LG: {detail}")
            if adapter_factory:
                supplied=tuple(adapter_factory())
                if len(supplied)==2: lg_kz,sulpak=supplied; lg_ru=None
                elif len(supplied)==3: lg_kz,lg_ru,sulpak=supplied
                else: lg_kz,lg_ru,sulpak,lg_browser_search=supplied  # Stage 43: optional 4th element, adapters.lg_browser_search.LGBrowserSearch
            else:
                lg_kz,lg_ru,sulpak,lg_browser_search=default_lg_adapters(database.parent,clock=clock)
            official_deadline=min(total_deadline,start+OFFICIAL_BUDGET_SECONDS)
            for adapter in (lg_kz,lg_ru):
                if adapter is None: continue
                if clock()>=official_deadline:
                    doc=SourceDocument(adapter.source_key,adapter.site_name,"",error="Регион не проверен: исчерпан общий 20-секундный бюджет официального поиска.")
                elif isinstance(adapter,(LGAdapter,LGRUAdapter)):
                    doc=adapter.find_source(full,deadline=official_deadline,fallback_models=name_models)
                else: doc=adapter.find_source(full,deadline=official_deadline)
                official_docs.append(doc); _save(database,product_id,doc,stages)
                jobs.progress(database,job_id,1,f"{doc.site_name}: {doc.match_level}. {doc.error or doc.evidence}",level="warning" if doc.error or doc.match_level not in {"full_sku","base_model"} else "info",source_url=doc.url)
            # Reuse observed URLs already saved for this row and content-tied hits
            # from the existing LG browser search. No per-SKU URL table or new discovery.
            saved_support = [page for page in jobs.get_source_pages(database, product_id)
                             if page["source_key"] in {"lg_kz_support", "lg_ru_support"}
                             and is_official_support_url(page["url"])]
            observed_support = []
            # An injected product adapter may be a fully offline test double.
            # Never add a new live support fetch behind that double unless the
            # caller also supplied a support adapter. Production uses both.
            if adapter_factory is None or lg_support_adapter_factory is not None:
                for page in jobs.get_source_pages(database, product_id):
                    if page["source_key"] not in {"lg_kz", "lg_ru"} or not page["url"] or page["error"]:
                        continue
                    snapshot = latest_source_snapshot(database, product_id, page["source_key"])
                    if snapshot and snapshot["source_url"] == page["url"] and snapshot["content"]:
                        observed_support.extend(observed_product_support_urls(snapshot["content"], page["url"]))
            support_urls = tuple(dict.fromkeys(
                [page["url"] for page in saved_support] + observed_support
                + [url for adapter in (lg_kz, lg_ru) if adapter is not None
                   for url in getattr(adapter, "support_candidate_urls", ()) if is_official_support_url(url)]
            ))
            if support_urls or lg_support_adapter_factory:
                support_pages = {}
                support_payloads = {}
                for page in saved_support:
                    snapshot = latest_source_snapshot(database, product_id, page["source_key"])
                    if snapshot and snapshot["source_url"] == page["url"] and snapshot["content"]:
                        support_pages[page["url"]] = snapshot["content"]
                    api_snapshot = latest_source_snapshot(database, product_id, page["source_key"] + "_api")
                    if api_snapshot and api_snapshot["extracted"].get("support_url") == page["url"]:
                        try:
                            support_payloads[page["url"]] = json.loads(api_snapshot["content"])
                        except (ValueError, TypeError):
                            pass
                support_pages.update({url: html for adapter in (lg_kz, lg_ru) if adapter is not None
                                      for url, html in getattr(adapter, "support_candidate_pages", {}).items()})
                lg_support=(lg_support_adapter_factory or (lambda: LGSupportAdapter(
                    log_path=database.parent / "lg_fetch_log.json", clock=clock,
                    candidate_urls=support_urls, candidate_pages=support_pages,
                    candidate_payloads=support_payloads)))()
                if lg_support_adapter_factory:
                    lg_support.candidate_urls = support_urls
                    lg_support.candidate_pages = {**support_pages, **lg_support.candidate_pages}
                    lg_support.candidate_payloads = {**support_payloads, **lg_support.candidate_payloads}
                support_doc=lg_support.find_source(full,deadline=official_deadline)
                if support_doc.url:
                    official_docs.append(support_doc)
                    if not support_doc.error:
                        _save(database,product_id,support_doc,stages)
                    jobs.progress(database,job_id,1,f"{support_doc.site_name}: {support_doc.match_level}. {support_doc.error or support_doc.evidence}",
                                  level="info" if support_doc.match_level=="full_sku" else "warning",source_url=support_doc.url)
            # The LG-only supplier fallback (Sulpak) -- unchanged scope, per standing instructions.
            fallback_deadline=min(total_deadline,clock()+FALLBACK_BUDGET_SECONDS)
            if clock()>=fallback_deadline:
                doc=SourceDocument(sulpak.source_key,sulpak.site_name,"",error="Источник не проверен: исчерпан 30-секундный бюджет fallback.")
            else: doc=sulpak.find_source(full,deadline=fallback_deadline)
            _save(database,product_id,doc,stages)
            jobs.progress(database,job_id,1,f"{doc.site_name}: {doc.match_level}. {doc.error or doc.evidence}",level="warning" if doc.error or doc.match_level!="full_sku" else "info",source_url=doc.url)
            dns_query = full
        elif is_hyperx:
            # HyperX (Stage 14): a single official adapter, no regional
            # split, no supplier fallback -- KNOWN_URLS is empty in
            # production (no real per-SKU URL is human-verified yet), so
            # this is a genuine no-op except for rows a human has supplied
            # a verified URL for, exactly like DNS's own KNOWN_URLS.
            hyperx_code = (product["search_code"] or "").strip().upper()
            # Stage 16: the default factory colocates the persisted fetch
            # log with whatever jobs database this run uses, so a host
            # stop (403/429/challenge) survives a fresh worker.run_once()
            # call, not just this one's lifetime -- see adapters/hyperx.py
            # and adapters/policy_fetch.py.
            hyperx = (hyperx_adapter_factory or (
                lambda: HyperXAdapter(clock=clock, fetch_log_path=database.parent / "hyperx_fetch_log.json")
            ))()
            hyperx_deadline = min(total_deadline, start+OFFICIAL_BUDGET_SECONDS)
            if clock()>=hyperx_deadline:
                hyperx_doc=SourceDocument(hyperx.source_key,hyperx.site_name,"",error="Товар не проверен: исчерпан общий 20-секундный бюджет официального поиска.")
            else:
                hyperx_doc=hyperx.find_source(hyperx_code,deadline=hyperx_deadline)
            official_docs.append(hyperx_doc); _save(database,product_id,hyperx_doc,stages)
            jobs.progress(
                database,job_id,1,f"{hyperx_doc.site_name}: {hyperx_doc.match_level}. {hyperx_doc.error or hyperx_doc.evidence}",
                level="warning" if hyperx_doc.error or hyperx_doc.match_level!="exact_variant" else "info",
                source_url=hyperx_doc.url,
            )
            dns_query = hyperx_code
        elif is_samsung:
            # Samsung (Stage 26): one official adapter (samsung.com/kz_ru) on the observed routes only, every request through the policy session (a persisted
            # log of stops, a per-row request budget). The stages themselves live in samsung_pipeline.py; the instruction stage runs BEFORE the dealer fallback
            # so the dealer is asked only about what is still missing. The dealer gets no values into the card unless its match is exact model AND variant.
            samsung = (samsung_adapter_factory or (lambda: default_samsung_adapter(database.parent, clock=clock)))()
            samsung_code = (product["search_code"] or "").strip().upper()
            samsung_budget = samsung_pipeline.new_budget(product_id)
            samsung_doc = samsung_pipeline.official_stage(database, job_id, product_id, product, samsung, samsung_code, stages=stages, deadline=min(total_deadline, start+OFFICIAL_BUDGET_SECONDS), clock=clock, budget=samsung_budget, documents_deadline=total_deadline)
            official_docs.append(samsung_doc)
            if 6 in stages:
                samsung_pipeline.documents_stage(database, job_id, product_id, samsung, samsung_doc, samsung_code, deadline=total_deadline, budget=samsung_budget)
            dns_query = samsung_code
        else:
            # No official adapter exists yet for this brand in the production
            # pipeline. adapter_factory (the LG 2/3-tuple convention) is
            # intentionally never invoked here -- the Sulpak fallback stays LG-only.
            jobs.progress(database,job_id,1,f"Бренд «{product['brand']}» вне конвейера официальных источников; проверяем только резервный источник DNS.")
            dns_query = (product["search_code"] or "").strip().upper()

        # DNS dealer fallback -- available for ANY brand/category (explicit
        # user authorization, Stage 11.3/11.4), always checked AFTER whatever
        # official/Sulpak stage above ran, never before. It only ever
        # acts on a pre-verified URL (adapters/dns.py KNOWN_URLS/KNOWN_DOCUMENT_URLS)
        # -- there is no discovery/crawl method, so this is a genuine no-op
        # for every catalog row except the ones explicitly seeded there.
        dns_model_tokens = _model_tokens_from_name(effective_name)
        dns_missing_fields = samsung_pipeline.dealer_missing_fields(database, product_id, stages) if is_samsung else _compute_missing_fields(database, product_id, stages)
        dns = (dns_adapter_factory or (lambda: DnsAdapter(clock=clock, fetch_log_path=database.parent / "dns_fetch_log.json")))()
        dns_deadline = min(total_deadline, clock()+DNS_BUDGET_SECONDS)
        dns_doc = dns.find_source(
            dns_query, deadline=dns_deadline, model_tokens=dns_model_tokens,
            brand=product["brand"], name=effective_name, missing_fields=dns_missing_fields,
        )
        if is_samsung: dns_doc=samsung_pipeline.gate_dealer(dns_doc)
        _save(database,product_id,dns_doc,stages)
        if is_samsung: samsung_pipeline.dealer_check(database,product_id,dns_doc)
        jobs.progress(
            database,job_id,1,
            f"{dns_doc.site_name} (дилер, резервный источник): {dns_doc.match_level}. {dns_doc.error or dns_doc.evidence}",
            level="warning" if dns_doc.error or dns_doc.match_level!="model_and_code_confirmed" else "info",
            source_url=dns_doc.url,
        )

        if 3 in stages:
            jobs.progress(database,job_id,3,"Нормализуем и сравниваем характеристики."); jobs.resolve_product(database,product_id)

        if 6 in stages:
            if is_lg:
                ru=next((x for x in official_docs if x.source_key=="lg_ru"),None)
                if ru and lg_ru and ru.url and not ru.error and clock()<total_deadline:
                    documents,error=lg_ru.find_documents(ru,base,deadline=total_deadline)
                    report = lg_ru.reports[-1] if getattr(lg_ru, "reports", None) else {}
                    if report.get("_support_html") and report.get("support_page_url"):
                        printed = report.get("support_page_sales_code", "")
                        relation = structured_sales_relation(full, printed)
                        level = ("full_sku" if relation == "exact" else
                                 "base_model" if relation in {"family_of", "regional_variant_of"} else "unknown")
                        jobs.save_source_document(
                            database, product_id,
                            SourceDocument("lg_ru_support", "LG RU support", report["support_page_url"],
                                           found_model=printed, match_level=level,
                                           evidence=f"Support page printed sales code: {printed or 'none'}; relation: {relation}.",
                                           html=report["_support_html"]),
                            update_description=False, update_attributes=False, update_photos=False,
                        )
                    retry_failed = (report.get("outcome") == "support_page_unreachable"
                                    or any(item.get("state") == "candidate_link_unreachable"
                                           for item in report.get("files", [])))
                    if documents or not (retry_failed and _has_retained_documents(database, product_id, "lg_ru")):
                        jobs.save_documents(database,product_id,"lg_ru",documents)
                    russian=sum(1 for d in documents if d.language=="Русский")
                    message=(f"Инструкций подтверждено по содержимому: {len(documents)}; русских: {russian}."+("" if russian else " "+error)) if documents else error
                    if getattr(lg_ru, "reports", None) and not russian:
                        files = lg_ru.reports[-1].get("files", [])
                        unreadable = sum(1 for item in files if item.get("error", "").startswith("pdf:"))
                        if unreadable:
                            message += f" PDF не удалось прочитать: {unreadable}."
                else:
                    retained = _has_retained_documents(database, product_id, "lg_ru")
                    if not retained:
                        jobs.save_documents(database,product_id,"lg_ru",[])
                    message="Инструкции не проверены: официальная страница LG Россия недоступна."
                jobs.progress(database,job_id,6,message,level="info" if jobs.get_documents(database,product_id) else "warning",source_url=ru.url if ru else "")
            if is_lg and support_doc and lg_support and support_doc.url and not support_doc.error:
                support_documents, support_report = lg_support.find_documents(support_doc, full, deadline=total_deadline)
                retry_failed = any(item.get("state") == "unreachable"
                                   for item in support_report.get("files", []))
                if support_documents or not (retry_failed and _has_retained_documents(
                        database, product_id, support_doc.source_key)):
                    jobs.save_documents(database, product_id, support_doc.source_key, support_documents)
                checked = support_report.get("files", [])
                detail = "; ".join(
                    f"{item.get('state')}: {item.get('url')}; models={item.get('assessment', {}).get('model_references', [])}"
                    for item in checked
                )
                jobs.progress(database,job_id,6,
                              f"LG KZ support manual: {support_report['outcome']}; {detail}",
                              level="info" if support_documents else "warning",
                              source_url=support_documents[0].direct_url if support_documents else support_doc.url)
            if is_hyperx:
                # A genuine downloadable link is the only thing that counts
                # -- a Quick Start Guide named in "what's in the box" text
                # is never turned into a document (see adapters/hyperx.py
                # and adapters/structured_page.py's dom-table extraction).
                hyperx_documents, hyperx_doc_reason = hyperx.find_documents(hyperx_code, deadline=total_deadline)
                jobs.save_documents(database, product_id, "hyperx", hyperx_documents)
                jobs.progress(
                    database,job_id,6,f"HyperX: {hyperx_doc_reason}",
                    level="info" if hyperx_documents else "warning",
                    source_url=hyperx_doc.url,
                )
            # DNS documents: full-content verification before acceptance --
            # a matching filename/label is never enough (see adapters/
            # document_verification.py). This is where the Stage 11.3
            # negative fixture (the original QuadCast manual, wrong model)
            # gets rejected rather than silently attached to the card.
            dns_documents, dns_doc_reason = dns.find_documents(dns_query, model_tokens=dns_model_tokens, deadline=total_deadline)
            if dns_documents:
                _save_dns_documents(database, product_id, dns_documents)
            else:
                jobs.save_documents(database, product_id, "dns", [])
            jobs.progress(
                database,job_id,6,f"DNS (дилер): {dns_doc_reason}",
                level="info" if dns_documents else "warning",
                source_url=dns.document_urls.get(dns_query, ""),
            )

        sources=jobs.get_source_pages(database,product_id)
        counts=jobs.result_counts(database,product_id)
        dns_confirmed = any(x["source_key"]=="dns" and x["match_level"]=="model_and_code_confirmed" for x in sources)
        dns_summary = " DNS (дилер, резервный источник): " + ("модель и код подтверждены." if dns_confirmed else "кандидат не подтверждён или не задан.")

        if is_lg:
            identity=jobs.identification_status(sources)
            # Stage 21 (owner decision D2): an official page whose article matches the FULL row article, with no real
            # conflict, is enough for `done`; a supplier/dealer confirmation is optional. Card completeness is judged
            # apart from the status (readiness.py) and its gaps are written next to it, never hidden behind `done`.
            # Support/manual identity does not establish the commerce product's specs or photo identity.
            official_exact=any(x["source_key"] in {"lg_kz","lg_ru"} and x["match_level"]=="full_sku" and not x["error"] for x in sources)
            support_pages = [x for x in sources if x["source_key"] in {"lg_kz_support", "lg_ru_support"}
                             and x["url"] and not x["error"]]
            if not official_exact and support_pages:
                if any(x["match_level"] == "full_sku" for x in support_pages):
                    identity = "Официальная страница поддержки LG подтверждает модель/комплект для инструкции; товарная страница с характеристиками и фото полного артикула не подтверждена"
                else:
                    identity = "Официальная страница поддержки LG найдена как кандидат; содержимое пока не подтверждает полный артикул"
            confirmed=any(x["source_key"] in SUPPLIERS and x["match_level"]=="full_sku" for x in sources)  # an official BASE-model page confirmed by a supplier's full article stays sufficient, as before
            summary=f" Реальных конфликтов: {counts['conflicts']}; только базовая модель LG: {counts['official_base_only']}; подтверждено поставщиком: {counts['supplier_confirmed']}."
            card=card_readiness(database,product_id); card_text=" "+readiness_text(card)
            jobs.progress(database,job_id,max(stages),card_text.strip(),level="info" if card["verdict"]=="export_ready" else "warning")
            if sources and all(x["error"] for x in sources): jobs.finish(database,job_id,"error","Все источники недоступны. "+identity+summary+dns_summary+card_text)
            elif counts["conflicts"] or not (official_exact or confirmed): jobs.finish(database,job_id,"needs_review",identity+"."+summary+dns_summary+card_text)
            else: jobs.finish(database,job_id,"done",identity+"."+summary+dns_summary+card_text)
        elif is_samsung:
            samsung_pipeline.finish(database,job_id,product_id,stages,samsung_doc,dns_doc,dns_summary,samsung_budget)
        elif is_hyperx:
            summary=f" Реальных конфликтов: {counts['conflicts']}."
            if hyperx_doc.match_level=="exact_variant" and not counts["conflicts"]:
                jobs.finish(database,job_id,"done",f"HyperX: {hyperx_doc.match_level}."+summary+dns_summary)
            elif dns_confirmed:
                # Mirrors the non-official-brand priority order: a DNS
                # confirmation is never discarded just because the official
                # HyperX adapter itself found nothing this run (no URL yet,
                # or a real error) -- it still needs human review, not error.
                jobs.finish(database,job_id,"needs_review","HyperX (официальный источник): "+hyperx_doc.match_level+"."+dns_summary+" Требуется проверка человеком перед принятием.")
            elif hyperx_doc.error:
                jobs.finish(database,job_id,"error",f"Официальная страница HyperX недоступна: {hyperx_doc.error}"+summary+dns_summary)
            elif hyperx_doc.match_level=="official_url_needed":
                jobs.finish(database,job_id,"error",hyperx_doc.evidence)
            else:
                # base_code_confirmed / mismatch / unknown / a real
                # conflict -- never silently accepted, always to review.
                jobs.finish(database,job_id,"needs_review",f"HyperX: {hyperx_doc.match_level}. {hyperx_doc.evidence}"+summary+dns_summary)
        else:
            # Official-source priority is preserved by construction: no
            # official adapter ran for this brand, so DNS never had an
            # official value it could have overwritten. A DNS-only result
            # always needs human review before being trusted (never
            # silently confirmed from a single dealer source), matching
            # resolve_attributes()'s existing single-unconfirmed-source rule.
            if dns_confirmed:
                jobs.finish(database,job_id,"needs_review","Официального адаптера для этого бренда пока нет; DNS (дилер) нашёл и подтвердил кандидата -- требуется проверка человеком перед принятием."+dns_summary)
            elif dns_doc.match_level == "dealer_url_needed":
                # Surface the ready-to-ask request verbatim -- brand, model,
                # missing fields -- instead of a generic "not found" message.
                jobs.finish(database,job_id,"error",dns_doc.evidence)
            else:
                jobs.finish(database,job_id,"error","Официальный источник для этого бренда не подключён, и подтверждённого DNS-кандидата для этого товара нет."+dns_summary)
    except Exception:
        LOGGER.exception("Unexpected source comparison failure for job %s",job_id)
        jobs.finish(database,job_id,"error","Ошибка сравнения источников. Подробности смотрите в консоли worker.")
    finally:
        # Stage 43: a real browser subprocess (if one was opened for the LG site-search fallback) gets a
        # bounded, one-product lifetime -- never a long-lived cross-call singleton.
        if lg_browser_search is not None:
            lg_browser_search.close()
    return True

@contextmanager
def single_worker(directory: Path):
    """Hold a nonblocking process lock before recovering interrupted jobs."""
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / "worker.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another worker is already running for this data directory.") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Another worker is already running for this data directory.") from exc
        yield
    finally:
        if os.name == "nt":
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()

def main():
    parser=argparse.ArgumentParser(description="Worker сравнения источников LG")
    parser.add_argument("--data-dir",type=Path); parser.add_argument("--poll-interval",type=float,default=3.0); parser.add_argument("--once",action="store_true"); args=parser.parse_args()
    root=(args.data_dir or Path(os.environ.get("PRODUCT_CARDS_DATA_DIR") or PROJECT_DIR/"data")).resolve(); database=root/"batches.sqlite3"
    jobs.initialize(database); logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    with single_worker(root):
        jobs.recover_interrupted(database)
        try:
            while True:
                processed=run_once(database)
                if args.once: break
                if not processed: time.sleep(args.poll_interval)
        except KeyboardInterrupt: LOGGER.info("Worker остановлен.")
if __name__=="__main__": main()
