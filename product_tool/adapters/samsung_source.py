"""Stage 26: the Samsung source adapter the worker uses (samsung.com/kz_ru).

`samsung.py` reads a page that was already fetched; this module fetches it, on the observed official routes only, through PolicyAwareSession (host allowlist, redirect check, a persisted log of
stops, a per-row request budget), and turns the result into the objects the pipeline stores: a SourceDocument (page, variant level, specifications, photos) and ProductDocuments.

Routes (all observed in Stages 24-25; nothing is constructed):
  * a TV, monitor, soundbar and other audio/video row -> the official sitemap `kz_ru/vd-sitemap.xml`; a home appliance row -> `kz_ru/da-sitemap.xml`; the page is the sitemap URL whose slug shows the article;
  * a smartphone row (SM-...) -> the hubs `smartphones/all-smartphones/`, then `smartphones/galaxy-a/`; a tablet row -> `tablets/all-tablets/`; a phone's photos are on the buy page its JSON-LD names;
  * any other SM- row (wearables) has no established route: nothing is requested.

Evidence levels are stored as they are (see samsung.py): the article in the page's markup or title is `full_sku`; the article only in the visible text is `code_in_page_text` (never the same as
`full_sku`); the same base model with another regional/colour code is `base_model`, with the differences left open.
"""
from __future__ import annotations

import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Callable

import requests

from .common import PhotoCandidate, ProductDocument, SourceDocument, SourceError, clean_text, fetch_with_retry, meta_description
from .lg_documents import BinarySafeSession, document_bytes, looks_like_pdf
from .policy_session import PolicyAwareSession
from .samsung import (SamsungCard, assess_samsung_document, brief_guide_note, is_brief_guide, buy_page_url, extract_document_links, extract_photos, find_in_sitemap, find_on_hub, hub_product_links, assign_devices, extract_spec_table, instruction_acceptance, manual_device_tables, norm, order_for_request, page_model_data, parse_product_page, photo_variant_binding, soup_of,
                      spec_attributes, _json_ld_product, PAGE_TIES)
from .sitemap_urls import sitemap_locs

BASE = "https://www.samsung.com/kz_ru/"
VD_SITEMAP, DA_SITEMAP = BASE + "vd-sitemap.xml", BASE + "da-sitemap.xml"
# Stage 28: the other sub-sitemaps the official index `b2c-sitemap.xml` lists (observed in Stage 8.2, confirmed and read in full in Stage 28)
MEMORY_SITEMAP, IM_SITEMAP, ASSORTED_SITEMAP = BASE + "memory-sitemap.xml", BASE + "im-sitemap.xml", BASE + "assorted-sitemap.xml"
PHONE_HUBS = (BASE + "smartphones/all-smartphones/", BASE + "smartphones/galaxy-a/")
TABLET_HUBS = (BASE + "tablets/all-tablets/",)
PAGE_HOSTS = ("www.samsung.com",)
DOCUMENT_HOSTS = ("org.downloadcenter.samsung.com", "downloadcenter.samsung.com")
DOCUMENT_MAX_BYTES = 40_000_000
MAX_REQUESTS_PER_ROW = 7          # sitemap(s) or hubs (<= 2) + the page + the buy page + <= 2 files
MAX_FILES_PER_PRODUCT = 2
USER_AGENT = "ProductCardsSourceCensus/2.0 (bounded diagnostic probe)"   # the agent the 33 requests of Stages 24-25 were made with
LOG_NAME = "samsung_fetch_log.json"
RECORDED_DOCUMENTS = Path(__file__).resolve().parents[1] / "config" / "samsung_recorded_documents.v1.json"
_HALT_MARKERS = ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")
_MEMORY = ("накопител", "карты памяти", "карта памяти", "оператив", "ssd", "flash")
_ACCESSORY = ("кабел", "зарядн", "наушник", "гарнитур", "трекер", "часы", "браслет")
_APPLIANCE = ("холодиль", "стираль", "сушиль", "духов", "варочн", "пылесос", "микровол", "кондиционер", "сплит", "посудомо", "вытяжк", "плит")
_LANGUAGE_NAMES = {"ru": "Русский", "kk": "Казахский", "en": "Английский", "uk": "Украинский"}
BRIEF_GUIDE_LANGUAGE = "Многоязычная памятка (есть русский раздел)"
LOGGER = logging.getLogger(__name__)


def load_recorded_documents(path: Path = RECORDED_DOCUMENTS) -> dict[str, dict]:
    """Document assessments recorded by an earlier content check of the very file (keyed by the link the official page prints). Using one makes no request for that file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {item["href"]: item for item in data.get("documents", [])}


def samsung_log_path(directory: Path) -> Path:
    return Path(directory) / LOG_NAME


def pdf_pages(data: bytes) -> list[str]:
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    return [(page.extract_text() or "") for page in pypdf.PdfReader(io.BytesIO(data)).pages]


def match_level_of(identity) -> str:
    """The level stored for the page: the article in the page's markup or title is `full_sku`; only in the visible text it is `code_in_page_text`."""
    if identity.level == "full_sku":
        return "full_sku" if identity.evidence_strength == "strong" else "code_in_page_text"
    return identity.level if identity.level in ("base_model", "mismatch") else "unknown"


def route_for(code: str, category: str) -> tuple[str, tuple[str, ...], str]:
    """(kind, addresses, reason). kind is 'hub' (phones, tablets), 'sitemap' (everything else) or 'none' (no established route: nothing is requested)."""
    text = (category or "").casefold()
    if code.upper().startswith("SM-"):
        if "смартфон" in text:
            return "hub", PHONE_HUBS, ""
        if "планшет" in text:
            return "hub", TABLET_HUBS, ""
        if any(word in text for word in _ACCESSORY):
            return "sitemap", (IM_SITEMAP, ASSORTED_SITEMAP), ""       # watches, bands, earbuds: the "im" sitemap lists their pages (a page listed there is a current model)
        return "none", (), "для прочих кодов SM- маршрут на официальном сайте не установлен"
    if any(word in text for word in _APPLIANCE):
        return "sitemap", (DA_SITEMAP, VD_SITEMAP), ""
    if any(word in text for word in _MEMORY):
        return "sitemap", (MEMORY_SITEMAP, IM_SITEMAP), ""
    if any(word in text for word in _ACCESSORY):
        return "sitemap", (IM_SITEMAP, ASSORTED_SITEMAP), ""
    return "sitemap", (VD_SITEMAP, DA_SITEMAP), ""


def levels_note(facts: dict) -> str:
    """The three separate facts about a document as one line (kept apart from each other, stored in the document's title)."""
    if facts.get("content_status") == "text_not_extractable":
        return "текст файла не извлекается: язык, модель и связь проверяются вручную"
    tie = {"exact_page": "страница показывает полный артикул", "page_with_code_in_text_only": "страница показывает артикул только в тексте", "base_model_page": "страница только той же базовой модели"}.get(facts["tied_by_official_page"], "нет")
    catalog, link = facts["names_catalog_model"], facts["names_link_model"]
    if catalog["exact"]:
        model = "в тексте назван точный код каталога"
    elif catalog["family_mask"]:
        model = f"в тексте назвал семейство ({', '.join(catalog['family_mask'][:2])}), точный код не назван"
    elif link["exact"] or link["family_mask"]:
        model = f"в тексте назван только код из ссылки страницы ({link['model_name']}), код каталога не назван"
    else:
        model = "в тексте ни код каталога, ни код из ссылки не названы"
    language = "русский по тексту" if facts["russian_by_text"] else "многоязычная памятка: русский раздел есть, целиком не русская" if is_brief_guide(facts) else "не русский по тексту"
    acceptance = facts.get("acceptance") or {}
    tail = ""
    if acceptance.get("accepted") and acceptance.get("note"):
        tail = " · принята с пометкой: " + acceptance["note"]
    elif acceptance and not acceptance.get("accepted"):
        tail = " · не принята: " + acceptance.get("note", acceptance.get("basis", ""))
    return f"{language}; связь с товаром: {tie}; {model}{tail}"


class SamsungAdapter:
    source_key = "samsung"
    site_name = "Samsung Казахстан"

    def __init__(self, http, *, documents_http=None, clock: Callable[[], float] = time.monotonic, pages_reader: Callable[[bytes], list[str]] | None = None, recorded_documents: dict[str, dict] | None = None):
        self.http = http
        self.recorded = load_recorded_documents() if recorded_documents is None else recorded_documents
        self.documents_http = documents_http if documents_http is not None else http
        self.clock = clock
        self.pages_reader = pages_reader or pdf_pages
        self.reports: dict[str, dict] = {}
        self.pending: dict[str, tuple] = {}     # documents assessed before the page is saved (the device split needs the manual): article -> (documents, reason)
        self.halted = ""

    # -- fetching ------------------------------------------------------------------------------------------------------------------

    def _get(self, session, report: dict, step: str, url: str, deadline: float):
        """One request through the policy session. A refusal or a stop is recorded and halts the row's remaining requests; nothing is retried elsewhere."""
        entry = {"step": step, "url": url}
        report["steps"].append(entry)
        if self.halted:
            entry["skipped"] = self.halted
            return None
        try:
            response = fetch_with_retry(session, url, deadline=deadline, clock=self.clock)
        except SourceError as exc:
            entry["error"] = str(exc)[:240]
            if any(marker in str(exc) for marker in _HALT_MARKERS):
                self.halted = str(exc)[:240]
                report["halted"] = self.halted
            return None
        entry["status"] = response.status_code
        return response

    # -- the page ------------------------------------------------------------------------------------------------------------------

    def _locate(self, code: str, category: str, report: dict, deadline: float) -> str:
        kind, addresses, reason = route_for(code, category)
        report["route"] = {"kind": kind, "addresses": list(addresses), "reason": reason}
        if kind == "none":
            return ""
        for address in addresses:
            response = self._get(self.http, report, "hub" if kind == "hub" else "sitemap", address, deadline)
            if response is None:
                if self.halted:
                    return ""
                continue
            if kind == "hub":
                links = hub_product_links(response.text, address)
                exact = next((u for u in links if len(norm(code)) >= 10 and norm(code) in norm(u.rsplit("/kz_ru/", 1)[-1])), "")  # a page whose address shows the whole catalog code
                url = exact or find_on_hub(links, code)
            else:
                url = find_in_sitemap(sitemap_locs(response.text), code)
            if url:
                report["route"]["found_via"] = address
                return url
        return ""

    def find_source(self, code: str, *, deadline: float, category: str = "", name: str = "") -> SourceDocument:
        article = (code or "").strip().upper()
        report = {"article": article, "route": {}, "steps": [], "page_url": "", "buy_page_url": "", "identity": {}, "specs": 0, "photos": {}, "document_links": [], "gaps": [], "missing_fields": []}
        self.reports[article] = report
        self.halted = ""
        if len(norm(article)) < 6:   # the article cannot be looked up in a sitemap or a hub (a blank or a stub code): nothing is requested
            report["outcome"] = "no_usable_code"
            return SourceDocument(self.source_key, self.site_name, "", match_level="unknown", evidence="Артикул строки пуст или слишком короток для поиска на официальном сайте: запросов не делалось.")
        page_url = self._locate(article, category, report, deadline)
        if not page_url:
            report["outcome"] = "route_not_established" if report["route"].get("kind") == "none" else ("halted" if self.halted else "page_not_listed")
            evidence = {"route_not_established": report["route"].get("reason", ""), "halted": f"запросы остановлены: {self.halted}", "page_not_listed": "на официальных страницах Samsung (карта сайта или список моделей) страница этого артикула не найдена"}[report["outcome"]]
            return SourceDocument(self.source_key, self.site_name, "", match_level="unknown", evidence=clean_text(evidence), error=self.halted)
        report["page_url"] = page_url
        response = self._get(self.http, report, "product_page", page_url, deadline)
        if response is None:
            report["outcome"] = "page_unreachable"
            error = next((s.get("error", "") for s in reversed(report["steps"]) if s["step"] == "product_page"), "") or "страница не получена"
            return SourceDocument(self.source_key, self.site_name, page_url, match_level="unknown", error=error)
        card = parse_product_page(response.text, page_url, article)
        photos = card.photos
        if not photos.photos and card.identity.is_product_page:
            buy = buy_page_url(response.text, page_url)   # a phone keeps its gallery on the buy page its own markup names
            if buy:
                report["buy_page_url"] = buy
                buy_response = self._get(self.http, report, "buy_page", buy, deadline)
                if buy_response is not None:
                    photos = extract_photos(buy_response.text, buy)
        level = match_level_of(card.identity)
        report.update({"outcome": "page_read", "identity": {"level": card.identity.level, "strength": card.identity.evidence_strength, "match_level": level, "evidence": card.identity.evidence, "jsonld_sku": card.identity.jsonld_sku,
                                                            "title": card.identity.title[:140], "is_product_page": card.identity.is_product_page, "open_differences": card.identity.open_differences},
                       "specs": len(card.specs), "photos": {"full_size": len(photos.photos), "thumbnails": len(photos.thumbnails), "three_d_excluded": len(photos.three_d), "from": report["buy_page_url"] if report["buy_page_url"] and photos is not card.photos else page_url,
                                                            "bound_by_asset_path": [p.asset_key for p in photo_variant_binding(photos.photos, article)],
                                                            "gap": "" if photos.photos else (photos.gap or "фото не найдены")},
                       "document_links": [{"file": d.file_name, "model_name": d.model_name, "language_hint": d.language_hint} for d in card.documents], "gaps": list(card.gaps)})
        report["missing_fields"] = [m for m in card.missing_fields if not (m == "фото" and photos.photos)]
        candidates = list(photos.photos) + [PhotoCandidate(u, u, "excluded", excluded_reason="thumbnail") for u in photos.thumbnails] + [PhotoCandidate(u, u, "excluded", excluded_reason="3d_model") for u in photos.three_d]
        soup = soup_of(response.text)
        description = meta_description(soup) or clean_text(str(_json_ld_product(soup).get("description", "")))
        return SourceDocument(self.source_key, self.site_name, page_url, found_model=card.identity.jsonld_sku or (article if level == "full_sku" else ""), match_level=level, evidence=identity_evidence(card, article, level),
                              attributes=spec_attributes(card.specs), description=description, photos=[p.url for p in photos.photos], photo_candidates=candidates, html=response.text)

    # -- the documents -------------------------------------------------------------------------------------------------------------

    def split_devices(self, document: SourceDocument, catalog_article: str) -> tuple[list, dict]:
        """The page's specification rows as pipeline attributes; a plain size / weight row gets the device it belongs to ONLY when a manual table that names that device carries the same value
        (assign_devices). Returns (attributes, evidence record: the tables read, the rows assigned with their basis, the rows left unassigned with the reason)."""
        article = (catalog_article or "").strip().upper()
        items = extract_spec_table(document.html or "")
        tables = self.reports.get(article, {}).get("device_tables", [])
        assigned, records, unassigned = assign_devices(items, tables)
        return spec_attributes(items, assigned), {"tables": tables, "assigned": records, "unassigned": unassigned}

    def find_documents(self, document: SourceDocument, catalog_article: str, *, deadline: float, only_hrefs: list[str] | None = None) -> tuple[list[ProductDocument], str]:
        article = (catalog_article or "").strip().upper()
        report = self.reports.setdefault(article, {"article": article, "steps": []})
        report["documents"] = []
        links = order_for_request(extract_document_links(document.html or "", document.url))
        if only_hrefs is not None:       # a limited, declared attempt at named files only (nothing else the page prints is requested)
            links = [link for link in links if link.href in only_hrefs]
        if not links:
            report["documents_outcome"] = "no_links_on_the_page"
            return [], "На официальной странице Samsung нет ссылок на руководство."
        page_level = match_level_of_document(document)
        page_data = page_model_data(document.html or "")
        report["page_model_data"] = page_data
        documents: list[ProductDocument] = []
        for link in links[:MAX_FILES_PER_PRODUCT]:
            entry = {"href": link.href, "file": link.file_name, "language_hint_from_file_name": link.language_hint, "link_model_name": link.model_name, "state": "candidate_link"}
            report["documents"].append(entry)
            recorded = self.recorded.get(link.href)
            if recorded and norm(recorded["article"]) == norm(article):
                # Evidence recorded by an earlier content check of this very file (its page-level tie is still read live from the page). No request is made.
                report["steps"].append({"step": "document", "url": link.href, "recorded": True, "requests": 0})
                facts = {**recorded["facts"], "tied_by_official_page": PAGE_TIES.get(page_level, "none"), "assessed_from": "recorded", "evidence_report": recorded["evidence"], "recorded_basis": recorded["basis"]}
                final_url = recorded["final_url"]
                entry.update({"bytes": recorded.get("bytes"), "final_url": final_url, "recorded": True})
            else:
                response = self._get(self.documents_http, report, "document", link.href, deadline)
                if response is None:
                    entry["state"] = "candidate_link_unreachable"
                    if self.halted:
                        break
                    continue
                data = document_bytes(response)
                entry.update({"bytes": len(data), "final_url": response.url})
                if not looks_like_pdf(data) or getattr(response, "truncated", False):
                    entry["state"] = "reachable_but_not_a_complete_pdf"
                    continue
                entry["state"] = "reachable_file"
                try:
                    pages = self.pages_reader(data)
                except Exception as exc:  # noqa: BLE001 -- an unreadable file is an outcome, not a crash
                    entry["state"] = "pdf_unreadable"
                    entry["error"] = str(exc)[:160]
                    continue
                facts = assess_samsung_document(pages, article, link.model_name, page_level)
                final_url = response.url
                tables = manual_device_tables(pages, article)
                if tables:
                    entry["device_tables"] = tables
                    report.setdefault("device_tables", tables)
            facts["acceptance"] = instruction_acceptance(facts, page_data, article, link.model_name)
            entry["facts"] = facts
            if facts.get("content_status") == "text_not_extractable":
                entry["state"] = "manual_check_text_not_extractable"      # nothing is saved: the file proves nothing by its content
                continue
            if facts["regulatory"] or not facts["instruction_by_content"]:
                entry["state"] = "not_an_instruction"
                continue
            if facts["conflicting_models"]:
                entry["state"] = "conflicting_model_in_text"
                continue
            letters = facts["letters_by_language"]
            brief = is_brief_guide(facts)
            language = "Русский" if facts["russian_by_text"] else BRIEF_GUIDE_LANGUAGE if brief else (_LANGUAGE_NAMES.get(max(letters, key=letters.get), "Не определён") if letters else "Не определён")
            entry["state"] = "instruction_saved"
            entry["language_by_text"] = language
            entry["brief_guide"] = brief
            title = f"Краткая памятка Samsung · {brief_guide_note(facts)}" if brief else f"Руководство пользователя Samsung · {levels_note(facts)}"
            documents.append(ProductDocument(title, language, "", "", final_url, document.url, article.split("/")[0], link.model_name, document.url))
            if language == "Русский" and (facts["acceptance"]["accepted"] or facts["acceptance"]["basis"] == "page_tie_not_exact"):
                break      # an accepted Russian instruction ends the search; so does one that a weaker PAGE tie leaves to a person (another file of the same page would be tied no better); a Russian one needing a person for another reason does not
        documents.sort(key=lambda d: d.language != "Русский")
        documents = [ProductDocument(**{**d.__dict__, "primary": i == 0}) for i, d in enumerate(documents)]
        states = [d["state"] for d in report["documents"]]
        russian = sum(1 for d in documents if d.language == "Русский")
        report["documents_outcome"] = "russian_instruction_saved" if russian else "instruction_saved_not_russian" if documents else "no_instruction_saved"
        if russian:
            return documents, ""
        reasons = {"manual_check_text_not_extractable": "текст файла не извлекается (скан или нарисованный текст): проверка вручную", "not_an_instruction": "файл не является инструкцией по содержимому",
                   "conflicting_model_in_text": "в тексте названа другая модель", "candidate_link_unreachable": "файл не получен", "reachable_but_not_a_complete_pdf": "получен не полный PDF",
                   "pdf_unreadable": "PDF не читается", "instruction_saved": "инструкция не на русском языке", "brief_guide_saved": "сохранена краткая памятка с русским разделом; полной русской инструкции нет"}
        states = ["brief_guide_saved" if d.get("brief_guide") else d["state"] for d in report["documents"]]
        unread_candidate = any(d["state"] in ("reachable_but_not_a_complete_pdf", "candidate_link_unreachable", "pdf_unreadable") and d.get("language_hint_from_file_name") == "RU" for d in report["documents"])
        prefix = "Кандидат на русскую инструкцию не проверен (файл с пометкой RU в имени не получен целиком или не прочитан); это не значит, что русской инструкции нет. " if unread_candidate else ""
        return documents, prefix + "Файлов проверено по содержимому: " + f"{len(states)}; " + "; ".join(sorted({reasons.get(s, s) for s in states})) + "."


def match_level_of_document(document: SourceDocument) -> str:
    """The tie level of the page that printed the link, in the vocabulary of samsung.PAGE_TIES."""
    return document.match_level if document.match_level in ("full_sku", "code_in_page_text", "base_model") else "unknown"


def identity_evidence(card: SamsungCard, article: str, level: str) -> str:
    identity = card.identity
    labels = {"jsonld_sku": "sku в разметке товара", "jsonld_name": "название в разметке товара", "title": "заголовок страницы", "visible_text": "видимый текст страницы", "product_data_code": "единственный код в данных товара страницы (modelCode/shopSKU)"}
    shown = ", ".join(labels[e] for e in identity.evidence if e in labels)
    if level == "full_sku":
        return f"Артикул каталога {article} подтверждён содержимым официальной страницы: {shown}."
    if level == "code_in_page_text":
        return (f"Артикул каталога {article} найден на официальной странице только в видимом тексте, не в разметке товара и не в заголовке ({shown}); вариант не считается подтверждённым безусловно, нужна проверка.")
    if level == "base_model":
        return f"Страница той же базовой модели: на ней {identity.jsonld_sku or 'другой код'}, каталог {article}. Открыто: " + "; ".join(identity.open_differences[:4]) + "."
    if not identity.is_product_page:
        return "Страница найдена, но это не страница товара (нет разметки товара и таблицы характеристик)."
    return f"Страница товара найдена, но артикул каталога {article} на ней не показан."


def default_samsung_adapter(directory: Path, *, clock: Callable[[], float] = time.monotonic, underlying=None, underlying_documents=None, min_interval_seconds: float | None = None,
                            pages_reader: Callable[[bytes], list[str]] | None = None, document_max_bytes: int = DOCUMENT_MAX_BYTES,
                            recorded_documents: dict[str, dict] | None = None) -> SamsungAdapter:
    """The adapter the worker builds when nothing is injected. `underlying*` are for tests: a transport double instead of a real requests.Session. Every real call goes through PolicyAwareSession with
    one persisted log (`<data dir>/samsung_fetch_log.json`), so a stop (401/403/429 or a confirmed challenge) outlives the process; pacing is 1.5 s unless the caller replaces it."""
    pacing = {"min_interval_seconds": 1.5 if min_interval_seconds is None else min_interval_seconds}
    log = samsung_log_path(directory)

    def plain():
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"})
        return session

    pages = PolicyAwareSession(log, allowed_hosts=PAGE_HOSTS, underlying=underlying if underlying is not None else plain(), **pacing)
    documents = PolicyAwareSession(log, allowed_hosts=DOCUMENT_HOSTS, underlying=BinarySafeSession(underlying_documents if underlying_documents is not None else (underlying if underlying is not None else plain())),
                                   max_bytes=document_max_bytes, **pacing)
    return SamsungAdapter(pages, documents_http=documents, clock=clock, pages_reader=pages_reader, recorded_documents=recorded_documents)
