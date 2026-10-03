"""Bosch Home discovery and page extraction for ordinary catalog rows.

The legacy two-page Stage 36 manifest remains in ``bosch_home``. This adapter
uses the same source/evidence storage and policy-aware HTTP client, but obtains
new URLs from exact regional routes and Bosch's published sitemaps. A URL is
only a candidate until the page's own JSON-LD Product.mpn confirms identity.
"""
from __future__ import annotations

import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pypdf
import requests
from bs4 import BeautifulSoup

from .common import PhotoCandidate, ProductDocument, RawAttribute, SourceDocument
from .policy_session import PolicyAwareSession
from .sitemap_urls import sitemap_locs
from .structured_page import extract_json_ld_product
from .bosch_home import _asset_key, _exact_photo_code

HOST = "www.bosch-home.com"
MEDIA_HOST = "media3.bsh-group.com"
SOURCE_KEY = "bosch_home"
REGIONAL_SITEMAPS = ("kz", "eg/en", "ne", "ge", "de", "ae/en", "sa/en")
_FLIGHT = re.compile(r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)')
_SPEC_GROUP = re.compile(r'"specifications"\s*:\s*\[\s*\{\s*"name"\s*:')
_SUFFIX = re.compile(r"_(?:[A-Z]{2,3}|\d+)$")
_REVISION = re.compile(r"/\d{2}$")
_DOCUMENT_TITLES_RU = {
    "User manual": "Руководство пользователя", "Interactive manual": "Интерактивное руководство",
    "Installation instructions": "Инструкция по установке", "Datasheet": "Технический паспорт",
    "Product specification sheet": "Спецификация товара", "Product fiche": "Информационный лист",
    "Assembly guide": "Инструкция по сборке", "Supplement": "Дополнение",
    "Planning data": "Монтажные чертежи",
}
_MANUAL_TYPES = {"user-manuals": "User manual", "user-interactive-manuals": "Interactive manual",
                 "installation-instruction": "Installation instructions", "data-sheet": "Datasheet",
                 "product-specification-sheet": "Product specification sheet",
                 "product-fiche": "Product fiche", "assembly-instruction": "Assembly guide",
                 "supplement": "Supplement", "kitchen-planning-data": "Planning data"}


def model_query(article: str) -> tuple[str, str]:
    """Return a URL candidate and the identity relation it may establish."""
    value = re.sub(r"\s+", "", article.strip().upper())
    if _REVISION.search(value):
        return _REVISION.sub("", value), "base_model"
    if _SUFFIX.search(value):
        return _SUFFIX.sub("", value), "base_model"
    return value, "full_sku"


def _flight_chunks(html: str) -> list[str]:
    chunks = []
    for script in BeautifulSoup(html, "html.parser").select("script"):
        raw = script.string or script.get_text()
        if "self.__next_f.push" not in raw:
            continue
        for match in _FLIGHT.finditer(raw):
            try:
                chunks.append(json.loads(match.group(1)))
            except (ValueError, TypeError):
                continue
    return chunks


def grouped_specs(chunks: list[str]) -> list[RawAttribute]:
    """Decode Bosch's server-rendered section/label/value specification tree."""
    for chunk in chunks:
        marker = _SPEC_GROUP.search(chunk)
        if not marker:
            continue
        try:
            groups, _ = json.JSONDecoder().raw_decode(chunk[chunk.find("[", marker.start()):])
        except (ValueError, TypeError):
            continue
        result = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            section = str(group.get("name") or "").strip()
            for item in group.get("specifications") or []:
                if not isinstance(item, dict):
                    continue
                name = (item.get("name") or {}).get("text")
                value = (item.get("value") or {}).get("text")
                unit = item.get("unit")
                if not isinstance(name, str) or not isinstance(value, str):
                    continue
                name, value = " ".join(name.split()), " ".join(value.split())
                value = {"specifications.translatedBoolean.yes": "Да",
                         "specifications.translatedBoolean.no": "Нет"}.get(value, value)
                if not name or not value or len(name) > 110 or len(value) > 240 or name.endswith((".", ":")):
                    continue
                if isinstance(unit, str) and unit and not re.search(r"\b" + re.escape(unit) + r"\b", value, re.I):
                    value += " " + unit
                result.append(RawAttribute(name, value, section))
        if result:
            return result
    return []


def typed_documents(chunks: list[str]) -> list[dict]:
    """Keep document type and URL separately; a PDF may have two types."""
    found = {}
    for chunk in chunks:
        for match in re.finditer(r'"titleKey"\s*:\s*"([^"]+)"', chunk):
            start, end = chunk.rfind("{", 0, match.start()), chunk.find("}", match.end())
            if start < 0 or end < 0 or end-start > 1500:
                continue
            try:
                item = json.loads(chunk[start:end+1])
            except ValueError:
                continue
            key, url = item.get("titleKey"), item.get("url")
            if (key not in _MANUAL_TYPES or not isinstance(url, str)
                    or urlsplit(url).hostname not in {HOST, MEDIA_HOST}):
                continue
            found.setdefault((key, url), {"type": _MANUAL_TYPES[key], "type_key": key,
                                          "url": url, "locale": item.get("locale", ""),
                                          "link_type": item.get("linkType", "")})
    return list(found.values())


def parse_official_page(html: str, url: str, article: str) -> tuple[SourceDocument, dict]:
    requested = re.sub(r"\s+", "", article.strip().upper())
    candidate, relation = model_query(article)
    region = urlsplit(url).path.strip("/").split("/")[0]
    document = SourceDocument(SOURCE_KEY, f"Bosch Home {region.upper()}", url, html=html)
    relation_type = ("bosch_enr_revision_of_model" if _REVISION.search(requested) else
                     "commercial_suffix_of_model" if _SUFFIX.search(requested) else
                     "bosch_model_identifier_exact")
    report = {"article": article, "query_variants": [requested, candidate] if requested != candidate else [requested],
              "identity_relation_type": relation_type,
              "requested_enr": requested if _REVISION.search(requested) else None,
              "model_confirmed": False, "catalog_revision": requested.rsplit("/", 1)[1] if _REVISION.search(requested) else None,
              "page_enr": None, "revision_status": "unknown", "gtin": None,
              "photo_selected": [], "photo_excluded": [], "documents_typed": [],
              "manual_links": [], "manual_verified": False, "manual_russian_by_text": False,
              "manual_exact_code_in_pdf": False, "manual_family": ""}
    fields = extract_json_ld_product(html, url)
    mpns = {field.value.strip().upper() for field in fields if field.name == "mpn"}
    gtins = {field.value.strip() for field in fields if field.name in {"gtin", "gtin13"}}
    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].upper()
    if mpns != {candidate} or slug != candidate:
        document.found_model = ", ".join(sorted(mpns))
        document.match_level = "mismatch" if mpns else "unknown"
        document.error = "Bosch Product.mpn or URL slug does not match the requested candidate."
        return document, report
    document.found_model = candidate
    document.match_level = relation
    document.evidence = (f"Official JSON-LD Product.mpn={candidate}; URL slug={slug}; "
                         f"catalog relation={relation}; E-Nr revision not established by PDP.")
    report.update({"model_confirmed": relation == "full_sku", "gtin": next(iter(sorted(gtins)), None),
                   "page_enr": candidate})
    if relation != "full_sku":
        # Preserve the gallery as rejected candidates; a base PDP does not
        # prove that an inventory suffix or E-Nr revision uses these photos.
        for field in fields:
            if field.name == "json_ld_image":
                report["photo_excluded"].append({"url": field.value, "reason": "base_model_only"})
                document.photo_candidates.append(PhotoCandidate(
                    field.value, _asset_key(field.value) + "_excluded", kind="excluded",
                    excluded_reason="base_model_only"))
        return document, report
    chunks = _flight_chunks(html)
    document.attributes = grouped_specs(chunks)
    if not document.attributes:
        document.attributes = [RawAttribute(f.name, f.value) for f in fields
                               if f.name not in {"name", "sku", "productID", "gtin", "gtin13", "mpn", "json_ld_image"}
                               and len(f.name) <= 80 and not f.name.endswith((".", ":"))]
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.select_one('meta[name="description"],meta[property="og:description"]')
    document.description = (meta.get("content", "") if meta else "").strip()
    seen = set()
    for field in fields:
        if field.name != "json_ld_image":
            continue
        photo_url = field.value
        if not _exact_photo_code(photo_url, candidate):
            report["photo_excluded"].append({"url": photo_url, "reason": "not_model_bound"})
            document.photo_candidates.append(PhotoCandidate(
                photo_url, _asset_key(photo_url) + "_excluded", kind="excluded",
                excluded_reason="not_model_bound"))
            continue
        asset = _asset_key(photo_url)
        if asset in seen:
            continue
        seen.add(asset)
        document.photos.append(photo_url)
        document.photo_candidates.append(PhotoCandidate(photo_url, asset))
        report["photo_selected"].append(photo_url)
    report["documents_typed"] = typed_documents(chunks)
    report["manual_links"] = [item["url"] for item in report["documents_typed"]
                              if item["type_key"] == "user-manuals"]
    return document, report


class BoschOfficialAdapter:
    source_key = SOURCE_KEY

    def __init__(self, http=None, *, clock=time.monotonic, fetch_log_path: Path | None = None,
                 trace_callback=None, browser_search=None):
        self.clock = clock
        self.http = http or PolicyAwareSession(fetch_log_path or Path("bosch_home_fetch_log.json"),
                  allowed_hosts=(HOST,), underlying=requests.Session(), clock=clock,
                  max_bytes=25_000_000, min_interval_seconds=1.5)
        self.trace_callback = trace_callback
        self.browser_search = browser_search
        self.reports = {}

    def _trace(self, **event):
        if self.trace_callback:
            self.trace_callback({"event": "bosch_discovery", "timestamp": datetime.now(timezone.utc).isoformat(), **event})

    def _fetch_candidate(self, url: str, article: str, provider: str, deadline: float) -> SourceDocument | None:
        if self.clock() >= deadline:
            self._trace(provider=provider, url=url, decision="rejected", reason="deadline", identity="unknown")
            return None
        try:
            response = self.http.get(url, timeout=min(18, max(1, deadline-self.clock())))
        except requests.RequestException as exc:
            self._trace(provider=provider, url=url, decision="rejected", reason=type(exc).__name__, identity="unknown")
            return None
        if response.status_code != 200 or getattr(response, "truncated", False):
            self._trace(provider=provider, url=url, decision="rejected",
                        reason=f"http_{response.status_code}_or_truncated", identity="unknown")
            return None
        if urlsplit(response.url).hostname != HOST:
            self._trace(provider=provider, url=url, decision="rejected", reason="off_host_redirect", identity="unknown")
            return None
        document, report = parse_official_page(response.text, response.url, article)
        accepted = document.match_level == "full_sku" and not document.error
        self._trace(provider=provider, url=url, final_url=response.url,
                    region=urlsplit(response.url).path.strip("/").split("/")[0],
                    decision="accepted" if accepted else "rejected",
                    reason="exact_product_identity" if accepted else document.error or "base_model_only",
                    identity=document.match_level, specs=len(document.attributes), photos=len(document.photos))
        if not document.error:
            self.reports[article] = report
        return document

    def find_source(self, article: str, *, category: str, deadline: float) -> SourceDocument:
        candidate, _ = model_query(article)
        self._trace(provider="model_variants", query=article, variants=[article.strip().upper(), candidate],
                    decision="candidate", reason="normalized_spaces_and_explicit_suffix_relation", identity="unknown")
        best = None
        kz = f"https://{HOST}/kz/ru/product/{candidate}"
        page = self._fetch_candidate(kz, article, "bosch_kz_direct", deadline)
        if page and page.match_level == "full_sku" and not page.error:
            return page
        if page and page.match_level == "base_model":
            best = page
        for region in REGIONAL_SITEMAPS:
            if self.clock() >= deadline:
                break
            sitemap = f"https://{HOST}/{region}/sitemap.xml"
            try:
                response = self.http.get(sitemap, timeout=min(18, max(1, deadline-self.clock())))
                if response.status_code != 200 or getattr(response, "truncated", False):
                    raise ValueError(f"http_{response.status_code}_or_truncated")
                urls = sitemap_locs(response.text)
            except (requests.RequestException, ValueError) as exc:
                self._trace(provider="bosch_sitemap", url=sitemap, decision="rejected",
                            reason=str(exc)[:120], identity="unknown")
                continue
            matches = [url for url in urls if urlsplit(url).hostname == HOST
                       and any(part in urlsplit(url).path for part in ("/product/", "/mkt-product/"))]
            matches = [url for url in matches if urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].upper() == candidate]
            self._trace(provider="bosch_sitemap", url=sitemap, query=candidate,
                        decision="candidate" if matches else "rejected",
                        reason="exact_slug_candidate" if matches else "sitemap_miss_not_product_absence",
                        identity="unverified", candidate_count=len(matches))
            for url in matches[:2]:
                page = self._fetch_candidate(url, article, "bosch_sitemap", deadline)
                if page and page.match_level == "full_sku" and not page.error:
                    return page
                if page and page.match_level == "base_model" and best is None:
                    best = page
        # Some official PDPs are live but omitted from their regional sitemap.
        for prefix in ("eg/en/product", "ne/en/mkt-product", "ge/ka/mkt-product", "de/de/product",
                       "ae/en/mkt-product", "sa/en/mkt-product"):
            if self.clock() >= deadline:
                break
            url = f"https://{HOST}/{prefix}/{candidate}"
            page = self._fetch_candidate(url, article, "bosch_other_region_direct", deadline)
            if page and page.match_level == "full_sku" and not page.error:
                return page
            if page and page.match_level == "base_model" and best is None:
                best = page
        found = self._external_fallback(article, deadline=deadline)
        if found is not None:
            return found
        return best or SourceDocument(SOURCE_KEY, "Bosch Home", kz,
                                      error="No content-validated exact official Bosch PDP within bounded regional search.")

    def _external_fallback(self, article: str, *, deadline: float) -> SourceDocument | None:
        """Use the existing browser search transport only after official misses."""
        if self.clock() >= deadline:
            return None
        from .lg_browser_search import LGBrowserSearch
        owned = self.browser_search is None
        browser = self.browser_search or LGBrowserSearch(
            getattr(self.http, "log_path", Path("bosch_home_fetch_log.json")),
            allowed_hosts=(HOST, "bosch-home.com", "www.google.com", "google.com",
                           "gstatic.com", "www.bing.com", "bing.com", "duckduckgo.com"),
            official_host=HOST, clock=self.clock)
        candidate, _ = model_query(article)
        terms = list(dict.fromkeys((article.strip().upper(), candidate)))
        opened, seen = 0, set()
        try:
            for provider in ("google", "bing"):
                for term in terms:
                    if self.clock() >= deadline or opened >= 4:
                        return None
                    query = f'site:bosch-home.com "{term}"'
                    result = browser.search_provider(provider, query)
                    self._trace(provider=provider + "_browser", query=query,
                                decision="candidate" if result.candidates else "rejected",
                                reason=result.outcome, identity="unverified")
                    if result.outcome in {"host_stopped", "challenge_detected", "rate_limited",
                                          "http_denied", "runtime_unavailable"}:
                        return None
                    for item in result.candidates:
                        url = item.url
                        if url in seen:
                            continue
                        seen.add(url)
                        parsed = urlsplit(url)
                        product = parsed.scheme == "https" and parsed.hostname == HOST and any(
                            part in parsed.path for part in ("/product/", "/mkt-product/"))
                        if not product:
                            self._trace(provider=item.provider or provider, query=query, url=url,
                                        decision="rejected", reason="support_or_non_product_result",
                                        identity="unverified")
                            continue
                        if opened >= 4 or self.clock() >= deadline:
                            return None
                        opened += 1
                        document = self._fetch_candidate(url, article, item.provider or provider, deadline)
                        if document and document.match_level == "full_sku" and not document.error:
                            return document
            return None
        finally:
            if owned:
                browser.close()

    def find_support(self, document: SourceDocument, article: str, *, deadline: float) -> list[str]:
        """Read the official E-Nr search list without treating revisions as the catalog's own."""
        if document.error or document.match_level != "full_sku":
            return []
        region = urlsplit(document.url).path.strip("/").split("/")[0]
        candidate, _ = model_query(article)
        url = f"https://{HOST}/{region}/support/list/{candidate}"
        if self.clock() >= deadline:
            return []
        try:
            response = self.http.get(url, timeout=min(15, max(1, deadline-self.clock())))
        except requests.RequestException as exc:
            self._trace(provider="bosch_support_list", url=url, decision="rejected",
                        reason=type(exc).__name__, identity="unknown")
            return []
        if response.status_code != 200 or getattr(response, "truncated", False):
            self._trace(provider="bosch_support_list", url=url, decision="rejected",
                        reason=f"http_{response.status_code}_or_truncated", identity="unknown")
            return []
        found = []
        for anchor in BeautifulSoup(response.text, "html.parser").select('a[href*="supportdetail/product/"]'):
            href = anchor.get("href", "")
            match = re.search(r"/supportdetail/product/" + re.escape(candidate) + r"/(\d{2})(?:[/?#]|$)", href, re.I)
            if match:
                full = f"https://{HOST}/{region}/supportdetail/product/{candidate}/{match.group(1)}"
                if full not in found:
                    found.append(full)
        self.reports.setdefault(article, {})["support_revision_candidates"] = found
        self.reports[article]["support_list_url"] = url
        self._trace(provider="bosch_support_list", url=url, decision="candidate" if found else "rejected",
                    reason="revision_candidates_not_catalog_exact" if found else "no_revision_candidates",
                    identity="revision_unknown", candidate_count=len(found))
        return found

    def _verify_russian_pdf(self, url: str, article: str) -> dict:
        """Read a bounded official PDF and distinguish language from E-Nr identity."""
        result = {"url": url, "checked": False, "russian_by_text": False,
                  "exact_model_in_pdf": False, "reason": ""}
        if urlsplit(url).scheme != "https" or urlsplit(url).hostname != MEDIA_HOST:
            result["reason"] = "not_official_pdf_host"
            return result
        fetcher = getattr(self.http, "_fetcher", None)
        if fetcher is not None and fetcher.host_stopped(url):
            result["reason"] = "host_access_stopped"
            return result
        session = getattr(self.http, "underlying", None)
        if session is None:
            result["reason"] = "binary_fetch_unavailable"
            return result
        response = None
        try:
            response = session.get(url, timeout=18, stream=True, allow_redirects=False)
            if response.status_code != 200 or urlsplit(response.url).hostname != MEDIA_HOST:
                result["reason"] = f"http_{response.status_code}_or_redirect"
                return result
            if "pdf" not in response.headers.get("Content-Type", "").lower():
                result["reason"] = "non_pdf_content_type"
                return result
            max_bytes = 15_000_000
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                result["reason"] = "pdf_exceeds_size_cap"
                return result
            parts, total = [], 0
            for chunk in response.iter_content(65536):
                total += len(chunk)
                if total > max_bytes:
                    result["reason"] = "pdf_exceeds_size_cap"
                    return result
                parts.append(chunk)
            reader = pypdf.PdfReader(io.BytesIO(b"".join(parts)), strict=False)
            russian, exact = False, False
            candidate, _ = model_query(article)
            for page in reader.pages:
                text = page.extract_text() or ""
                if sum("\u0400" <= char <= "\u04ff" for char in text) >= 40 and re.search(
                        r"руководств|инструкц|безопасност", text, re.I):
                    russian = True
                if candidate in text.upper():
                    exact = True
            result.update({"checked": True, "russian_by_text": russian,
                           "exact_model_in_pdf": exact, "reason": "pdf_text_checked",
                           "bytes": total, "pages": len(reader.pages)})
            return result
        except (requests.RequestException, ValueError, OSError, pypdf.errors.PdfReadError) as exc:
            result["reason"] = type(exc).__name__
            return result
        finally:
            if response is not None:
                response.close()

    def find_documents(self, document: SourceDocument, article: str) -> list[ProductDocument]:
        if document.error or document.match_level != "full_sku":
            return []
        report = self.reports.get(article, {})
        grouped = {}
        for item in report.get("documents_typed", []):
            url = item["url"]
            if urlsplit(url).hostname != MEDIA_HOST or not urlsplit(url).path.lower().endswith(".pdf"):
                continue
            grouped.setdefault(url, []).append(item["type"])
        found, checks = [], []
        for url, types in grouped.items():
            title = "; ".join(_DOCUMENT_TITLES_RU.get(kind, kind) for kind in dict.fromkeys(types))
            check = (self._verify_russian_pdf(url, article) if "User manual" in types
                     else {"url": url, "checked": False, "russian_by_text": False,
                           "exact_model_in_pdf": False, "reason": "not_user_manual"})
            checks.append(check)
            language = "Русский" if check["russian_by_text"] else ""
            found.append(ProductDocument(title=title, language=language, document_date="", size="",
                                         direct_url=url, source_url=document.url, product_model=article,
                                         support_model=document.found_model, relation_url=document.url,
                                         primary="User manual" in types))
        verified = [x for x in checks if x["russian_by_text"]]
        report.update({"pdf_checks": checks, "manual_verified": bool(verified),
                       "manual_russian_by_text": bool(verified),
                       "manual_exact_code_in_pdf": any(x["exact_model_in_pdf"] for x in verified),
                       "manual_family": "linked from exact PDP; PDF model unprinted" if verified
                       and not any(x["exact_model_in_pdf"] for x in verified) else ""})
        return found
