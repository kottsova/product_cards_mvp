"""Same frozen Stage 66 dataset; ordinary worker, no SKU/URL inputs."""
import hashlib,json,sys
from pathlib import Path
from product_tool import jobs,storage,worker,readiness,discovery_trace,card_evidence
from product_tool.adapters.playstation import PlayStationAdapter
R=Path('reports/playstation_stage67');F=Path('reports/playstation_stage66/dataset_frozen.json')
DIGEST='c2cac5f22132a2061c2ad114b1fa6030188f1ad26ddfc665734d0a75014d1422'

def run(mode):
 assert hashlib.sha256(F.read_bytes()).hexdigest()==DIGEST
 rows=json.loads(F.read_text(encoding='utf-8'))['models'];db=R/(mode+'.sqlite3');assert not db.exists()
 jobs.initialize(db)
 with storage._connection(db) as c:
  c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('ps67','PlayStation Stage 67','Products','{}',storage._now()))
  for i,x in enumerate(rows,1):c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('ps67',i,x['name'],'PlayStation',x['article'],'',x['category'],0,'[]','{}'))
 results=[]
 for p in storage.get_batch(db,'ps67')['products']:
  pid=p['id'];jid=jobs.enqueue(db,pid,[1,2,3,4,6]);trace=lambda e:discovery_trace.record(db,jid,pid,e)
  kwargs={}
  if mode.startswith('replay'):
   from .replay import CapturedSession,CapturedSearch
   kwargs=dict(session=CapturedSession(),search_factory=CapturedSearch)
  factory=lambda:PlayStationAdapter(fetch_log_path=R/('replay_http.json' if kwargs else 'playstation_fetch.json'),trace_callback=trace,**kwargs)
  worker.run_once(db,playstation_adapter_factory=factory)
  row=dict(input=p,job=jobs.list_jobs(db,pid)[0],sources=jobs.get_source_pages(db,pid),facts=jobs.get_facts(db,pid),resolved=jobs.get_resolved(db,pid),photos=jobs.get_photo_candidates(db,pid),documents=jobs.get_documents(db,pid),readiness=readiness.card_readiness(db,pid),trace=discovery_trace.for_job(db,jid),evidence=card_evidence.load(db,pid,'playstation'))
  results.append(row);(R/(mode+'.json')).write_text(json.dumps(dict(mode=mode,dataset_sha256=DIGEST,results=results),ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  print(p['search_code'],row['job']['status'],row['readiness']['confirmed_specs'],len([x for x in row['photos'] if x['selected']]),row['readiness']['verdict'],flush=True)
 assert hashlib.sha256(F.read_bytes()).hexdigest()==DIGEST
if __name__=='__main__':run(sys.argv[1])
