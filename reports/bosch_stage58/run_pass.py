"""Stage 58 real production run_once for control and frozen Bosch sample."""
from pathlib import Path
import json,sys
from product_tool import bosch_readiness,card_evidence,discovery_trace,jobs,manual_status,storage,worker
root=Path(__file__).resolve().parent
control=sys.argv[1]=='control'
items=[{'article':'PUE611BB5E','category':'Варочные панели'}] if control else json.loads((root/'dataset_frozen.json').read_text(encoding='utf-8-sig'))['models']
name='control_pass' if control else 'batch_pass'
path=root/(name+'.sqlite3')
if path.exists():raise SystemExit(name+' exists; do not overwrite a run')
jobs.initialize(path)
with storage._connection(path) as c:c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',(name,'Stage 58 live','Товары','{}',storage._now()))
results=[]
for i,item in enumerate(items,2):
 with storage._connection(path) as c:
  pid=c.execute('''INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)''',(name,i,item['article'],'BOSCH',item['article'],'',item['category'],0,'[]','{}')).lastrowid
 jid=jobs.enqueue(path,pid,[1,2,3,4,6])
 processed=worker.run_once(path)
 job=jobs.list_jobs(path,pid)[0]
 result={'article':item['article'],'category':item['category'],'processed':processed,'job_status':job['status'],'job_message':job['message'],'pages':jobs.get_source_pages(path,pid),'documents':jobs.get_documents(path,pid),'facts':jobs.get_facts(path,pid),'photos':jobs.get_photo_candidates(path,pid),'readiness':bosch_readiness.card_readiness(path,pid),'manual_status':manual_status.russian_status(path,pid,item['article'],lg=False),'evidence':card_evidence.load(path,pid,'bosch_home'),'trace':discovery_trace.for_job(path,jid),'events':jobs.list_events(path,jid)}
 results.append(result)
 print(json.dumps({'article':item['article'],'job_status':job['status'],'readiness':result['readiness']['verdict'],'pages':len(result['pages']),'facts':len(result['facts']),'photos':len(result['photos']),'documents':len(result['documents'])},ensure_ascii=False),flush=True)
(root/(name+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

