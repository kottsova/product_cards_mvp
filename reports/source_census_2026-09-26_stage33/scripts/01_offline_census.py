"""Offline Samsung checkpoint and Bosch Home representative census."""
from __future__ import annotations
import hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
from product_tool.offline_guard import offline_only
from product_tool.coverage import planner
OBSERVED={
 'MMB2111M':('https://www.bosch-home.com/mt/en/mkt-product/MMB2111M','MT','product_tool/config/source_catalog.v2.json'),
 'TWK7203':('https://www.bosch-home.com/de/de/product/kuechengeraete/wasserkocher/TWK7203','DE','reports/source_census_2026-09-22_stage8_1/report.md'),
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 with offline_only():
  units=[json.loads(x) for x in (ROOT/'reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl').read_text(encoding='utf-8').splitlines() if x]
  samsung=[u for u in planner.build_plan()['units'] if u['family']=='samsung']
  selected=[u for u in samsung if u['status']=='ready_to_run']
  pending=json.loads((ROOT/'reports/source_census_2026-09-26_stage32/raw/remaining_categories.json').read_text(encoding='utf-8'))['remaining_categories']
  assert len(samsung)==1182 and len(selected)==20 and len({u['category'] for u in selected})==20 and len(pending)==11
  s32=json.loads((ROOT/'reports/source_census_2026-09-26_stage32/raw/route_check_result.json').read_text(encoding='utf-8'))
  samsung_out={'catalog_rows':len(samsung),'selected_products':len(selected),'selected_categories':len({u['category'] for u in selected}),'open_categories':[{**r,'new_page_identity':s32['results'][r['key']]['identity'] if r['key'] in s32['results'] else None} for r in pending],'charger_unselected':all(u['seller_sku']!='EP-T4511XBEGEU' for u in selected),'projector_unselected':all(u['seller_sku']!='SP-LSP3BLAXCE_SU' for u in selected),'smarttag_unselected':all(u['seller_sku']!='EI-T5600BWEGWW' for u in selected),'gps_classification_review':'SmartTag2 catalog category GPS trackers may need review; source catalog unchanged'}
  (STAGE/'raw/samsung_checkpoint.json').write_text(json.dumps(samsung_out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  bosch=[u for u in units if u['family']=='bosch_home']
  grouped={c:[u for u in bosch if u['category']==c] for c in sorted({u['category'] for u in bosch})}
  result=[]
  for category,rows in grouped.items():
   override='MMB2111M' if any(u['seller_sku']=='MMB2111M' for u in rows) else 'TWK7203' if any(u['seller_sku']=='TWK7203' for u in rows) else None
   if override:choice=next(u for u in rows if u['seller_sku']==override)
   else:
    clean=[u for u in rows if re.fullmatch(r'[A-Z0-9][A-Z0-9/-]*',u['seller_sku'].upper()) and u['seller_sku'].upper() in u['title'].upper()]
    choice=(clean or rows)[0]
   obs=OBSERVED.get(choice['seller_sku'])
   result.append({'category':category,'catalog_rows':len(rows),'representative_article':choice['seller_sku'],'representative_title':choice['title'],'catalog_row':choice['catalog_row'],'official_observed_url':obs[0] if obs else '','observed_market':obs[1] if obs else '','route_evidence':obs[2] if obs else '','route_status':'observed_other_market_product_candidate' if obs else 'no_observed_exact_product_route','classification_review':category in {'Пылесосы строительные','Триммеры садовые'}})
  assert len(bosch)==565 and len(result)==21 and sum(x['catalog_rows'] for x in result)==565
  assert [x['representative_article'] for x in result if x['official_observed_url']]==['MMB2111M','TWK7203']
  output={'family':'bosch_home','brand_catalog':'BOSCH','unique_products':len(bosch),'categories':result,'first_batch':['MMB2111M','TWK7203'],'basis':['reports/source_census_2026-09-22_stage8_1/report.md','reports/source_census_2026-09-24_stage18/report.md','product_tool/config/source_catalog.v2.json','reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl']}
  (STAGE/'raw/bosch_home_categories.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  declaration={'declared_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'first_batch':{sku:{'url':url,'market':market,'observed_in':basis} for sku,(url,market,basis) in OBSERVED.items()},'budget':{'max_real_requests_total':4,'max_per_product':2,'pacing_seconds':1.5,'page_cap_bytes':25000000,'document_cap_bytes':40000000,'dealer_requests':0,'image_requests':0,'stop':'401/403/429 or confirmed challenge stops host and run'},'catalog_sha256_before':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx'),'registry_sha256_before':sha(ROOT/'product_tool/config/source_catalog.v2.json'),'db_sha256_before':sha(ROOT/'data/batches.sqlite3')}
  (STAGE/'raw/bosch_route_declaration.json').write_text(json.dumps(declaration,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps({'samsung_selected':len(selected),'samsung_open':len(pending),'bosch_products':len(bosch),'bosch_categories':len(result),'batch':declaration['first_batch'],'budget':declaration['budget']},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
