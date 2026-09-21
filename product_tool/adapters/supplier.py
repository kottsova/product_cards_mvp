"""Helpers shared only by LG trusted fallback suppliers."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import RawAttribute, clean_text


def visible_text(soup: BeautifulSoup) -> str:
    clone = BeautifulSoup(str(soup), "html.parser")
    for tag in clone.select("script, style, template, noscript"):
        tag.decompose()
    return clean_text(clone.get_text(" ", strip=True))


def find_full_sku(text: str, full_sku: str) -> tuple[str, str]:
    pattern = re.compile(rf"(?<![\w]){re.escape(full_sku)}(?![\w])", re.I)
    match = pattern.search(text)
    if match:
        start = max(0, match.start() - 90)
        end = min(len(text), match.end() + 90)
        return full_sku.upper(), clean_text(text[start:end])
    return "", ""


def extract_table_attributes(soup: BeautifulSoup) -> list[RawAttribute]:
    facts: list[RawAttribute] = []
    seen: set[tuple[str, str]] = set()
    pairs = []
    for row in soup.select("table tr, .characteristics tr, .specifications tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2:
            pairs.append((cells[0].get_text(" ", strip=True), cells[-1].get_text(" ", strip=True)))
    for node in soup.select("dl"):
        terms = node.find_all("dt")
        descriptions = node.find_all("dd")
        pairs.extend((a.get_text(" ", strip=True), b.get_text(" ", strip=True))
                     for a, b in zip(terms, descriptions))
    for item in soup.select(
        ".characteristics__item, .specification-item, .product-characteristics__item, "
        "[class*='characteristic'] [class*='item'], [class*='specification'] [class*='item']"
    ):
        parts = [clean_text(x.get_text(" ", strip=True)) for x in item.find_all(recursive=False)]
        parts = [x for x in parts if x]
        if len(parts) == 2:
            pairs.append((parts[0], parts[1]))
    for name, value in pairs:
        key = (clean_text(name), clean_text(value))
        if key[0] and key[1] and key not in seen and key[0] != key[1]:
            seen.add(key)
            facts.append(RawAttribute(*key))
    return facts


def extract_photos(soup: BeautifulSoup, page_url: str) -> list[str]:
    result: list[str] = []
    for image in soup.select("img"):
        raw = image.get("src") or image.get("data-src") or ""
        url = urljoin(page_url, raw)
        if raw and url.startswith("http") and url not in result:
            result.append(url)
        if len(result) >= 20:
            break
    return result