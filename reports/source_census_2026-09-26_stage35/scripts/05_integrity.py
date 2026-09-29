"""Verify preserved evidence, network budget, protected files, and planner state."""
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
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 d=json.loads((STAGE/'raw/declaration.json').read_text(encoding='utf-8'))
 started=datetime.fromisoformat(d['declared_at']).timestamp()
 pins={p:mig.check_migrated_file(p,sha(ROOT/p))[0] for p in mig.ALL_AUTHORIZED_CHANGES}
 prior=[p for p in (ROOT/'reports').glob('source_census_*') if p!=STAGE]
 modified=sorted(p.relative_to(ROOT).as_posix() for directory in prior for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.stat().st_mtime>started)
 page_result=json.loads((STAGE/'raw/limited_pages_result.json').read_text(encoding='utf-8'))
 doc_result=json.loads((STAGE/'raw/MMB2111M_manual_result.json').read_text(encoding='utf-8'))
 page_index=[json.loads(x) for x in (STAGE/'route_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
 doc_index=[json.loads(x) for x in (STAGE/'document_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
 hashes={}
 for e in page_index:
  with gzip.open(STAGE/'route_check/responses'/e['saved_as'],'rt',encoding='utf-8',newline='') as h:body=h.read()
  hashes[e['url']]=sha(STAGE/'route_check/responses'/e['saved_as']) != '' and hashlib.sha256(body.encode('utf-8')).hexdigest()==e['sha256']
 # The binary response recorder stores latin-1 text; the separately checked PDF digest is authoritative.
 for e in doc_index:
  with gzip.open(STAGE/'document_check/responses'/e['saved_as'],'rb') as h:recorded=h.read()
  recovered=recorded.decode('utf-8').encode('latin-1')
  hashes[e['url']]=(e['status']==200 and e['url']==doc_result['url'] and
                   hashlib.sha256(recorded).hexdigest()==e['sha256'] and
                   hashlib.sha256(recovered).hexdigest()==doc_result['sha256'] and
                   recovered.startswith(b'%PDF-') and not doc_result['truncated'])
 logs=[]
 for path in (STAGE/'route_check/workdir/bosch_fetch_log.json',STAGE/'document_check/workdir/bosch_fetch_log.json'):
  if path.exists():logs.extend(json.loads(path.read_text(encoding='utf-8')))
 with offline_only():
  plan=planner.build_plan()
  bosch=[u for u in plan['units'] if u['family']=='bosch_home']
  targets={u['seller_sku']:u for u in bosch if u['seller_sku'] in ('MMB2111M','TWK7203')}
  samsung=[u for u in plan['units'] if u['family']=='samsung']
 config=json.loads((ROOT/'product_tool/config/coverage_planner.v1.json').read_text(encoding='utf-8'))
 out={'catalog_unchanged':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx')==d['catalog_sha256_before'],
      'source_registry_unchanged':sha(ROOT/'product_tool/config/source_catalog.v2.json')==d['registry_sha256_before'],
      'database_unchanged':sha(ROOT/'data/batches.sqlite3')==d['db_sha256_before'],
      'planner_config_unchanged':sha(ROOT/'product_tool/config/coverage_planner.v1.json')==d['planner_sha256_before'],
      'protected_pins_ok':all(pins.values()),'failed_pins':[p for p,ok in pins.items() if not ok],
      'prior_report_files_modified_since_declaration':modified,
      'response_hashes_ok':len(hashes)==4 and all(hashes.values()),'responses_count':len(hashes),
      'all_responses_200':all(e['status']==200 for e in page_index+doc_index),
      'requests_spent':page_result['budget_spent']+doc_result['budget_spent_this_step'],
      'within_budget':page_result['budget_spent']<=d['budget']['max_product_and_category_gets'] and doc_result['budget_spent_this_step']<=d['budget']['max_documents'] and page_result['budget_spent']+doc_result['budget_spent_this_step']<=d['budget']['max_real_requests_total'],
      'stopped_hosts':sorted(stopped_hosts_from_fetch_log(x for x in logs if isinstance(x,dict))),
      'bosch_selected_products':len([u for u in bosch if u['status']=='ready_to_run']),
      'bosch_target_statuses':{k:[v['status'],v['reason']] for k,v in targets.items()},
      'selected_products_config_families':sorted(config.get('selected_products',{})),
      'samsung_selected':len([u for u in samsung if u['status']=='ready_to_run']),
      'samsung_total':len(samsung),
      'kz_blender_product_url_observed':bool(page_result['blender_product_url_observed'])}
 (STAGE/'protected_hashes_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(out,ensure_ascii=True,indent=2))
 assert all(out[k] for k in ('catalog_unchanged','source_registry_unchanged','database_unchanged','planner_config_unchanged','protected_pins_ok','response_hashes_ok','all_responses_200','within_budget','kz_blender_product_url_observed'))
 assert not modified and not out['stopped_hosts'] and out['requests_spent']==4
 assert out['bosch_selected_products']==0 and len(targets)==2 and out['selected_products_config_families']==['samsung']
 assert out['samsung_selected']==20 and out['samsung_total']==1182
if __name__=='__main__':main()
