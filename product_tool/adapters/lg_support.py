"""Bounded LG support-page evidence, separate from commerce product evidence.

Candidate URLs come from the existing LG search or a saved source snapshot.
A URL, title or generated metadata does not confirm a sales code; the page
must print the product designation in an identity field.
"""
from __future__ import annotations

import re
import time
from types import SimpleNamespace

import requests
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

from .common import ProductDocument, SourceDocument, SourceError, fetch_with_retry
from .lg import lg_article_components, lg_base_model, normalize_lg_sku
from .lg_documents import BinarySafeSession, assess_document, document_bytes, looks_like_pdf
from .lg_documents_adapter import _pdf_pages
from .policy_session import PolicyAwareSession


def is_official_support_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    parts = [part.casefold() for part in parsed.path.split("/") if part]
    return (parsed.scheme == "https" and (host == "lg.com" or host.endswith(".lg.com"))
            and len(parts) >= 3 and parts[0] in {"kz", "ru"}
            and parts[1] == "support" and parts[2] in {"product-support", "product"})


def observed_product_support_urls(html: str, product_url: str) -> tuple[str, ...]:
    """Product-page anchors to observed LG support routes, never identity proof."""
    from .lg_browser_search import is_lg_support_product_url

    soup = BeautifulSoup(html or "", "html.parser")
    urls = []
    for anchor in soup.select("a[href]"):
        url = urldefrag(urljoin(product_url, anchor.get("href", ""))).url
        if is_lg_support_product_url(url):
            urls.append(url)
    return tuple(dict.fromkeys(urls))


def printed_support_codes(html: str) -> tuple[str, ...]:
    """Only product-designation fields, excluding title, route and generic UI text."""
    soup = BeautifulSoup(html or "", "html.parser")
    values = []
    for selector, attribute in (("[data-product-id]", "data-product-id"),
                                ("[data-cs-sales-code]", "data-cs-sales-code"),
                                (".support-product-area .model", None),
                                (".CS0028__productgallery__container .model", None)):
        for node in soup.select(selector):
            value = node.get(attribute, "") if attribute else node.get_text(" ", strip=True)
            code = normalize_lg_sku(value)
            if re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{3,}", code):
                values.append(code)
    return tuple(dict.fromkeys(values))


def registration_component_codes(html: str, page_url: str) -> tuple[str, ...]:
    """Explicit sales codes in registration links printed by this same official page."""
    soup = BeautifulSoup(html or "", "html.parser")
    values = []
    for anchor in soup.select('a[href*="product-registration"]'):
        link = urljoin(page_url, anchor.get("href", ""))
        parsed = urlsplit(link)
        if not is_official_support_url(link) or "product-registration" not in parsed.path.casefold():
            continue
        for key, found in parse_qs(parsed.query).items():
            if key.casefold() != "cssalescode":
                continue
            for value in found:
                code = normalize_lg_sku(value)
                if re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{3,}", code):
                    values.append(code)
    return tuple(dict.fromkeys(values))


def support_payload_codes(payload: dict) -> tuple[str, ...]:
    """Sales codes linked by one official support API response, not route text."""
    page = payload.get("productSupportPage", {}) if isinstance(payload, dict) else {}
    if not isinstance(page, dict):
        return ()
    manual = page.get("manualSoftwareList") or {}
    if not isinstance(manual, dict) or manual.get("localeCode") not in {"KZ", "RU"}:
        return ()
    model = manual.get("modelData") or {}
    values = (page.get("csSalesCode"), manual.get("csSalesCode"),
              model.get("csSalesCode"), (manual.get("modelList") or {}).get("csSalesCode"))
    return tuple(dict.fromkeys(normalize_lg_sku(value) for value in values
                               if isinstance(value, str) and re.fullmatch(
                                   r"[A-Z0-9][A-Z0-9._-]{3,}", normalize_lg_sku(value))))


def support_manual_candidates(html: str, page_url: str) -> tuple[dict, ...]:
    """Direct official PDF links printed in the support DOM; a language label is only a fetch hint."""
    soup = BeautifulSoup(html or "", "html.parser")
    candidates = []
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", ""))
        host = (urlsplit(href).hostname or "").casefold()
        if host not in {"www.lg.com", "gscs-b2c.lge.com"}:
            continue
        if not ("downloadfile" in href.casefold() or href.casefold().split("?", 1)[0].endswith(".pdf")):
            continue
        container = anchor.find_parent(["li", "tr"]) or anchor.parent or anchor
        label = " ".join(container.stripped_strings)
        low = label.casefold()
        if not ("russian" in low or "\u0440\u0443\u0441\u0441\u043a" in low):
            continue
        manual_list_anchor = str(anchor.get("id", "")).startswith("download-manual-label-manualList-")
        if not (manual_list_anchor or "manual" in low or "\u0440\u0443\u043a\u043e\u0432\u043e\u0434" in low
                or "\u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446" in low):
            continue
        if any(bad in low for bad in ("quick", "\u043a\u0440\u0430\u0442\u043a", "\u0434\u0435\u043a\u043b\u0430\u0440", "\u0441\u0435\u0440\u0442\u0438\u0444\u0438\u043a")):
            continue
        candidates.append({"url": href, "label": label[:160]})
    return tuple(dict((item["url"], item) for item in candidates).values())


class LGSupportAdapter:
    source_key, site_name = "lg_kz_support", "LG Казахстан — поддержка"

    def __init__(self, http=None, *, log_path: Path | None = None,
                 candidate_urls: tuple[str, ...] = (), candidate_pages: dict[str, str] | None = None,
                 documents_http=None, candidate_payloads: dict[str, dict] | None = None,
                 clock=time.monotonic):
        self.http = http or PolicyAwareSession(
            log_path or Path("data/lg_fetch_log.json"), allowed_hosts=("www.lg.com",)
        )
        self.documents_http = documents_http or PolicyAwareSession(
            log_path or Path("data/lg_fetch_log.json"), allowed_hosts=("www.lg.com", "gscs-b2c.lge.com"),
            underlying=BinarySafeSession(requests.Session()), max_bytes=25_000_000
        )
        self.candidate_urls = tuple(candidate_urls)
        self.candidate_pages = candidate_pages or {}
        self.candidate_payloads = candidate_payloads or {}
        self.clock = clock

    def find_source(self, article: str, *, deadline: float) -> SourceDocument:
        components = lg_article_components(article)
        urls = tuple(url for url in dict.fromkeys(self.candidate_urls) if is_official_support_url(url))
        if not urls:
            return SourceDocument(self.source_key, self.site_name, "", match_level="support_route_unknown",
                                  evidence="Для артикула нет наблюдаемой официальной ссылки на страницу поддержки.")
        notes = []
        best = None
        rank = {"support_candidate": 0, "base_model": 1, "component_only": 2, "full_sku": 3}
        for url in urls[:3]:
            try:
                response = (SimpleNamespace(url=url, text=self.candidate_pages[url])
                            if url in self.candidate_pages else
                            fetch_with_retry(self.http, url, deadline=deadline, clock=self.clock))
            except SourceError as exc:
                notes.append(f"Наблюдаемую страницу поддержки не удалось проверить: {url}; {exc}")
                continue
            if not is_official_support_url(response.url):
                notes.append(f"Перенаправление увело с официальной страницы поддержки: {response.url}")
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            canonical = soup.select_one('link[rel="canonical"][href]')
            if canonical and urljoin(response.url, canonical["href"]) != response.url:
                notes.append(f"Канонический адрес отличается от открытого: {canonical['href']}")
            printed = printed_support_codes(response.text)
            registered = registration_component_codes(response.text, response.url)
            api_codes = support_payload_codes(self.candidate_payloads.get(response.url, {}))
            matched = tuple(code for code in components if code in printed or code in registered or code in api_codes)
            if len(matched) == len(components):
                level, found = "full_sku", normalize_lg_sku(article)
            elif matched:
                level, found = "component_only", ", ".join(matched)
            elif len(components) == 1 and lg_base_model(components[0]) in printed:
                level, found = "base_model", lg_base_model(components[0])
            else:
                level, found = "support_candidate", ""
            evidence = (f"Официальная страница поддержки открыта. Поля с кодом товара: {', '.join(printed) or 'нет'}; "
                        f"компоненты комплекта, подтверждённые содержимым: {', '.join(matched) or 'нет'}. "
                        "Адрес, заголовок и метаданные остаются лишь признаками кандидата. "
                        "Характеристики, фото и инструкции требуют отдельной проверки.")
            if api_codes:
                evidence += f" Official support API sales codes: {', '.join(api_codes)}."
            region = urlsplit(response.url).path.split("/")[1].casefold()
            document = SourceDocument(f"lg_{region}_support",
                                      self.site_name if region == "kz" else "LG RU support", response.url,
                                      found_model=found, match_level=level, evidence=evidence, html=response.text)
            if best is None or rank[level] > rank[best.match_level]:
                best = document
            if level == "full_sku":
                break
        if best is not None:
            return best
        return SourceDocument(self.source_key, self.site_name, urls[0], match_level="support_candidate",
                              evidence=" ".join(notes), error=" ".join(notes))

    def find_documents(self, support: SourceDocument, article: str, *, deadline: float):
        """Verify a full Russian PDF only when the official page ties every bundle component."""
        report = {"support_url": support.url, "article": article, "candidates": [], "files": [], "outcome": ""}
        if support.match_level != "full_sku":
            report["outcome"] = "kit_identity_unconfirmed"
            return [], report
        candidates = list(support_manual_candidates(support.html, support.url))
        payload = self.candidate_payloads.get(support.url, {})
        page = payload.get("productSupportPage", {}) if isinstance(payload, dict) else {}
        manual = page.get("manualSoftwareList", {}) if isinstance(page, dict) else {}
        manual_list = (manual.get("manualList") or {}).get("manualList", []) if isinstance(manual, dict) else []
        for item in manual_list:
            if not isinstance(item, dict) or item.get("fileNamePrint", "").casefold() != "russian":
                continue
            file_id = item.get("fileName", "")
            for candidate in candidates:
                if file_id and file_id in candidate["url"]:
                    candidate["title"] = item.get("originalFileName", "")
                    candidate["language_label"] = item.get("fileNamePrint", "")
                    candidate["fileUrl"] = item.get("fileUrl", "")
                    candidate["fileName"] = file_id
        report["candidates"] = list(candidates)
        base = lg_base_model(article)
        for candidate in candidates[:2]:
            entry = {"url": candidate["url"], "label": candidate["label"], "state": "candidate"}
            report["files"].append(entry)
            try:
                response = fetch_with_retry(self.documents_http, candidate["url"], deadline=deadline, clock=self.clock)
            except SourceError as exc:
                entry["error"] = str(exc)
                entry["state"] = "unreachable"
                if any(word in str(exc) for word in ("policy_host_stopped", "HTTP 403", "HTTP 429")):
                    break
                continue
            data = document_bytes(response)
            if not looks_like_pdf(data) or getattr(response, "truncated", False):
                entry["state"] = "not_complete_pdf"
                continue
            try:
                assessment = assess_document(_pdf_pages(data), [base])
            except Exception as exc:
                entry["state"], entry["error"] = "unreadable_pdf", str(exc)[:160]
                continue
            language = assessment["languages"]
            entry["assessment"] = {"kind": assessment["kind"], "model_references": assessment["names_model"],
                                   "family_masks": assessment["model_masks"], "russian_by_text": language["russian_instruction"]}
            support_relation = (support.match_level == "full_sku" and
                                assessment["kind"] == "instruction_model_not_named" and
                                not assessment["conflicting_models"])
            if not (assessment["accepted"] or support_relation) or not language["russian_instruction"]:
                entry["state"] = "not_confirmed_russian_instruction"
                continue
            entry["evidence_relation"] = ("official_support_page" if support_relation else "pdf_model_reference")
            entry["state"] = "verified_russian_instruction"
            report["outcome"] = "verified_russian_instruction"
            document = ProductDocument(candidate.get("title") or candidate["label"], "\u0420\u0443\u0441\u0441\u043a\u0438\u0439", "", "", response.url,
                                       support.url, base, ", ".join(lg_article_components(article)), support.url, True)
            return [document], report
        report["outcome"] = "no_verified_russian_instruction"
        return [], report
