"""Same frozen Stage 68 inputs, ordinary production worker and isolated live log."""
import sys,json,hashlib,time,os
from pathlib import Path
from product_tool import jobs,storage,worker,card_evidence,readiness,discovery_trace
R=Path(__file__).parent;D=R.parent/'xbox_stage68'/'dataset.json'
sha=hashlib.sha256(D.read_bytes()).hexdigest();assert sha=='556dfe669181b1959e1d21dd52ed491f78719744bdbdab3442bef981de76191c'
phase=sys.argv[1];U=R/phase;U.mkdir(exist_ok=True);db=U/'batches.sqlite3';assert not db.exists();rows=json.loads(D.read_text(encoding='utf8'))['rows']
jobs.initialize(db);discovery_trace.initialize(db);os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('xb69','Xbox Stage 69','Products','{}',storage._now()))
 for r in rows:c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('xb69',r['row'],r['name'],r['brand'],r['article'],'',r['category'],0,'[]',json.dumps({'requested_region':r['requested_region'],'identifier_type':r['identifier_type']})))
out=dict(stage=69,phase=phase,frozen_dataset_sha256=sha,ordinary_worker=True,transport='Live public network; fresh process, log/session cache',source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product_tool').rglob('*.py')},rows=[]);start=time.monotonic()
for p in storage.get_batch(db,'xb69')['products']:
 t=time.monotonic();jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db)
 row=dict(input=p,job=jobs.list_jobs(db,p['id'])[0],readiness=readiness.card_readiness(db,p['id']),evidence=card_evidence.load(db,p['id'],'xbox') or {},sources=jobs.get_source_pages(db,p['id']),facts=jobs.get_facts(db,p['id']),resolved=jobs.get_resolved(db,p['id']),photos=jobs.get_photo_candidates(db,p['id']),trace=discovery_trace.for_job(db,jid),elapsed_seconds=time.monotonic()-t)
 out['rows'].append(row);out['elapsed_seconds']=time.monotonic()-start;(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8');print(p['row_number'],p['search_code'],row['job']['status'],row['readiness']['verdict'],'specs',row['readiness']['confirmed_specs'],'photos',sum(bool(x['selected']) for x in row['photos']),round(row['elapsed_seconds'],1),row['readiness']['blocking_gaps'],flush=True)
assert sha==hashlib.sha256(D.read_bytes()).hexdigest()
