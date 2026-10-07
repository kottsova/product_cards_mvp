from pathlib import Path
import json
from product_tool import jobs,storage,worker,readiness,discovery_trace
r=Path('reports/apple_stage64');p=r/'baseline.sqlite3';fresh=not p.exists();jobs.initialize(p)
if fresh and "apple_pipeline.run_job" in Path("product_tool/worker.py").read_text(encoding="utf-8"):
 raise SystemExit("Historical unchanged baseline requires Stage 63 source checkout")
if fresh:
 with storage._connection(p) as db:
  db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('apple64','Apple baseline','Products','{}',storage._now()))
  db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('apple64',1,'Refurbished MacBook Air 13-inch M4 16GB 256GB Midnight','Apple','FW123LL/A','','laptops',0,'[]','{}'))
pid=storage.get_batch(p,'apple64')['products'][0]['id']
if fresh:
 jid=jobs.enqueue(p,pid,[1,2,3,4,6]);worker.run_once(p)
jid=jobs.list_jobs(p,pid)[0]['id']
x={'article':'FW123LL/A','pipeline':'unchanged run_once; no Apple hardcode or URL injection','job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'resolved':jobs.get_resolved(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':readiness.card_readiness(p,pid),'events':jobs.list_events(p,jid),'trace':{'available':False,'reason':'Unsupported brand branch does not initialize discovery_trace; events and source pages retained'}}
(r/'baseline.json').write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(x['job']['status'],x['readiness'])
