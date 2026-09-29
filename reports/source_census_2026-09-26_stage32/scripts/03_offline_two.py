"""Ordinary upload -> job -> worker -> export using only saved Stage 32 pages."""
from __future__ import annotations
import gzip,importlib.util,json,logging,sys
from pathlib import Path
from tempfile import TemporaryDirectory
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'));logging.disable(logging.CRITICAL)
import _samsung_replay as R
from product_tool import jobs
from product_tool.offline_guard import offline_only
spec=importlib.util.spec_from_file_location('run4',ROOT/'reports/source_census_2026-09-25_stage27/scripts/02_run_batch4.py')
run4=importlib.util.module_from_spec(spec);spec.loader.exec_module(run4)
def main():
 pages={};directory=STAGE/'route_check/responses'
 for line in (directory/'index.jsonl').read_text(encoding='utf-8').splitlines():
  entry=json.loads(line)
  if entry['saved_as']:
   with gzip.open(directory/entry['saved_as'],'rt',encoding='utf-8',newline='') as h:pages[entry['url']]=(entry['status'],h.read())
 cards=[('Проекторы','SP-LSP3BLAXCE_SU'),('GPS-трекеры','EI-T5600BWEGWW')]
 with offline_only(),TemporaryDirectory() as tmp:
  replay=R.Replay(extra_pages=pages)
  batch=R.run_products(Path(tmp),cards=cards,replay=replay)
  records=[]
  for outcome in batch['outcomes']:
   record=run4.card_record(batch['database'],outcome)
   record['official_facts']=[{'name':f['raw_name'],'value':f['raw_value'],'source_key':f['source_key']} for f in jobs.get_facts(batch['database'],outcome['product_id']) if f['source_key']=='samsung']
   records.append(record)
  (STAGE/'raw/offline_two_result.json').write_text(json.dumps({'cards':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  (STAGE/'raw/offline_replay_calls.json').write_text(json.dumps({'calls':replay.calls,'refused':replay.refused,'dealer_calls':batch['dealer_session'].calls},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  (STAGE/'export').mkdir(exist_ok=True)
  (STAGE/'export/samsung_two_export.xlsx').write_bytes(batch['export'])
  print(json.dumps({'cards':[{'article':r['article'],'job':r['job_status'],'readiness':r['readiness']['verdict'],'page_match':r['readiness']['page_match_level'],'facts':r['facts']['samsung'],'photos':r['photos'],'documents':len(r['documents']),'gaps':r['readiness']['gaps']} for r in records],'replay_calls':replay.calls,'refused':replay.refused,'dealer_calls':batch['dealer_session'].calls,'export_bytes':len(batch['export'])},ensure_ascii=True,indent=2))
  assert not replay.refused and not batch['dealer_session'].calls
if __name__=='__main__':main()
