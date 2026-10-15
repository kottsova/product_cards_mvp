import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,discovery_trace,card_evidence
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;db=root/'data/batches.sqlite3'
with sqlite3.connect(db) as c:
 c.row_factory=sqlite3.Row
 batches=[dict(r) for r in c.execute('select * from batches order by confirmed_at desc limit 5')]
 products=[dict(r) for r in c.execute("select * from products where upper(search_code) like '%S3WER%' or upper(search_code) like '%S40T%'")]
 latest=[dict(r) for r in c.execute('select id,product_id,status,message,stages_json,started_at,finished_at from search_jobs order by rowid desc limit 12')]
 evidence=[]
 for p in products:
  history=jobs.list_jobs(db,p['id'])
  evidence.append(dict(product=p,jobs=history,sources=jobs.get_source_pages(db,p['id']),counts=jobs.result_counts(db,p['id']),events=jobs.list_events(db,history[0]['id']) if history else [],trace=discovery_trace.for_job(db,history[0]['id']) if history else []))
 snapshot=dict(batches=batches,latest_jobs=latest,lg=evidence)
target=out/'initial_state.json'
if not target.exists():target.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print(json.dumps(dict(batches=[{k:b[k] for k in ('id','filename','mapping_json','confirmed_at')} for b in batches],latest_jobs=latest,lg=[dict(product={k:e['product'][k] for k in ('id','batch_id','row_number','brand','name','search_code','alternate_code','category','original_values_json')},counts=e['counts'],latest_job=e['jobs'][0] if e['jobs'] else None,sources=[{k:s[k] for k in ('source_key','url','found_model','match_level','error','evidence')} for s in e['sources']]) for e in evidence]),ensure_ascii=False,indent=2))
backup=root/'data/backups/stage83_acceptance_before.sqlite3';backup.parent.mkdir(exist_ok=True)
if not backup.exists():
 with sqlite3.connect(db) as source,sqlite3.connect(backup) as destination:source.backup(destination)
