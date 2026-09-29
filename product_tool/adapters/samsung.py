"""Stage 25: a limited Samsung (samsung.com/kz_ru) adapter working on a page that was already fetched.

It does not fetch anything and is not wired into the worker; it turns the HTML of an official product page (and, separately, the text of a document) into facts, each with
the evidence it came from. Nothing is filled in by guessing: what the static HTML does not contain is reported as a gap.

What it reads (all observed in the saved batch 1 / batch 2 pages):
  * identity: JSON-LD Product (name, sku), the page title, the visible text; the URL alone never confirms a variant;
  * the specification table: the server-rendered accordion `pdd32-product-spec` (group title, item title, item value);
  * photos: the gallery lightbox images (`hdd02-gallery__popup-vertical-image`, `$Q90_..$` sizes), one asset once, the largest size; thumbnails (`-thumb-`, `$104_104_PNG$`)
    and 3D models (.glb/.usdz) are never photos;
  * document links: `org.downloadcenter.samsung.com ... CDCttType=UM ... ModelName=...`, printed by the page itself;
  * documents, three SEPARATE facts: Russian by the text; tied to the product by the official page; exact model named inside the document.
"""
from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Comment, Doctype

from .common import PhotoCandidate, RawAttribute, clean_text
from .lg_documents import RU_INSTRUCTION_MARKERS, _chunks, assess_document, chunk_language

_NOT_A_PHOTO = re.compile(r"-thumb-|104_104|\.(?:glb|usdz)(?:$|\?)|Delivery-Service|\.pdf(?:$|\?)", re.I)


@lru_cache(maxsize=4)
def soup_of(html: str) -> BeautifulSoup:
    """One parse of a page for all the readers below (a Samsung page is ~1 MB; html.parser takes over a second). No reader mutates the tree."""
    return BeautifulSoup(html, "html.parser")


def visible_text(soup: BeautifulSoup) -> str:
    """The text a visitor can see: every string outside script/style/noscript, joined by spaces."""
    return " ".join(node for node in soup.find_all(string=True) if node.parent.name not in ("script", "style", "noscript") and not isinstance(node, (Comment, Doctype)))


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


# ---------------------------------------------------------------- identity ------------------------------------------------------------

@dataclass
class Identity:
    title: str = ""
    canonical: str = ""
    jsonld_name: str = ""
    jsonld_sku: str = ""
    is_product_page: bool = False
    level: str = "unknown"            # full_sku | base_model | unknown
    evidence_strength: str = ""       # strong: JSON-LD sku/name, the page title, or the page's own single product-data code; text_only: the code appears only in the visible text (e.g. the purchase panel's model line)
    evidence: list[str] = field(default_factory=list)
    open_differences: list[str] = field(default_factory=list)


_SM_CODE = re.compile(r"^(SM-[A-Z]\d{3}[A-Z]?)([A-Z0-9]{2})([A-Z0-9])([A-Z]{3})$")


def sm_code_parts(code: str) -> dict:
    """SM-A376E DG G SKZ -> base, colour, memory, region (Samsung phone/tablet/watch codes). Empty when the code has another shape."""
    match = _SM_CODE.match(str(code or "").upper())
    return dict(zip(("base", "colour", "memory", "region"), match.groups())) if match else {}


def _json_ld_product(soup: BeautifulSoup) -> dict:
    import json
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.string or "{}")
        except (ValueError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            kind = item.get("@type") if isinstance(item, dict) else None
            if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                return item
    return {}


# The page's OWN product data: the sales code of the product this page sells, printed in the purchase component (hidden form fields and data attributes). Template placeholders ({{...}}) are not data.
_PRODUCT_DATA_CODE_FIELDS = (r'name="modelCode"[^>]*?value="([^"]*)"', r'name="apiChangeModelCode"[^>]*?value="([^"]*)"', r'id="shopSKU"[^>]*?value="([^"]*)"', r'name="apiChangeShopSKU"[^>]*?value="([^"]*)"',
                             r'name="originShopSku"[^>]*?value="([^"]*)"', r'data-model-code="([^"]*)"', r'data-shop-sku="([^"]*)"')


def product_data_codes(html: str) -> set[str]:
    """The normalized codes the page's own product data declares (empty when it declares none). Only concrete values count: a template placeholder or an empty value is skipped."""
    codes = set()
    for pattern in _PRODUCT_DATA_CODE_FIELDS:
        for value in re.findall(pattern, html):
            if value and "{" not in value and norm(value):
                codes.add(norm(value))
    return codes


def extract_identity(html: str, url: str, catalog_article: str) -> Identity:
    """Exact only when the page CONTENT (JSON-LD sku/name, title, visible text) shows the catalog article; the URL is recorded but never counts."""
    soup = soup_of(html)
    product = _json_ld_product(soup)
    title = clean_text(soup.title.string if soup.title and soup.title.string else "")
    canonical_node = soup.select_one('link[rel="canonical"]')
    identity = Identity(title=title, canonical=(canonical_node.get("href", "") if canonical_node else ""), jsonld_name=clean_text(str(product.get("name", ""))), jsonld_sku=clean_text(str(product.get("sku", ""))),
                        is_product_page=bool(product) or bool(soup.select_one(".pdd32-product-spec")))
    article = norm(catalog_article)
    base_key = norm(catalog_article.split("/")[0])
    text = norm(visible_text(soup))
    if identity.jsonld_sku and norm(identity.jsonld_sku) == article:
        identity.evidence.append("jsonld_sku")
    if article and article in norm(identity.jsonld_name):
        identity.evidence.append("jsonld_name")
    if article and article in norm(title):
        identity.evidence.append("title")
    if article and len(article) >= 8 and article in text:
        identity.evidence.append("visible_text")
    if article and article in norm(url):
        identity.evidence.append("url_only_not_counted")
    content_evidence = [e for e in identity.evidence if e != "url_only_not_counted"]
    if content_evidence:
        identity.level = "full_sku"
        identity.evidence_strength = "strong" if {"jsonld_sku", "jsonld_name", "title"} & set(content_evidence) else "text_only"
        # Stage 30 (owner decision): the page's own product data declaring exactly ONE code, equal to the catalog code, with no other code declared and no other sku in the markup, is strong
        # evidence of the variant even when the markup and title do not show the code. A different code anywhere in that data (a fridge's "/WT" suffix, a phone's other colour) confirms nothing.
        if identity.evidence_strength == "text_only" and product_data_codes(html) == {article} and (not identity.jsonld_sku or norm(identity.jsonld_sku) == article):
            identity.evidence.append("product_data_code")
            identity.evidence_strength = "strong"
        return identity
    # a page of the same base model but another variant: compare the code the page shows with the catalog article
    sku = norm(identity.jsonld_sku)
    catalog_parts, page_parts = sm_code_parts(catalog_article), sm_code_parts(identity.jsonld_sku)
    if catalog_parts and page_parts and catalog_parts["base"] == page_parts["base"]:
        identity.level = "base_model"
        identity.evidence.append("jsonld_sku_same_base_model")
        for key, label in (("region", "региональный код"), ("colour", "код цвета"), ("memory", "код памяти")):
            if catalog_parts[key] != page_parts[key]:
                identity.open_differences.append(f"{label}: каталог {catalog_parts[key]}, страница {page_parts[key]}")
        identity.open_differences.append("вариант каталога на официальной странице KZ не подтверждён; различие остаётся открытым")
    elif sku and len(base_key) >= 6 and (sku.startswith(base_key) or base_key.startswith(sku)):
        identity.level = "base_model"
        identity.evidence.append("jsonld_sku_shares_the_base_code")
        identity.open_differences.append(f"код на странице {identity.jsonld_sku}, артикул каталога {catalog_article}")
    return identity


# ---------------------------------------------------------------- specifications ------------------------------------------------------

@dataclass
class SpecItem:
    group: str
    name: str
    value: str


def extract_spec_table(html: str) -> list[SpecItem]:
    """The server-rendered accordion: group (button text) -> items (title, value). An item without a title carries the group's own value (e.g. product type)."""
    soup = soup_of(html)
    items: list[SpecItem] = []
    for group_node in soup.select(".pdd32-product-spec__item"):
        button = group_node.select_one(".pdd32-product-spec__toggle-cta")
        group = clean_text(button.get_text(" ")) if button else ""
        for row in group_node.select(".pdd32-product-spec__content-item"):
            title, value = row.select_one(".pdd32-product-spec__content-item-title"), row.select_one(".pdd32-product-spec__content-item-desc")
            text = clean_text(value.get_text(" ")) if value else ""
            if not text:
                continue
            items.append(SpecItem(group, clean_text(title.get_text(" ")) if title else group, text))
    return items


def spec_attributes(items: list[SpecItem], devices: dict[int, str] | None = None) -> list[RawAttribute]:
    """RawAttribute rows for the pipeline; a repeated item name gets its group in brackets (the same convention as the LG Russia adapter). `devices` (item index -> device) is only ever filled from
    explicit evidence (see assign_devices): such a row's name carries the device in square brackets, its value is untouched. A row of a group that names a part in its own title always shows the group."""
    devices = devices or {}

    def slug(text: str) -> str:  # two names that differ only in punctuation/brackets are one name to the pipeline ("Количество ящиков (для овощей)" / "Количество ящиков для овощей")
        return re.sub(r"[^a-zа-я0-9]+", "_", text.casefold().replace("ё", "е")).strip("_")

    base = [f"{item.name} [{DEVICE_LABELS[devices[i]]}]" if i in devices and devices[i] in DEVICE_LABELS else item.name for i, item in enumerate(items)]
    counts: dict[str, int] = {}
    for name in base:
        counts[slug(name)] = counts.get(slug(name), 0) + 1
    seen, result = set(), []
    for item, name in zip(items, base):
        grouped = (counts[slug(name)] > 1 or bool(PART_GROUP.search(item.group))) and item.group and item.group != item.name
        name = f"{name} ({item.group})" if grouped else name
        if (name, item.value) not in seen:
            seen.add((name, item.value))
            result.append(RawAttribute(name, item.value))
    return result


# ---------------------------------------------------------------- devices of one product: which size and weight belong to which part ---------

_MASS = re.compile(r"Масса\s+(\d+(?:[.,]\d+)?)\s*кг")
_SIZE = re.compile(r"Размер\s+(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)\*?\s*мм")
_FOOTNOTE = re.compile(r"\*\s*включая[^:\n]*:\s*(\d+(?:[.,]\d+)?)\s*мм")
_DEVICE_NAME = re.compile(r"Название\s+([А-Яа-яЁё][А-Яа-яЁё ]{2,40}?)\s*(?:\n|Номинальн)")
DEVICE_LABELS = {"product": "основное изделие", "station": "станция очистки"}
_PLAIN_MASS = re.compile(r"^(?:вес|масса)$", re.I)
_PLAIN_SIZE = re.compile(r"^размеры?\s*\(\s*ш\s*[xх×]\s*в\s*[xх×]\s*г\s*\)$", re.I)
PART_GROUP = re.compile(r"станци[яи]\s+очистки", re.I)   # a page group that names a part of the product in its own title


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def manual_device_tables(pages: list[str], catalog_article: str) -> list[dict]:
    """Technical-data blocks of the manual that NAME their device: a block headed 'Название <device>' (e.g. Станция очистки) is that device; the block headed by a series mask that covers the
    catalog code (`Серия VR50T95****`) is the product itself. Each block gives its mass (kg) and size (mm; a footnote may name a second height). Nothing is read from the order of anything."""
    tables = []
    for number, page in enumerate(pages, start=1):
        mass, size = _MASS.search(page), _SIZE.search(page)
        if not (mass and size):
            continue
        named = _DEVICE_NAME.search(page)
        series = re.search(r"Серия\s+([A-Za-z0-9*]{5,})", page)
        if named:
            device, shown = "station" if PART_GROUP.search(named.group(1)) else "other:" + named.group(1).strip(), "Название " + named.group(1).strip()
        elif series and positional_masks(series.group(1), catalog_article):
            device, shown = "product", "Серия " + series.group(1)
        else:
            continue
        note = _FOOTNOTE.search(page)
        tables.append({"device": device, "block_heading": shown, "page": number, "mass_kg": _number(mass.group(1)), "size_mm": [_number(size.group(i)) for i in (1, 2, 3)], "size_note_mm": _number(note.group(1)) if note else None})
    return tables


def _match_table(kind: str, value: str, table: dict) -> bool:
    if kind == "mass":
        found = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", value)
        return bool(found) and abs(_number(found.group(1)) - table["mass_kg"]) < 1e-9
    numbers = sorted(_number(n) for n in re.findall(r"\d+(?:[.,]\d+)?", value)[:3])
    if len(numbers) != 3:
        return False
    options = [sorted(table["size_mm"])]
    if table["size_note_mm"] is not None:      # the footnote names the height that includes a protruding sensor: the page may print that one
        widest = table["size_mm"]
        options.append(sorted([widest[0], widest[1], table["size_note_mm"]]))
    return numbers in options


def assign_devices(items: list[SpecItem], tables: list[dict]) -> tuple[dict[int, str], list[dict], list[dict]]:
    """For each PLAIN mass / size row of the page (name exactly 'Вес' / 'Масса' / 'Размеры (ШxВxГ)'), the device whose manual table carries the same value -- only when exactly one table does.
    Returns ({item index: device}, assigned records with their basis, unassigned rows). A page group whose own title names a part (Детали Станции очистки) is recorded as explicit for that part.
    Row order is never used."""
    assigned, records, unassigned = {}, [], []
    if len(tables) < 2:
        return assigned, records, unassigned
    for index, item in enumerate(items):
        kind = "mass" if _PLAIN_MASS.match(item.name.strip()) else "size" if _PLAIN_SIZE.match(item.name.strip()) else ""
        if not kind:
            continue
        if PART_GROUP.search(item.group):
            hits = [t for t in tables if t["device"] == "station" and _match_table(kind, item.value, t)]
            basis = "название группы на самой странице называет часть; таблица инструкции «станция очистки» содержит то же значение" if hits else "название группы на самой странице называет часть"
            assigned[index] = "station"
            records.append({"row": item.name, "group": item.group, "value": item.value, "device": "station", "basis": basis, "manual_page": hits[0]["page"] if hits else None})
            continue
        hits = [t for t in tables if _match_table(kind, item.value, t)]
        if len(hits) == 1:
            assigned[index] = hits[0]["device"]
            records.append({"row": item.name, "group": item.group, "value": item.value, "device": hits[0]["device"], "basis": f"таблица инструкции «{hits[0]['block_heading']}» (стр. {hits[0]['page']}) названа этим устройством и содержит то же значение", "manual_page": hits[0]["page"]})
        else:
            unassigned.append({"row": item.name, "group": item.group, "value": item.value, "reason": "ни одна таблица инструкции с названным устройством не содержит этого значения" if not hits else "это значение содержат несколько таблиц"})
    return assigned, records, unassigned


# ---------------------------------------------------------------- photos --------------------------------------------------------------

def _absolute(url: str, page_url: str) -> str:
    return urljoin(page_url, url.strip())


def _width(url: str) -> int:
    match = re.search(r"\$(?:Q\d+_)?(\d{3,4})_(\d{3,4})", url)
    return int(match.group(1)) if match else 0


@dataclass
class PhotoSet:
    photos: list[PhotoCandidate] = field(default_factory=list)
    thumbnails: list[str] = field(default_factory=list)
    three_d: list[str] = field(default_factory=list)
    candidate_thumbnail_only: list[str] = field(default_factory=list)
    gap: str = ""


def extract_photos(html: str, page_url: str) -> PhotoSet:
    """Gallery photos: every lightbox/header image of the product's own gallery, one per asset (query string dropped), the largest size named. Thumbnails and 3D files are
    listed apart and never counted; when the page has no gallery markup, only the JSON-LD image is reported, as a candidate that is not a confirmed photo."""
    soup = soup_of(html)
    result = PhotoSet()
    best: dict[str, tuple[int, str, str]] = {}
    scope = soup.select(".hdd02-gallery__popup-vertical-image, .hdd02-pdp-header__gallery-area, .hdd02-pdp-header")
    seen_nodes = set()
    for container in scope:
        for node in container.select("img, source"):
            if id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))
            for attr in ("src", "data-src", "srcset", "data-srcset"):
                value = node.get(attr)
                if not value:
                    continue
                for raw in re.findall(r"(?:https?:)?//images\.samsung\.com/[^\s,\"']+", value):
                    url = _absolute(raw, page_url)
                    key = re.sub(r"\?.*$", "", url)
                    if re.search(r"\.(?:glb|usdz)$", key, re.I):
                        result.three_d.append(key)
                    elif re.search(r"-thumb-|104_104", url):
                        result.thumbnails.append(key)
                    elif _NOT_A_PHOTO.search(url):
                        continue
                    else:
                        width = _width(url)
                        if key not in best or width > best[key][0]:
                            best[key] = (width, url, clean_text(node.get("alt", "")))
    for key, (width, url, alt) in best.items():
        result.photos.append(PhotoCandidate(url, key, "product_gallery", width=width or None))
    result.thumbnails = sorted(set(result.thumbnails))
    result.three_d = sorted(set(result.three_d))
    if not result.photos:
        product = _json_ld_product(soup)
        image = product.get("image")
        image = image[0] if isinstance(image, list) and image else image
        if isinstance(image, dict):
            image = image.get("url")
        if isinstance(image, str) and image:
            result.candidate_thumbnail_only.append(_absolute(image, page_url))
        result.gap = "в статическом HTML нет галереи товара: полноразмерные фото не найдены"
    return result


def buy_page_url(html: str, page_url: str) -> str:
    """The purchase page the product's own JSON-LD names (potentialAction BuyAction target), on the same site; never built from the product address."""
    product = _json_ld_product(soup_of(html))
    action = product.get("potentialAction")
    for item in (action if isinstance(action, list) else [action]):
        if isinstance(item, dict) and item.get("@type") == "BuyAction":
            target = item.get("target")
            target = target.get("urlTemplate") if isinstance(target, dict) else target
            if isinstance(target, str) and target:
                url = _absolute(target, page_url)
                if (urlsplit(url).hostname or "") == (urlsplit(page_url).hostname or "") and "/kz_ru/" in url:
                    return url
    return ""


# ---------------------------------------------------------------- document links ------------------------------------------------------

_LANGUAGE_HINTS = (("RU", re.compile(r"(?:^|[_\-])RU(?:[_\-.]|$)|_RUS_|RUS_", re.I)), ("KK", re.compile(r"(?:^|[_\-])KK(?:[_\-.]|$)", re.I)), ("UZ", re.compile(r"(?:^|[_\-])UZ(?:[_\-.]|$)", re.I)),
                   ("EN", re.compile(r"(?:^|[_\-])(?:EN|ENG)(?:[_\-.]|$)|_ENG_", re.I)), ("UK", re.compile(r"(?:^|[_\-])UK(?:[_\-.]|$)", re.I)))


@dataclass
class DocumentLink:
    href: str
    model_name: str            # the model the official page's own link declares (ModelName=...)
    file_name: str
    language_hint: str         # from the FILE NAME: orders requests only, never evidence of what the file says
    anchor: str = ""


def extract_document_links(html: str, page_url: str) -> list[DocumentLink]:
    soup = soup_of(html)
    links, seen = [], set()
    for anchor in soup.select("a[href]"):
        href = _absolute(anchor["href"], page_url)
        if "CDCttType=UM" not in href or (urlsplit(href).hostname or "").split(".")[-2:] != ["samsung", "com"] or href in seen:
            continue
        seen.add(href)
        query = parse_qs(urlsplit(href).query)
        model = unquote((query.get("ModelName") or [""])[0])
        name = unquote((query.get("VPath") or [""])[0]).rsplit("/", 1)[-1]
        hint = next((label for label, pattern in _LANGUAGE_HINTS if pattern.search(name)), "")
        links.append(DocumentLink(href, model, name, hint, clean_text(anchor.get_text(" "))))
    return links


def order_for_request(links: list[DocumentLink], wanted: str = "RU") -> list[DocumentLink]:
    """Russian-looking file names first. This decides which file is asked for first; it proves nothing about the file."""
    return sorted(links, key=lambda link: 0 if link.language_hint == wanted else 1)


# ---------------------------------------------------------------- documents: three separate facts -----------------------------------------

def positional_masks(text: str, model: str) -> list[str]:
    """Samsung prints families with one '*' per unknown character ("WD1*T******/WD9*T******"): the mask names the model when it is as long as the model and every fixed
    character equals the model's. At least 4 fixed characters, so a mask of stars alone names nothing."""
    fixed = re.sub(r"[^A-Z0-9]", "", str(model).upper().split("/")[0])
    found = []
    for token in dict.fromkeys(re.findall(r"[A-Za-z0-9*]{5,}(?:/[A-Za-z0-9*]{3,})*", text)):
        for part in token.split("/"):
            if "*" in part and len(part) == len(fixed) and sum(1 for c in part if c != "*") >= 4 and all(c == "*" or c.upper() == f for c, f in zip(part, fixed)):
                found.append(part)
    return found[:5]


MIN_READABLE_CHARS, MAX_EMPTY_PAGE_SHARE = 2000, 0.5
# How the official page that prints a file's link ties the file to the row: by a page that shows the full article in its markup/title (exact), by a page that shows the article only in its visible
# text (weaker), or by a page of the same base model (another variant). Nothing else ties a file.
PAGE_TIES = {"full_sku": "exact_page", "code_in_page_text": "page_with_code_in_text_only", "base_model": "base_model_page"}


def russian_section(pages: list[str], languages: dict) -> dict:
    """A Russian PART of a multilingual document that is not a Russian instruction: `present` when Russian text is there in an amount that counts as a language being present AND carries instruction
    wording (a leaflet printing its short guide in thirty languages, not a legal notice); the whole document is not a Russian instruction. `pages` are the 1-based pages carrying that Russian text.
    Nothing else is read into it: it names no model by itself."""
    per_page: dict[int, int] = {}
    for number, page in enumerate(pages, start=1):
        letters = sum(sum(1 for c in chunk if c.isalpha()) for chunk in _chunks(page) if chunk_language(chunk) == "ru")
        if letters:
            per_page[number] = letters
    total = sum(per_page.values())
    return {"present": bool(languages["russian_present"] and not languages["russian_instruction"] and languages["russian_instruction_markers"] >= RU_INSTRUCTION_MARKERS), "pages": sorted(per_page), "letters": total}


def assess_samsung_document(pages: list[str], catalog_article: str, link_model_name: str, page_level: str) -> dict:
    """Keeps apart what is known about a document:
       russian_by_text          -- the extracted TEXT is a Russian instruction (not a declaration);
       tied_by_official_page    -- the official product page prints this file's link: 'exact_page' when that page shows the row's full article, 'base_model_page' when it shows only the base model;
       names_model_in_document  -- which model the TEXT names: the catalog article (exact / family mask), and separately the model the page's own link declares (ModelName).
    No code equivalence (e.g. SC = VC) is assumed anywhere: the two names are compared with the text one at a time."""
    chars = sum(len(p) for p in pages)
    empty = sum(1 for p in pages if len(p.strip()) < 40)
    readable = chars >= MIN_READABLE_CHARS and (empty / max(len(pages), 1)) <= MAX_EMPTY_PAGE_SHARE
    if not readable:  # a file whose text cannot be extracted (drawn text, scans) proves nothing by content: manual check, no guesses
        return {"content_status": "text_not_extractable", "pages": len(pages), "empty_pages": empty, "chars": chars, "russian_by_text": None, "instruction_by_content": None, "regulatory": None,
                "tied_by_official_page": PAGE_TIES.get(page_level, "none"),
                "names_catalog_model": {"exact": None, "family_mask": [], "tokens": [catalog_article.split("/")[0]]}, "names_link_model": {"model_name": link_model_name, "exact": None, "family_mask": []},
                "conflicting_models": [], "languages_by_text": [], "letters_by_language": {}, "russian_section": {"present": False, "pages": [], "letters": 0}}
    catalog = assess_document(pages, [catalog_article.split("/")[0]])
    linked = assess_document(pages, [link_model_name]) if link_model_name else None
    languages = catalog["languages"]
    conflicting = catalog["conflicting_models"] or (linked["conflicting_models"] if linked else [])
    text = "\n".join(pages)
    catalog_masks = list(dict.fromkeys(catalog["model_masks"] + positional_masks(text, catalog_article)))
    link_masks = list(dict.fromkeys((linked["model_masks"] if linked else []) + (positional_masks(text, link_model_name) if link_model_name else [])))
    return {
        "content_status": "readable", "pages": len(pages), "empty_pages": empty, "chars": chars,
        "russian_by_text": bool(languages["russian_instruction"]) and not catalog["regulatory"],
        "instruction_by_content": catalog["kind"] in ("instruction_confirmed", "instruction_model_not_named", "instruction_conflicting_model"),
        "regulatory": catalog["regulatory"],
        "tied_by_official_page": PAGE_TIES.get(page_level, "none"),
        "names_catalog_model": {"exact": catalog["model_evidence"] == "exact", "family_mask": catalog_masks, "tokens": [catalog_article.split("/")[0]]},
        "names_link_model": {"model_name": link_model_name, "exact": bool(linked and linked["model_evidence"] == "exact"), "family_mask": link_masks},
        "conflicting_models": conflicting,
        "languages_by_text": languages["present"], "letters_by_language": languages["letters_by_language"],
        "russian_section": russian_section(pages, languages),
    }


def is_brief_guide(facts: dict) -> bool:
    """A multilingual leaflet with a short Russian section (Stage 30 owner decision): kept as a brief guide with its pages, never a full Russian instruction."""
    return bool(facts.get("instruction_by_content") and not facts.get("russian_by_text") and (facts.get("russian_section") or {}).get("present"))


def brief_guide_note(facts: dict) -> str:
    section = facts["russian_section"]
    pages = ", ".join(str(n) for n in section["pages"])
    catalog, link = facts["names_catalog_model"], facts["names_link_model"]
    model = "модель в тексте не названа" if not (catalog["exact"] or catalog["family_mask"] or link["exact"] or link["family_mask"]) else "в тексте назван код модели (не проверено как связь с вариантом)"
    return f"краткая памятка (краткое руководство), русский раздел на стр. {pages}; {model}; полной русской инструкцией не считается"


def _unescape(value: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value).replace("\\/", "/")


def page_model_data(html: str) -> dict:
    """The model the exact official page declares for ITSELF in its own data: `digitalData.product.model_code` (the sales code, e.g. VC18M21D0VG/EV) and `digitalData.product.model_name`
    (the model name the page's manual links use, e.g. SC18M21D0VG). Read from this page only; it is evidence about this product, not a rule between two code families."""
    found = {}
    for key in ("model_code", "model_name"):
        values = sorted({_unescape(v) for v in re.findall(r'digitalData\.product\.%s\s*=\s*"([^"]*)"' % key, html) if v})
        if len(values) == 1:
            found[key] = values[0]
    if len(found) == 2:
        found["source"] = "digitalData.product (model_code / model_name)"
        return found
    return {}


# What makes a Russian instruction acceptable for the card, and on what basis (the owner's Stage 27 rule). Accepted with a mark when the exact official page prints the link, the text is a
# Russian instruction and no conflicting model is named; the mark says the exact code is not in the PDF. A PDF that names ANOTHER code is accepted only when this page's own data declares that code
# as its model name next to the catalog code as its model code; no equality between code families (SC / VC, LS / S) is assumed anywhere.
ACCEPTED_BASES = ("exact_code_in_pdf", "family_mask_in_pdf", "exact_page_link_only", "code_relation_declared_by_page_data")
MARK_LINK_ONLY = "связь с моделью подтверждена точной официальной страницей; точный код в PDF не назван"


def instruction_acceptance(facts: dict, page_data: dict, catalog_article: str, link_model: str) -> dict:
    """{"basis", "accepted", "note", "code_relation"}. `facts` is assess_samsung_document()'s result."""
    def verdict(basis: str, accepted: bool, note: str = "", relation: dict | None = None) -> dict:
        return {"basis": basis, "accepted": accepted, "note": note, "code_relation": relation or {}}

    if facts.get("content_status") == "text_not_extractable":
        return verdict("manual_check_text_not_extractable", False, "текст файла не извлекается: проверка вручную")
    if is_brief_guide(facts) and not facts["regulatory"]:
        return verdict("brief_guide_russian_section", False, brief_guide_note(facts))
    if not facts["russian_by_text"] or facts["regulatory"]:
        return verdict("not_a_russian_instruction_by_text", False, "по тексту это не русская инструкция")
    if facts["conflicting_models"]:
        return verdict("conflicting_model_in_text", False, "в тексте названа другая модель")
    if facts["tied_by_official_page"] != "exact_page":
        return verdict("page_tie_not_exact", False, "файл связан страницей, которая не подтверждает полный артикул по разметке или заголовку")
    catalog, link = facts["names_catalog_model"], facts["names_link_model"]
    if catalog["exact"]:
        return verdict("exact_code_in_pdf", True)
    if catalog["family_mask"]:
        return verdict("family_mask_in_pdf", True, "в PDF назван только семейный код (маска " + ", ".join(catalog["family_mask"][:2]) + "); точный код в PDF не назван")
    page_name, page_code = norm(page_data.get("model_name", "")), norm(page_data.get("model_code", ""))
    article_keys = {norm(catalog_article), norm(catalog_article.split("/")[0])}
    relation = {"link_model_name": link_model, "page_model_name": page_data.get("model_name", ""), "page_model_code": page_data.get("model_code", ""), "source": page_data.get("source", "")}
    if link["exact"] or link["family_mask"]:
        if page_name and norm(link_model) == page_name and page_code in article_keys:
            relation["declared_by_page_data"] = True
            return verdict("code_relation_declared_by_page_data", True,
                           f"связь с моделью подтверждена точной официальной страницей: назван код {link_model}, и эта же страница в своих данных объявляет его названием модели (model_name) при коде каталога {page_data['model_code']} (model_code); точный код каталога в PDF не назван", relation)
        relation["declared_by_page_data"] = False
        return verdict("link_code_relation_unverified", False, f"в PDF назван код {link_model}, официальных данных о его связи с кодом каталога {catalog_article} нет: проверка вручную", relation)
    if page_name and norm(link_model) != page_name:
        relation["declared_by_page_data"] = False
        return verdict("link_model_differs_from_page_model_name", False, "ссылка на файл объявляет модель, которая не совпадает с названием модели в данных страницы: проверка вручную", relation)
    return verdict("exact_page_link_only", True, MARK_LINK_ONLY, relation)


def photo_variant_binding(photos, catalog_article: str) -> list:
    """Photos whose OWN asset path names exactly the catalog code (`.../p6pim/kz_ru/nz64t3506ak-wt/gallery/...` for NZ64T3506AK/WT): bound to the variant by official structured data, whatever
    the page itself proves. A path that names another code (the phone's `sm-a376edggskz` for a `SM-A376EZAGINS` row) or only part of the catalog code binds nothing."""
    wanted = norm(catalog_article)
    bound = []
    for photo in photos:
        match = re.search(r"/p6pim/[^/]+/([^/]+)/", photo.url)
        if match and wanted and norm(match.group(1)) == wanted:
            bound.append(photo)
    return bound


def rule4_analog(facts: dict) -> str:
    """The owner's LG rule 4, read on the three facts: a Russian instruction by content, tied by an EXACT official page, with no conflicting model is acceptable; the basis is stated."""
    if facts.get("content_status") == "text_not_extractable":
        return "manual_check_text_not_extractable"
    if not facts["russian_by_text"] or facts["regulatory"] or facts["conflicting_models"] or facts["tied_by_official_page"] != "exact_page":
        return "not_accepted"
    if facts["names_catalog_model"]["exact"]:
        return "accepted_catalog_model_named_in_text"
    if facts["names_catalog_model"]["family_mask"]:
        return "accepted_family_of_the_catalog_model_named_in_text"
    if facts["names_link_model"]["exact"] or facts["names_link_model"]["family_mask"]:
        return "accepted_only_the_model_declared_by_the_pages_link_is_named_in_text"
    return "accepted_tied_by_page_not_by_text"


# ---------------------------------------------------------------- finding a page ------------------------------------------------------

def find_in_sitemap(urls: list[str], article: str) -> str:
    """The sitemap URL whose alphanumeric slug contains the alphanumeric article (the part before '/' is the fallback); nothing is built."""
    for key in (norm(article), norm(article.split("/")[0])):
        if len(key) >= 6:
            hit = next((u for u in urls if key in norm(u.rsplit("/kz_ru/", 1)[-1])), "")
            if hit:
                return hit
    return ""


def hub_product_links(html: str, page_url: str) -> list[str]:
    """Pages a hub links to: its anchors AND the /kz_ru/ addresses its embedded data lists (the listing is partly built from data). Only page-shaped addresses count: under /kz_ru/, a
    trailing slash, no /gallery/ path and no image/document file -- the hub also embeds image URLs (Stage 24 asked for one of them and got a 404)."""
    soup = soup_of(html)
    raw = [anchor["href"] for anchor in soup.select("a[href]")]
    raw += re.findall(r"""(?:https?://www\.samsung\.com)?/kz_ru/[^"'\s<>\\)]+""", html)
    links = set()
    for value in raw:
        url = urljoin(page_url, value).split("#")[0].split("?")[0]
        path = urlsplit(url).path
        if "/kz_ru/" in path and path.endswith("/") and "/gallery/" not in path and not re.search(r"\.(?:jpe?g|png|pdf|webp|glb|usdz)/?$", path, re.I):
            links.add(url)
    return sorted(links)


def find_on_hub(links: list[str], catalog_article: str) -> str:
    """A hub link for the catalog row's BASE MODEL code (SM-X826 -> ...-sm-x826...). A neighbouring model of the same series (S10 Lite, SM-X406) is not a match."""
    parts = sm_code_parts(catalog_article)
    key = norm(parts["base"]) if parts else norm(catalog_article.split("/")[0])
    if len(key) < 6:
        return ""
    return next((u for u in links if key in norm(u.rsplit("/kz_ru/", 1)[-1])), "")


# ---------------------------------------------------------------- the page as a whole -------------------------------------------------

@dataclass
class SamsungCard:
    url: str
    identity: Identity
    specs: list[SpecItem]
    photos: PhotoSet
    documents: list[DocumentLink]
    gaps: list[str]
    missing_fields: list[str]   # the fields a dealer fallback may be asked about: characteristics / photos / instruction


def parse_product_page(html: str, url: str, catalog_article: str) -> SamsungCard:
    identity = extract_identity(html, url, catalog_article)
    specs = extract_spec_table(html)
    photos = extract_photos(html, url)
    documents = extract_document_links(html, url)
    gaps, missing = [], []
    if not identity.is_product_page:
        gaps.append("страница не является страницей товара (нет узла Product и таблицы характеристик)")
    if identity.level != "full_sku":
        gaps.append("полный артикул каталога на странице не подтверждён")
    if not specs:
        gaps.append("таблицы характеристик в статическом HTML нет")
        missing.append("характеристики")
    if not photos.photos:
        gaps.append(photos.gap or "фото не найдены")
        missing.append("фото")
    if not documents:
        gaps.append("ссылок на руководство на странице нет")
        missing.append("инструкция")
    return SamsungCard(url, identity, specs, photos, documents, gaps, missing)


def merge_dealer_fields(official: dict[str, object], dealer: dict[str, dict]) -> dict[str, dict]:
    """Dealer fallback, kept honest: a dealer value is added ONLY for a field the official page does not have, only when the dealer match is exact (model AND variant), and each
    added field carries its own source. An official value is never replaced; a differing dealer value is reported, not used.
    `dealer` maps field -> {"value", "source", "exact_model", "exact_variant"}."""
    merged: dict[str, dict] = {}
    for name, value in official.items():
        if value:
            merged[name] = {"value": value, "source": "official"}
    notes: list[dict] = []
    for name, item in dealer.items():
        if not (item.get("exact_model") and item.get("exact_variant")):
            notes.append({"field": name, "outcome": "rejected: dealer match is not exact model and variant"})
            continue
        if name in merged:
            if merged[name]["value"] != item["value"]:
                notes.append({"field": name, "outcome": "official value kept; dealer value differs", "dealer_value": item["value"], "dealer_source": item["source"]})
            continue
        merged[name] = {"value": item["value"], "source": item["source"]}
    merged["_notes"] = {"value": notes, "source": "merge"}
    return merged
