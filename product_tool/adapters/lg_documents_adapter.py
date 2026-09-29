"""Stage 22: the LG Russia documents adapter.

Route (established in Stage 22, see docs/LG_STAGE22_RULES.md): the support page printed on the LG Russia product page
(/ru/support/product/lg-<full code>) -> its static manuals list (`.support-downloads li.manuals`) -> a complete PDF -> an instruction
confirmed by the file's OWN text. What the page prints next to a link (a type, a language label) only decides which links are worth a
request; it is never evidence of what the file says.
"""
from __future__ import annotations

import io
import logging
import re
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .common import ProductDocument, SourceError, clean_text, fetch_with_retry
from .lg import LGRUAdapter, _support_page_sales_code
from .lg_documents import assess_document, document_bytes, looks_like_pdf

MAX_FILES_PER_PRODUCT = 2
_SUPPORT_LINK = re.compile(r"/ru/support/product/lg-([A-Za-z0-9._-]+)", re.I)
_LANGUAGE_NAMES = {"ru": "Русский", "kk": "Казахский", "en": "Английский", "uk": "Украинский"}
_HALT_MARKERS = ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")


def _pdf_pages(data: bytes) -> list[str]:
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)  # font-decoding warnings are noise here; the extracted text is what is judged
    return [(page.extract_text() or "") for page in pypdf.PdfReader(io.BytesIO(data)).pages]


def _host_ok(url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold()
    return host in {"lg.com", "www.lg.com", "lge.com"} or host.endswith(".lge.com")


def support_candidates(html: str, page_url: str) -> list[dict]:
    """Manuals listed on an LG support page: what the PAGE prints (a type text, a language LABEL, a date, a size, an href). A candidate link, no confirmation."""
    soup = BeautifulSoup(html or "", "html.parser")
    candidates = []
    for li in soup.select(".support-downloads .list > li.manuals"):
        anchor = li.select_one(".name a[href]") or li.select_one("a[href]")
        if anchor is None:
            continue
        spans = [clean_text(x.get_text(" ")) for x in li.select(".data span")]
        raw = anchor.get("href", "")
        href = urljoin(page_url, raw)
        candidates.append({"type": clean_text((li.select_one(".type") or li).get_text(" "))[:80], "label": clean_text(anchor.get_text(" "))[:80], "date": spans[0] if spans else "",
                           "size": spans[1] if len(spans) > 1 else "", "href": href, "fetchable": bool(re.match(r"https?://", raw)) and _host_ok(href)})
    return candidates


def fetch_order(candidates: list[dict]) -> list[dict]:
    """Only guides (the type text mentions руководство) whose printed label says Russian are worth a request, the fuller manual first."""
    wanted = [c for c in candidates if c["fetchable"] and "руководств" in c["type"].casefold() and "русск" in c["label"].casefold()]
    return sorted(wanted, key=lambda c: 0 if "пользовател" in c["type"].casefold() else 1)


SUPPORT_TIE_NOTE = " · связь с моделью подтверждена страницей поддержки, а не текстом PDF"


def support_page_ties_article(html: str, article: str) -> tuple[bool, str]:
    """Does the official support page itself name the row's FULL article as the product whose document list it shows? Its printed model text (the product
    heading) must be the article, or the article followed by a regional suffix ("50UT91006LA" -> "50UT91006LA.ARUG"). A support URL that merely contains the
    article proves nothing (owner decision, Stage 23)."""
    soup = BeautifulSoup(html or "", "html.parser")
    node = soup.select_one(".support-product-area .text-block .model") or soup.select_one("h1")
    printed = re.sub(r"\s+", "", node.get_text(" ")).upper() if node else ""
    wanted = re.sub(r"\s+", "", article or "").upper()
    return bool(printed and wanted and (printed == wanted or printed.startswith(wanted + "."))), printed


class LGRUDocumentAdapter(LGRUAdapter):
    """LGRUAdapter with the Stage 22 find_documents. The old label-based method (a "Русский" label became the language "Русский") is not used."""

    def __init__(self, http=None, *, documents_http=None, clock=time.monotonic, browser_search=None):
        super().__init__(http, clock=clock, browser_search=browser_search)
        self.documents_http = documents_http if documents_http is not None else self.http
        self.reports: list[dict] = []

    def find_documents(self, document, product_model: str, *, deadline: float):
        report = {"product_model": product_model, "support_url": "", "candidates": [], "files": [], "outcome": ""}
        self.reports.append(report)
        soup = BeautifulSoup(document.html or "", "html.parser")
        codes: dict[str, str] = {}
        for a in soup.select('a[href*="/ru/support/product/"]'):
            match = _SUPPORT_LINK.search(a.get("href", ""))
            if match:
                codes.setdefault(match.group(1).upper(), urljoin(document.url, a["href"]))
        if len(codes) != 1:
            report["outcome"] = "support_link_not_printed" if not codes else "several_support_links"
            return [], "Страница поддержки LG на странице товара не указана." if not codes else "На странице товара несколько разных страниц поддержки."
        support_code, support_url = next(iter(codes.items()))
        report["support_url"] = support_url
        try:
            page = fetch_with_retry(self.documents_http, support_url, deadline=deadline, clock=self.clock)
        except SourceError as exc:
            report["outcome"] = "support_page_unreachable"
            return [], str(exc)
        # Preserve the fetched support page in this run, so the worker can
        # record its printed product code without another request. A link on
        # the PDP or the requested URL is never the support page's identity.
        report["support_page_url"] = page.url
        report["support_page_sales_code"] = _support_page_sales_code(page.text)
        report["_support_html"] = page.text
        candidates = support_candidates(page.text, page.url)
        report["candidates"] = candidates
        if not candidates:
            report["outcome"] = "no_manual_candidates"
            return [], "На странице поддержки нет списка руководств."
        tokens = [product_model, support_code.split(".")[0]]
        exact_article = document.found_model if document.match_level == "full_sku" else ""
        tie, printed_model = support_page_ties_article(page.text, exact_article)
        report["support_page_model"], report["support_page_ties_full_article"] = printed_model, tie
        documents: list[ProductDocument] = []
        unnamed_russian = False
        for candidate in fetch_order(candidates)[:MAX_FILES_PER_PRODUCT]:
            entry = {"href": candidate["href"], "type": candidate["type"], "label": candidate["label"], "state": "candidate_link"}
            report["files"].append(entry)
            try:
                response = fetch_with_retry(self.documents_http, candidate["href"], deadline=deadline, clock=self.clock)
            except SourceError as exc:
                entry["state"] = "candidate_link_unreachable"
                entry["error"] = str(exc)[:200]
                if any(marker in str(exc) for marker in _HALT_MARKERS):
                    break
                continue
            data = document_bytes(response)
            entry["bytes"] = len(data)
            if not looks_like_pdf(data) or getattr(response, "truncated", False):
                entry["state"] = "reachable_but_not_a_complete_pdf"
                continue
            entry["state"] = "reachable_file"
            try:
                pages = _pdf_pages(data)
            except Exception as exc:  # noqa: BLE001 -- an unreadable file is an outcome, not a crash
                entry["error"] = f"pdf: {str(exc)[:120]}"
                continue
            assessment = assess_document(pages, tokens)
            languages = assessment["languages"]
            entry["assessment"] = {"accepted": assessment["accepted"], "kind": assessment["kind"], "names_model": assessment["names_model"], "model_masks": assessment["model_masks"],
                                   "model_evidence": assessment["model_evidence"], "conflicting_models": assessment.get("conflicting_models", []), "text_chars": assessment["text_chars"], "languages": languages["present"],
                                   "russian_instruction": languages["russian_instruction"], "letters_by_language": languages["letters_by_language"]}
            if not assessment["accepted"]:
                if assessment["kind"] == "instruction_model_not_named" and languages["russian_instruction"] and tie:
                    # Owner decision (Stage 23): a Russian instruction by its content, listed on the official support page that names the row's FULL article, on a
                    # product page that shows that article, with no conflicting model in the text -- accepted, and marked: the tie to the model is the support page's.
                    entry["state"] = "instruction_confirmed_by_support_page"
                    entry["content_language"] = "Русский"
                    documents.append(ProductDocument(candidate["type"] + SUPPORT_TIE_NOTE, "Русский", candidate["date"], candidate["size"], response.url, page.url, product_model, support_code, document.url))
                    break
                if assessment["kind"] == "instruction_model_not_named":
                    # An instruction by its content whose text never names this model or its family: tied to the product only by the official support page
                    # it was listed on. It is reported, not saved as the product's instruction; and when it is Russian there is nothing more to fetch.
                    entry["state"] = "instruction_by_content_model_not_named"
                    entry["content_language"] = "Русский" if languages["russian_instruction"] else "не русский"
                    unnamed_russian = unnamed_russian or languages["russian_instruction"]
                    if languages["russian_instruction"]:
                        break
                else:
                    entry["state"] = "reachable_file_not_confirmed_as_instruction"
                continue
            entry["state"] = "instruction_confirmed_by_content"
            letters = languages["letters_by_language"]
            if languages["russian_instruction"]:
                language = "Русский"
            else:
                language = _LANGUAGE_NAMES.get(max(letters, key=letters.get), "Не определён") if letters else "Не определён"
            entry["content_language"] = language
            documents.append(ProductDocument(candidate["type"], language, candidate["date"], candidate["size"], response.url, page.url, product_model, support_code, document.url))
            if language == "Русский":
                break
        documents.sort(key=lambda d: d.language != "Русский")
        documents = [ProductDocument(**{**d.__dict__, "primary": i == 0}) for i, d in enumerate(documents)]
        russian = sum(1 for d in documents if d.language == "Русский")
        report["outcome"] = ("russian_instruction_confirmed" if russian else "instruction_confirmed_not_russian" if documents else
                             "russian_instruction_model_not_named" if unnamed_russian else "no_instruction_confirmed")
        if russian:
            return documents, ""
        reason = (f"Кандидатов на странице поддержки: {len(candidates)}; файлов проверено по содержимому: {len(report['files'])}; "
                  + ("подтверждена инструкция не на русском языке (язык определён по тексту файла)." if documents else
                     "найдена инструкция на русском языке, но её текст не называет модель или её семейство (связь только через страницу поддержки), она не сохранена." if unnamed_russian else
                     "ни один файл не подтверждён как инструкция на русском языке."))
        return documents, reason
