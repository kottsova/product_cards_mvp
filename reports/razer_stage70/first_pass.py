"""Ordinary worker on the frozen inputs; actual network/browser, no result replay."""
from pathlib import Path
import json,hashlib,os,time,sys
from product_tool import storage,jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.razer import RazerAdapter
R=Path(__file__).parent;phase=sys.argv[1] if len(sys.argv)>1 else 'first_pass';assert phase in {'first_pass','corrected_live','guarded_live'};os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()));raw=(R/'frozen_inputs.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip();rows=json.loads(raw)['rows'];db=R/(phase+'.sqlite3');assert not db.exists();jobs.initialize(db);discovery_trace.initialize(db)
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('rz70','Razer Stage 70','Products','{}',storage._now()))
 for row in rows:c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('rz70',row['id'],row['name'],'Razer',row['article'],'',row['category'],0,'[]',json.dumps({'requested_region':row['region'],'configuration':row['configuration']})))
out={'phase':'first adapted ordinary worker, live sources; catalog cache explicitly traced','input_sha256':hashlib.sha256(raw).hexdigest(),'rows':[]}
for product in storage.get_batch(db,'rz70')['products']:
 jid=jobs.enqueue(db,product['id'],[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,razer_adapter_factory=lambda:RazerAdapter(fetch_log_path=R/'razer_fetch_log.json',capture_dir=R/'captures'));ev=card_evidence.load(db,product['id'],'razer') or {};item={'id':product['row_number'],'input':product,'elapsed':time.monotonic()-start,'evidence':ev,'sources':jobs.get_source_pages(db,product['id']),'facts':jobs.get_facts(db,product['id']),'resolved':jobs.get_resolved(db,product['id']),'photos':jobs.get_photo_candidates(db,product['id']),'documents':jobs.get_documents(db,product['id']),'trace':discovery_trace.for_job(db,jid),'job':jobs.list_jobs(db,product['id'])[0],'readiness':readiness.card_readiness(db,product['id'])};out['rows'].append(item);(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8');print(item['id'],item['job']['status'],item['readiness']['verdict'],item['readiness']['confirmed_specs'],ev.get('identity',{}).get('model'),item['readiness']['gaps'],flush=True)
assert len(out['rows'])==10
