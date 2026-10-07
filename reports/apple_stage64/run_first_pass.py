from pathlib import Path
import json,hashlib
from product_tool import jobs,storage,worker,readiness
assert 'apple_pipeline.run_job' not in Path('product_tool/worker.py').read_text(encoding='utf-8'), 'Historical first pass requires Stage 63 source checkout'
r=Path('reports/apple_stage64');dataset=r/'dataset_frozen.json';digest=hashlib.sha256(dataset.read_bytes()).hexdigest();rows=json.loads(dataset.read_text(encoding='utf-8'))['models'];p=r/'first_pass.sqlite3';assert not p.exists();jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('apple64','Apple frozen first pass','Products','{}',storage._now()))
 for n,row in enumerate(rows,1):
  db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('apple64',n,row['name'],'Apple',row['article'],'',row['category'],0,'[]','{}'))
results=[]
for product in storage.get_batch(p,'apple64')['products']:
 pid=product['id'];jid=jobs.enqueue(p,pid,[1,2,3,4,6]);worker.run_once(p)
 x={'article':product['search_code'],'job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'resolved':jobs.get_resolved(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':readiness.card_readiness(p,pid),'events':jobs.list_events(p,jid),'trace_available':False};results.append(x)
 (r/'first_pass.json').write_text(json.dumps({'dataset_sha256':digest,'pipeline':'unchanged run_once; unsupported Apple branch; no injected sources','results':results},ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(product['search_code'],x['job']['status'],len(x['facts']),flush=True)
assert hashlib.sha256(dataset.read_bytes()).hexdigest()==digest
