"""Shared source adapter primitives with bounded HTTP retries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Callable

from bs4 import BeautifulSoup
import requests

REQUEST_TIMEOUT = 10
MAX_RETRIES = 1
TRANSIENT = (requests.Timeout, requests.ConnectionError)
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RawAttribute:
    name: str
    value: str


@dataclass(frozen=True)
class PhotoCandidate:
    url: str
    asset_key: str
    kind: str = "product_gallery"
    width: int | None = None
    height: int | None = None
    excluded_reason: str = ""


@dataclass(frozen=True)
class ProductDocument:
    title: str
    language: str
    document_date: str
    size: str
    direct_url: str
    source_url: str
    product_model: str
    support_model: str
    relation_url: str
    primary: bool = False


@dataclass
class SourceDocument:
    source_key: str
    site_name: str
    url: str
    found_model: str = ""
    match_level: str = "unknown"
    evidence: str = ""
    fetched_at: str = field(default_factory=utc_now)
    error: str = ""
    attributes: list[RawAttribute] = field(default_factory=list)
    description: str = ""
    photos: list[str] = field(default_factory=list)
    photo_candidates: list[PhotoCandidate] = field(default_factory=list)
    html: str = ""


class SourceError(RuntimeError):
    pass


class BudgetExceeded(SourceError):
    pass


def fetch_with_retry(session, url: str, *, deadline: float, clock: Callable[[], float] = time.monotonic, timeout: float = REQUEST_TIMEOUT):
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            raise BudgetExceeded("Исчерпан бюджет времени источника.")
        request_timeout = min(timeout, remaining, REQUEST_TIMEOUT)
        try:
            response = session.get(url, timeout=request_timeout)
            if response.status_code in TRANSIENT_STATUS and attempt < MAX_RETRIES:
                last_error = requests.HTTPError(f"HTTP {response.status_code}")
                continue
            response.raise_for_status()
            return response
        except TRANSIENT as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
        except requests.RequestException as exc:
            raise SourceError(f"HTTP-ошибка: {exc}") from exc
    raise SourceError(f"Источник недоступен после повторной попытки: {last_error}")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def meta_description(soup: BeautifulSoup) -> str:
    tag = soup.select_one('meta[property="og:description"], meta[name="description"]')
    return clean_text(tag.get("content", "")) if tag else ""