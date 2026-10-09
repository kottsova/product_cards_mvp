"""Ordinary worker first pass; inputs have no source URLs or adapter factory."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
from product_tool import jobs,storage,worker,readiness,card_evidence,discovery_trace
R=Path(__file__).parent;phase=sys.argv[1] if len(sys.argv)>1 else 'first_pass'
sha=hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest();assert sha==(R/'dataset.sha256').read_text().strip()
db=R/(phase+'.sqlite3');assert not db.exists(),'Do not overwrite a completed or partial audit run'
rows=json.loads((R/'dataset.json').read_text(encoding='utf8'))['rows'];jobs.initialize(db);discovery_trace.initialize(db)
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('xb68','Xbox Stage 68','Products','{}',storage._now()))
 for row in rows:
  c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('xb68',row['row'],row['name'],row['brand'],row['article'],'',row['category'],0,'[]',json.dumps({'requested_region':row['requested_region'],'identifier_type':row['identifier_type']})))
out=dict(stage=68,phase=phase,started=datetime.now(timezone.utc).isoformat(),dataset_sha256=sha,ordinary_run_once=True,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product_tool').rglob('*.py')},rows=[])
for p in storage.get_batch(db,'xb68')['products']:
 jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db)
 ev=card_evidence.load(db,p['id'],'xbox') or {};ready=readiness.card_readiness(db,p['id'])
 result=dict(input=p,job=jobs.list_jobs(db,p['id'])[0],readiness=ready,evidence=ev,sources=jobs.get_source_pages(db,p['id']),resolved=jobs.get_resolved(db,p['id']),facts=jobs.get_facts(db,p['id']),photos=jobs.get_photo_candidates(db,p['id']),trace=discovery_trace.for_job(db,jid),events=jobs.list_events(db,jid))
 out['rows'].append(result);(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8')
 print(p['row_number'],p['search_code'],result['job']['status'],ready['verdict'],len(result['facts']),len(result['photos']),ready['blocking_gaps'],flush=True)
assert sha==hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()
out['finished']=datetime.now(timezone.utc).isoformat();(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8')
