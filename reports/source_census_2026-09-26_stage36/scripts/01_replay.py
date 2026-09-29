"""Capture the tested two-product Bosch replay and its Excel export."""
from __future__ import annotations
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
from tests.test_stage36_bosch_home import BoschOrdinaryPath
from product_tool import bosch_readiness,jobs

def main():
 BoschOrdinaryPath.setUpClass()
 try:
  out=[]
  for code in BoschOrdinaryPath.manifest:
   pid=BoschOrdinaryPath.products[code]['id']
   readiness=bosch_readiness.card_readiness(BoschOrdinaryPath.db,pid)
   out.append({'code':code,'category':BoschOrdinaryPath.manifest[code]['category'],
               'job_status':jobs.list_jobs(BoschOrdinaryPath.db,pid)[0]['status'],
               'readiness':readiness,'page':next(x for x in jobs.get_source_pages(BoschOrdinaryPath.db,pid) if x['source_key']=='bosch_home')['url'],
               'photos':[x['url'] for x in jobs.get_photo_candidates(BoschOrdinaryPath.db,pid,include_excluded=False) if x['source_key']=='bosch_home' and x['selected']],
               'documents':[{'url':x['direct_url'],'language':x['language'],'support_model':x['support_model'],'title':x['title']} for x in jobs.get_documents(BoschOrdinaryPath.db,pid) if x['source_key']=='bosch_home']})
  (STAGE/'offline_bosch_export.xlsx').write_bytes(BoschOrdinaryPath.xlsx)
  result={'transport_calls':BoschOrdinaryPath.replay.calls,'export_bytes':len(BoschOrdinaryPath.xlsx),'products':out,
          'unselected_seller_sku':BoschOrdinaryPath.other.seller_sku,
          'unselected_job_count':len(jobs.list_jobs(BoschOrdinaryPath.db,BoschOrdinaryPath.products[BoschOrdinaryPath.other.seller_sku]['id']))}
  (STAGE/'offline_replay_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  print(json.dumps({'calls':len(result['transport_calls']),'products':[{'code':x['code'],'job_status':x['job_status'],'readiness':x['readiness']['verdict'],'photos':len(x['photos']),'documents':len(x['documents']),'revision':x['readiness']['revision_status']} for x in out],
                    'unselected_job_count':result['unselected_job_count'],'export_bytes':result['export_bytes']},ensure_ascii=True,indent=2))
 finally:BoschOrdinaryPath.tearDownClass()
if __name__=='__main__':main()
