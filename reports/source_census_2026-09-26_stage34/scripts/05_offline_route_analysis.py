"""Offline conclusion from exactly three saved KZ route responses."""
from __future__ import annotations
import gzip,json,re,sys
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
from product_tool.offline_guard import offline_only
EXPECTED='https://www.bosch-home.com/kz/ru/product/kuhonnaya-tehnika/chajniki/TWK7203'
def main():
 with offline_only():
  ix=[json.loads(x) for x in (STAGE/'region_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
  assert len(ix)==3
  pages={}
  for e in ix:
   with gzip.open(STAGE/'region_check/responses'/e['saved_as'],'rt',encoding='utf-8') as h:html=h.read()
   pages[e['final_url']]=html
  home=pages['https://www.bosch-home.com/kz/ru'];kitchen=pages['https://www.bosch-home.com/kz/ru/category/kuhonnaya-tehnika'];kettle=pages['https://www.bosch-home.com/kz/ru/category/kuhonnaya-tehnika/chajniki']
  soup=BeautifulSoup(kettle,'html.parser')
  anchor=next(a for a in soup.select('a[href]') if urljoin('https://www.bosch-home.com',a['href'])==EXPECTED)
  teasers=[a for a in soup.select('a[href]') if 'TWK7203' in a['href']]
  mmb_mentions={url:html.upper().count('MMB2111M') for url,html in pages.items()}
  twk_mentions={url:html.upper().count('TWK7203') for url,html in pages.items()}
  blender_url='https://www.bosch-home.com/kz/ru/category/kuhonnaya-tehnika/blender'
  assert any(urljoin('https://www.bosch-home.com',a['href'])==blender_url for a in BeautifulSoup(kitchen,'html.parser').select('a[href]'))
  assert not any(mmb_mentions.values())
  assert '4242002901923' not in kettle and not re.search(r'TWK7203/\d{2}',kettle,re.I)
  result={'regional_home':'https://www.bosch-home.com/kz/ru','regional_kitchen_category':'https://www.bosch-home.com/kz/ru/category/kuhonnaya-tehnika','regional_kettle_category':'https://www.bosch-home.com/kz/ru/category/kuhonnaya-tehnika/chajniki','observed_kz_twk7203_candidate_url':EXPECTED,'kz_twk7203_teaser_count':len(teasers),'kz_twk7203_teaser_text':anchor.get_text(' ',strip=True),'kz_twk7203_teaser_has_gtin':False,'kz_twk7203_teaser_has_product_specific_revision':False,'kz_twk7203_primary_photo_same_as_de_page':'MCSA01013178_G6247_TWK7203_635924_kor_def.webp' in kettle,'kz_mmb2111m_mentions_on_checked_pages':mmb_mentions,'observed_but_unfetched_kz_blender_category':blender_url,'twk7203_status':'KZ category listing gives exact model URL candidate; product page content, E-Nr and local GTIN not checked; variant remains unconfirmed','mmb2111m_status':'No exact model route on three checked KZ pages; blender subcategory observed but not fetched within budget; variant remains unconfirmed','requests_spent':3,'next_small_category':{'category':'Кофемолки электрические','catalog_rows':3,'representative':'TSM6A011W','route':'not yet observed; offline route check first'}}
  (STAGE/'raw/regional_route_analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps(result,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
