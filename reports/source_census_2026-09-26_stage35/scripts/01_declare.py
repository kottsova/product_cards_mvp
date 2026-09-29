"""Offline route provenance and Stage 35 request declaration."""
from __future__ import annotations
import gzip,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
from product_tool.offline_guard import offline_only
S34=ROOT/'reports/source_census_2026-09-26_stage34'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 with offline_only():
  evidence=json.loads((S34/'raw/regional_route_analysis.json').read_text(encoding='utf-8'))
  ix=[json.loads(x) for x in (S34/'region_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
  kettle_index=next(x for x in ix if x['final_url']==evidence['regional_kettle_category'])
  kitchen_index=next(x for x in ix if x['final_url']==evidence['regional_kitchen_category'])
  with gzip.open(S34/'region_check/responses'/kettle_index['saved_as'],'rt',encoding='utf-8') as h:kettle=BeautifulSoup(h.read(),'html.parser')
  with gzip.open(S34/'region_check/responses'/kitchen_index['saved_as'],'rt',encoding='utf-8') as h:kitchen=BeautifulSoup(h.read(),'html.parser')
  twk=evidence['observed_kz_twk7203_candidate_url'];blenders=evidence['observed_but_unfetched_kz_blender_category']
  assert any(urljoin(kettle_index['final_url'],a.get('href',''))==twk for a in kettle.select('a[href]'))
  assert any(urljoin(kitchen_index['final_url'],a.get('href',''))==blenders for a in kitchen.select('a[href]'))
  record={'TWK7203':{'observed_url':twk,'parent_saved_page':kettle_index['final_url']},'MMB2111M':{'observed_category_url':blenders,'parent_saved_page':kitchen_index['final_url'],'product_url':'only if the KZ category itself prints one'}}
  (STAGE/'raw/route_provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  d={'declared_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'products':['TWK7203','MMB2111M'],'starting_urls':{'TWK7203':twk,'MMB2111M_category':blenders},'allowed_hosts':['www.bosch-home.com','media3.bsh-group.com'],'budget':{'max_real_requests_total':4,'max_product_and_category_gets':3,'max_documents':1,'pacing_seconds':1.5,'page_cap_bytes':25000000,'document_cap_bytes':40000000,'image_requests':0,'dealer_requests':0,'stop':'401/403/429 or confirmed challenge stops the host and remaining work'},'catalog_sha256_before':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx'),'registry_sha256_before':sha(ROOT/'product_tool/config/source_catalog.v2.json'),'planner_sha256_before':sha(ROOT/'product_tool/config/coverage_planner.v1.json'),'db_sha256_before':sha(ROOT/'data/batches.sqlite3')}
  (STAGE/'raw/declaration.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps({'routes':record,'allowed_hosts':d['allowed_hosts'],'budget':d['budget'],'declared_at':d['declared_at']},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
