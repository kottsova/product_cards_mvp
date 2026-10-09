"""Unmodified ordinary run_once baseline before any Razer-specific dispatch."""
from pathlib import Path
import hashlib,json,subprocess
from product_tool import jobs,storage,worker,readiness,discovery_trace
R=Path(__file__).parent;db=R/'baseline.sqlite3';assert not db.exists()
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head=='39f5b3868e5916f0711995468a32b0b34de9f239'
sha=hashlib.sha256(Path('product_tool/worker.py').read_bytes()).hexdigest()
jobs.initialize(db);discovery_trace.initialize(db)
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('rz70baseline','Razer baseline','Products','{}',storage._now()))
 c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('rz70baseline',1,'Razer DeathAdder V3 Black','Razer','RZ01-04640100-R3U1','','mice',0,'[]',json.dumps({'requested_region':'en-US'})))
p=storage.get_batch(db,'rz70baseline')['products'][0];jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db)
out=dict(stage=70,phase='unmodified ordinary run_once baseline',head_before=head,worker_sha256=sha,worker_unchanged=sha==hashlib.sha256(Path('product_tool/worker.py').read_bytes()).hexdigest(),input=p,commercial_model='Razer DeathAdder V3',part_number='RZ01-04640100-R3U1',generation='V3',color='Black (research reference only; not pipeline confirmed)',regional_suffix='R3U1 (opaque until official evidence)',reference_url='https://www.razer.com/gaming-mice/razer-deathadder-v3/RZ01-04640100-R3U1',reference_support='https://mysupport.razer.com/app/answers/detail/a_id/6124',reference_not_given_to_worker=True,query_variants_requested=['RZ01-04640100-R3U1','Razer DeathAdder V3 Black'],sources=jobs.get_source_pages(db,p['id']),facts=jobs.get_facts(db,p['id']),resolved=jobs.get_resolved(db,p['id']),photos=jobs.get_photo_candidates(db,p['id']),documents=jobs.get_documents(db,p['id']),job=jobs.list_jobs(db,p['id'])[0],events=jobs.list_events(db,jid),trace=discovery_trace.for_job(db,jid),readiness=readiness.card_readiness(db,p['id']))
(R/'baseline.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8');print(out['job']['status'],out['readiness']['verdict'],len(out['facts']),len(out['photos']),out['worker_unchanged'],flush=True)
