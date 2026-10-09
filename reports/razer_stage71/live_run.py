"""Frozen inputs through ordinary worker and a fresh visible public browser session."""
from pathlib import Path
import json,hashlib,os,time,sys
from product_tool import storage,jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.razer import RazerAdapter
from product_tool.census.public_browser import PublicBrowserSession
R=Path(__file__).parent;phase=sys.argv[1];assert phase in {'live_initial','live_final','second_live'}
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
raw=(R/'frozen_inputs.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip();rows=json.loads(raw)['rows']
if phase=='second_live':rows=[r for r in rows if r['id'] in {1,3,5,6,7,8}]
db=R/(phase+'.sqlite3');assert not db.exists();jobs.initialize(db);discovery_trace.initialize(db)
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('rz71','Razer Stage 71','Products','{}',storage._now()))
 for row in rows:c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('rz71',row['id'],row['name'],'Razer',row['article'],'',row['category'],0,'[]',json.dumps(row)))
session=PublicBrowserSession(allowed_hosts=('razer.com','razerzone.com'),fetch_log_path=R/'razer_fetch_log.json',profile_dir=R/'attended_profile',visible=True)
adapter=RazerAdapter(fetch_log_path=R/'razer_fetch_log.json',capture_dir=R/'captures',browser_session=session)
out={'phase':phase,'provenance':'fresh live DOM in visible persistent Chrome; no capture replay','input_sha256':hashlib.sha256(raw).hexdigest(),'rows':[]}
try:
 session.start()
 for p in storage.get_batch(db,'rz71')['products']:
  jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,razer_adapter_factory=lambda:adapter)
  ev=card_evidence.load(db,p['id'],'razer') or {};item={'id':p['row_number'],'input':p,'elapsed':time.monotonic()-start,'evidence':ev,'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id']),'documents':jobs.get_documents(db,p['id']),'trace':discovery_trace.for_job(db,jid),'job':jobs.list_jobs(db,p['id'])[0],'readiness':readiness.card_readiness(db,p['id'])}
  out['rows'].append(item);(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8')
  print(item['id'],item['job']['status'],item['readiness']['confirmed_specs'],ev.get('identity',{}).get('model'),item['readiness']['gaps'],flush=True)
finally:session.close()
assert len(out['rows'])==len(rows)
