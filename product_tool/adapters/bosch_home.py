"""Narrow Bosch Home KZ adapter for the two Stage 35 verified catalog rows.

No URL discovery. A category/model pair must be selected in the local manifest
before an HTTP client is used. Page identity comes from JSON-LD Product.mpn,
not its URL. The catalog has no E-Nr for these rows; revision stays unknown.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from .common import PhotoCandidate, ProductDocument, RawAttribute, SourceDocument, SourceError, fetch_with_retry
from .policy_session import PolicyAwareSession
from .structured_page import extract_json_ld_product

MANIFEST = Path(__file__).resolve().parents[1] / "config" / "bosch_home_verified.v1.json"
ALLOWED_HOSTS = ("www.bosch-home.com",)
SOURCE_KEY = "bosch_home"
SITE_NAME = "Bosch Home Kazakhstan"


def verified_pages() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported Bosch Home verified-page manifest")
    return data["pages"]


def selected_page(code: str, category: str) -> dict | None:
    record = verified_pages().get((code or "").strip().upper())
    if record and (category or "").strip().casefold() == record["category"].casefold():
        return record
    return None


def _asset_key(url: str) -> str:
    stem = Path(urlsplit(url).path).stem
    return re.sub(r"(?i)(?:_(?:def|highres|\d{2,4}x\d{2,4}|w\d+))+$", "", stem).casefold()


def _exact_photo_code(url: str, code: str) -> bool:
    filename = Path(urlsplit(url).path).name
    return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(code) + r"(?![A-Za-z0-9])", filename, re.I))


def parse_page(html: str, url: str, code: str, category: str) -> tuple[SourceDocument, dict]:
    record = selected_page(code, category)
    document = SourceDocument(SOURCE_KEY, SITE_NAME, url, html=html)
    report = {"code": code, "category": category, "page_url": url, "model_confirmed": False,
              "catalog_revision": None, "page_enr": None, "revision_status": "unknown",
              "gtin": None, "photo_selected": [], "photo_excluded": [], "manual_links": []}
    if not record or url != record["page_url"]:
        document.error = "Bosch KZ: category/model or observed URL is outside the two verified rows."
        return document, report
    fields = extract_json_ld_product(html, url)
    mpn = [f.value.strip().upper() for f in fields if f.name == "mpn"]
    gtins = [f.value.strip() for f in fields if f.name in ("gtin", "gtin13")]
    if mpn != [code] or record["gtin"] not in gtins:
        document.found_model = ", ".join(mpn)
        document.match_level = "mismatch"
        document.error = "Bosch KZ: Product.mpn or GTIN differs from the verified catalog model page."
        return document, report
    # An E-Nr revision is only confirmed when the full code is printed as the
    # product's own value. This page/catalog pair supplies no such number.
    report["model_confirmed"] = True
    report["gtin"] = record["gtin"]
    document.found_model = code
    document.match_level = "full_sku"
    document.evidence = f"KZ JSON-LD Product.mpn={code}; gtin={record['gtin']}; catalog E-Nr absent, revision unknown."
    specs = [f for f in fields if f.name not in
             {"name", "sku", "productID", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn", "json_ld_image"}]
    # Bosch also publishes long marketing paragraphs as additionalProperty.
    # They are not atomic technical facts: generic normalization can read a
    # nearby number (for example 30 seconds) as a different RPM value.
    technical = [f for f in specs if len(f.name) <= 80 and not f.name.rstrip().endswith((".", ":"))]
    report["marketing_properties_not_normalized"] = [{"name": f.name, "value": f.value} for f in specs if f not in technical]
    document.attributes = [RawAttribute(f.name, f.value) for f in technical]
    soup = BeautifulSoup(html, "html.parser")
    description = soup.select_one('meta[name="description"],meta[property="og:description"]')
    document.description = (description.get("content", "") if description else "").strip()
    seen: set[str] = set()
    for field in fields:
        if field.name != "json_ld_image":
            continue
        photo_url = field.value
        key = _asset_key(photo_url)
        if not _exact_photo_code(photo_url, code):
            report["photo_excluded"].append({"url": photo_url, "reason": "another_variant_or_shared_set"})
            continue
        if key in seen:
            report["photo_excluded"].append({"url": photo_url, "reason": "size_duplicate"})
            continue
        seen.add(key)
        document.photos.append(photo_url)
        document.photo_candidates.append(PhotoCandidate(photo_url, key))
        report["photo_selected"].append(photo_url)
    decoded = html.replace('\\"', '"').replace('\\/', '/')
    report["manual_links"] = list(dict.fromkeys(re.findall(
        r'"titleKey":"user-manuals"[^{}]{0,240}?"url":"(https://media3\.bsh-group\.com/Documents/[^" ]+?\.pdf)"',
        decoded, re.I)))
    return document, report


class BoschHomeAdapter:
    source_key = SOURCE_KEY
    site_name = SITE_NAME

    def __init__(self, http=None, *, clock: Callable[[], float] = time.monotonic,
                 fetch_log_path: Path | None = None):
        self.clock = clock
        self.http = http or PolicyAwareSession(
            fetch_log_path or Path("bosch_home_fetch_log.json"), allowed_hosts=ALLOWED_HOSTS,
            underlying=requests.Session(), clock=clock, max_bytes=25_000_000,
            min_interval_seconds=1.5)
        self.reports: dict[str, dict] = {}

    def find_source(self, code: str, *, category: str, deadline: float) -> SourceDocument:
        code = (code or "").strip().upper()
        record = selected_page(code, category)
        if record is None:
            return SourceDocument(SOURCE_KEY, SITE_NAME, "", error="Bosch row is not one of the two selected category/model pairs.")
        url = record["page_url"]
        try:
            response = fetch_with_retry(self.http, url, deadline=deadline, clock=self.clock)
        except SourceError as exc:
            return SourceDocument(SOURCE_KEY, SITE_NAME, url, error=str(exc))
        if response.url != url or getattr(response, "truncated", False):
            return SourceDocument(SOURCE_KEY, SITE_NAME, response.url, error="Bosch KZ page redirected or truncated.")
        document, report = parse_page(response.text, response.url, code, category)
        self.reports[code] = report
        return document

    def find_documents(self, document: SourceDocument, code: str) -> list[ProductDocument]:
        if document.error or document.match_level != "full_sku":
            return []
        record = verified_pages().get(code)
        report = self.reports.get(code, {})
        manual = record["manual"] if record else None
        if not manual or manual["url"] not in report.get("manual_links", []):
            return []
        family = manual["family"]
        title = f"\u0420\u0443\u0441\u0441\u043a\u043e\u0435 \u0440\u0443\u043a\u043e\u0432\u043e\u0434\u0441\u0442\u0432\u043e \u0441\u0435\u043c\u0435\u0439\u0441\u0442\u0432\u0430 {family}; {code} \u0432 PDF \u043d\u0435 \u043d\u0430\u0437\u0432\u0430\u043d"
        return [ProductDocument(title=title, language=manual["language"], document_date="", size="",
                                direct_url=manual["url"], source_url=document.url, product_model=code,
                                support_model=family, relation_url=document.url, primary=True)]
