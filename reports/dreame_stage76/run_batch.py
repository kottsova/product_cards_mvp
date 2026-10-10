"""Frozen Excel -> unseeded actual run_once batch; no capture replay substitution."""
import sys,json,hashlib,sqlite3,time,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import Workbook
from product_tool import jobs,worker,readiness,discovery_trace,card_evidence,importer
from product_tool.adapters.dreame import DreameAdapter
from product_tool.adapters.policy_session import record_responses
R=Path(__file__).parent
def main():
 raw=(R/'dataset.json').read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==(R/'dataset.sha256').read_text().strip()
 rows=json.loads(raw)['rows'];run=sys.argv[1] if len(sys.argv)>1 else 'first_pass';o=R/run;o.mkdir(exist_ok=True);db=o/'live.sqlite3';assert not db.exists()
 w=Workbook();s=w.active;s.title='Products';s.append(['Бренд','Артикул','Наименование','Категория'])
 for x in rows:s.append([x['brand'],x['article'],x['name'],x['category']])
 w.save(o/'input.xlsx');preview=importer.preview_xlsx(o/'input.xlsx');assert len(preview.products)==10
 jobs.initialize(db);discovery_trace.initialize(db)
 with sqlite3.connect(db) as c:
  c.execute("INSERT INTO batches VALUES ('dr76','input.xlsx','Products','{}','2026-10-11')")
  for i,p in enumerate(preview.products,1):c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,'dr76',?,?,?,?,?,?,0,'[]',?)",(i,p.row_number,p.name,p.brand,p.search_code,p.alternate_code,p.category,json.dumps(p.original_values,ensure_ascii=False)))
 log=o/'dreame_fetch_log.json';prior=R/'baseline/official_diagnostic_log.json' if run=='first_pass' else R/'first_pass/dreame_fetch_log.json'
 if prior.exists():shutil.copyfile(prior,log)
 adapter=DreameAdapter(fetch_log_path=log,capture_dir=o/'captures');results=[]
 with record_responses(o/'http'):
  for p in rows:
   assert hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()==sha
   start=time.monotonic();j=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db,dreame_adapter_factory=lambda:adapter)
   result={'id':p['id'],'input':p,'observation':'actual_live_worker','seconds':round(time.monotonic()-start,2),'job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id']),'documents':jobs.get_documents(db,p['id']),'readiness':readiness.card_readiness(db,p['id']),'evidence':card_evidence.load(db,p['id'],'dreame'),'trace':discovery_trace.for_job(db,j)}
   results.append(result);(o/'results.json').write_text(json.dumps({'dataset_sha256':sha,'rows':results},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(p['id'],p['model'],result['job']['status'],result['readiness']['confirmed_specs'],result['readiness']['verdict'],flush=True)
if __name__=='__main__':main()
