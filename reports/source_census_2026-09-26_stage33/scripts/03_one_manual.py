"""One product-linked Bosch user manual under the predeclared remaining budget."""
from __future__ import annotations
import gzip,hashlib,io,json,logging,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT));logging.disable(logging.CRITICAL)
import pypdf,requests
from product_tool.adapters.common import SourceError,fetch_with_retry
from product_tool.adapters.lg_documents import BinarySafeSession,document_bytes,looks_like_pdf,assess_document
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import PolicyAwareSession,RequestBudget,record_responses,request_budget
URL='https://media3.bsh-group.com/Documents/8001342866_A.pdf'
def stopped(log):
 if not log.exists():return []
 return sorted(stopped_hosts_from_fetch_log(x for x in json.loads(log.read_text(encoding='utf-8')) if isinstance(x,dict)))
def main():
 d=json.loads((STAGE/'raw/bosch_route_declaration.json').read_text(encoding='utf-8'))
 route=json.loads((STAGE/'raw/bosch_route_result.json').read_text(encoding='utf-8'))
 assert route['budget']['spent']==2 and not route['stopped_hosts']
 index=[json.loads(x) for x in (STAGE/'bosch_route/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
 item=next(x for x in index if x['url']==d['first_batch']['TWK7203']['url'])
 with gzip.open(STAGE/'bosch_route/responses'/item['saved_as'],'rt',encoding='utf-8') as h:html=h.read()
 assert URL in html and '"titleKey":"user-manuals"' in html.replace('\\"','"')
 log=STAGE/'bosch_route/workdir/bosch_fetch_log.json'
 plain=requests.Session();plain.headers.update({'User-Agent':'product-cards-mvp/1.0 (limited official document verification)'})
 client=PolicyAwareSession(log,allowed_hosts=('media3.bsh-group.com',),underlying=BinarySafeSession(plain),max_bytes=d['budget']['document_cap_bytes'],min_interval_seconds=d['budget']['pacing_seconds'])
 budget=RequestBudget(max_per_row=1,max_total=d['budget']['max_real_requests_total']-route['budget']['spent']);budget.begin_row('TWK7203')
 result={'url':URL,'observed_on':d['first_batch']['TWK7203']['url']}
 if stopped(log):result['skipped']='host stopped'
 else:
  try:
   with record_responses(STAGE/'bosch_route/responses'),request_budget(budget):response=fetch_with_retry(client,URL,deadline=1e12,clock=lambda:0.0)
   data=document_bytes(response)
   result.update({'status':response.status_code,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'is_pdf':looks_like_pdf(data),'truncated':response.truncated})
   if looks_like_pdf(data) and not response.truncated:
    pages=[p.extract_text() or '' for p in pypdf.PdfReader(io.BytesIO(data)).pages]
    assessment=assess_document(pages,['TWK7203'])
    result.update({'pages':len(pages),'assessment':assessment,'first_page_excerpt':pages[0][:500] if pages else ''})
    out=STAGE/'docs_extract';out.mkdir(exist_ok=True)
    with gzip.open(out/'TWK7203_manual_text.txt.gz','wt',encoding='utf-8') as h:h.write('\n\f\n'.join(pages))
   else:result['assessment']='unreadable or truncated PDF'
  except (SourceError,ValueError) as exc:result['error']=str(exc)[:500]
 result['budget_spent_this_step']=budget.total;result['budget_spent_cumulative']=route['budget']['spent']+budget.total;result['stopped_hosts']=stopped(log)
 (STAGE/'raw/bosch_manual_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
