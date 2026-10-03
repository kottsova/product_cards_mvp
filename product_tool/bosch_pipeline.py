"""The two selected Bosch Home rows in the ordinary queued worker path."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Callable

from . import bosch_readiness, card_evidence, discovery_trace, jobs
from .adapters.bosch_home import MANIFEST, BoschHomeAdapter, selected_page
from .adapters.bosch_official import BoschOfficialAdapter
from .adapters.dns import DnsAdapter
from .adapters.policy_session import RequestBudget, request_budget

PLANNER = Path(__file__).resolve().parent / "config" / "coverage_planner.v1.json"
BOSCH_PROFESSIONAL_CATEGORIES = frozenset({
    "Шлифовальные машины", "Биты для шуруповерта", "Дрели", "Лобзики",
    "Перфораторы", "Пилы строительные", "Пилы торцовочные",
    "Пылесосы строительные", "Сверла", "Триммеры садовые", "Шуруповерты",
})


def is_selected(category: str, code: str) -> bool:
    code = (code or "").strip().upper()
    if selected_page(code, category) is None:
        return False
    config = json.loads(PLANNER.read_text(encoding="utf-8"))
    entries = config.get("selected_products", {}).get("bosch_home", {}).get("products", [])
    return any(e["category"].strip().casefold() == (category or "").strip().casefold()
               and e["seller_sku"].strip().upper() == code for e in entries)


def run_job(database: Path, job_id: str, product_id: int, product: dict, *, stages: list[int],
            adapter_factory: Callable[[], BoschHomeAdapter] | None = None,
            dns_adapter_factory=None,
            clock: Callable[[], float] = time.monotonic) -> None:
    code = (product.get("search_code") or "").strip().upper()
    category = product.get("category", "")
    if category in BOSCH_PROFESSIONAL_CATEGORIES:
        jobs.finish(database, job_id, "needs_review",
                    "Bosch Professional category: Bosch Home appliance adapter is not applicable.")
        return
    if not is_selected(category, code):
        return run_general_job(database, job_id, product_id, product, stages=stages,
                               adapter_factory=adapter_factory,
                               dns_adapter_factory=dns_adapter_factory, clock=clock)
    adapter = (adapter_factory or (lambda: BoschHomeAdapter(clock=clock,
               fetch_log_path=database.parent / "bosch_home_fetch_log.json")))()
    budget = RequestBudget(max_per_row=1, max_total=1)
    budget.begin_row(str(product_id))
    with request_budget(budget):
        document = adapter.find_source(code, category=category, deadline=clock() + 20.0)
    jobs.save_source_document(database, product_id, document,
                              update_description=2 in stages,
                              update_attributes=3 in stages,
                              update_photos=4 in stages)
    report = adapter.reports.get(code, {})
    evidence = {**report, "manual_verified": False, "manual_family": "",
                "manual_russian_by_text": False, "manual_exact_code_in_pdf": False,
                "other_manuals_unverified": []}
    if 4 in stages and document.photos and not document.error:
        jobs.set_photo_selection(database, product_id, [], mode="source", source_key=adapter.source_key)
    jobs.progress(database, job_id, 1,
                  f"Bosch Home KZ: {document.match_level}; {document.error or document.evidence}",
                  level="warning" if document.error else "info", source_url=document.url)
    if 3 in stages:
        jobs.resolve_product(database, product_id)
        jobs.progress(database, job_id, 3, f"Bosch KZ specifications: {len(document.attributes)} fields.", source_url=document.url)
    if 6 in stages:
        manuals = adapter.find_documents(document, code)
        jobs.save_documents(database, product_id, adapter.source_key, manuals)
        config = json.loads(MANIFEST.read_text(encoding="utf-8"))["pages"].get(code, {})
        verified = config.get("manual", {})
        evidence.update({"manual_verified": bool(manuals),
                         "manual_family": verified.get("family", "") if manuals else "",
                         "manual_russian_by_text": bool(verified.get("russian_by_text")) if manuals else False,
                         "manual_exact_code_in_pdf": bool(verified.get("exact_code_in_pdf")) if manuals else False,
                         "manual_verified_sha256": verified.get("sha256", "") if manuals else "",
                         "other_manuals_unverified": [u for u in report.get("manual_links", [])
                                                      if u != verified.get("url")]})
        jobs.progress(database, job_id, 6,
                      f"Bosch KZ family manual: {verified.get('family', '') if manuals else 'none verified'}; exact catalog code absent from PDF; other links unverified.",
                      level="info" if manuals else "warning", source_url=document.url)
    card_evidence.save(database, product_id, "bosch_home", evidence)
    readiness = bosch_readiness.card_readiness(database, product_id)
    jobs.progress(database, job_id, max(stages),
                  f"Bosch card readiness: {readiness['verdict']}; revision {readiness['revision_status']}; gaps {', '.join(readiness['blocking_gaps']) or 'none'}.",
                  level="info" if readiness["verdict"] == "export_ready" else "warning")
    if document.error:
        status = "needs_review" if document.match_level == "mismatch" else "error"
    elif document.match_level == "full_sku" and not readiness["real_conflicts"]:
        status = "done"
    else:
        status = "needs_review"
    jobs.finish(database, job_id, status,
                f"Bosch Home KZ model {code}: {document.evidence or document.error} Job {status}; card {readiness['verdict']}; E-Nr revision unknown.")


def run_general_job(database: Path, job_id: str, product_id: int, product: dict, *, stages: list[int],
                    adapter_factory=None, dns_adapter_factory=None,
                    clock: Callable[[], float] = time.monotonic) -> None:
    """Run ordinary Bosch rows through shared source, evidence and readiness stores."""
    article = (product.get("search_code") or "").strip().upper()
    discovery_trace.initialize(database)
    trace = lambda event: discovery_trace.record(database, job_id, product_id, event)
    if adapter_factory is None:
        adapter = BoschOfficialAdapter(clock=clock,
                      fetch_log_path=database.parent / "bosch_home_fetch_log.json",
                      trace_callback=trace)
    else:
        adapter = adapter_factory()
        adapter.trace_callback = trace
    budget = RequestBudget(max_per_row=18, max_total=18)
    budget.begin_row(str(product_id))
    with request_budget(budget):
        document = adapter.find_source(article, category=product.get("category", ""),
                                       deadline=clock() + 140.0)
        if 6 in stages and hasattr(adapter, "find_support"):
            adapter.find_support(document, article, deadline=clock() + 20.0)
    jobs.save_source_document(database, product_id, document,
                              update_description=2 in stages,
                              update_attributes=3 in stages,
                              update_photos=4 in stages)
    report = adapter.reports.get(article, {})
    evidence = {**report, "manual_verified": False, "manual_russian_by_text": False,
                "manual_exact_code_in_pdf": False, "manual_family": "",
                "other_manuals_unverified": report.get("manual_links", [])}
    if 4 in stages and document.photos and not document.error:
        jobs.set_photo_selection(database, product_id, [], mode="source", source_key=adapter.source_key)
    jobs.progress(database, job_id, 1,
                  f"Bosch official PDP: {document.match_level}; {document.error or document.evidence}",
                  level="warning" if document.error else "info", source_url=document.url)
    if 3 in stages:
        jobs.resolve_product(database, product_id)
        jobs.progress(database, job_id, 3,
                      f"Bosch grouped specifications: {len(document.attributes)} fields.",
                      source_url=document.url)
    if 6 in stages:
        documents = adapter.find_documents(document, article)
        evidence.update({key: adapter.reports.get(article, {}).get(key, evidence.get(key)) for key in
                         ("manual_verified", "manual_russian_by_text", "manual_exact_code_in_pdf",
                          "manual_family", "pdf_checks", "support_revision_candidates", "support_list_url")})
        jobs.save_documents(database, product_id, adapter.source_key, documents)
        jobs.progress(database, job_id, 6,
                      f"Bosch typed documents: {len(documents)}; Russian manual verified={evidence['manual_verified']}.",
                      level="warning" if not evidence["manual_verified"] else "info", source_url=document.url)
    card_evidence.save(database, product_id, "bosch_home", evidence)
    readiness = bosch_readiness.card_readiness(database, product_id)
    if readiness["verdict"] == "not_ready":
        # Existing DNS fallback has only preverified URLs. A missing candidate
        # is a diagnostic, never an empty dealer source column.
        dns = (dns_adapter_factory or (lambda: DnsAdapter(clock=clock,
                    fetch_log_path=database.parent / "dns_fetch_log.json")))()
        dealer = dns.find_source(article, deadline=clock() + 12.0,
                                 model_tokens=[article], brand=product.get("brand", "BOSCH"),
                                 name=product.get("name") or article,
                                 missing_fields=readiness["blocking_gaps"])
        evidence["dealer_fallback"] = {"status": dealer.match_level,
                                        "url": dealer.url, "reason": dealer.error or dealer.evidence}
        if dealer.match_level == "model_and_code_confirmed" and not dealer.error:
            jobs.save_source_document(database, product_id, dealer,
                                      update_description=2 in stages,
                                      update_attributes=3 in stages,
                                      update_photos=4 in stages)
            if 3 in stages:
                jobs.resolve_product(database, product_id)
        jobs.progress(database, job_id, 1,
                      f"DNS dealer fallback: {dealer.match_level}; {dealer.error or dealer.evidence}",
                      level="warning", source_url=dealer.url)
    card_evidence.save(database, product_id, "bosch_home", evidence)
    readiness = bosch_readiness.card_readiness(database, product_id)
    status = "done" if document.match_level == "full_sku" and not document.error else "needs_review"
    jobs.finish(database, job_id, status,
                f"Bosch {article}: {document.evidence or document.error} Job {status}; "
                f"card {readiness['verdict']}; E-Nr revision {readiness['revision_status']}.")
