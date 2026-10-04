"""Stage 59 unchanged production baseline for catalog Samsung WW90T554CAT/LD."""
from pathlib import Path
import json
from product_tool import card_evidence, jobs, samsung_readiness, storage, worker

root=Path(__file__).resolve().parent
path=root/'baseline.sqlite3'
if path.exists(): raise SystemExit('baseline already exists; do not overwrite')
article='WW90T554CAT/LD'
jobs.initialize(path)
with storage._connection(path) as db:
    db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('stage59-control','Catalog row 12657','Товары','{}',storage._now()))
    pid=db.execute('''INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)''',('stage59-control',12657,'Стиральная машина WW90T554CAT/LD','Samsung',article,'','Стиральные машины',0,'[]','{}')).lastrowid
job_id=jobs.enqueue(path,pid,[1,2,3,4,6])
processed=worker.run_once(path)
job=jobs.list_jobs(path,pid)[0]
result={'article':article,'base_model':'WW90T554CAT','category':'Стиральные машины','processed':processed,'job_status':job['status'],'job_message':job['message'],'pages':jobs.get_source_pages(path,pid),'documents':jobs.get_documents(path,pid),'facts':jobs.get_facts(path,pid),'photos':jobs.get_photo_candidates(path,pid),'readiness':samsung_readiness.card_readiness(path,pid),'page_evidence':card_evidence.load(path,pid,'samsung_page'),'document_evidence':card_evidence.load(path,pid,'samsung_documents'),'dealer_evidence':card_evidence.load(path,pid,'dealer'),'trace':[],'events':jobs.list_events(path,job_id)}
(root/'baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps({'article':article,'job_status':job['status'],'readiness':result['readiness']['verdict'],'pages':len(result['pages']),'documents':len(result['documents']),'facts':len(result['facts']),'photos':len(result['photos'])},ensure_ascii=False),flush=True)

