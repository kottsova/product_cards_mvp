"""Read-only Stage 33 integrity and budget verification."""
from __future__ import annotations
import gzip,hashlib,json,sys
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import _pipeline_migration as mig
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.coverage import planner
from product_tool.offline_guard import offline_only
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 d=json.loads((STAGE/'raw/bosch_route_declaration.json').read_text(encoding='utf-8'))
 started=datetime.fromisoformat(d['declared_at']).timestamp()
 pins={p:mig.check_migrated_file(p,sha(ROOT/p))[0] for p in mig.ALL_AUTHORIZED_CHANGES}
 prior=[p for p in (ROOT/'reports').glob('source_census_*') if p!=STAGE]
 modified=sorted(p.relative_to(ROOT).as_posix() for directory in prior for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.stat().st_mtime>started)
 route=json.loads((STAGE/'raw/bosch_route_result.json').read_text(encoding='utf-8'))
 manual=json.loads((STAGE/'raw/bosch_manual_result.json').read_text(encoding='utf-8'))
 records=[json.loads(x) for x in (STAGE/'bosch_route/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
 hashes={}
 for e in records:
  if not e.get('saved_as'):continue
  with gzip.open(STAGE/'bosch_route/responses'/e['saved_as'],'rt',encoding='utf-8',newline='') as h:body=h.read()
  hashes[e['url']]=hashlib.sha256(body.encode('utf-8')).hexdigest()==e['sha256']
 pdf=next(e for e in records if e['url']==manual['url'])
 with gzip.open(STAGE/'bosch_route/responses'/pdf['saved_as'],'rt',encoding='utf-8',newline='') as h:pdf_bytes=h.read().encode('latin-1')
 log=STAGE/'bosch_route/workdir/bosch_fetch_log.json'
 entries=json.loads(log.read_text(encoding='utf-8')) if log.exists() else []
 with offline_only():
  plan=planner.build_plan()
  samsung=[u for u in plan['units'] if u['family']=='samsung']
  bosch=[u for u in plan['units'] if u['family']=='bosch_home']
 selected=[u for u in samsung if u['status']=='ready_to_run']
 s=json.loads((STAGE/'raw/samsung_checkpoint.json').read_text(encoding='utf-8'))
 cats=json.loads((STAGE/'raw/bosch_home_categories.json').read_text(encoding='utf-8'))
 result={'catalog_unchanged':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx')==d['catalog_sha256_before'],'registry_unchanged':sha(ROOT/'product_tool/config/source_catalog.v2.json')==d['registry_sha256_before'],'local_database_unchanged':sha(ROOT/'data/batches.sqlite3')==d['db_sha256_before'],'protected_pins_ok':all(pins.values()),'failed_pins':[p for p,ok in pins.items() if not ok],'prior_report_files_modified_since_declaration':modified,'selected_samsung_products':len(selected),'selected_samsung_categories':len({u['category'] for u in selected}),'samsung_catalog_rows':len(samsung),'samsung_open_categories':len(s['open_categories']),'bosch_products':len(bosch),'bosch_categories':len({u['category'] for u in bosch}),'bosch_representatives':len(cats['categories']),'bosch_first_batch_articles':cats['first_batch'],'requests_spent':route['budget']['spent']+manual['budget_spent_this_step'],'requests_within_budget':route['budget']['spent']+manual['budget_spent_this_step']<=d['budget']['max_real_requests_total'],'response_hashes_ok':len(hashes)==3 and all(hashes.values()),'document_raw_hash_ok':hashlib.sha256(pdf_bytes).hexdigest()==manual['sha256'],'stopped_hosts':sorted(stopped_hosts_from_fetch_log(x for x in entries if isinstance(x,dict))),'planner_config_unchanged_since_declaration':(ROOT/'product_tool/config/coverage_planner.v1.json').stat().st_mtime<=started,'samsung_variant_guards':{'charger_unselected':s['charger_unselected'],'projector_unselected':s['projector_unselected'],'smarttag_unselected':s['smarttag_unselected']}}
 (STAGE/'protected_hashes_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=True,indent=2))
 assert result['catalog_unchanged'] and result['registry_unchanged'] and result['local_database_unchanged'] and result['protected_pins_ok'] and not modified
 assert result['response_hashes_ok'] and result['document_raw_hash_ok'] and result['requests_within_budget'] and result['requests_spent']==3 and not result['stopped_hosts']
 assert (result['selected_samsung_products'],result['selected_samsung_categories'],result['samsung_catalog_rows'],result['samsung_open_categories'])==(20,20,1182,11)
 assert (result['bosch_products'],result['bosch_categories'],result['bosch_representatives'])==(565,21,21)
 assert result['planner_config_unchanged_since_declaration'] and all(result['samsung_variant_guards'].values())
if __name__=='__main__':main()
