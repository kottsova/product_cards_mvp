"""Inspect the captured KZ pages without new requests."""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup

HERE=Path(__file__).resolve().parent
STAGE=HERE.parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from product_tool.adapters.structured_page import extract_json_ld_product

def inspect(entry):
    with gzip.open(STAGE/'route_check/responses'/entry['saved_as'],'rt',encoding='utf-8') as stream:
        html=stream.read()
    url=entry['final_url']
    fields=extract_json_ld_product(html,url)
    identity=[{"name":f.name,"value":f.value} for f in fields if f.name in ('name','sku','productID','gtin','gtin13','mpn')]
    specs=[{"name":f.name,"value":f.value} for f in fields if f.name not in ('name','sku','productID','gtin','gtin13','mpn','json_ld_image')]
    photos=[f.value for f in fields if f.name=='json_ld_image']
    soup=BeautifulSoup(html,'html.parser')
    anchors=[{"text":a.get_text(' ',strip=True)[:150],"href":a.get('href','')} for a in soup.select('a[href]') if '.pdf' in a.get('href','').lower()]
    decoded=html.replace('\\"','"').replace('\\/','/')
    docs=[]
    for match in re.finditer(r'https://media3\.bsh-group\.com/Documents/[^"\\\s<>]+?\.pdf',decoded,re.I):
        docs.append({"url":match.group(0),"context":decoded[max(0,match.start()-220):match.end()+160]})
    model='TWK7203' if 'TWK7203' in url else 'MMB2111M' if 'MMB2111M' in url else None
    enrs=sorted(set(re.findall(re.escape(model)+r'/\d{2}',html,re.I))) if model else []
    tracking=sorted(set(re.findall(r'"productId"\s*:\s*"([^" ]+)"',decoded)))[:20]
    return {"url":url,"identity":identity,"specifications":specs,"photos":photos,
            "pdf_anchors":anchors,"document_occurrences":docs,"enrs_printed":enrs,
            "tracking_product_ids":tracking,"body_contains_model":bool(model and model in soup.get_text(' ',strip=True))}

def main():
    index=[json.loads(x) for x in (STAGE/'route_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
    out={('TWK7203' if 'TWK7203' in e['final_url'] else 'MMB2111M' if 'MMB2111M' in e['final_url'] else 'blender_category'):inspect(e) for e in index}
    (STAGE/'raw/kz_page_extract.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for key,item in out.items():
        print(json.dumps({"product":key,"identity":item['identity'],"specifications":item['specifications'],
                          "photo_count":len(item['photos']),"photo_examples":item['photos'][:4],
                          "pdf_anchors":item['pdf_anchors'][:15],"documents":list(dict.fromkeys(x['url'] for x in item['document_occurrences'])),
                          "enrs_printed":item['enrs_printed'],"tracking_product_ids":item['tracking_product_ids'],
                          "body_contains_model":item['body_contains_model']},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
