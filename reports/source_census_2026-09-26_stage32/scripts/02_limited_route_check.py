"""Two observed official pages maximum, under the repository policy session."""
from __future__ import annotations
import json,logging,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; STAGE=HERE.parent
sys.path.insert(0,str(ROOT)); logging.disable(logging.CRITICAL)
import requests
from product_tool.adapters.common import SourceError,fetch_with_retry
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import PolicyAwareSession,RequestBudget,record_responses,request_budget
from product_tool.adapters.samsung import parse_product_page,product_data_codes
from product_tool.adapters.samsung_source import PAGE_HOSTS,USER_AGENT
def stopped(path):
 if not path.exists():return []
 return sorted(stopped_hosts_from_fetch_log(x for x in json.loads(path.read_text(encoding='utf-8')) if isinstance(x,dict)))
def main():
 d=json.loads((STAGE/'raw/route_declaration.json').read_text(encoding='utf-8'))
 work=STAGE/'route_check/workdir'; assert not work.exists(),'run once only'; work.mkdir(parents=True)
 plain=requests.Session(); plain.headers.update({'User-Agent':USER_AGENT,'Accept-Language':'ru-RU,ru;q=0.9,en;q=0.7'})
 log=work/'samsung_fetch_log.json'
 client=PolicyAwareSession(log,allowed_hosts=PAGE_HOSTS,underlying=plain,max_bytes=d['budget']['page_cap_bytes'],min_interval_seconds=d['budget']['pacing_seconds'])
 budget=RequestBudget(max_per_row=1,max_total=2)
 results={}; halted=''
 with record_responses(STAGE/'route_check/responses'),request_budget(budget):
  for key in ('PROJECTOR','GPS'):
   sku=d['products'][key]; url=d['observed_urls'][key]
   if halted or stopped(log):results[key]={'url':url,'skipped':'host stopped'};continue
   budget.begin_row(sku)
   try:
    response=fetch_with_retry(client,url,deadline=1e12,clock=lambda:0.0)
    card=parse_product_page(response.text,url,sku)
    results[key]={'url':url,'status':response.status_code,'bytes':len(response.content),'identity':{'level':card.identity.level,'strength':card.identity.evidence_strength,'jsonld_sku':card.identity.jsonld_sku,'title':card.identity.title,'is_product_page':card.identity.is_product_page,'evidence':card.identity.evidence,'open_differences':card.identity.open_differences},'product_data_codes':sorted(product_data_codes(response.text)),'specs':[{'name':x.name,'value':x.value} for x in card.specs],'photos':{'full_size':len(card.photos.photos),'thumbnails':len(card.photos.thumbnails),'three_d':len(card.photos.three_d)},'document_links':[{'href':x.href,'file_name':x.file_name,'model_name':x.model_name,'language_hint':x.language_hint} for x in card.documents],'gaps':card.gaps}
   except SourceError as exc:
    results[key]={'url':url,'error':str(exc)[:500]}
    if stopped(log) or any(x in str(exc) for x in ('policy_host_stopped','HTTP 401','HTTP 403','HTTP 429','challenge')):halted=str(exc)[:500]
 out={'budget':{'max':2,'spent':budget.total,'log':budget.log},'results':results,'stopped_hosts':stopped(log),'halted':halted}
 (STAGE/'raw/route_check_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'spent':budget.total,'stopped_hosts':out['stopped_hosts'],'results':{k:{'status':v.get('status'),'error':v.get('error'),'identity':v.get('identity'),'codes':v.get('product_data_codes'),'specs':len(v.get('specs',[])),'photos':v.get('photos'),'documents':len(v.get('document_links',[]))} for k,v in results.items()}},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
