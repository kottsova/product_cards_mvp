"""Source-labelled relations, including an explicitly historical HyperX comparison."""
import sys,json,gzip
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.structured_page import extract_shopify_product
R=Path(__file__).parent
sources=json.loads((R/'support_census.json').read_text(encoding='utf8'))
out={'origin':'source census, not card discovery','relations':[]}
hp=sources[1];hp_text=BeautifulSoup((R/hp['raw_path']).read_text(encoding='utf8'),'html.parser').get_text(' ',strip=True)
archive=Path('reports/source_census_2026-09-24_stage18/raw/pages/products_hyperx-cloud-iii-wired-gaming-headset.gz')
if archive.exists():
 product=extract_shopify_product(gzip.decompress(archive.read_bytes()).decode('utf8'),'https://hyperx.com/products/hyperx-cloud-iii-wired-gaming-headset')
 for code in ('727A8AA','727A9AA'):
  target=product.variant_by_sku(code) if product else None
  if code in hp_text and target:out['relations'].append({'hp_part_number':code,'hp_source':hp['url'],'hyperx_merchant_sku':target.sku,'hyperx_options':dict(target.options),'hyperx_provenance':'historical Stage18 official capture, not current live','archive':str(archive),'relation':'same literal code and named Cloud III wired product; not an alias to Cloud III Wireless'})
press=sources[2];text=BeautifulSoup((R/press['raw_path']).read_text(encoding='utf8'),'html.parser').get_text(' ',strip=True)
for code in ('4P5D6AA#ABA','4P5D6AN#UUW','4P5D6AX#ACB','56R64AA#ABA'):
 position=text.find(code)
 if position>=0:out['relations'].append({'published_part_number':code,'source':press['url'],'source_type':'official_press_part_number_table','context':text[max(0,position-60):position+len(code)+40],'current_retail_availability_confirmed':False,'current_exact_gallery_confirmed':False})
(R/'part_number_findings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(len(out['relations']))
