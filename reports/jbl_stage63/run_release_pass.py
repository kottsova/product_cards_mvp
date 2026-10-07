from pathlib import Path
import json,hashlib
from product_tool import jobs,storage,worker,card_evidence,discovery_trace,jbl_pipeline
import logging
logging.getLogger('pypdf').setLevel(logging.ERROR)
r=Path('reports/jbl_stage63');dataset=Path('reports/jbl_stage62/dataset_frozen.json');digest=hashlib.sha256(dataset.read_bytes()).hexdigest();rows=json.loads(dataset.read_text())['models'];p=r/'release_pass.sqlite3';assert not p.exists();jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage62','JBL frozen first pass','Products','{}',storage._now()))
 for n,row in enumerate([dict(article='JBLFLIP6BLKEU',name='JBL Flip 6 Black EU',category='speakers')]+rows,1):
  db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('stage62',n,row['name'],'JBL',row['article'],'',row['category'],0,'[]','{}'))
results=[]
for product in storage.get_batch(p,'stage62')['products']:
 pid=product['id'];jid=jobs.enqueue(p,pid,[1,2,3,4,6]);worker.run_once(p)
 x={'article':product['search_code'],'job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'resolved':jobs.get_resolved(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':jbl_pipeline.card_readiness(p,pid),'evidence':card_evidence.load(p,pid,'jbl'),'trace':discovery_trace.for_job(p,jid)};results.append(x)
 (r/'release_pass.json').write_text(json.dumps({'dataset_sha256':digest,'baseline':results[0],'results':results[1:]},ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(product['search_code'],x['job']['status'],len(x['facts']),x['readiness']['verdict'],flush=True)
assert hashlib.sha256(dataset.read_bytes()).hexdigest()==digest
