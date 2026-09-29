"""Official LG Kazakhstan and Russia adapters."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
import time
from typing import Callable
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

from .common import (PhotoCandidate, ProductDocument, RawAttribute, SourceDocument,
                     SourceError, clean_text, fetch_with_retry, meta_description)
from .supplier import find_full_sku

LG_KZ_SITEMAP = "https://www.lg.com/kz/sitemap.xml"
LG_RU_PRODUCT = "https://www.lg.com/ru/laundry/lg-{model}"  # legacy pattern, no longer requested: it answered 404 for every pilot row (Stage 20)
# Stage 21: the observed route to LG Russia product pages. https://www.lg.com/sitemap.xml lists https://www.lg.com/ru/index.xml, an index whose
# child https://www.lg.com/ru/sitemap.xml lists /ru/<category>/lg-<model> product URLs (11 of the 12 pilot rows are in it).
LG_RU_SITEMAP = "https://www.lg.com/ru/sitemap.xml"
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
    http.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"})
    return http


def normalize_lg_sku(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


_MARKET_TAG = re.compile(r"_(?:KZ|SU)$")


def lg_article_components(value: str) -> tuple[str, ...]:
    """Split explicit kits; keep a slash within a single article intact."""
    raw = str(value or "").strip()
    parts = tuple(normalize_lg_sku(part) for part in re.split(r"\s*\+\s*", raw))
    if len(parts) > 1 and all(re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{3,}", part) for part in parts):
        return parts
    # Slash, comma, ampersand or whitespace is a kit separator only when
    # BOTH full articles are present and share their base before the dot.
    pair = re.fullmatch(r"\s*([A-Za-z0-9][A-Za-z0-9._-]{3,})\s*(?:/|,|&|\s+)\s*([A-Za-z0-9][A-Za-z0-9._-]{3,})\s*", raw)
    if pair:
        left, right = (normalize_lg_sku(part) for part in pair.groups())
        first_base, first_dot, _ = left.rpartition(".")
        second_base, second_dot, _ = right.rpartition(".")
        if first_dot and second_dot and first_base == second_base:
            return left, right
    return (normalize_lg_sku(value),)


def lg_base_model(full_sku: str) -> str:
    """The base model used to FIND a candidate page. A trailing market tag "_KZ" / "_SU" of the seller's article is dropped here and only here (owner decision,
    Stage 23): the page found through the base model is a base_model match until the FULL article is confirmed by the official content itself."""
    components = lg_article_components(full_sku)
    if len(components) > 1:
        bases = tuple(lg_base_model(part) for part in components)
        return bases[0] if len(set(bases)) == 1 else normalize_lg_sku(full_sku)
    untagged = _MARKET_TAG.sub("", components[0])
    base, dot, suffix = untagged.rpartition(".")
    return base if dot and base and re.fullmatch(r"[A-Z]{3,}", suffix) else untagged


def lg_article_key(article: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_lg_sku(article).lower())


def lg_article_lookup_keys(article: str) -> list[str]:
    return list(dict.fromkeys(filter(None, (lg_article_key(article), lg_article_key(lg_base_model(article))))))


def lg_is_product_url(url: str) -> bool:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.lower().split("/") if part]
    return parsed.scheme == "https" and parsed.netloc.lower() == "www.lg.com" and len(parts) >= 3 and parts[0] in {"kz", "ru"} and not any(x in parts for x in {"support", "search", "sitemap"})


def _slug_key(url: str) -> str:
    return lg_article_key(unquote(urlparse(url).path.rstrip("/").split("/")[-1]).removeprefix("lg-"))


def lg_url_matches_article(url: str, article: str) -> bool:
    return lg_is_product_url(url) and _slug_key(url) in lg_article_lookup_keys(article)


def _visible_text(soup: BeautifulSoup) -> str:
    clone = BeautifulSoup(str(soup), "html.parser")
    for tag in clone.select("script, style, template, noscript"):
        tag.decompose()
    return clean_text(clone.get_text(" ", strip=True))


def _designation(text: str, full_sku: str, base: str) -> tuple[str, str, str]:
    found, evidence = find_full_sku(text, full_sku)
    if found:
        return found, "full_sku", evidence
    match = re.search(rf"(?<![\w]){re.escape(base)}(?![\w])", text, re.I)
    if match:
        return base, "base_model", clean_text(text[max(0, match.start()-90):match.end()+90])
    return "", "unknown", "\u041e\u0431\u043e\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u043c\u043e\u0434\u0435\u043b\u0438 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e \u0432 \u0432\u0438\u0434\u0438\u043c\u043e\u043c \u0442\u0435\u043a\u0441\u0442\u0435 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b."

def _product_designation(soup: BeautifulSoup, full_sku: str, base: str, *, region: str) -> tuple[str, str, str]:
    """Read the main PDP's own sales code, not a URL or a related-product tile."""
    values: list[tuple[str, str]] = []
    if region == "kz":
        for node in soup.select(".price-area__PD0033[data-analytics]"):
            try:
                code = json.loads(node.get("data-analytics", "{}")).get("data-pim-sku", "")
            except (ValueError, TypeError):
                continue
            if code:
                values.append((str(code), "data-pim-sku"))
    elif region == "ru":
        for node in soup.select(".GPC0009[data-adobe-salesmodelcode]"):
            code = node.get("data-adobe-salesmodelcode", "")
            suffix = node.get("data-adobe-salessuffixcode", "")
            if code and suffix:
                values.append((f"{code}.{suffix}", "data-adobe-salesmodelcode + data-adobe-salessuffixcode"))
    expected = normalize_lg_sku(full_sku)
    from ..lg_identity import structured_sales_relation
    exact = [(code, field) for code, field in values
             if structured_sales_relation(full_sku, code) == "exact"]
    if exact and len(exact) == len(values):
        code, field = exact[0]
        return expected, "full_sku", f"Полный артикул в поле {field} основной карточки LG: {code}."
    # A main PDP code for another variant, or several different PDP codes,
    # cannot be overridden by full-code text elsewhere on the page.
    if values:
        visible = _visible_text(soup)
        if re.search(rf"(?<![\w]){re.escape(base)}(?![\w])", visible, re.I):
            return base, "base_model", "Основная карточка LG не подтверждает полный артикул; видна только базовая модель."
        return "", "unknown", "Основная карточка LG не подтверждает полный артикул."
    return _designation(_visible_text(soup), full_sku, base)


def _support_page_sales_code(html_text: str) -> str:
    """The ONE sales code an LG support page (`/ru/support/product/lg-<code>`) itself prints as ITS OWN
    product (Stage 43: a page reached this way, including via a full-article URL, commonly redirects to
    the shared base model and then names only ONE -- not necessarily our target -- variant's own code)."""
    soup = BeautifulSoup(html_text, "html.parser")
    node = soup.select_one("[data-product-id]")
    return normalize_lg_sku(node.get("data-product-id", "")) if node else ""


def _augment_with_browser_search(doc: SourceDocument, adapter, full: str, base: str, deadline: float, *, region: str) -> SourceDocument:
    """Stage 43: after the sitemap failed to reach full_sku, ask LG's own site search (a bounded, real
    browser render -- see adapters/lg_browser_search.py) and add what it found as EVIDENCE TEXT ONLY.
    A search hit is never enough by itself to upgrade match_level: only the CANDIDATE PAGE'S OWN printed
    code, fetched and read like any other official page, counts -- exactly the project's existing rule for
    support pages (a URL/label containing the article proves nothing on its own)."""
    if adapter.browser_search is None:
        return doc
    notes: list[str] = []
    for component in lg_article_components(full):
        component_base = lg_base_model(component)
        queries = [component] if component == component_base else [component, component_base]
        result = adapter.browser_search.search(region, queries)
        if result.outcome != "candidates_found":
            if result.note:
                notes.append(result.note)
            continue
        for candidate in result.candidates:
            try:
                response = fetch_with_retry(adapter.http, candidate.url, deadline=deadline, clock=adapter.clock)
            except SourceError as exc:
                notes.append(f"Не удалось открыть кандидата поиска LG ({region}) {candidate.url}: {exc}")
                continue
            # Keep a verified support hit as a candidate for the ordinary support
            # evidence step. The search label and URL never establish identity.
            from .lg_support import is_official_support_url, printed_support_codes, registration_component_codes
            if not is_official_support_url(response.url):
                notes.append(f"LG support candidate redirected off the official support route: {response.url}.")
                continue
            codes = (*printed_support_codes(response.text), *registration_component_codes(response.text, response.url))
            code = codes[0] if codes else ""
            if normalize_lg_sku(component) in codes:
                adapter.support_candidate_urls.append(response.url)
                adapter.support_candidate_pages[response.url] = response.text
                notes.append(f"Поиск LG ({region}) подтвердил артикул «{component}» на официальной странице поддержки: {response.url}.")
            elif code:
                notes.append(f"Поиск LG ({region}) нашёл «{component}» в результатах, но открытая страница поддержки показывает другой код: {code} ({response.url}); артикул этим источником не подтверждён.")
            else:
                notes.append(f"Страница-кандидат поиска LG ({region}) не содержит распознаваемого кода товара: {response.url}.")
    notes = list(dict.fromkeys(notes))  # several candidate links commonly redirect to the same support page; do not repeat the same sentence
    if not notes:
        return doc
    return replace(doc, evidence=(doc.evidence + " " if doc.evidence else "") + " ".join(notes), fetched_at=doc.fetched_at)


def extract_lg_attributes(soup: BeautifulSoup) -> list[RawAttribute]:
    facts: list[RawAttribute] = []
    for table in soup.select("#pdp-specs-section .c-compare-selling--all .c-compare-selling__table"):
        heading = table.select_one("h2, h3, h4")
        section = clean_text(heading.get_text(" ", strip=True)) if heading else ""
        for item in table.select(".c-compare-selling__item"):
            name = item.select_one(".c-compare-selling__spec-name")
            value = item.select_one(".c-compare-selling__spec-desc")
            if name and value and clean_text(name.get_text(" ", strip=True)):
                facts.append(RawAttribute(clean_text(name.get_text(" ", strip=True)), clean_text(value.get_text(" ", strip=True)), section, True))
    return _dedupe_facts(facts)


def extract_lg_ru_attributes(soup: BeautifulSoup) -> list[RawAttribute]:
    facts: list[RawAttribute] = []
    for group in soup.select("#pdp_spec .tech-spacs"):
        title_node = group.select_one(".tech-spacs-title")
        group_title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
        for row in group.select(".tech-spacs-contents dl"):
            dt, dd = row.find("dt"), row.find("dd")
            if not dt or not dd:
                continue
            name, value = clean_text(dt.get_text(" ", strip=True)), clean_text(dd.get_text(" ", strip=True))
            if not name:
                continue
            facts.append(RawAttribute(name, value, group_title, True))
    return _dedupe_facts(facts)


def _dedupe_facts(facts: list[RawAttribute]) -> list[RawAttribute]:
    result, seen = [], set()
    for fact in facts:
        key = (fact.section, fact.name, fact.value, fact.value_cell)
        if key not in seen:
            seen.add(key); result.append(fact)
    return result


def extract_lg_description(soup: BeautifulSoup) -> str:
    overview = soup.select_one("#pdp-overview-section")
    if overview:
        text = [clean_text(x) for x in overview.stripped_strings if clean_text(x)]
        if text:
            return "\n".join(dict.fromkeys(text))
    return _jsonld_description(soup) or meta_description(soup)


def extract_lg_ru_description(soup: BeautifulSoup) -> str:
    overview = soup.select_one("#overview")
    blocks: list[str] = []
    banned = re.compile(r"купить|отзыв|поддержк|где купить|интернет-магазин", re.I)
    if overview:
        nodes = list(overview.select(".text-block"))
        if not nodes:
            nodes = [heading.find_parent(["section", "div"]) or heading for heading in overview.select("h2, h3")]
        for node in nodes:
            heading = node.select_one(".title h2, .title h3, h2, h3")
            copies = node.select(".copy, p")
            title = clean_text(heading.get_text(" ", strip=True)) if heading else ""
            body = " ".join(dict.fromkeys(clean_text(x.get_text(" ", strip=True)) for x in copies if clean_text(x.get_text(" ", strip=True))))
            combined = "\n\n".join(x for x in (title, body) if x)
            if title and body and len(body) > 20 and not banned.search(combined) and combined not in blocks:
                blocks.append(combined)
    return "\n\n".join(blocks) or _jsonld_description(soup) or meta_description(soup)


def _jsonld_description(soup: BeautifulSoup) -> str:
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.string or "{}")
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("description"):
                return clean_text(item["description"])
    return ""


def _image_urls(node, page_url: str) -> list[tuple[str, int]]:
    values: list[tuple[str, int]] = []
    for attr in ("src", "data-src", "data-original", "data-zoom-image"):
        raw = node.get(attr, "")
        if raw:
            values.append((urljoin(page_url, raw), 0))
    for attr in ("srcset", "data-srcset"):
        for part in node.get(attr, "").split(","):
            bits = part.strip().split()
            if bits:
                size = int(re.sub(r"\D", "", bits[1])) if len(bits) > 1 and re.search(r"\d", bits[1]) else 0
                values.append((urljoin(page_url, bits[0]), size))
    return values


_RU_GALLERY_FILE = re.compile(r"/ru/images/[^/]+/md\d+/(?:gallery/)?[^/]+\.(?:jpe?g|png|webp)$")


def _ru_image_variants(node, page_url: str) -> list[tuple[str, int]]:
    """LG Russia gallery nodes: data-large > data-zoom-image > data-medium > data-original > data-src > src (higher rank = larger picture)."""
    values: list[tuple[str, int]] = []
    for rank, attr in enumerate(("src", "data-src", "data-original", "data-medium", "data-zoom-image", "data-large"), start=1):
        raw = node.get(attr, "")
        if raw:
            values.append((urljoin(page_url, raw), rank))
    return values


def extract_lg_photo_candidates(soup: BeautifulSoup, page_url: str, *, region: str) -> list[PhotoCandidate]:
    gallery_selectors = ("#popSummaryGallery img, #popSummaryGallery source, .c-summary-gallery img, .c-summary-gallery source" if region == "kz" else "#desktop_summary_gallery img, #desktop_summary_gallery source, #mobile_summary_gallery img, #mobile_summary_gallery source, #pdpGallery img, #pdpGallery source, .product-gallery img, .product-gallery source")
    candidates: list[PhotoCandidate] = []
    for node in soup.select(gallery_selectors):
        variants = _image_urls(node, page_url)
        if region == "ru":  # Stage 22: a thumbnail's own large picture is in data-medium/data-large; take the largest variant the node names
            variants = _ru_image_variants(node, page_url) or variants
        if not variants:
            continue
        url, size = max(variants, key=lambda x: x[1])
        low = url.lower()
        if any(x in low for x in ("logo", "icon", "review", "sprite")):
            continue
        if region == "ru" and "/stylers/" not in low and not _RU_GALLERY_FILE.search(low.split("?", 1)[0]):  # observed: /ru/images/<category>/<md...>/[gallery/]<file>; the objet placeholder is elsewhere
            continue
        clean_url = url.split("?", 1)[0]
        key = clean_url.lower()
        key = re.sub(r"(?i)(?:small|medium|large)_?(\d+)", r"image_\1", key)
        key = re.sub(r"(?i)_(?:small|medium|large)(\d+)(?:-new)?", r"_image_\1", key)
        candidates.append(PhotoCandidate(clean_url, key, "product_gallery", width=None if region == "ru" else (size or None)))
    overview = soup.select_one("#overview, #pdp-overview-section")
    if overview:
        for node in overview.select("img, source"):
            variants = _image_urls(node, page_url)
            if variants:
                url, size = max(variants, key=lambda x: x[1])
                if not any(x in url.lower() for x in ("logo", "icon")):
                    candidates.append(PhotoCandidate(url.split("?",1)[0], re.sub(r"[?#].*$", "", url.lower()), "feature", width=size or None))
    dedup: dict[str, PhotoCandidate] = {}
    def quality(item):
        low=item.url.lower()
        return (3 if "large" in low else 2 if "medium" in low else 1 if "small" in low else 4, item.width or 0)
    for item in candidates:
        if item.asset_key not in dedup or quality(item) > quality(dedup[item.asset_key]): dedup[item.asset_key]=item
    return list(dedup.values())


def extract_lg_photos(soup: BeautifulSoup, page_url: str) -> list[str]:
    return [x.url for x in extract_lg_photo_candidates(soup, page_url, region="kz") if x.kind == "product_gallery"]


class LGAdapter:
    source_key, site_name = "lg_kz", "LG Казахстан"
    def __init__(self, http=None, *, clock: Callable[[], float] = time.monotonic, browser_search=None):
        self.http, self.clock, self.request_count = http or lg_session(), clock, 0
        self.browser_search = browser_search  # Existing bounded LG site-search route.
        self.support_candidate_urls: list[str] = []  # Content-tied hits passed to support verification.
        self.support_candidate_pages: dict[str, str] = {}  # Reuse the response; no second request.
    def _get(self, url, deadline):
        self.request_count += 1
        try: return fetch_with_retry(self.http, url, deadline=deadline, clock=self.clock)
        except SourceError as exc: raise LGSourceError(str(exc)) from exc
    def sitemap_product_urls(self, deadline):
        response = self._get(LG_KZ_SITEMAP, deadline)
        try: root = ET.fromstring(response.content)
        except ET.ParseError as exc: raise LGSourceError(f"Некорректный LG sitemap: {exc}") from exc
        return [(n.text or "").strip() for n in root.iter() if (n.tag.endswith("}loc") or n.tag == "loc") and lg_is_product_url((n.text or "").strip())]
    def fetch_page(self, url, deadline=None):
        response = self._get(url, deadline or self.clock()+10)
        soup = BeautifulSoup(response.text, "html.parser")
        if not soup.select_one("h1") or not soup.select_one("#pdp-specs-section, #pdp-overview-section"):
            raise LGSourceError("LG Казахстан не вернул ожидаемую карточку товара.")
        return ProductPage(response.url, soup)
    def _document(self, page, full, base):
        found, level, evidence = _product_designation(page.soup, full, base, region="kz")
        photos = extract_lg_photo_candidates(page.soup, page.url, region="kz")
        return SourceDocument(self.source_key,self.site_name,page.url,found_model=found,match_level=level,evidence=evidence,attributes=extract_lg_attributes(page.soup),description=extract_lg_description(page.soup),photos=[p.url for p in photos if p.kind=="product_gallery"],photo_candidates=photos,html=str(page.soup))
    def find_source(self, full_sku, *, deadline, fallback_models=()):
        official_deadline=min(deadline,self.clock()+OFFICIAL_BUDGET_SECONDS); full=normalize_lg_sku(full_sku); base=lg_base_model(full)
        try:
            urls=self.sitemap_product_urls(official_deadline)
            doc=None
            for model in dict.fromkeys((full,base,*fallback_models)):
                key=lg_article_key(model)
                for url in [u for u in urls if _slug_key(u)==key][:MAX_CANDIDATES]:
                    doc=self._document(self.fetch_page(url,official_deadline),full,base if model in (full,base) else model)
                    if doc.match_level in {"full_sku","base_model"}: break
                if doc is not None and doc.match_level in {"full_sku","base_model"}: break
                doc=None
            if doc is None:
                doc=SourceDocument(self.source_key,self.site_name,"",match_level="mismatch",evidence="Страница артикула или базовой модели не найдена в LG sitemap.")
            if doc.match_level!="full_sku":
                doc=_augment_with_browser_search(doc,self,full,base,official_deadline,region="kz")
            return doc
        except LGSourceError as exc:
            return SourceDocument(self.source_key,self.site_name,"",error=str(exc))
    def find_page(self, article):
        d=self.find_source(article,deadline=self.clock()+20)
        return LookupResult("exact" if d.match_level=="full_sku" else "needs_review" if d.match_level=="base_model" else "not_found",d.url,(d.url,) if d.url else (),d.evidence or d.error)


class LGRUAdapter:
    source_key, site_name = "lg_ru", "LG Россия"
    def __init__(self, http=None, *, clock: Callable[[], float] = time.monotonic, browser_search=None):
        self.http, self.clock, self.request_count = http or lg_session(), clock, 0
        self.browser_search = browser_search  # Existing bounded LG site-search route.
        self.support_candidate_urls: list[str] = []  # Content-tied hits passed to support verification.
        self.support_candidate_pages: dict[str, str] = {}  # Reuse the response; no second request.
    def sitemap_product_urls(self, deadline):
        self.request_count += 1
        response = fetch_with_retry(self.http, LG_RU_SITEMAP, deadline=deadline, clock=self.clock)
        try: root = ET.fromstring(response.content)
        except ET.ParseError as exc: raise LGSourceError(f"Некорректный LG Россия sitemap: {exc}") from exc
        return [(n.text or "").strip() for n in root.iter() if (n.tag.endswith("}loc") or n.tag == "loc") and lg_is_product_url((n.text or "").strip())]
    def _document_at(self, url, full, base, deadline):
        self.request_count += 1; response=fetch_with_retry(self.http,url,deadline=deadline,clock=self.clock)
        soup=BeautifulSoup(response.text,"html.parser")
        if not soup.select_one("#pdp_spec, #overview"):
            raise LGSourceError("LG Россия не вернул ожидаемую карточку товара.")
        found,level,evidence=_product_designation(soup,full,base,region="ru")
        photos=extract_lg_photo_candidates(soup,response.url,region="ru")
        return SourceDocument(self.source_key,self.site_name,response.url,found_model=found,match_level=level,evidence=evidence,attributes=extract_lg_ru_attributes(soup),description=extract_lg_ru_description(soup),photos=[p.url for p in photos if p.kind=="product_gallery"],photo_candidates=photos,html=response.text)
    def find_source(self, full_sku, *, deadline, fallback_models=()):
        full=normalize_lg_sku(full_sku); base=lg_base_model(full)
        try:
            urls=self.sitemap_product_urls(deadline)
            doc=None
            for model in dict.fromkeys((full,base,*fallback_models)):
                key=lg_article_key(model)
                for url in [u for u in urls if _slug_key(u)==key][:MAX_CANDIDATES]:
                    doc=self._document_at(url,full,base if model in (full,base) else model,deadline)
                    if doc.match_level in {"full_sku","base_model"}: break
                if doc is not None and doc.match_level in {"full_sku","base_model"}: break
                doc=None
            if doc is None:
                doc=SourceDocument(self.source_key,self.site_name,"",match_level="mismatch",evidence="Страница артикула или базовой модели не найдена в sitemap LG Россия.")
            if doc.match_level!="full_sku":
                doc=_augment_with_browser_search(doc,self,full,base,deadline,region="ru")
            return doc
        except SourceError as exc:
            return SourceDocument(self.source_key,self.site_name,"",error=str(exc))
    def find_documents(self, document: SourceDocument, product_model: str, *, deadline: float) -> tuple[list[ProductDocument], str]:
        soup=BeautifulSoup(document.html or "", "html.parser")
        links=[]
        for a in soup.select('a[href*="/ru/support/"]'):
            href=urljoin(document.url,a.get("href","")); text=clean_text(a.get_text(" ",strip=True))
            if href and ("manual" in href.lower() or "product" in href.lower()): links.append((href,text))
        raw=" ".join(x[0]+" "+x[1] for x in links)
        match=re.search(r"(S3RERB(?:\.[A-Z0-9]+)?)",raw,re.I)
        if not match:
            return [], "Официальная связь с моделью поддержки не найдена на странице товара."
        support_model=match.group(1).upper(); support_url=next((u for u,_ in links if "/support/product/" in u.lower()), "") or next((u for u,_ in links if "support" in u),"")
        if not support_url: return [], "Официальная страница поддержки не найдена."
        try:
            response=fetch_with_retry(self.http,support_url,deadline=deadline,clock=self.clock)
        except SourceError as exc:
            return [], str(exc)
        final_model = re.search(r"lg-([A-Z0-9]+)", response.url, re.I)
        if final_model: support_model = final_model.group(1).upper()
        support_soup=BeautifulSoup(response.text,"html.parser"); docs=[]
        for a in support_soup.select('a[href*="downloadFile"], a[href*="gscs-b2c.lge.com"]'):
            container=a.find_parent(["li","tr","div"]) or a
            text=clean_text(container.get_text(" ",strip=True))
            if not re.search(r"русск|russian",text,re.I): continue
            date=(re.search(r"\d{2}[./-]\d{2}[./-]\d{4}|\d{4}[./-]\d{2}[./-]\d{2}",text) or [""])[0]
            size=(re.search(r"\d+(?:[.,]\d+)?\s*(?:MB|KB|МБ|КБ)",text,re.I) or [""])[0]
            docs.append(ProductDocument(clean_text(a.get("title") or a.get_text(" ",strip=True) or "Руководство пользователя"),"Русский",date,size,urljoin(response.url,a.get("href","")),response.url,product_model,support_model,document.url))
        docs.sort(key=lambda x:x.document_date,reverse=True)
        return [ProductDocument(**{**d.__dict__,"primary":i==0}) for i,d in enumerate(docs)], "" if docs else "Русские инструкции на официальной странице поддержки не найдены."
