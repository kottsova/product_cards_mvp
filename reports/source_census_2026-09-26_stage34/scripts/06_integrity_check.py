"""Read-only Stage 34 integrity, budget and planner guard check."""
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
 d=json.loads((STAGE/'raw/regional_declaration.json').read_text(encoding='utf-8'))
 started=datetime.fromisoformat(d['declared_at']).timestamp()
 pins={p:mig.check_migrated_file(p,sha(ROOT/p))[0] for p in mig.ALL_AUTHORIZED_CHANGES}
 prior=[p for p in (ROOT/'reports').glob('source_census_*') if p!=STAGE]
 modified=sorted(p.relative_to(ROOT).as_posix() for directory in prior for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.stat().st_mtime>started)
 records=[json.loads(x) for x in (STAGE/'region_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
 hashes={}
 for e in records:
  if e['saved_as']:
   with gzip.open(STAGE/'region_check/responses'/e['saved_as'],'rt',encoding='utf-8',newline='') as h:body=h.read()
   hashes[e['url']]=hashlib.sha256(body.encode('utf-8')).hexdigest()==e['sha256']
 route=json.loads((STAGE/'raw/region_kettle_result.json').read_text(encoding='utf-8'))
 result=json.loads((STAGE/'raw/regional_route_analysis.json').read_text(encoding='utf-8'))
 log=STAGE/'region_check/workdir/bosch_fetch_log.json'
 entries=json.loads(log.read_text(encoding='utf-8')) if log.exists() else []
 with offline_only():
  plan=planner.build_plan()
  bosch=[u for u in plan['units'] if u['family']=='bosch_home']
  targets={u['seller_sku']:u for u in bosch if u['seller_sku'] in ('MMB2111M','TWK7203')}
  samsung=[u for u in plan['units'] if u['family']=='samsung']
  samsung_selected=[u for u in samsung if u['status']=='ready_to_run']
 config=json.loads((ROOT/'product_tool/config/coverage_planner.v1.json').read_text(encoding='utf-8'))
 out={'catalog_unchanged':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx')==d['catalog_sha256_before'],'source_registry_unchanged':sha(ROOT/'product_tool/config/source_catalog.v2.json')==d['registry_sha256_before'],'database_unchanged':sha(ROOT/'data/batches.sqlite3')==d['db_sha256_before'],'planner_config_unchanged':sha(ROOT/'product_tool/config/coverage_planner.v1.json')==d['planner_sha256_before'],'protected_pins_ok':all(pins.values()),'failed_pins':[p for p,ok in pins.items() if not ok],'prior_report_files_modified_since_declaration':modified,'response_hashes_ok':len(hashes)==3 and all(hashes.values()),'responses_count':len(records),'all_responses_200':all(e['status']==200 for e in records),'requests_spent':route['budget_spent_cumulative'],'within_budget':route['budget_spent_cumulative']<=d['budget']['max_real_requests_total'],'stopped_hosts':sorted(stopped_hosts_from_fetch_log(x for x in entries if isinstance(x,dict))),'bosch_selected_products':len([u for u in bosch if u['status']=='ready_to_run']),'bosch_target_statuses':{k:[v['status'],v['reason']] for k,v in targets.items()},'selected_products_config_families':sorted(config.get('selected_products',{})),'samsung_selected':len(samsung_selected),'samsung_total':len(samsung),'kz_twk_url_observed':bool(result['observed_kz_twk7203_candidate_url'])}
 (STAGE/'protected_hashes_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(out,ensure_ascii=True,indent=2))
 assert all(out[k] for k in ('catalog_unchanged','source_registry_unchanged','database_unchanged','planner_config_unchanged','protected_pins_ok','response_hashes_ok','all_responses_200','within_budget','kz_twk_url_observed')) and not modified and not out['stopped_hosts']
 assert out['requests_spent']==3 and out['bosch_selected_products']==0 and len(targets)==2 and out['selected_products_config_families']==['samsung']
 assert out['samsung_selected']==20 and out['samsung_total']==1182
if __name__=='__main__':main()
