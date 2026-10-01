"""Exact-content verification of official LG product candidates outside KZ/RU.

A search result is ranking-only evidence. This adapter uses the existing LG
extractors only after opening an official product page and checking its own
primary product identity. A base-model page stays base-only for suffixed SKUs.
"""
from __future__ import annotations

import json
import re
import time
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .common import SourceDocument, SourceError, clean_text, fetch_with_retry
from .lg import (extract_lg_attributes, extract_lg_ru_attributes,
                 extract_lg_description, extract_lg_photo_candidates,
                 extract_lg_ru_description, lg_article_components,
                 lg_article_key, lg_base_model, normalize_lg_sku, _slug_key)
from ..lg_identity import structured_sales_relation


REGION = re.compile(r"[a-z]{2}(?:-[a-z]{2})?")
EXCLUDED = frozenset({"support", "search", "sitemap", "news", "blog", "lg-magazine"})


def official_product_url(url: str) -> bool:
    parsed = urlsplit(url)
    parts = [part.lower() for part in parsed.path.split("/") if part]
    return (parsed.scheme == "https" and (parsed.hostname or "").casefold() == "www.lg.com"
            and len(parts) >= 3 and bool(REGION.fullmatch(parts[0]))
            and not any(part in EXCLUDED for part in parts))


def _primary_codes(soup: BeautifulSoup) -> list[tuple[str, str]]:
    codes = []
    for node in soup.select(".price-area__PD0033[data-analytics]"):
        try:
            value = json.loads(node.get("data-analytics", "{}")).get("data-pim-sku", "")
        except (TypeError, ValueError):
            value = ""
        if value:
            codes.append((str(value), "data-pim-sku"))
    for node in soup.select(".GPC0009[data-adobe-salesmodelcode]"):
        model = node.get("data-adobe-salesmodelcode", "")
        suffix = node.get("data-adobe-salessuffixcode", "")
        if model:
            codes.append((model + ("." + suffix if suffix else ""), "data-adobe-salesmodelcode"))
    return codes


def _own_model(soup: BeautifulSoup, url: str, article: str) -> tuple[str, str, str]:
    requested = normalize_lg_sku(article)
    base = lg_base_model(requested)
    codes = _primary_codes(soup)
    if len(lg_article_components(requested)) > 1:
        headings = [clean_text(h.get_text(" ", strip=True)) for h in soup.select("h1")]
        if _slug_key(url) == lg_article_key(base) and any(base.casefold() in h.casefold() for h in headings):
            return base, "base_model", "A product page for the base model does not establish the full kit."
        return "", "unknown", "The opened page does not establish the requested kit."
    relations = [structured_sales_relation(requested, code) for code, _ in codes]
    if codes:
        if relations and all(relation == "exact" for relation in relations):
            return requested, "full_sku", "Main product sales code: " + "; ".join(f"{field}={code}" for code, field in codes)
        if any(relation in {"family_of", "regional_variant_of"} for relation in relations):
            return base, "base_model", "Main product code names only a family or another variant: " + "; ".join(code for code, _ in codes)
        return "", "unknown", "Main product code belongs to a different model: " + "; ".join(code for code, _ in codes)
    # With no variant in the requested catalog row, a page's own H1 and slug
    # can establish that model. Related-product tiles and search labels cannot.
    headings = [clean_text(h.get_text(" ", strip=True)) for h in soup.select("h1")]
    exact_heading = any(re.search(r"(?<![A-Za-z0-9])" + re.escape(requested) + r"(?![A-Za-z0-9])", h, re.I)
                        for h in headings)
    if requested == base and _slug_key(url) == lg_article_key(requested) and exact_heading:
        return requested, "full_sku", "Main product H1 and official page slug name the catalog model: " + headings[0]
    if _slug_key(url) == lg_article_key(base) and any(base.casefold() in h.casefold() for h in headings):
        return base, "base_model", "Official product H1 and slug name only the base model."
    return "", "unknown", "The opened product page does not print the requested model as its own product."


class LGGlobalAdapter:
    source_key = "lg_global"

    def __init__(self, http, *, clock=time.monotonic):
        self.http = http
        self.clock = clock

    def fetch_candidate(self, url: str, article: str, *, deadline: float) -> SourceDocument:
        if not official_product_url(url):
            return SourceDocument(self.source_key, "LG other official region", url,
                                  match_level="unknown", evidence="Not an official LG product URL.")
        try:
            response = fetch_with_retry(self.http, url, deadline=deadline, clock=self.clock)
        except SourceError as exc:
            return SourceDocument(self.source_key, "LG other official region", url, error=str(exc))
        if not official_product_url(response.url):
            return SourceDocument(self.source_key, "LG other official region", response.url,
                                  match_level="unknown", evidence="Redirected away from an official LG product page.")
        soup = BeautifulSoup(response.text, "html.parser")
        region = [part for part in urlsplit(response.url).path.split("/") if part][0].upper()
        site_name = "LG " + region
        found, level, evidence = _own_model(soup, response.url, article)
        if level not in {"full_sku", "base_model"}:
            return SourceDocument(self.source_key, site_name, response.url,
                                  found_model=found, match_level=level, evidence=evidence, html=response.text)
        facts = extract_lg_attributes(soup) or extract_lg_ru_attributes(soup)
        photos = extract_lg_photo_candidates(soup, response.url, region="global")
        description = extract_lg_description(soup) or extract_lg_ru_description(soup)
        return SourceDocument(self.source_key, site_name, response.url,
                              found_model=found, match_level=level, evidence=evidence,
                              attributes=facts, description=description,
                              photos=[p.url for p in photos if p.kind == "product_gallery"],
                              photo_candidates=photos, html=response.text)
