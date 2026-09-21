"""LG Kazakhstan official adapter with LG-specific SKU normalization."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Callable
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

from .common import (
    BudgetExceeded, RawAttribute, SourceDocument, SourceError, clean_text,
    fetch_with_retry, meta_description,
)


LG_KZ_SITEMAP = "https://www.lg.com/kz/sitemap.xml"
OFFICIAL_BUDGET_SECONDS = 20
MAX_CANDIDATES = 3


class LGSourceError(SourceError):
    pass


@dataclass(frozen=True)
class ProductPage:
    url: str
    soup: BeautifulSoup
    sku: str = ""


@dataclass(frozen=True)
class LookupResult:
    status: str
    page_url: str
    candidate_urls: tuple[str, ...]
    message: str


def lg_session() -> requests.Session:
    http = requests.Session()
    http.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    })
    return http


def normalize_lg_sku(value: str) -> str:
    """LG-only normalization. Other brands must define their own rules."""
    return re.sub(r"\s+", "", str(value or "")).upper()


def lg_base_model(full_sku: str) -> str:
    normalized = normalize_lg_sku(full_sku)
    base, dot, suffix = normalized.rpartition(".")
    if dot and base and re.fullmatch(r"[A-Z]{5,}", suffix):
        return base
    return normalized


def lg_article_key(article: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_lg_sku(article).lower())


def lg_article_lookup_keys(article: str) -> list[str]:
    full = lg_article_key(article)
    base = lg_article_key(lg_base_model(article))
    return list(dict.fromkeys(key for key in (full, base) if key))


def lg_is_product_url(url: str) -> bool:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.lower().split("/") if part]
    return (
        parsed.scheme == "https" and parsed.netloc.lower() == "www.lg.com"
        and len(parts) >= 4 and parts[0] == "kz"
        and not any(part in {"support", "lg-magazine", "search", "sitemap"} for part in parts)
    )


def _slug_key(url: str) -> str:
    return lg_article_key(unquote(urlparse(url).path.rstrip("/").split("/")[-1]))


def lg_url_matches_article(url: str, article: str) -> bool:
    return lg_is_product_url(url) and _slug_key(url) in lg_article_lookup_keys(article)


def _visible_text(soup: BeautifulSoup) -> str:
    copy = BeautifulSoup(str(soup), "html.parser")
    for tag in copy.select("script, style, template, noscript"):
        tag.decompose()
    return clean_text(copy.get_text(" ", strip=True))


def _designation(text: str, full_sku: str, base_model: str) -> tuple[str, str, str]:
    full_pattern = re.compile(rf"(?<![\w]){re.escape(full_sku)}(?![\w])", re.I)
    base_pattern = re.compile(rf"(?<![\w]){re.escape(base_model)}(?![\w])", re.I)
    full = full_pattern.search(text)
    if full:
        excerpt = text[max(0, full.start() - 90):min(len(text), full.end() + 90)]
        return full_sku, "full_sku", clean_text(excerpt)
    base = base_pattern.search(text)
    if base:
        excerpt = text[max(0, base.start() - 90):min(len(text), base.end() + 90)]
        return base_model, "base_model", clean_text(excerpt)
    return "", "unknown", "Обозначение модели не найдено в видимом тексте страницы."


def extract_lg_attributes(soup: BeautifulSoup) -> list[RawAttribute]:
    attributes: list[RawAttribute] = []
    seen: set[tuple[str, str]] = set()
    for item in soup.select("#pdp-specs-section .c-compare-selling--all .c-compare-selling__item"):
        name_tag = item.select_one(".c-compare-selling__spec-name")
        value_tag = item.select_one(".c-compare-selling__spec-desc")
        if not name_tag or not value_tag:
            continue
        name = clean_text(name_tag.get_text(" ", strip=True))
        value = clean_text(value_tag.get_text(" ", strip=True))
        if not name or not value:
            continue
        if name in {fact.name for fact in attributes}:
            table = item.find_parent(class_="c-compare-selling__table")
            group = table.select_one(".c-compare-selling__table-head") if table else None
            if group:
                name = f"{name} ({clean_text(group.get_text(' ', strip=True))})"
        key = (name, value)
        if key not in seen:
            seen.add(key)
            attributes.append(RawAttribute(name, value))
    return attributes


def extract_lg_description(soup: BeautifulSoup) -> str:
    overview = soup.select_one("#pdp-overview-section")
    if overview:
        content = BeautifulSoup(str(overview), "html.parser")
        for tag in content.select("script, style, template, nav, button"):
            tag.decompose()
        description = "\n".join(
            clean_text(text) for text in content.stripped_strings if clean_text(text)
        )
        if description:
            return description
    return meta_description(soup)


def extract_lg_photos(soup: BeautifulSoup, page_url: str) -> list[str]:
    photos: list[str] = []
    selectors = (
        "#popSummaryGallery #tabpanel-image .c-gallery__display img",
        ".c-summary-gallery #tabpanel-image .c-gallery__display img",
    )
    for selector in selectors:
        for img in soup.select(selector):
            raw = img.get("src") or img.get("data-src") or ""
            url = urljoin(page_url, raw).split("?", 1)[0]
            if raw and url.startswith("https://www.lg.com/content/dam/") and url not in photos:
                photos.append(url)
        if photos:
            break
    if not photos:
        cover = soup.select_one('meta[property="og:image"]')
        raw = cover.get("content") if cover else ""
        url = urljoin(page_url, raw).split("?", 1)[0]
        if raw and url.startswith("https://www.lg.com/content/dam/"):
            photos.append(url)
    return photos


class LGAdapter:
    source_key = "lg"
    site_name = "LG Казахстан"

    def __init__(
        self,
        http: requests.Session | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.http = http or lg_session()
        self.clock = clock
        self.request_count = 0

    def _get(self, url: str, deadline: float) -> requests.Response:
        self.request_count += 1
        try:
            return fetch_with_retry(self.http, url, deadline=deadline, clock=self.clock)
        except (SourceError, BudgetExceeded) as exc:
            raise LGSourceError(str(exc)) from exc

    def sitemap_product_urls(self, deadline: float) -> list[str]:
        response = self._get(LG_KZ_SITEMAP, deadline)
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise LGSourceError(f"Некорректный LG sitemap: {exc}") from exc
        urls = [
            (node.text or "").strip() for node in root.iter()
            if (node.tag.endswith("}loc") or node.tag == "loc")
            and lg_is_product_url((node.text or "").strip())
        ]
        if not urls:
            raise LGSourceError("LG sitemap не содержит товарных страниц.")
        return urls

    def fetch_page(self, url: str, deadline: float | None = None) -> ProductPage:
        if not lg_is_product_url(url):
            raise LGSourceError("Адрес не является товарной страницей LG Казахстан.")
        deadline = deadline if deadline is not None else self.clock() + 10
        response = self._get(url, deadline)
        if not lg_is_product_url(response.url):
            raise LGSourceError("LG перенаправил запрос вне товарной страницы Казахстана.")
        soup = BeautifulSoup(response.text, "html.parser")
        if not soup.select_one("h1") or not soup.select_one(
            "#pdp-specs-section, #pdp-overview-section"
        ):
            raise LGSourceError("LG не вернул ожидаемую карточку товара.")
        return ProductPage(response.url, soup)

    def _document(self, page: ProductPage, full_sku: str, base_model: str) -> SourceDocument:
        found, level, evidence = _designation(_visible_text(page.soup), full_sku, base_model)
        return SourceDocument(
            self.source_key, self.site_name, page.url,
            found_model=found, match_level=level, evidence=evidence,
            attributes=extract_lg_attributes(page.soup),
            description=extract_lg_description(page.soup),
            photos=extract_lg_photos(page.soup, page.url),
        )

    def find_source(self, full_sku: str, *, deadline: float) -> SourceDocument:
        start = self.clock()
        official_deadline = min(deadline, start + OFFICIAL_BUDGET_SECONDS)
        normalized = normalize_lg_sku(full_sku)
        base = lg_base_model(normalized)
        try:
            urls = self.sitemap_product_urls(official_deadline)
            # Exact public slug first. Stop immediately on a confirmed page.
            exact_key = lg_article_key(normalized)
            exact_urls = [url for url in urls if _slug_key(url) == exact_key][:MAX_CANDIDATES]
            for url in exact_urls:
                document = self._document(self.fetch_page(url, official_deadline), normalized, base)
                if document.match_level == "full_sku":
                    return document
            # Then the LG-specific base model. Stop after the first valid base page.
            base_key = lg_article_key(base)
            base_urls = [url for url in urls if _slug_key(url) == base_key][:MAX_CANDIDATES]
            for url in base_urls:
                document = self._document(self.fetch_page(url, official_deadline), normalized, base)
                if document.match_level in {"full_sku", "base_model"}:
                    return document
            return SourceDocument(
                self.source_key, self.site_name, "",
                match_level="mismatch",
                evidence="В LG sitemap не найдена страница полного артикула или базовой модели.",
            )
        except LGSourceError as exc:
            return SourceDocument(
                self.source_key, self.site_name, "",
                match_level="unknown", evidence="", error=str(exc),
            )

    # Compatibility for the previous worker API.
    def find_page(self, article: str) -> LookupResult:
        document = self.find_source(article, deadline=self.clock() + OFFICIAL_BUDGET_SECONDS)
        if document.match_level == "full_sku":
            return LookupResult("exact", document.url, (document.url,), "Полный артикул найден на LG.")
        if document.match_level == "base_model":
            return LookupResult("needs_review", document.url, (document.url,), "На LG найдена базовая модель.")
        if document.error:
            raise LGSourceError(document.error)
        return LookupResult("not_found", "", (), "Источники LG не найдены за отведённое время.")

    def extract_description(self, soup: BeautifulSoup) -> str:
        return extract_lg_description(soup)

    def extract_attributes(self, soup: BeautifulSoup) -> list[RawAttribute]:
        return extract_lg_attributes(soup)

    def extract_photos(self, soup: BeautifulSoup, page_url: str) -> list[str]:
        return extract_lg_photos(soup, page_url)