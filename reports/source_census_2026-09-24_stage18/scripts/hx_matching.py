"""Stage 18 research helper (NOT an adapter): propose which *already observed* official
product-page slugs could belong to a HyperX catalog row.

A candidate is only a reason to spend one request. It is never a URL for the working map:
the page's own JSON-LD `sku` must equal the catalog code (HyperXAdapter.parse_page ->
match_level == "exact_variant") before anything is added to hyperx.KNOWN_URLS.

Nothing here builds a URL. Slugs come from links saved on official pages or from an
official sitemap that robots.txt declares.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

LATIN = re.compile(r"[A-Za-z0-9]+")
# Words that never distinguish a model (brand, product type, platform, colour, switch, locale).
OPTIONAL = {
    "HYPERX", "RU", "PS", "PS5", "PS4", "PC", "XBOX", "RED", "BLACK", "WHITE", "BLUE", "PINK", "GREY", "GRAY", "SWITCH",
    "GAMING", "MECHANICAL", "KEYBOARD", "MOUSE", "HEADSET", "MICROPHONE", "USB", "FOR", "THE", "MAT", "PAD", "WEBCAM", "CAMERA",
}
SLUG_NOISE = OPTIONAL | {"WIRELESS", "WIRED", "S"}


def _words(text: str) -> list[str]:
    return [w.upper() for w in LATIN.findall(text or "")]


def wireless_hint(title: str) -> str:
    lowered = (title or "").casefold()
    if "беспровод" in lowered:
        return "WIRELESS"
    if "провод" in lowered:
        return "WIRED"
    return ""


def model_tokens(title: str) -> tuple[list[str], str]:
    """Distinctive Latin tokens of a catalog title plus a wired/wireless hint."""
    tokens = [w for w in _words(title) if w not in OPTIONAL]
    return tokens, wireless_hint(title)


def slug_of(url_or_path: str) -> str:
    path = urlsplit(url_or_path).path if "://" in url_or_path else url_or_path
    return path.rstrip("/").rsplit("/", 1)[-1]


def candidates(title: str, slugs: list[str], limit: int = 2) -> list[str]:
    """Slugs that contain every distinctive title token, closest (fewest extra words) first."""
    tokens, hint = model_tokens(title)
    if not tokens:
        return []
    found = []
    for slug in slugs:
        slug_tokens = _words(slug.replace("-", " "))
        slug_set = set(slug_tokens)
        if not all(token in slug_set for token in tokens):
            continue
        if hint and hint == "WIRELESS" and "WIRELESS" not in slug_set:
            continue
        if hint == "WIRED" and "WIRELESS" in slug_set:
            continue
        extra = [w for w in slug_tokens if w not in tokens and w not in SLUG_NOISE]
        if any(w.isdigit() for w in extra):  # 'quadcast-2-s' is not 'QuadCast S': a generation number is a different model
            continue
        found.append((len(extra), len(slug_tokens), slug))
    return [slug for _, _, slug in sorted(found)[:limit]]
