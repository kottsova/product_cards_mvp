"""Stage 58 unmodified production baseline for PUE611BB5E."""
from pathlib import Path
from uuid import uuid4
import json
from product_tool import bosch_readiness, jobs, storage, worker

root=Path(__file__).resolve().parent
path=root/'baseline.sqlite3'
if path.exists():
    raise SystemExit('baseline already exists; results are frozen')
jobs.initialize(path)
with storage._connection(path) as c:
    c.execute("INSERT INTO batches VALUES (?,?,?,?,?)", ('stage58-control','catalog row 8615','Товары','{}',storage._now()))
    product_id=c.execute("""INSERT INTO products
        (batch_id,row_number,name,brand,search_code,alternate_code,category,
         needs_confirmation,issues_json,original_values_json)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ('stage58-control',2,'Варочная панель индукционная 60 см, PUE611BB5E',
         'BOSCH','PUE611BB5E','','Варочные панели',0,'[]','{}')).lastrowid
try:
    jobs.enqueue(path,product_id,[1,2,3,4,6])
    enqueue={'accepted':True}
except ValueError as exc:
    enqueue={'accepted':False,'reason':str(exc)}
# Exercise the production worker on an already queued job, as for a job
# persisted before the current enqueue gate. This does not change its code.
job_id=uuid4().hex
with storage._connection(path) as c:
    c.execute("""INSERT INTO search_jobs
        (id,product_id,stages_json,status,message,created_at,updated_at)
        VALUES (?,?,?,'queued',?,?,?)""",
        (job_id,product_id,'[1,2,3,4,6]','Stage 58 baseline',storage._now(),storage._now()))
ran=worker.run_once(path)
job=jobs.list_jobs(path,product_id)[0]
result={
    'article':'PUE611BB5E','category':'Варочные панели','enqueue':enqueue,
    'run_once_processed':ran,'job_status':job['status'],'job_message':job['message'],
    'query_variants':[],'official_urls':[],'support_pages':[],
    'documents':jobs.get_documents(path,product_id),
    'facts':jobs.get_facts(path,product_id),
    'photos':jobs.get_photo_candidates(path,product_id),
    'source_pages':jobs.get_source_pages(path,product_id),
    'readiness':bosch_readiness.card_readiness(path,product_id),
    'events':jobs.list_events(path,job_id),
}
(root/'baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('article','enqueue','run_once_processed','job_status','job_message','readiness')},ensure_ascii=False,default=str))
