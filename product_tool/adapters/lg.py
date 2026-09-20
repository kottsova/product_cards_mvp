"""LG Kazakhstan adapter, adapted from the original parser's modes 6–9.

The sitemap lookup, page validation, and extraction selectors come from the
working LG routines. This module has no spreadsheet or credential dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests


LG_KZ_SITEMAP = "https://www.lg.com/kz/sitemap.xml"
PRODUCT_TIMEOUT = 25
SITEMAP_TIMEOUT = 30


class LGSourceError(RuntimeError):
    """The official source could not be read reliably."""


@dataclass(frozen=True)
class ProductPage:
    url: str
    soup: BeautifulSoup
    sku: str


@dataclass(frozen=True)
class LookupResult:
    status: str  # exact, needs_review, not_found
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


def lg_is_product_url(url: str) -> bool:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.lower().split("/") if part]
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "www.lg.com"
        and len(parts) >= 4
        and parts[0] == "kz"
        and not any(part in {"support", "lg-magazine", "search", "sitemap"} for part in parts)
    )


def lg_article_key(article: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(article).lower())


def lg_article_lookup_keys(article: str) -> list[str]:
    keys = [lg_article_key(article)]
    # Regional sales suffixes can be absent from a public product URL.
    # Keep the full code for page-SKU verification before accepting a fallback.
    base, dot, suffix = str(article).rpartition(".")
    if dot and re.fullmatch(r"[A-Za-z]{5,}", suffix):
        keys.append(lg_article_key(base))
    return [key for key in dict.fromkeys(keys) if key]


def lg_url_matches_article(url: str, article: str) -> bool:
    """Original candidate rule; a base-only match still needs SKU verification."""
    if not lg_is_product_url(url):
        return False
    slug = unquote(urlparse(url).path.rstrip("/").split("/")[-1])
    return lg_article_key(slug) in lg_article_lookup_keys(article)


def _slug_key(url: str) -> str:
    return lg_article_key(unquote(urlparse(url).path.rstrip("/").split("/")[-1]))


def _primary_sku(html: str) -> str:
    # The current LG PDP embeds its own sales SKU in an inline script. The
    # first unescaped sku entry belongs to the page, before Next.js duplicates.
    match = re.search(r'"sku"\s*:\s*[\x60"\']([A-Za-z0-9._-]+)', html, re.I)
    return match.group(1) if match else ""


def _sku_matches(article: str, sku: str) -> bool:
    wanted = article.strip().upper()
    actual = sku.strip().upper()
    if not wanted or not actual.startswith(wanted):
        return False
    return len(actual) == len(wanted) or actual[len(wanted)] in ".-_"


def match_kind(page: ProductPage, article: str) -> str:
    """Return exact, base_only, or mismatch without confusing related models."""
    slug = _slug_key(page.url)
    keys = lg_article_lookup_keys(article)
    if not keys or slug not in keys:
        return "mismatch"
    if page.sku and not _sku_matches(article, page.sku):
        return "base_only" if slug == keys[-1] and len(keys) > 1 else "mismatch"
    if slug == keys[0]:
        return "exact"
    return "exact" if _sku_matches(article, page.sku) else "base_only"


def extract_lg_attributes(soup: BeautifulSoup) -> dict[str, str]:
    attributes: dict[str, str] = {}
    # The full specification panel is in HTML even when visually collapsed.
    for item in soup.select("#pdp-specs-section .c-compare-selling--all .c-compare-selling__item"):
        name_tag = item.select_one(".c-compare-selling__spec-name")
        value_tag = item.select_one(".c-compare-selling__spec-desc")
        if not name_tag or not value_tag:
            continue
        name = re.sub(r"\s+", " ", name_tag.get_text(" ", strip=True)).strip()
        value = re.sub(r"\s+", " ", value_tag.get_text(" ", strip=True)).strip()
        if not name or not value or re.search(r"(?<!\w)нет(?!\w)", value, re.I):
            continue
        if name in attributes:
            if attributes[name] == value:
                continue
            table = item.find_parent(class_="c-compare-selling__table")
            group = table.select_one(".c-compare-selling__table-head") if table else None
            if group:
                name = f"{name} ({group.get_text(' ', strip=True)})"
        if name not in attributes:
            attributes[name] = value
    return attributes


def extract_lg_description(soup: BeautifulSoup) -> str:
    overview = soup.select_one("#pdp-overview-section")
    if overview:
        content = BeautifulSoup(str(overview), "html.parser")
        for tag in content.select("script, style, template, nav, button"):
            tag.decompose()
        lines = [re.sub(r"\s+", " ", text).strip() for text in content.stripped_strings]
        description = "\n".join(line for line in lines if line)
        if description:
            return description
    meta = soup.select_one('meta[property="og:description"], meta[name="description"]')
    return (meta.get("content") or "").strip() if meta else ""


def extract_lg_photos(soup: BeautifulSoup, page_url: str) -> list[str]:
    photos: list[str] = []
    seen: set[str] = set()
    selectors = (
        "#popSummaryGallery #tabpanel-image .c-gallery__display img",
        ".c-summary-gallery #tabpanel-image .c-gallery__display img",
    )
    for selector in selectors:
        for img in soup.select(selector):
            raw = img.get("src") or img.get("data-src") or ""
            url = urljoin(page_url, raw).split("?", 1)[0]
            if not raw or not url.startswith("https://www.lg.com/content/dam/") or url in seen:
                continue
            seen.add(url)
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
    def __init__(self, http: requests.Session | None = None):
        self.http = http or lg_session()

    def sitemap_product_urls(self) -> list[str]:
        try:
            response = self.http.get(LG_KZ_SITEMAP, timeout=SITEMAP_TIMEOUT)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError) as exc:
            raise LGSourceError(f"LG sitemap недоступен: {exc}") from exc
        urls = []
        for node in root.iter():
            if node.tag.endswith("}loc") or node.tag == "loc":
                url = (node.text or "").strip()
                if lg_is_product_url(url):
                    urls.append(url)
        if not urls:
            raise LGSourceError("LG sitemap не содержит товарных страниц.")
        return urls

    def fetch_page(self, url: str) -> ProductPage:
        if not lg_is_product_url(url):
            raise LGSourceError("Адрес не является товарной страницей LG Казахстан.")
        try:
            response = self.http.get(url, timeout=PRODUCT_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LGSourceError(f"Страница LG недоступна: {exc}") from exc
        if not lg_is_product_url(response.url):
            raise LGSourceError("LG перенаправил запрос вне товарной страницы Казахстана.")
        soup = BeautifulSoup(response.text, "html.parser")
        if not soup.select_one("h1") or not soup.select_one(
            "#pdp-specs-section, #pdp-overview-section"
        ):
            raise LGSourceError("LG не вернул ожидаемую карточку товара.")
        return ProductPage(response.url, soup, _primary_sku(response.text))

    def extract_description(self, soup: BeautifulSoup) -> str:
        return extract_lg_description(soup)

    def extract_attributes(self, soup: BeautifulSoup) -> dict[str, str]:
        return extract_lg_attributes(soup)

    def extract_photos(self, soup: BeautifulSoup, page_url: str) -> list[str]:
        return extract_lg_photos(soup, page_url)
    def find_page(self, article: str) -> LookupResult:
        keys = lg_article_lookup_keys(article)
        if not keys:
            return LookupResult("not_found", "", (), "Артикул товара пустой.")
        urls = self.sitemap_product_urls()
        candidates = [
            url for key in keys
            for url in urls
            if _slug_key(url) == key
        ]
        candidates = list(dict.fromkeys(candidates))
        if not candidates:
            return LookupResult(
                "not_found", "", (), "В официальном каталоге LG нет страницы с этим артикулом."
            )

        exact: list[str] = []
        uncertain: list[str] = []
        failures: list[str] = []
        for url in candidates:
            try:
                page = self.fetch_page(url)
            except LGSourceError as exc:
                failures.append(str(exc))
                continue
            kind = match_kind(page, article)
            if kind == "exact":
                exact.append(page.url)
            elif kind == "base_only":
                uncertain.append(page.url)
        if len(exact) == 1:
            return LookupResult("exact", exact[0], tuple(candidates), "Точная карточка LG подтверждена.")
        if len(exact) > 1:
            return LookupResult(
                "needs_review", "", tuple(exact),
                "Найдено несколько точных страниц LG; выберите карточку вручную."
            )
        if uncertain:
            return LookupResult(
                "needs_review", "", tuple(uncertain),
                "Найдена базовая модель, но полный артикул на странице не подтверждён."
            )
        if failures:
            raise LGSourceError("Кандидаты найдены, но LG не дал проверить карточку: " + failures[0])
        return LookupResult(
            "not_found", "", tuple(candidates),
            "Кандидаты LG не совпали с полным артикулом."
        )