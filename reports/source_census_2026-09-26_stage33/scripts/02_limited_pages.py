"""Bounded Bosch Home product pages from previously observed official URLs."""
from __future__ import annotations
import json,logging,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT));logging.disable(logging.CRITICAL)
import requests
from product_tool.adapters.common import SourceError,fetch_with_retry
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import PolicyAwareSession,RequestBudget,record_responses,request_budget
def stopped(log):
 if not log.exists():return []
 return sorted(stopped_hosts_from_fetch_log(x for x in json.loads(log.read_text(encoding='utf-8')) if isinstance(x,dict)))
def main():
 d=json.loads((STAGE/'raw/bosch_route_declaration.json').read_text(encoding='utf-8'))
 work=STAGE/'bosch_route/workdir';assert not work.exists(),'run once only';work.mkdir(parents=True)
 plain=requests.Session();plain.headers.update({'User-Agent':'product-cards-mvp/1.0 (limited official product verification)','Accept-Language':'ru-RU,ru;q=0.9,en;q=0.7'})
 log=work/'bosch_fetch_log.json'
 client=PolicyAwareSession(log,allowed_hosts=('www.bosch-home.com',),underlying=plain,max_bytes=d['budget']['page_cap_bytes'],min_interval_seconds=d['budget']['pacing_seconds'])
 budget=RequestBudget(max_per_row=2,max_total=4);result={};halted=''
 with record_responses(STAGE/'bosch_route/responses'),request_budget(budget):
  for sku in ('MMB2111M','TWK7203'):
   url=d['first_batch'][sku]['url'];budget.begin_row(sku)
   if halted or stopped(log):result[sku]={'url':url,'skipped':'host stopped'};continue
   try:
    response=fetch_with_retry(client,url,deadline=1e12,clock=lambda:0.0)
    result[sku]={'url':url,'market':d['first_batch'][sku]['market'],'status':response.status_code,'bytes':len(response.content),'final_url':response.url,'truncated':bool(response.truncated)}
   except SourceError as exc:
    result[sku]={'url':url,'error':str(exc)[:500]}
    if stopped(log) or any(x in str(exc) for x in ('policy_host_stopped','HTTP 401','HTTP 403','HTTP 429','challenge')):halted=str(exc)[:500]
 out={'budget':{'max':4,'spent':budget.total,'log':budget.log},'pages':result,'stopped_hosts':stopped(log),'halted':halted}
 (STAGE/'raw/bosch_route_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(out,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
