"""Official LG Kazakhstan and Russia adapters."""
from __future__ import annotations

from dataclasses import dataclass
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

LG_KZ_SITEMAP = "https://www.lg.com/kz/sitemap.xml"
LG_RU_PRODUCT = "https://www.lg.com/ru/laundry/lg-{model}"
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


def lg_base_model(full_sku: str) -> str:
    normalized = normalize_lg_sku(full_sku)
    base, dot, suffix = normalized.rpartition(".")
    return base if dot and base and re.fullmatch(r"[A-Z]{5,}", suffix) else normalized


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
    for model, level in ((full_sku, "full_sku"), (base, "base_model")):
        match = re.search(rf"(?<![\w]){re.escape(model)}(?![\w])", text, re.I)
        if match:
            return model, level, clean_text(text[max(0, match.start()-90):match.end()+90])
    return "", "unknown", "Обозначение модели не найдено в видимом тексте страницы."


def extract_lg_attributes(soup: BeautifulSoup) -> list[RawAttribute]:
    facts: list[RawAttribute] = []
    for item in soup.select("#pdp-specs-section .c-compare-selling--all .c-compare-selling__item"):
        name = item.select_one(".c-compare-selling__spec-name")
        value = item.select_one(".c-compare-selling__spec-desc")
        if name and value and clean_text(value.get_text(" ", strip=True)):
            facts.append(RawAttribute(clean_text(name.get_text(" ", strip=True)), clean_text(value.get_text(" ", strip=True))))
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
            if not name or not value:
                continue
            duplicate = any(f.name == name for f in facts)
            facts.append(RawAttribute(f"{name} ({group_title})" if duplicate and group_title else name, value))
    return _dedupe_facts(facts)


def _dedupe_facts(facts: list[RawAttribute]) -> list[RawAttribute]:
    result, seen = [], set()
    for fact in facts:
        key = (fact.name, fact.value)
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


def extract_lg_photo_candidates(soup: BeautifulSoup, page_url: str, *, region: str) -> list[PhotoCandidate]:
    gallery_selectors = ("#popSummaryGallery img, #popSummaryGallery source, .c-summary-gallery img, .c-summary-gallery source" if region == "kz" else "#desktop_summary_gallery img, #desktop_summary_gallery source, #mobile_summary_gallery img, #mobile_summary_gallery source, #pdpGallery img, #pdpGallery source, .product-gallery img, .product-gallery source")
    candidates: list[PhotoCandidate] = []
    for node in soup.select(gallery_selectors):
        variants = _image_urls(node, page_url)
        if not variants:
            continue
        url, size = max(variants, key=lambda x: x[1])
        low = url.lower()
        if any(x in low for x in ("logo", "icon", "review", "sprite")):
            continue
        if region == "ru" and "/stylers/" not in low:
            continue
        clean_url = url.split("?", 1)[0]
        key = clean_url.lower()
        key = re.sub(r"(?i)(?:small|medium|large)_?(\d+)", r"image_\1", key)
        key = re.sub(r"(?i)_(?:small|medium|large)(\d+)(?:-new)?", r"_image_\1", key)
        candidates.append(PhotoCandidate(clean_url, key, "product_gallery", width=size or None))
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
    def __init__(self, http=None, *, clock: Callable[[], float] = time.monotonic):
        self.http, self.clock, self.request_count = http or lg_session(), clock, 0
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
        found, level, evidence = _designation(_visible_text(page.soup), full, base)
        photos = extract_lg_photo_candidates(page.soup, page.url, region="kz")
        return SourceDocument(self.source_key,self.site_name,page.url,found_model=found,match_level=level,evidence=evidence,attributes=extract_lg_attributes(page.soup),description=extract_lg_description(page.soup),photos=[p.url for p in photos if p.kind=="product_gallery"],photo_candidates=photos,html=str(page.soup))
    def find_source(self, full_sku, *, deadline):
        official_deadline=min(deadline,self.clock()+OFFICIAL_BUDGET_SECONDS); full=normalize_lg_sku(full_sku); base=lg_base_model(full)
        try:
            urls=self.sitemap_product_urls(official_deadline)
            for key in (lg_article_key(full),lg_article_key(base)):
                for url in [u for u in urls if _slug_key(u)==key][:MAX_CANDIDATES]:
                    doc=self._document(self.fetch_page(url,official_deadline),full,base)
                    if doc.match_level in ({"full_sku"} if key==lg_article_key(full) and full!=base else {"full_sku","base_model"}): return doc
                    if doc.match_level in {"full_sku","base_model"}: return doc
            return SourceDocument(self.source_key,self.site_name,"",match_level="mismatch",evidence="Страница артикула или базовой модели не найдена в LG sitemap.")
        except LGSourceError as exc:
            return SourceDocument(self.source_key,self.site_name,"",error=str(exc))
    def find_page(self, article):
        d=self.find_source(article,deadline=self.clock()+20)
        return LookupResult("exact" if d.match_level=="full_sku" else "needs_review" if d.match_level=="base_model" else "not_found",d.url,(d.url,) if d.url else (),d.evidence or d.error)


class LGRUAdapter:
    source_key, site_name = "lg_ru", "LG Россия"
    def __init__(self, http=None, *, clock: Callable[[], float] = time.monotonic):
        self.http, self.clock, self.request_count = http or lg_session(), clock, 0
    def find_source(self, full_sku, *, deadline):
        full=normalize_lg_sku(full_sku); base=lg_base_model(full); url=LG_RU_PRODUCT.format(model=base)
        try:
            self.request_count += 1; response=fetch_with_retry(self.http,url,deadline=deadline,clock=self.clock)
            soup=BeautifulSoup(response.text,"html.parser")
            if not soup.select_one("#pdp_spec, #overview"):
                raise LGSourceError("LG Россия не вернул ожидаемую карточку товара.")
            found,level,evidence=_designation(_visible_text(soup),full,base)
            photos=extract_lg_photo_candidates(soup,response.url,region="ru")
            return SourceDocument(self.source_key,self.site_name,response.url,found_model=found,match_level=level,evidence=evidence,attributes=extract_lg_ru_attributes(soup),description=extract_lg_ru_description(soup),photos=[p.url for p in photos if p.kind=="product_gallery"],photo_candidates=photos,html=response.text)
        except SourceError as exc:
            return SourceDocument(self.source_key,self.site_name,url,error=str(exc))
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