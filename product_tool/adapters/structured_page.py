"""Reusable, source-agnostic Product-page extraction primitives.

Built from the structural contract Stage 8.1's census actually confirmed
for the JSON-LD-Product-plus-Shopify-DOM shape shared by several brand
profiles (see reports/source_census_2026-09-23_stage13/readiness_table.md,
"Group A": Bosch/HyperX/Cudy) -- json_ld identity paths
(name/sku/productID/gtin*), a dl:dt+dd or accordion:details+summary
specifications table, and a data-media-id/data-fancybox gallery pattern.

This module only ever answers "what does this page's markup literally
say" -- it never decides whether the page is the RIGHT product (that is
each source-specific adapter's identity job, e.g. adapters/hyperx.py) and
it never treats structural similarity between brands as proof of an exact
product match. Every extracted field carries its own url, evidence, role
(which extraction layer produced it) and confirmation level -- there is no
such thing as a bare value here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .common import clean_text

# Extraction roles -- which layer of the page produced a field.
ROLE_JSON_LD = "json_ld"
ROLE_DOM_TABLE = "dom_table"
ROLE_GALLERY = "gallery"
ROLE_DESCRIPTION_IMAGE = "description_image"
ROLE_VIDEO = "video"

CONFIRMED = "confirmed"
PARTIAL = "partial"

_LOGO_CLASS_RE = re.compile(r"\blogo\b", re.I)


@dataclass(frozen=True)
class ExtractedField:
    name: str
    value: str
    url: str
    evidence: str
    role: str
    confirmation: str
    # Where inside the page the field sits (Stage 19). `section` is the heading row a specification row sits under,
    # `block` numbers the spec blocks of the page in document order (a repeated heading is still a new block), and
    # `media_id` is the numeric media id of a gallery item. All default to "unknown".
    section: str = ""
    block: int = 0
    media_id: str = ""


def _json_ld_blocks(soup: BeautifulSoup) -> list[dict]:
    """Every dict claiming @type include 'Product' in any JSON-LD script
    tag, including one nested inside an @graph array. Malformed JSON is
    silently skipped, never guessed at."""
    blocks: list[dict] = []
    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string if tag.string is not None else tag.get_text()
        try:
            data = json.loads(raw or "null")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        expanded: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            expanded.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                expanded.extend(x for x in graph if isinstance(x, dict))
        blocks.extend(expanded)
    return blocks


def _is_product_block(block: dict) -> bool:
    types = block.get("@type")
    types = types if isinstance(types, list) else [types]
    return "Product" in (types or [])


def extract_json_ld_product(html: str, page_url: str) -> list[ExtractedField]:
    """Identity fields, additionalProperty specs, and the primary JSON-LD
    image -- only from a real @type=Product block, never merged across
    unrelated blocks on the same page."""
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    for block in _json_ld_blocks(soup):
        if not _is_product_block(block):
            continue
        for key in ("name", "sku", "productID", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                fields.append(ExtractedField(
                    name=key, value=clean_text(value), url=page_url,
                    evidence=f"JSON-LD Product.{key} = {value!r}",
                    role=ROLE_JSON_LD, confirmation=CONFIRMED,
                ))
        additional = block.get("additionalProperty")
        if isinstance(additional, list):
            for prop in additional:
                if not isinstance(prop, dict):
                    continue
                name, value = prop.get("name"), prop.get("value")
                if isinstance(name, str) and name.strip() and isinstance(value, (str, int, float)) and str(value).strip():
                    fields.append(ExtractedField(
                        name=clean_text(name), value=clean_text(str(value)), url=page_url,
                        evidence=f"JSON-LD Product.additionalProperty: {name!r} = {value!r}",
                        role=ROLE_JSON_LD, confirmation=CONFIRMED,
                    ))
        image = block.get("image")
        images = image if isinstance(image, list) else ([image] if image else [])
        for item in images:
            url = item.get("url") if isinstance(item, dict) else item if isinstance(item, str) else None
            if url:
                full = urljoin(page_url, url)
                fields.append(ExtractedField(
                    name="json_ld_image", value=full, url=full,
                    evidence="JSON-LD Product.image", role=ROLE_JSON_LD, confirmation=CONFIRMED,
                ))
    return fields


def extract_dom_spec_table(html: str, page_url: str) -> list[ExtractedField]:
    """dl:dt+dd and table rows are treated as confirmed (an explicit
    name/value pair the page itself structured); an accordion's
    details+summary body is treated as partial -- it is prose under a
    heading, not a structured pair, so it can carry more than one fact."""
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    seen: set[tuple[str, str, str]] = set()

    def add(name: str, value: str, evidence: str, confirmation: str, section: str = "", block: int = 0) -> None:
        name, value = clean_text(name), clean_text(value)
        if not name or not value or name == value:
            return
        # An explicitly named boom/built-in mic owns the fact even when a
        # vendor repeats it under both specs and connections. Unqualified
        # fields still belong to their component section.
        owner = 'named_component' if re.search(r'\b(?:boom|built[- ]in)\s+mic\b', name, re.I) else section
        key = (owner, name, value)
        if key in seen:
            return
        seen.add(key)
        fields.append(ExtractedField(name=name, value=value, url=page_url, evidence=evidence, role=ROLE_DOM_TABLE, confirmation=confirmation,
                                     section=section, block=block))

    for dl in soup.select("dl"):
        # A price widget ("Unit price" $99.99 / from $99.99) is a <dl> too; it is a price, not a specification.
        if _in_price_widget(dl):
            continue
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            name, value = dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)
            add(name, value, f"<dl><dt>{name}</dt><dd>{value}</dd></dl>", CONFIRMED)

    section, block = "", 0
    carried = {}
    previous_table = None
    for row in soup.select("table tr"):
        table = row.find_parent("table")
        if table is not previous_table:
            carried = {}
            previous_table = table
        cells = row.find_all(["th", "td"], recursive=False)
        # Expand only this table's explicitly declared grid. A one-cell row
        # under rowspan is a value continuation, not a new section heading.
        grid = {column: cell for column, (cell, remaining) in carried.items()}
        carried = {column: (cell, remaining-1) for column, (cell, remaining) in carried.items() if remaining > 1}
        column = 0
        for cell in cells:
            while column in grid:
                column += 1
            def span(name):
                try: return min(100, max(1, int(cell.get(name, 1))))
                except (ValueError, TypeError): return 1
            width, height = span("colspan"), span("rowspan")
            for offset in range(width):
                grid[column+offset] = cell
                if height > 1:
                    carried[column+offset] = (cell, height-1)
            column += width
        expanded = [grid[column] for column in sorted(grid)]
        if not expanded:
            continue
        if len({id(cell) for cell in expanded}) == 1:
            # A single spanning cell is a heading row: it opens a new block even when the same heading text comes again.
            section, block = expanded[0].get_text(" ", strip=True), block + 1
            continue
        if len(expanded) >= 2:
            name, value = expanded[0].get_text(" ", strip=True), expanded[-1].get_text(" ", strip=True)
            add(name, value, f"<table><tr><th>{name}</th><td>{value}</td></tr></table>", CONFIRMED, section, block)

    # Stage 19: the same "Technical Specifications" tab is also published as headings + <ul><li><strong>Name: </strong>value</li>
    # (Cloud II Core, Cloud III Wireless). Each <h3> opens a block, like a heading row of the table form.
    tab = soup.select_one("#tab-technical-specifications")
    if tab is not None:
        for heading in tab.find_all("h3"):
            section, block = heading.get_text(" ", strip=True), block + 1
            sibling = heading.find_next_sibling()
            while sibling is not None and sibling.name != "h3":
                if sibling.name == "ul":
                    for item in sibling.find_all("li", recursive=False):
                        label = item.find("strong")
                        if label is None:
                            continue
                        name = label.get_text(" ", strip=True).rstrip(":").strip()
                        value = item.get_text(" ", strip=True)[len(label.get_text(" ", strip=True)):].strip()
                        add(name, value, f"<h3>{section}</h3><li><strong>{name}:</strong> {value}</li>", CONFIRMED, section, block)
                sibling = sibling.find_next_sibling()

    for details in soup.select("details"):
        summary = details.find("summary")
        if summary is None:
            continue
        name = summary.get_text(" ", strip=True)
        full_text = details.get_text(" ", strip=True)
        body = full_text[len(name):].strip() if full_text.startswith(name) else full_text
        add(name, body, f"<details><summary>{name}</summary>{body[:80]}</details>", PARTIAL)

    return fields


def _in_price_widget(node) -> bool:
    current = node
    while current is not None and getattr(current, "name", None):
        classes = current.get("class") or []
        classes = classes.split() if isinstance(classes, str) else classes
        if any(re.fullmatch(r"(?:unit-)?price(?:[_-].*)?", c) for c in classes):
            return True
        current = current.parent
    return False


def _has_logo_class(node) -> bool:
    classes = node.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    return any(_LOGO_CLASS_RE.search(c) for c in classes)


def _is_logo(node) -> bool:
    """True if `node` itself, its <img>, or any ancestor up the tree is
    marked as a logo. A logo's srcset must never count as gallery evidence
    just because it happens to also carry a gallery-shaped attribute."""
    current = node
    while current is not None and getattr(current, "name", None):
        if _has_logo_class(current):
            return True
        current = current.parent
    return False


def extract_main_gallery(html: str, page_url: str) -> list[ExtractedField]:
    """The full main gallery, strictly via data-media-id / data-fancybox --
    the confirmed Shopify PDP gallery pattern (Stage 8.1). A plain <img
    srcset> with neither attribute is not gallery evidence by itself, and
    anything under a logo-classed ancestor is excluded outright even if it
    does carry one of these attributes."""
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    seen_urls: set[str] = set()
    for node in soup.select("[data-media-id], [data-fancybox]"):
        # An <img data-media-id=...> nested inside an <a data-fancybox=...>
        # is the SAME logical gallery item as its wrapping anchor -- the
        # anchor (processed as its own node below) is the canonical,
        # full-size entry; without this the thumbnail <img> would be
        # counted a second time as a separate field.
        if node.name == "img" and node.find_parent(attrs={"data-fancybox": True}) is not None:
            continue
        if _is_logo(node):
            continue
        img = node if node.name == "img" else node.find("img")
        url = None
        if node.name == "a" and node.get("href"):
            url = node["href"]
        elif img is not None:
            url = img.get("src") or img.get("data-src")
        if not url:
            continue
        full = urljoin(page_url, url)
        if full in seen_urls:
            continue
        seen_urls.add(full)
        media_id = node.get("data-media-id") or (img.get("data-media-id") if img is not None else None)
        evidence = f"data-media-id={media_id!r}" if media_id else "data-fancybox gallery item"
        digits = re.search(r"(\d{8,})$", str(media_id or ""))
        fields.append(ExtractedField(name="gallery_image", value=full, url=full, evidence=evidence, role=ROLE_GALLERY, confirmation=CONFIRMED,
                                     media_id=digits.group(1) if digits else ""))
    return fields


def extract_description_images(html: str, page_url: str) -> list[ExtractedField]:
    """Images embedded in a description/body content block -- distinct
    from the main gallery. Anything already carrying a gallery attribute,
    or under a logo-classed ancestor, is excluded so the same image is
    never double-counted or misattributed."""
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    seen_urls: set[str] = set()
    for img in soup.select('[class*="description"] img, [class*="product-description"] img, .rte img'):
        if img.get("data-media-id") or img.get("data-fancybox") or img.find_parent(attrs={"data-fancybox": True}) or _is_logo(img):
            continue
        url = img.get("src") or img.get("data-src")
        if not url:
            continue
        full = urljoin(page_url, url)
        if full in seen_urls:
            continue
        seen_urls.add(full)
        fields.append(ExtractedField(
            name="description_image", value=full, url=full,
            evidence="<img> inside a description/body content block",
            role=ROLE_DESCRIPTION_IMAGE, confirmation=CONFIRMED,
        ))
    return fields


def extract_video(html: str, page_url: str) -> list[ExtractedField]:
    """A <video> element's own source, or an embedded YouTube/Vimeo/Wistia
    iframe -- never a guessed CDN transform of an image URL."""
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    for video in soup.select("video[src], video source[src]"):
        url = video.get("src")
        if url:
            full = urljoin(page_url, url)
            fields.append(ExtractedField(name="video", value=full, url=full, evidence="<video> element source", role=ROLE_VIDEO, confirmation=CONFIRMED))
    for iframe in soup.select("iframe[src]"):
        src = iframe.get("src", "")
        if re.search(r"youtube\.com|youtu\.be|vimeo\.com|wistia", src, re.I):
            full = urljoin(page_url, src)
            fields.append(ExtractedField(name="video", value=full, url=full, evidence=f"<iframe src={src!r}>", role=ROLE_VIDEO, confirmation=CONFIRMED))
    return fields


# ---------------------------------------------------------------- Shopify variants (Stage 19)
#
# A Shopify product page embeds the whole product once: <script data-product-json> lists every variant
# (id, sku, title, options, barcode, featured media) and every media item (id, alt, src), and the JSON-LD Product
# lists one Offer per variant (sku, name, gtin, url ...?variant=<id>). What the page's *selected* variant is
# (JSON-LD top-level sku, main image) is a separate fact. Nothing here builds a URL: a variant URL is used only
# when the page itself prints it, and it counts as confirmed only when the JSON-LD offer and the embedded product
# JSON agree on sku and variant id.

_ALT_TAG_RE = re.compile(r"\(([^)]+)\)\s*-\s*\d+\s*$")
_VARIANT_PARAM_RE = re.compile(r"[?&]variant=(\d+)(?:&|$)")


@dataclass(frozen=True)
class ShopifyMedia:
    media_id: str
    alt: str
    src: str
    tag: str  # "(Black/Red) - 03" -> "Black/Red"; "" when the alt carries none


@dataclass(frozen=True)
class ShopifyVariant:
    variant_id: str
    sku: str
    title: str
    name: str
    options: tuple[tuple[str, str], ...]
    barcode: str
    url: str  # the JSON-LD offer's own url, "" when the page prints none for this variant
    featured_media_id: str
    featured_alt: str
    sources: tuple[str, ...]

    @property
    def confirmed(self) -> bool:
        """Both in-page sources name this variant, and the offer url carries this very variant id."""
        match = _VARIANT_PARAM_RE.search(self.url or "")
        return set(self.sources) >= {"product_json", "json_ld_offer"} and bool(match) and match.group(1) == self.variant_id


@dataclass(frozen=True)
class ShopifyProduct:
    handle: str
    product_id: str
    page_url: str
    selected_sku: str
    variants: tuple[ShopifyVariant, ...]
    media: tuple[ShopifyMedia, ...]

    def variant_by_sku(self, sku: str) -> ShopifyVariant | None:
        wanted = (sku or "").strip().upper()
        found = [v for v in self.variants if v.sku.strip().upper() == wanted]
        return found[0] if len(found) == 1 else None

    def variant_media(self, variant: ShopifyVariant) -> tuple[tuple[ShopifyMedia, ...], str]:
        """The media that belong to this variant and how that was established. Never the page-default variant's."""
        if len(self.variants) == 1:
            return self.media, "single_variant_product"
        tag = _alt_tag(variant.featured_alt)
        tag_owners = [v for v in self.variants if _alt_tag(v.featured_alt).casefold() == tag.casefold()] if tag else []
        if tag and len(tag_owners) == 1:
            return tuple(m for m in self.media if m.tag.casefold() == tag.casefold()), "alt_tag_of_the_variants_featured_image"
        featured = tuple(m for m in self.media if m.media_id == variant.featured_media_id)
        return featured, ("featured_media_only" if featured else "unattributable")


def _alt_tag(alt: str) -> str:
    match = _ALT_TAG_RE.search(alt or "")
    return match.group(1).strip() if match else ""


def _abs(url: str, page_url: str) -> str:
    return urljoin(page_url, url) if url else ""


def extract_shopify_product(html: str, page_url: str) -> ShopifyProduct | None:
    """None when the page has no embedded product JSON (then nothing about variants is claimed)."""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("script[data-product-json]")
    if node is None:
        return None
    try:
        product = json.loads(node.string if node.string is not None else node.get_text())
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(product, dict) or not isinstance(product.get("variants"), list):
        return None
    handle = str(product.get("handle") or "")
    option_names = [o if isinstance(o, str) else str((o or {}).get("name", "")) for o in (product.get("options") or [])]

    offers: dict[str, dict] = {}
    selected_sku = ""
    for block in _json_ld_blocks(soup):
        if not _is_product_block(block):
            continue
        selected_sku = selected_sku or str(block.get("sku") or "").strip()
        raw = block.get("offers")
        for offer in raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else []):
            if isinstance(offer, dict) and str(offer.get("sku") or "").strip():
                offers[str(offer["sku"]).strip().upper()] = offer

    variants = []
    for item in product["variants"]:
        if not isinstance(item, dict) or not str(item.get("sku") or "").strip():
            continue
        sku = str(item["sku"]).strip()
        offer = offers.get(sku.upper())
        url = ""
        if offer and isinstance(offer.get("url"), str):
            candidate = _abs(offer["url"], page_url)
            same_page = urlsplit(candidate).path.rstrip("/") == f"/products/{handle}" if handle else False
            url = candidate if same_page else ""
        featured = item.get("featured_image") if isinstance(item.get("featured_image"), dict) else {}
        featured_media = item.get("featured_media") if isinstance(item.get("featured_media"), dict) else {}
        values = item.get("options") if isinstance(item.get("options"), list) else []
        variants.append(ShopifyVariant(
            variant_id=str(item.get("id", "")), sku=sku, title=str(item.get("public_title") or item.get("title") or ""),
            name=str(item.get("name") or (offer or {}).get("name") or ""),
            options=tuple((option_names[i] if i < len(option_names) else f"option{i + 1}", str(value)) for i, value in enumerate(values)),
            barcode=str(item.get("barcode") or (offer or {}).get("gtin12") or ""), url=url,
            featured_media_id=str(featured_media.get("id", "")), featured_alt=str(featured.get("alt") or ""),
            sources=("product_json", "json_ld_offer") if offer else ("product_json",),
        ))
    media = []
    for item in product.get("media") or []:
        if isinstance(item, dict) and item.get("src"):
            media.append(ShopifyMedia(media_id=str(item.get("id", "")), alt=str(item.get("alt") or ""), src=_abs(str(item["src"]), page_url), tag=_alt_tag(str(item.get("alt") or ""))))
    return ShopifyProduct(handle=handle, product_id=str(product.get("id", "")), page_url=page_url, selected_sku=selected_sku, variants=tuple(variants), media=tuple(media))
