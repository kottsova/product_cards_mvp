"""Unmodified Stage 58 first pass of the frozen ten Bosch catalog rows."""
from pathlib import Path
from uuid import uuid4
import json
from product_tool import bosch_readiness, jobs, storage, worker
root=Path(__file__).resolve().parent
sample=json.loads((root/'dataset_frozen.json').read_text(encoding='utf-8-sig'))['models']
path=root/'first_pass.sqlite3'
if path.exists(): raise SystemExit('first pass already exists; results are frozen')
jobs.initialize(path)
result=[]
with storage._connection(path) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage58-frozen','fixed Bosch sample','Товары','{}',storage._now()))
for index,item in enumerate(sample,2):
 with storage._connection(path) as c:
  product_id=c.execute('''INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)''',('stage58-frozen',index,item['article'],'BOSCH',item['article'],'',item['category'],0,'[]','{}')).lastrowid
 try:
  jobs.enqueue(path,product_id,[1,2,3,4,6]);enqueue={'accepted':True}
 except ValueError as exc:
  enqueue={'accepted':False,'reason':str(exc)}
 if not enqueue['accepted']:
  job_id=uuid4().hex
  with storage._connection(path) as c:
   c.execute('''INSERT INTO search_jobs (id,product_id,stages_json,status,message,created_at,updated_at) VALUES (?,?,?,'queued',?,?,?)''',(job_id,product_id,'[1,2,3,4,6]','Stage 58 frozen first pass',storage._now(),storage._now()))
 else: job_id=jobs.list_jobs(path,product_id)[0]['id']
 ran=worker.run_once(path)
 job=jobs.list_jobs(path,product_id)[0]
 result.append({'article':item['article'],'category':item['category'],'enqueue':enqueue,'run_once_processed':ran,'job_status':job['status'],'job_message':job['message'],'source_pages':jobs.get_source_pages(path,product_id),'documents':jobs.get_documents(path,product_id),'facts':jobs.get_facts(path,product_id),'photos':jobs.get_photo_candidates(path,product_id),'readiness':bosch_readiness.card_readiness(path,product_id),'events':jobs.list_events(path,job_id)})
(root/'first_pass.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps([{'article':x['article'],'enqueue':x['enqueue']['accepted'],'status':x['job_status'],'readiness':x['readiness']['verdict']} for x in result],ensure_ascii=False))
