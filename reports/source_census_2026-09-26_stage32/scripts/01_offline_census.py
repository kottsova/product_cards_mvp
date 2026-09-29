"""Stage 32 offline census and bounded route declaration; no network access."""
from __future__ import annotations
import hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from product_tool.adapters import samsung
from product_tool.adapters.sitemap_urls import sitemap_locs
from product_tool.offline_guard import offline_only
import _samsung_replay as R
CANDIDATES={
 'GPS':'EI-T5600BWEGWW',
 'HEADSET':'SM-R177NZKACISSM-R177NZKACIS',
 'CHARGER':'EP-T4511XBEGEU',
 'PLAYER':'MX-T40newMX-T40/RU',
 'MFP':'SS256M',
 'EARBUDS':'SM-R177NLVACISSM-R177NLVACIS',
 'RAM':'91581M323R2GA3BB0-CQKOL',
 'TABLET':'SM-X826BZARSKZ',
 'PROJECTOR':'SP-LSP3BLAXCE_SU',
 'WATCH':'SM-L325FDAAINS',
 'BAND':'SM-R390NZSACIS',
}
NOTES={
 'GPS':('other','other regional page only; EGWW exact route absent'),
 'HEADSET':('wearable_new_only','older Buds line; doubled catalog SKU; no exact route'),
 'CHARGER':('other','Stage 31 reviewed; GEU exact route absent; GRU is another variant; no repeat'),
 'PLAYER':('other','catalog SKU concatenated; no exact route'),
 'MFP':('other','clean catalog article; no exact route'),
 'EARBUDS':('wearable_new_only','older Buds2; doubled catalog SKU; no exact route'),
 'RAM':('other','catalog SKU has seller prefix/suffix; no exact route'),
 'TABLET':('tablet_new_only','Tab S10+ exact sitemap URL; novelty disproved by newer official tablet lines in Stage 24'),
 'PROJECTOR':('other','official page for base code SP-LSP3BLAXCE; catalog suffix _SU unverified'),
 'WATCH':('wearable_new_only','catalog Watch8 INS; KZ pages other regional codes; Watch7 is older'),
 'BAND':('wearable_new_only','Fit3 exact sitemap URL; novelty not established in Stage 29'),
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 with offline_only():
  units=[json.loads(x) for x in (ROOT/'reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl').read_text(encoding='utf-8').splitlines() if x]
  selected=json.loads((ROOT/'product_tool/config/coverage_planner.v1.json').read_text(encoding='utf-8'))['selected_products']['samsung']['products']
  categories={u['category'] for u in units if u['brand']=='Samsung'}-{x['category'] for x in selected}
  lists={u.rsplit('/',1)[-1]:sitemap_locs(body) for u,(status,body) in R.PAGES.items() if u.startswith('https://www.samsung.com/kz_ru/') and u.endswith('-sitemap.xml') and status==200}
  rows=[]
  for key,sku in CANDIDATES.items():
   product=next(u for u in units if u['brand']=='Samsung' and u['seller_sku']==sku)
   category=product['category']
   assert category in categories
   group=[u for u in units if u['brand']=='Samsung' and u['category']==category]
   exact=[{'article':u['seller_sku'],'sitemap':name,'url':url} for u in group for name,urls in lists.items() if (url:=samsung.find_in_sitemap(urls,u['seller_sku']))]
   related=[]
   if key=='GPS': related=[u for urls in lists.values() for u in urls if 'ei-t5600bwegru' in u.lower()]
   if key=='PROJECTOR': related=[u for urls in lists.values() for u in urls if 'sp-lsp3blaxce/' in u.lower()]
   if key=='CHARGER': related=[u for urls in lists.values() for u in urls if 'ep-t4511xbegru' in u.lower()]
   rule,note=NOTES[key]
   rows.append({'key':key,'category':category,'catalog_rows':len(group),'candidate_article':sku,'candidate_row':product['catalog_row'],'candidate_title':product['title'],'candidate_has_clean_sku':bool(re.fullmatch(r'[A-Z0-9][A-Z0-9-]*(?:/[A-Z0-9]+)?',sku)),'exact_sitemap_pages':exact,'related_observed_urls':related,'novelty_rule':rule,'assessment':note,'targeted_check':key in {'GPS','PROJECTOR'}})
  assert len(rows)==len(categories)==11 and len([r for r in rows if r['targeted_check']])==2
  out={'source_sitemaps':sorted(lists),'sitemap_url_counts':{k:len(v) for k,v in lists.items()},'selected_before':len(selected),'catalog_samsung_rows':len([u for u in units if u['brand']=='Samsung']),'remaining_categories':rows}
  (STAGE/'raw/remaining_categories.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  urls={key:next(r['related_observed_urls'][0] for r in rows if r['key']==key) for key in ('GPS','PROJECTOR')}
  declaration={'declared_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'offline_census':'raw/remaining_categories.json','products':{key:sku for key,sku in CANDIDATES.items() if key in {'GPS','PROJECTOR'}},'observed_urls':urls,'budget':{'max_real_requests_total':2,'max_per_product':1,'pacing_seconds':1.5,'page_cap_bytes':25000000,'dealer_requests':0,'images_requests':0,'stop':'401/403/429 or confirmed challenge stops host and run'},'catalog_sha256_before':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx'),'registry_sha256_before':sha(ROOT/'product_tool/config/source_catalog.v2.json'),'db_sha256_before':sha(ROOT/'data/batches.sqlite3')}
  (STAGE/'raw/route_declaration.json').write_text(json.dumps(declaration,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps({'remaining':len(rows),'selected_before':len(selected),'routes':urls,'declared_at':declaration['declared_at']},ensure_ascii=True))
if __name__=='__main__':main()
