from pathlib import Path
import json,hashlib
from product_tool import jobs,storage,worker,readiness
root=Path('reports/lenovo_stage60'); data=root/'dataset_frozen.json'
frozen=json.loads(data.read_text(encoding='utf-8-sig')); digest=hashlib.sha256(data.read_bytes()).hexdigest()
p=root/'first_pass.sqlite3'
if p.exists(): raise SystemExit('First pass exists')
jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage60-first','Lenovo frozen first pass','Products','{}',storage._now()))
 for n,row in enumerate(frozen['models'],1):
  db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('stage60-first',n,row['name'],'Lenovo',row['article'],'',row['category'],0,'[]','{}'))
results=[]
for product in storage.get_batch(p,'stage60-first')['products']:
 pid=product['id']; jid=jobs.enqueue(p,pid,[1,2,3,4,6]); worker.run_once(p)
 r={'article':product['search_code'],'job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':readiness.card_readiness(p,pid),'events':jobs.list_events(p,jid)}
 results.append(r)
 print(product['search_code'],r['job']['status'],len(r['facts']),flush=True)
(root/'first_pass.json').write_text(json.dumps({'dataset_sha256':digest,'pipeline':'unchanged production, no Lenovo adapter or research URL injection','results':results},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
assert hashlib.sha256(data.read_bytes()).hexdigest()==digest
