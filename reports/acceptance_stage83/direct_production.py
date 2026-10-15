"""Fresh DB, identical imported cells, ordinary worker; no injected providers/replay."""
import sys,json,time,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,storage,worker,readiness,discovery_trace,card_evidence,attribute_projection,photo_inventory
from product_tool.runtime_diagnostics import runtime_identity
out=Path(__file__).parent;root=out.parents[1]
batch=json.loads((out/'cross_batch_final.json').read_text(encoding='utf8'))
phase=sys.argv[1] if len(sys.argv)>1 else 'direct_production'
dest=out/phase;dest.mkdir(exist_ok=True);db=dest/'batches.sqlite3'
assert not db.exists(),'Fresh qualification DB required'
if 'shared_history' in phase:
 shutil.copyfile(root/'data/backups/stage83_acceptance_before.sqlite3',db)
jobs.initialize(db)
columns=('id','batch_id','row_number','name','brand','search_code','alternate_code','category','needs_confirmation','issues_json','original_values_json','identity_json')
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',(batch['id'],batch['filename'],batch['sheet_name'],json.dumps(batch['mapping']),batch['confirmed_at']))
 for p in batch['products']:
  raw={**p,'search_code':p.get('input_search_code',p['search_code'])}
  c.execute('INSERT INTO products ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[raw[k] for k in columns])
runtime=runtime_identity();summary=[]
for p in batch['products']:
 pid=p['id'];jid=jobs.enqueue(db,pid,[1,2,3,4,6]);started=time.monotonic()
 assert worker.run_once(db)
 p=jobs.get_product(db,pid);j=jobs.list_jobs(db,pid)[0];kind=photo_inventory.evidence_kind(p)
 result=dict(observation='actual_direct_run_once_default_factories_new_product_sources_no_capture_replay',prior_history='original_user_DB_before_stage83' if 'shared_history' in phase else 'empty_DB',runtime=runtime,product=p,job=j,events=jobs.list_events(db,jid),trace=discovery_trace.for_job(db,jid),sources=jobs.get_source_pages(db,pid),facts=jobs.get_facts(db,pid),resolved=jobs.get_resolved(db,pid),canonical=attribute_projection.final_attribute_rows(db,pid),photos=photo_inventory.enriched_photos(db,pid),documents=jobs.get_documents(db,pid),evidence=card_evidence.load(db,pid,kind),semantics=card_evidence.load(db,pid,'semantic_decomposition'),readiness=readiness.card_readiness(db,pid))
 (dest/f'{pid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf8')
 row=dict(id=pid,brand=p['brand'],article=p['search_code'],job=j['status'],seconds=round(time.monotonic()-started,2),specs=len(result['canonical']),photos=sum(x['identity_confirmed'] for x in result['photos']),readiness=result['readiness']['verdict'],sources=[s['url'] for s in result['sources'] if s['url'] and not s['error']])
 summary.append(row);(dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(row,ensure_ascii=False),flush=True)
