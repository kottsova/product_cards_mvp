"""Helpers shared by LG trusted fallback suppliers."""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup
from .common import PhotoCandidate, RawAttribute, clean_text

def visible_text(soup):
    clone=BeautifulSoup(str(soup),"html.parser")
    for tag in clone.select("script, style, template, noscript"): tag.decompose()
    return clean_text(clone.get_text(" ",strip=True))

def find_full_sku(text, full_sku):
    match=re.search(rf"(?<![\w]){re.escape(full_sku)}(?![\w])",text,re.I)
    return (full_sku.upper(),clean_text(text[max(0,match.start()-90):match.end()+90])) if match else ("","")

def extract_table_attributes(soup):
    pairs=[]
    for row in soup.select("table tr, .characteristics tr, .specifications tr"):
        cells=row.find_all(["th","td"],recursive=False)
        if len(cells)>=2: pairs.append((cells[0].get_text(" ",strip=True),cells[-1].get_text(" ",strip=True)))
    for node in soup.select("dl"):
        pairs.extend((a.get_text(" ",strip=True),b.get_text(" ",strip=True)) for a,b in zip(node.find_all("dt"),node.find_all("dd")))
    for item in soup.select(".characteristics__item, .specification-item, .product-characteristics__item, [class*='characteristic'] [class*='item'], [class*='specification'] [class*='item']"):
        parts=[clean_text(x.get_text(" ",strip=True)) for x in item.find_all(recursive=False)]
        parts=[x for x in parts if x]
        if len(parts)==2: pairs.append((parts[0],parts[1]))
    result=[]; seen=set()
    for name,value in pairs:
        key=(clean_text(name),clean_text(value))
        if key[0] and key[1] and key not in seen and key[0]!=key[1]: seen.add(key); result.append(RawAttribute(*key))
    return result

def _sulpak_asset(url):
    parts=urlsplit(url); path=re.sub(r"_(160|320)(?=\.[^.]+$)","",parts.path,flags=re.I)
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),path.lower(),"",""))

def extract_photo_candidates(soup, page_url, *, source_key):
    found=[]
    for image in soup.select("img, picture source"):
        variants=[]
        for attr in ("src","data-src","data-original","data-zoom-image"):
            if image.get(attr): variants.append((urljoin(page_url,image.get(attr)),0))
        for attr in ("srcset","data-srcset"):
            for part in image.get(attr,"").split(","):
                bits=part.strip().split()
                if bits: variants.append((urljoin(page_url,bits[0]),int(re.sub(r"\D","",bits[1])) if len(bits)>1 and re.search(r"\d",bits[1]) else 0))
        for url,size in variants:
            low=url.lower(); reason=""; kind="product_gallery"
            if source_key=="sulpak":
                garbage=("/banners/","/wwwroot/img/","cashback","city.webp","sulpak_logo","sulpak-dos","sbonus",".svg")
                if any(x in low for x in garbage): kind,reason="excluded","Служебное изображение Sulpak"
                elif "/lg.com/ru/images/" in low and "/features/" in low: kind="feature"
                elif "/cms/cms/photo/" not in low: kind,reason="excluded","Изображение не относится к товарной галерее Sulpak"
                key=_sulpak_asset(url)
            else:
                key=re.sub(r"[?#].*$","",low)
                if any(x in low for x in ("logo","banner","icon","sprite",".svg")): kind,reason="excluded","Служебное изображение"
            found.append(PhotoCandidate(url,key,kind,width=size or None,excluded_reason=reason))
    best={}
    for item in found:
        previous=best.get(item.asset_key)
        score=(0 if re.search(r"_(160|320)(?=\.[^.]+$)",urlsplit(item.url).path,re.I) else 100000)+(item.width or 0)
        prevscore=-1 if not previous else ((0 if re.search(r"_(160|320)(?=\.[^.]+$)",urlsplit(previous.url).path,re.I) else 100000)+(previous.width or 0))
        if score>prevscore: best[item.asset_key]=item
    return list(best.values())

def extract_photos(soup,page_url):
    return [x.url for x in extract_photo_candidates(soup,page_url,source_key="generic") if x.kind!="excluded"]