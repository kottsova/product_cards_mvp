from pathlib import Path
import json
from product_tool import jobs,storage,worker,card_evidence,discovery_trace,lenovo_pipeline
from product_tool.adapters.policy_session import record_responses
r=Path('reports/lenovo_stage61');p=r/'baseline_final.sqlite3'
if p.exists():raise SystemExit('Baseline after exists')
jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage60-baseline-after','Lenovo baseline after general adapter','Products','{}',storage._now()))
 pid=db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('stage60-baseline-after',1,'ThinkPad T14 Gen 5 (Intel)','Lenovo','21ML005BUS','','Laptops',0,'[]','{}')).lastrowid
jid=jobs.enqueue(p,pid,[1,2,3,4,6])
with record_responses(r/'baseline_final_responses'):worker.run_once(p)
result={'article':'21ML005BUS','job':jobs.list_jobs(p,pid)[0],'sources':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'resolved':jobs.get_resolved(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':lenovo_pipeline.card_readiness(p,pid),'evidence':card_evidence.load(p,pid,'lenovo'),'trace':discovery_trace.for_job(p,jid),'events':jobs.list_events(p,jid)}
(r/'baseline_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps({'job':result['job']['status'],'readiness':result['readiness'],'facts':len(result['facts'])},ensure_ascii=True),flush=True)
