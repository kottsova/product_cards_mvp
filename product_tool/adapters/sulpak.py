"""Sulpak trusted fallback adapter for LG full SKU confirmation."""

from __future__ import annotations

import time
from typing import Callable

from bs4 import BeautifulSoup
import requests

from .common import SourceDocument, SourceError, fetch_with_retry, meta_description
from .supplier import extract_photos, extract_table_attributes, find_full_sku, visible_text


KNOWN_LG_URLS = {
    "S3WER.ALWPCOM": "https://www.sulpak.kz/g/parovoj_shkaf_lg_styler_s3wer_alwpcom",
}


class SulpakAdapter:
    source_key = "sulpak"
    site_name = "Sulpak"

    def __init__(
        self, http: requests.Session | None = None, *,
        clock: Callable[[], float] = time.monotonic,
        urls: dict[str, str] | None = None,
    ):
        self.http = http or requests.Session()
        self.http.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "ru-RU,ru;q=0.9"})
        self.clock = clock
        self.urls = urls or KNOWN_LG_URLS
        self.request_count = 0

    def find_source(self, full_sku: str, *, deadline: float) -> SourceDocument:
        normalized = full_sku.strip().upper()
        url = self.urls.get(normalized, "")
        if not url:
            return SourceDocument(
                self.source_key, self.site_name, "", match_level="unknown",
                evidence="Для полного артикула нет ограниченного кандидата Sulpak.",
            )
        try:
            self.request_count += 1
            response = fetch_with_retry(self.http, url, deadline=deadline, clock=self.clock)
            soup = BeautifulSoup(response.text, "html.parser")
            text = visible_text(soup)
            found, evidence = find_full_sku(text, normalized)
            level = "full_sku" if found else ("mismatch" if text else "unknown")
            return SourceDocument(
                self.source_key, self.site_name, response.url,
                found_model=found, match_level=level,
                evidence=evidence or "Полный артикул не найден в видимом тексте страницы.",
                attributes=extract_table_attributes(soup),
                description=meta_description(soup),
                photos=extract_photos(soup, response.url),
            )
        except SourceError as exc:
            return SourceDocument(
                self.source_key, self.site_name, url,
                match_level="unknown", error=str(exc),
            )