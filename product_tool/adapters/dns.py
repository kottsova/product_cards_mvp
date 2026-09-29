"""DNS (dns-shop.ru) dealer-fallback adapter.

Per explicit user authorization (Stage 11.3/11.4): dns-shop.ru may be used as
a SECONDARY source, for ANY brand/category in the catalog, to fill in
characteristics, photos, or instructions that official sources could not
supply. Official sources always take priority and are always checked first
by the caller (see worker.py); this adapter never claims to be an official
source, and nothing here silently overwrites an official value -- that
guarantee lives in resolve_attributes()'s existing per-attribute-name
priority order (see resolution.py and source_types.py for why no change
there was needed).

Design constraints, all enforced in code, not just documentation:
  - Two distinct host roles, never interchangeable: PAGE_HOST serves product
    pages; DOCUMENT_HOST serves PDFs. A page URL on the wrong host, or a
    document URL on the wrong host, is rejected before any request.
  - No crawling, no search, no discovery. KNOWN_URLS / KNOWN_DOCUMENT_URLS
    are explicit, pre-verified maps of search_code -> URL, exactly mirroring
    the existing SulpakAdapter pattern (adapters/sulpak.py) -- a product
    with no entry simply yields no DNS candidate. This is what "no mass
    collection" means in code: there is no
    method on this class that could crawl dns-shop.ru at all.
  - A blocked response (401/403/429) is recorded as-is and never retried
    with different headers or any other bypass technique.
  - Documents are verified by their own extracted content (see
    document_verification.py) before being accepted -- a matching filename
    or DNS's own page label is never sufficient by itself.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from product_tool.census.endpoint_probe import ProbePolicy

from ..dealer_fallback import dealer_url_needed_request
from .common import SourceDocument, SourceError, clean_text, meta_description
from .document_verification import verify_document
from .supplier import extract_photo_candidates, extract_table_attributes, visible_text

PAGE_HOST = "www.dns-shop.ru"
DOCUMENT_HOST = "drv.dns-shop.ru"
ALLOWED_HOSTS = frozenset({PAGE_HOST, DOCUMENT_HOST})

# Explicit, pre-verified candidates only -- never crawled or guessed.
# Populated only for rows this project has actually investigated (Stage 11.3).
KNOWN_URLS: dict[str, str] = {
    "9A273AA": "https://www.dns-shop.ru/product/driver/e949b555b392d582/mikrofonnyj-komplekt-hyperx-quadcast-2-s-cernyj/",
    # Owner-supplied DNS page: the screenshot shows this exact value in
    # "Код производителя". The shorter 32LQ63006LA is a different catalog row.
    "32LQ63006LA.ARUG": "https://www.dns-shop.ru/product/dedc85f90ae5d21a/32-80-sm-televizor-lg-32lq63006la-cernyj/",
}
KNOWN_DOCUMENT_URLS: dict[str, str] = {
    "9A273AA": "https://drv.dns-shop.ru/drivers/Manuals/H/hyperx-quadcast-2-s_instrukcia_104913_30102025.pdf",
}

# Reuses the project's existing bounded-probe policy dataclass (product_tool.census)
# as this adapter's own request policy, instead of inventing a second one.
PAGE_POLICY = ProbePolicy(timeout_seconds=10.0, max_bytes=900_000, min_interval_seconds=2.0,
                           user_agent="ProductCardsSourceCensus/2.0 (dealer fallback, DNS)")
DOCUMENT_CHUNK_BYTES = 1_500_000
DOCUMENT_MAX_TOTAL_BYTES = 12_000_000

BLOCKED_STATUS = {401, 403, 429}
_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+)")


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold()


def _redirect_chain_hosts_allowed(response: requests.Response, allowed_host: str) -> str:
    """Returns '' if every hop (redirects + final) stayed on allowed_host, else the first bad host."""
    chain = [r.url for r in response.history] + [response.url]
    for hop in chain:
        host = _host_of(hop)
        if host != allowed_host:
            return host
    return ""


def _document_language_label(languages: tuple[str, ...]) -> str:
    """Use the same user-facing language labels as card_readiness()."""
    for code, label in (("ru", "Русский"), ("en", "Английский"),
                        ("kk", "Казахский"), ("uk", "Украинский")):
        if code in languages:
            return label
    return ",".join(languages) or "Не определён"


@dataclass(frozen=True)
class IdentityCheck:
    model_matched: bool
    code_matched: bool

    @property
    def level(self) -> str:
        if self.model_matched and self.code_matched:
            return "model_and_code_confirmed"
        if self.model_matched:
            return "model_only"
        if self.code_matched:
            return "code_only"
        return "unconfirmed"


def _manufacturer_codes(soup: BeautifulSoup) -> tuple[str, ...]:
    """Read only DNS's labelled manufacturer-code value, never page-wide text.

    DNS has used both specification rows and paired label/value divs. More
    than one distinct code is ambiguous, so the caller requires a singleton.
    Brackets in displayed values such as [32LQ63006LA.ARUG] are presentation.
    """
    visible = BeautifulSoup(str(soup), "html.parser")
    for hidden in visible.select("script, style, template, noscript, [hidden], [aria-hidden='true']"):
        hidden.decompose()

    def normalized(value: str) -> str:
        return clean_text(value).strip("[] \t\r\n").upper()

    values = [normalized(a.value) for a in extract_table_attributes(visible)
              if clean_text(a.name).casefold().rstrip(":") == "код производителя"]
    for label in visible.find_all(string=lambda s: bool(s) and clean_text(s).casefold().rstrip(":") == "код производителя"):
        node = label.parent
        if node is None or node.parent is None:
            continue
        siblings = node.parent.find_all(recursive=False)
        if node in siblings and len(siblings) <= 4:
            index = siblings.index(node)
            if index + 1 < len(siblings):
                values.append(normalized(siblings[index + 1].get_text(" ", strip=True)))
    return tuple(sorted({v for v in values if re.fullmatch(r"[A-Z0-9][A-Z0-9._/#-]{2,}", v)}))


def check_identity(text: str, *, model_tokens: list[str], code: str,
                   manufacturer_codes: tuple[str, ...] = ()) -> IdentityCheck:
    model_matched = any(re.search(re.escape(tok), text, re.I) for tok in model_tokens if tok)
    code_matched = bool(code) and manufacturer_codes == (code.upper(),)
    return IdentityCheck(model_matched, code_matched)


class DnsAdapter:
    source_key = "dns"
    site_name = "DNS"

    def __init__(
        self, http: requests.Session | None = None, *,
        clock: Callable[[], float] = time.monotonic,
        urls: dict[str, str] | None = None,
        document_urls: dict[str, str] | None = None,
    ):
        self.http = http or requests.Session()
        self.http.headers.update({
            "User-Agent": PAGE_POLICY.user_agent,
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        self.clock = clock
        self.urls = urls if urls is not None else KNOWN_URLS
        self.document_urls = document_urls if document_urls is not None else KNOWN_DOCUMENT_URLS
        self.request_count = 0
        self._last_request_at: float | None = None
        self._confirmed_codes: set[str] = set()
        self._requested_missing: dict[str, frozenset[str]] = {}

    def _respect_rate_limit(self) -> None:
        if self._last_request_at is not None:
            remaining = PAGE_POLICY.min_interval_seconds - (self.clock() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)

    # --- Product page -------------------------------------------------

    def find_source(
        self, search_code: str, *, deadline: float, model_tokens: list[str] | None = None,
        brand: str = "", name: str = "", missing_fields: list[str] | None = None,
    ) -> SourceDocument:
        normalized = (search_code or "").strip().upper()
        if missing_fields is not None:
            self._requested_missing[normalized] = frozenset(missing_fields)
        if missing_fields is not None and not missing_fields:
            return SourceDocument(
                self.source_key, self.site_name, "", match_level="not_needed",
                evidence="Все запрошенные для этого задания поля уже получены из других источников; дилерский запрос не требуется.",
            )
        url = self.urls.get(normalized, "")
        if not url:
            # missing_fields is the caller's concrete finding, not a guess
            # here: None means "caller did not check" (only true default
            # callers, e.g. older/direct tests, get the worst-case full
            # list); an explicit [] means the caller DID check and nothing
            # is actually missing, so there is nothing to ask about.
            request = dealer_url_needed_request(
                brand=brand, name=name, seller_code=normalized,
                missing_fields=missing_fields if missing_fields is not None else ["характеристики", "фото", "инструкция"],
            )
            return SourceDocument(
                self.source_key, self.site_name, "", match_level="dealer_url_needed",
                evidence=request.message,
            )
        if _host_of(url) != PAGE_HOST:
            return SourceDocument(
                self.source_key, self.site_name, url, match_level="unknown",
                error=f"Configured URL host '{_host_of(url)}' is not the allowed product-page host '{PAGE_HOST}'.",
            )
        try:
            self.request_count += 1
            self._respect_rate_limit()
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise SourceError("Time budget exhausted before the DNS page request.")
            response = self.http.get(url, timeout=min(PAGE_POLICY.timeout_seconds, remaining))
            self._last_request_at = self.clock()
        except requests.RequestException as exc:
            return SourceDocument(self.source_key, self.site_name, url, match_level="unknown", error=f"Request failed: {exc}")

        bad_host = _redirect_chain_hosts_allowed(response, PAGE_HOST)
        if bad_host:
            return SourceDocument(
                self.source_key, self.site_name, url, match_level="unknown",
                error=f"Redirected off the allowed host to '{bad_host}' -- not followed.",
            )
        if response.status_code in BLOCKED_STATUS:
            return SourceDocument(
                self.source_key, self.site_name, url, match_level="blocked",
                error=f"HTTP {response.status_code} -- access blocked. Not retried with different headers or any bypass.",
            )
        if response.status_code >= 400:
            return SourceDocument(self.source_key, self.site_name, url, match_level="unknown", error=f"HTTP {response.status_code}")

        text = response.text[:PAGE_POLICY.max_bytes]
        soup = BeautifulSoup(text, "html.parser")
        page_text = visible_text(soup)
        codes = _manufacturer_codes(soup)
        identity = check_identity(page_text, model_tokens=model_tokens or [], code=normalized,
                                  manufacturer_codes=codes)
        confirmed = identity.level == "model_and_code_confirmed"
        if confirmed:
            self._confirmed_codes.add(normalized)
        photos = extract_photo_candidates(soup, response.url, source_key=self.source_key) if confirmed else []
        evidence = (
            f"model_matched={identity.model_matched}, code_matched={identity.code_matched} "
            f"(catalog_code={normalized!r}, DNS 'Код производителя'={codes!r})"
        )
        return SourceDocument(
            self.source_key, self.site_name, response.url,
            found_model=normalized if identity.code_matched else "",
            match_level=identity.level,
            evidence=evidence,
            attributes=extract_table_attributes(soup) if confirmed else [],
            description=meta_description(soup) if confirmed else "",
            photos=[item.url for item in photos if item.kind != "excluded"],
            photo_candidates=photos,
        )

    # --- Bounded PDF fetch + content verification ----------------------

    def _single_range_request(self, url: str, start: int, end: int, *, deadline: float):
        remaining = deadline - self.clock()
        if remaining <= 0:
            return None, "Time budget exhausted before this document chunk."
        self._respect_rate_limit()
        try:
            self.request_count += 1
            response = self.http.get(
                url, timeout=min(PAGE_POLICY.timeout_seconds, remaining),
                headers={"Range": f"bytes={start}-{end}", "Accept": "application/pdf,*/*;q=0.1"},
                stream=True,
            )
            self._last_request_at = self.clock()
        except requests.RequestException as exc:
            return None, f"Request failed: {exc}"
        bad_host = _redirect_chain_hosts_allowed(response, DOCUMENT_HOST)
        if bad_host:
            response.close()
            return None, f"Redirected off the allowed document host to '{bad_host}' -- not followed."
        if response.status_code in BLOCKED_STATUS:
            response.close()
            return None, f"HTTP {response.status_code} -- access blocked, not retried."
        data = response.content[:DOCUMENT_CHUNK_BYTES + 1024]
        return {
            "status_code": response.status_code,
            "bytes": data,
            "content_range": response.headers.get("Content-Range", ""),
            "content_length": response.headers.get("Content-Length"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }, None

    def fetch_document_bounded(self, url: str, *, deadline: float) -> tuple[bytes | None, str]:
        """Bounded, Range-aware fetch. Returns (assembled_bytes_or_None, completeness_reason)."""
        if _host_of(url) != DOCUMENT_HOST:
            return None, f"Configured URL host '{_host_of(url)}' is not the allowed document host '{DOCUMENT_HOST}'."
        first, err = self._single_range_request(url, 0, DOCUMENT_CHUNK_BYTES - 1, deadline=deadline)
        if first is None:
            return None, f"unknown_completeness: {err}"
        match = _CONTENT_RANGE_RE.match(first["content_range"] or "")
        if first["status_code"] == 206 and match:
            start, end, total = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if total > DOCUMENT_MAX_TOTAL_BYTES:
                return None, f"unknown_completeness: total_size_{total}_exceeds_cap_{DOCUMENT_MAX_TOTAL_BYTES}"
            parts = [(start, end, first["bytes"])]
            ref_etag, ref_lm = first["etag"], first["last_modified"]
            next_start = end + 1
            while next_start < total:
                next_end = min(next_start + DOCUMENT_CHUNK_BYTES - 1, total - 1)
                part, perr = self._single_range_request(url, next_start, next_end, deadline=deadline)
                if part is None:
                    return b"".join(p[2] for p in parts), f"partial: {perr}"
                pm = _CONTENT_RANGE_RE.match(part["content_range"] or "")
                if part["status_code"] != 206 or not pm:
                    return b"".join(p[2] for p in parts), "partial: server_stopped_honoring_range"
                p_start, p_end, p_total = int(pm.group(1)), int(pm.group(2)), int(pm.group(3))
                if p_total != total or (ref_etag and part["etag"] and part["etag"] != ref_etag) or \
                   (ref_lm and part["last_modified"] and part["last_modified"] != ref_lm):
                    return None, "unknown_completeness: version_mismatch_between_parts"
                parts.append((p_start, p_end, part["bytes"]))
                next_start = p_end + 1
            assembled = b"".join(p[2] for p in sorted(parts, key=lambda x: x[0]))
            if len(assembled) == total:
                return assembled, "complete"
            return assembled, "partial: assembled_size_mismatch"
        # Range not honored -- do not attempt an unbounded fallback download.
        content_length = first.get("content_length")
        if first["status_code"] == 200 and content_length and content_length.isdigit():
            total = int(content_length)
            if total > DOCUMENT_MAX_TOTAL_BYTES:
                return None, f"unknown_completeness: range_unsupported_and_content_length_{total}_exceeds_cap"
            if len(first["bytes"]) == total:
                return first["bytes"], "complete"
        return None, "unknown_completeness: range_unsupported_and_no_reliable_content_length"

    def find_documents(
        self, search_code: str, *, model_tokens: list[str], deadline: float,
        conflicting_model_tokens: list[str] = (), conflicting_codes: list[str] = (),
    ) -> tuple[list[dict], str]:
        """Fetch and content-verify the known document for search_code, if any.

        Returns (accepted_documents, reason). accepted_documents is empty
        (never partially trusted) unless verify_document() accepts the text.
        """
        normalized = (search_code or "").strip().upper()
        if normalized in self._requested_missing and "инструкция" not in self._requested_missing[normalized]:
            return [], "DNS document not needed: the official/manual stage already filled the requested instruction field."
        if normalized not in self._confirmed_codes:
            return [], "DNS document not checked: the product page's 'Код производителя' has not confirmed this exact catalog article."
        url = self.document_urls.get(normalized, "")
        if not url:
            return [], "No pre-verified DNS document candidate for this search code."
        data, completeness = self.fetch_document_bounded(url, deadline=deadline)
        if data is None:
            return [], f"Document fetch failed ({completeness})."
        if not completeness.startswith("complete"):
            return [], f"Document fetch incomplete ({completeness}); not verified or accepted."
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            return [], f"PDF parsing failed: {exc}"
        verification = verify_document(
            text, expected_model_tokens=model_tokens, expected_code=normalized,
            conflicting_model_tokens=conflicting_model_tokens, conflicting_codes=conflicting_codes,
        )
        if not verification.accepted:
            return [], (
                f"Document rejected: {verification.document_type} -- {verification.reason}"
            )
        document = {
            "title": clean_text(f"{self.site_name} document ({verification.document_type})"),
            "language": _document_language_label(verification.languages),
            "direct_url": url,
            "source_url": self.urls.get(normalized, url),
            "product_model": normalized,
            "support_model": normalized,
            "relation_url": url,
            "primary": False,
            "document_type": "manufacturer_manual_dealer_hosted",
            "verification": verification,
        }
        return [document], verification.reason
