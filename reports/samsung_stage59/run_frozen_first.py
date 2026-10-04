"""Stage 59 frozen ten-model first pass through unchanged production run_once."""
from pathlib import Path
import json, traceback
from product_tool import card_evidence,jobs,samsung_readiness,storage,worker
root=Path(__file__).resolve().parent
items=json.loads((root/'dataset_frozen.json').read_text(encoding='utf-8-sig'))['models']
name='first_pass'; path=root/(name+'.sqlite3')
if path.exists(): raise SystemExit('first_pass exists; do not overwrite the frozen run')
jobs.initialize(path)
with storage._connection(path) as db:
    db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',(name,'Stage 59 frozen catalog sample','Товары','{}',storage._now()))
results=[]
for item in items:
    article=item['article']
    with storage._connection(path) as db:
        pid=db.execute('''INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)''',(name,item['catalog_row'],'Samsung '+article,'Samsung',article,'',item['category'],0,'[]','{}')).lastrowid
    try:
        jid=jobs.enqueue(path,pid,[1,2,3,4,6])
        processed=worker.run_once(path)
        error=''
    except Exception:
        processed=False; error=traceback.format_exc()
    history=jobs.list_jobs(path,pid)
    job=history[0] if history else {'status':'enqueue_error','message':error,'id':''}
    result={'article':article,'category':item['category'],'catalog_row':item['catalog_row'],'processed':processed,'exception':error,'job_status':job['status'],'job_message':job['message'],'pages':jobs.get_source_pages(path,pid),'documents':jobs.get_documents(path,pid),'facts':jobs.get_facts(path,pid),'photos':jobs.get_photo_candidates(path,pid),'readiness':samsung_readiness.card_readiness(path,pid),'page_evidence':card_evidence.load(path,pid,'samsung_page'),'document_evidence':card_evidence.load(path,pid,'samsung_documents'),'dealer_evidence':card_evidence.load(path,pid,'dealer'),'events':jobs.list_events(path,job['id']) if job['id'] else []}
    results.append(result)
    (root/'first_pass.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'article':article,'status':job['status'],'readiness':result['readiness']['verdict'],'pages':len(result['pages']),'facts':len(result['facts']),'photos':len(result['photos']),'docs':len(result['documents']),'error':bool(error)},ensure_ascii=False),flush=True)
