"""Unmodified ordinary worker baseline, before any Xbox dispatch or adapter."""
from pathlib import Path
import hashlib,json,subprocess
from product_tool import jobs,storage,worker,readiness,discovery_trace
R=Path('reports/xbox_stage68');R.mkdir(exist_ok=True)
db=R/'baseline.sqlite3';fresh=not db.exists()
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head=='aba854121464779dccf909d817d50d315a31018e'
source_hash=hashlib.sha256(Path('product_tool/worker.py').read_bytes()).hexdigest()
jobs.initialize(db);discovery_trace.initialize(db)
if fresh:
 with storage._connection(db) as c:
  c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('xb68baseline','Xbox baseline','Products','{}',storage._now()))
  c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('xb68baseline',1,'Xbox Series X','Xbox','1882','','consoles',0,'[]','{}'))
 p=storage.get_batch(db,'xb68baseline')['products'][0];jid=jobs.enqueue(db,p['id'],[1,2,3,4,6])
 worker.run_once(db)
else:
 p=storage.get_batch(db,'xb68baseline')['products'][0];jid=jobs.list_jobs(db,p['id'])[0]['id']
out=dict(stage=68,phase='unmodified ordinary run_once baseline',head_before=head,worker_sha256=source_hash,worker_unchanged=source_hash==hashlib.sha256(Path('product_tool/worker.py').read_bytes()).hexdigest(),input=p,identifier_type='hardware_model_number',identifier_grounding='Microsoft Learn official device identification page explicitly names Xbox Series X Model 1882; reference was not supplied to run_once',identifier_reference='https://learn.microsoft.com/en-us/xbox/service-guides/series-x-console/series-x-device-id-and-disassembly',requested_region='en-us',retail_sku=None,color=None,storage_configuration=None,query_variants=['1882','Xbox Series X 1882','Xbox Series X'],query_variants_executed='Only ordinary generic dealer fallback; no Xbox official discovery dispatch exists',sources=jobs.get_source_pages(db,p['id']),facts=jobs.get_facts(db,p['id']),resolved=jobs.get_resolved(db,p['id']),photos=jobs.get_photo_candidates(db,p['id']),documents=jobs.get_documents(db,p['id']),job=jobs.list_jobs(db,p['id'])[0],events=jobs.list_events(db,jid),trace=discovery_trace.for_job(db,jid),readiness=readiness.card_readiness(db,p['id']))
(R/'baseline.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(out['job']['status'],out['readiness']['verdict'],len(out['facts']),len(out['photos']),out['worker_unchanged'])
