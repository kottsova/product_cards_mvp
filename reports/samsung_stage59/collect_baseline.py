from pathlib import Path
import json
from product_tool import card_evidence,jobs,samsung_readiness,storage
root=Path(__file__).resolve().parent
path=root/'baseline.sqlite3'
product=storage.get_batch(path,'stage59-control')['products'][0]
pid=product['id']; job=jobs.list_jobs(path,pid)[0]
result={'article':product['search_code'],'base_model':'WW90T554CAT','category':product['category'],'processed':True,'job_status':job['status'],'job_message':job['message'],'pages':jobs.get_source_pages(path,pid),'documents':jobs.get_documents(path,pid),'facts':jobs.get_facts(path,pid),'photos':jobs.get_photo_candidates(path,pid),'readiness':samsung_readiness.card_readiness(path,pid),'page_evidence':card_evidence.load(path,pid,'samsung_page'),'document_evidence':card_evidence.load(path,pid,'samsung_documents'),'dealer_evidence':card_evidence.load(path,pid,'dealer'),'trace':[],'events':jobs.list_events(path,job['id'])}
(root/'baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps({'article':result['article'],'job_status':job['status'],'readiness':result['readiness']['verdict'],'pages':len(result['pages']),'documents':len(result['documents']),'facts':len(result['facts']),'photos':len(result['photos'])},ensure_ascii=False))
