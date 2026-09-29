"""Sulpak trusted fallback adapter for LG full SKU confirmation."""

from __future__ import annotations

import time
import json
from urllib.parse import urlsplit
from typing import Callable

from bs4 import BeautifulSoup
import requests

from .common import SourceDocument, SourceError, fetch_with_retry, meta_description
from .supplier import extract_photo_candidates, extract_table_attributes, find_full_sku, visible_text


KNOWN_LG_URLS = {
    "S3WER.ALWPCOM": "https://www.sulpak.kz/g/parovoj_shkaf_lg_styler_s3wer_alwpcom",
    # Owner-provided exact two-unit kit URL. Its slug names both components,
    # but the adapter must still verify them in page content before accepting facts.
    "P12ED.NSAR + P12ED.USAR": "https://www.sulpak.kz/g/kondicioneriy_split_sistemiy_lg_p12ednsar___p12edusar",
}


def _stopped_host_evidence(http, candidate_url: str) -> str:
    """Explain a persisted host stop without claiming the candidate was fetched."""
    log_path = getattr(http, "log_path", None)
    if log_path:
        try:
            events = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            events = []
        host = urlsplit(candidate_url).hostname
        for event in reversed(events):
            observed = event.get("url", "")
            if urlsplit(observed).hostname != host:
                continue
            status = event.get("status_code")
            protection = event.get("protection_status")
            if status not in (401, 403, 429) and protection != "challenge_confirmed":
                continue
            date = str(event.get("checked_at", ""))[:10]
            response = f"HTTP {status} со страницей проверки" if status == 200 else f"HTTP {status}"
            source_name = next((sku for sku, known in KNOWN_LG_URLS.items() if known == observed), "")
            other = f"другая страница Sulpak ({source_name}) " if observed != candidate_url else "эта страница Sulpak "
            return (f"{date}: {other}{observed} вернула {response}; после этого автоматические запросы к Sulpak остановлены. "
                    f"Запрос к кандидату {candidate_url} не отправлялся. Его адрес и текст поисковой выдачи не подтверждают состав товара.")
    return f"Запрос к кандидату {candidate_url} не отправлялся: Sulpak ранее остановлен политикой доступа. Адрес и текст выдачи не подтверждают состав товара."


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
        url = next((candidate for key, candidate in self.urls.items() if "".join(key.split()).upper() == "".join(normalized.split()).upper()), "")
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
            # A two-unit kit may be named only in the URL while the page body
            # says the shared model. The URL is a lead, not proof of the kit.
            unconfirmed_kit = "+" in normalized and not found
            level = "full_sku" if found else ("unknown" if unconfirmed_kit or not text else "mismatch")
            photos = extract_photo_candidates(soup, response.url, source_key=self.source_key) if found else []
            return SourceDocument(
                self.source_key, self.site_name, response.url,
                found_model=found, match_level=level,
                evidence=evidence or ("Оба кода есть в адресе кандидата, но полный состав комплекта не подтверждён текстом страницы." if unconfirmed_kit else "Полный артикул не найден в видимом тексте страницы."),
                attributes=extract_table_attributes(soup) if found else [],
                description=meta_description(soup) if found else "",
                photos=[item.url for item in photos if item.kind != "excluded"],
                photo_candidates=photos,
            )
        except SourceError as exc:
            return SourceDocument(
                self.source_key, self.site_name, url,
                match_level="unknown", error="policy_host_stopped: candidate page not requested" if "policy_host_stopped" in str(exc) else str(exc),
                evidence=_stopped_host_evidence(self.http, url) if "policy_host_stopped" in str(exc) else
                         ("????? ????????? ?? ???????????? ?????? ?????? ??? ??????????? ????????." if "+" in normalized else ""),
            )
