from pathlib import Path
import json,hashlib
from product_tool import jobs,storage,worker,readiness,apple_pipeline,card_evidence,discovery_trace
r=Path('reports/apple_stage64');dataset=r/'dataset_frozen.json';digest=hashlib.sha256(dataset.read_bytes()).hexdigest();rows=[dict(article='FW123LL/A',name='Refurbished MacBook Air 13-inch M4 16GB 256GB Midnight',category='laptops')]+json.loads(dataset.read_text(encoding='utf-8'))['models'];p=r/'final_acceptance.sqlite3';assert not p.exists();jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('apple64','Apple frozen first pass','Products','{}',storage._now()))
 for n,row in enumerate(rows,1):
  db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('apple64',n,row['name'],'Apple',row['article'],'',row['category'],0,'[]','{}'))
results=[]
for product in storage.get_batch(p,'apple64')['products']:
 pid=product['id'];jid=jobs.enqueue(p,pid,[1,2,3,4,6]);worker.run_once(p)
 x={'article':product['search_code'],'job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'resolved':jobs.get_resolved(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':apple_pipeline.card_readiness(p,pid),'events':jobs.list_events(p,jid),'evidence':card_evidence.load(p,pid,'apple'),'trace':discovery_trace.for_job(p,jid)};results.append(x)
 (r/'final_acceptance.json').write_text(json.dumps({'dataset_sha256':digest,'pipeline':'run_once with generic Apple order adapter; no per-model URLs injected','baseline':results[0],'results':results[1:]},ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(product['search_code'],x['job']['status'],len(x['facts']),flush=True)
assert hashlib.sha256(dataset.read_bytes()).hexdigest()==digest
