from pathlib import Path
import json,hashlib
from product_tool import jobs,storage,worker,card_evidence,discovery_trace,lenovo_pipeline
from product_tool.adapters.policy_session import record_responses
root=Path('reports/lenovo_stage61');data=Path('reports/lenovo_stage60/dataset_frozen.json');digest=hashlib.sha256(data.read_bytes()).hexdigest()
frozen=json.loads(data.read_text(encoding='utf-8-sig'));p=root/'release_pass.sqlite3'
if p.exists():raise SystemExit('Recovery database exists')
jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage60-final','Lenovo Stage61 recovery','Products','{}',storage._now()))
 for n,row in enumerate(frozen['models'],1):
  db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('stage60-final',n,row['name'],'Lenovo',row['article'],'',row['category'],0,'[]','{}'))
results=[]
with record_responses(root/'release_pass_responses'):
 for product in storage.get_batch(p,'stage60-final')['products']:
  pid=product['id'];jid=jobs.enqueue(p,pid,[1,2,3,4,6]);worker.run_once(p)
  r={'article':product['search_code'],'job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'resolved':jobs.get_resolved(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':lenovo_pipeline.card_readiness(p,pid),'evidence':card_evidence.load(p,pid,'lenovo'),'trace':discovery_trace.for_job(p,jid),'events':jobs.list_events(p,jid)}
  results.append(r)
  print(json.dumps({'article':product['search_code'],'job':r['job']['status'],'facts':len(r['facts']),'readiness':r['readiness'],'identity':r['evidence'].get('configuration_identity',{})},ensure_ascii=True),flush=True)
  (root/'release_pass.json').write_text(json.dumps({'dataset_sha256':digest,'pipeline':'production run_once; primary official attended PSREF captures, unchanged frozen dataset','results':results},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
assert hashlib.sha256(data.read_bytes()).hexdigest()==digest
