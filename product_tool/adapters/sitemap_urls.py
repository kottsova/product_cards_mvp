"""URLs listed in a sitemap or sitemap index, decoded the way XML defines them.

A `<loc>` is XML text: `&amp;` in it stands for `&`. Stage 18's research script read `<loc>` with a regex and
requested `...?from=1&amp;to=2` literally; the server happened to answer, but the URL asked for was not the URL
the sitemap lists. Everything that reads sitemap locations goes through `sitemap_locs()`; it never builds or
rewrites a URL beyond XML entity decoding, and it drops anything that is not an absolute http(s) URL.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

_LOC_FALLBACK = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sitemap_locs(xml_text: str) -> list[str]:
    """Every `<loc>` of a urlset or sitemapindex, entity-decoded, in document order, absolute http(s) only."""
    try:
        root = ET.fromstring((xml_text or "").encode("utf-8"))
        raw = [(node.text or "").strip() for node in root.iter() if _local(node.tag) == "loc"]
    except ET.ParseError:
        # Truncated or slightly malformed sitemap (the fetcher caps the body): fall back to the text, still decoded.
        raw = [html.unescape(match.strip()) for match in _LOC_FALLBACK.findall(xml_text or "")]
    result = []
    for url in raw:
        parts = urlsplit(url)
        if parts.scheme in {"http", "https"} and parts.hostname and not parts.username and not parts.password:
            result.append(url)
    return result
