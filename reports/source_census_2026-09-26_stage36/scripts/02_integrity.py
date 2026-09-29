"""Stage 36 offline integrity and scoped selection checks."""
from __future__ import annotations
import gzip,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import _pipeline_migration as migration
from product_tool.coverage.planner import build_plan
from product_tool.offline_guard import offline_only

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 before=json.loads((STAGE/'before_hashes.json').read_text(encoding='utf8'))
 protected={p:migration.check_migrated_file(p,sha(ROOT/p))[0] for p in migration.ALL_AUTHORIZED_CHANGES}
 saved=ROOT/'reports/source_census_2026-09-26_stage35/route_check/responses'
 pages=[json.loads(x) for x in (saved/'index.jsonl').read_text(encoding='utf8').splitlines()]
 page_hashes=[]
 for e in pages:
  with gzip.open(saved/e['saved_as'],'rt',encoding='utf8',newline='') as f:text=f.read()
  page_hashes.append(hashlib.sha256(text.encode('utf8')).hexdigest()==e['sha256'])
 with offline_only():
  plan=build_plan()
  bosch=[x for x in plan['units'] if x['family']=='bosch_home']
  samsung=[x for x in plan['units'] if x['family']=='samsung']
 replay=json.loads((STAGE/'offline_replay_result.json').read_text(encoding='utf8'))
 out={'catalog_unchanged':sha(ROOT/'data/catalog_2026-09-21_filtered.xlsx')==before['data/catalog_2026-09-21_filtered.xlsx'],
      'production_registry_unchanged':sha(ROOT/'product_tool/config/source_catalog.v2.json')==before['product_tool/config/source_catalog.v2.json'],
      'production_database_unchanged':sha(ROOT/'data/batches.sqlite3')==before['data/batches.sqlite3'],
      'protected_pins_ok':all(protected.values()),'failed_pins':[p for p,ok in protected.items() if not ok],
      'saved_kz_response_hashes_ok':all(page_hashes) and len(page_hashes)==3,
      'bosch_home_total_rows':len(bosch),'bosch_home_selected':[(x['category'],x['seller_sku']) for x in bosch if x['status']=='ready_to_run'],
      'bosch_home_unselected_ready_count':sum(x['status']=='ready_to_run' and x['seller_sku'] not in ('TWK7203','MMB2111M') for x in bosch),
      'samsung_selected':sum(x['status']=='ready_to_run' for x in samsung),'samsung_total':len(samsung),
      'offline_replay_calls':replay['transport_calls'],'offline_replay_statuses':{x['code']:[x['job_status'],x['readiness']['verdict']] for x in replay['products']},
      'unselected_job_count':replay['unselected_job_count']}
 (STAGE/'integrity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(out,ensure_ascii=True,indent=2))
 assert all(out[k] for k in ('catalog_unchanged','production_registry_unchanged','production_database_unchanged','protected_pins_ok','saved_kz_response_hashes_ok'))
 assert len(out['bosch_home_selected'])==2 and out['bosch_home_unselected_ready_count']==0
 assert out['samsung_selected']==20 and out['samsung_total']==1182 and out['unselected_job_count']==0
 assert len(out['offline_replay_calls'])==2
if __name__=='__main__':main()
