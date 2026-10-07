from pathlib import Path
import json
from product_tool import jobs, storage, worker, readiness
root=Path('reports/lenovo_stage60')
p=root/'baseline.sqlite3'
if p.exists(): raise SystemExit('Baseline exists; refusing overwrite')
jobs.initialize(p)
with storage._connection(p) as db:
 db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage60-control','Lenovo unchanged baseline','Products','{}',storage._now()))
 pid=db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('stage60-control',1,'ThinkPad T14 Gen 5 (Intel)','Lenovo','21ML005BUS','','Laptops',0,'[]','{}')).lastrowid
jid=jobs.enqueue(p,pid,[1,2,3,4,6])
processed=worker.run_once(p)
r={'article':'21ML005BUS','model_name':'ThinkPad T14 Gen 5 (Intel)','machine_type':'21ML','full_mtm':'21ML005BUS','part_number':'21ML005BUS','processed':processed,'jobs':jobs.list_jobs(p,pid),'pages':jobs.get_source_pages(p,pid),'facts':jobs.get_facts(p,pid),'photos':jobs.get_photo_candidates(p,pid),'documents':jobs.get_documents(p,pid),'readiness':readiness.card_readiness(p,pid),'events':jobs.list_events(p,jid),'note':'Unmodified production run_once. Generic readiness is LG-specific; stored for audit, not Lenovo acceptance.'}
(root/'baseline.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps(r,ensure_ascii=True,indent=2,default=str))
