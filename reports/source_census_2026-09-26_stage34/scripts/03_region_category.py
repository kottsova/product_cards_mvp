"""Follow one observed KZ category link, never a constructed product URL."""
from __future__ import annotations
import gzip,json,logging,sys
from pathlib import Path
from bs4 import BeautifulSoup
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT));logging.disable(logging.CRITICAL)
import requests
from product_tool.adapters.common import SourceError,fetch_with_retry
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import PolicyAwareSession,RequestBudget,record_responses,request_budget
URL='https://www.bosch-home.com/kz/ru/category/kuhonnaya-tehnika'
def stopped(log):
 if not log.exists():return []
 return sorted(stopped_hosts_from_fetch_log(x for x in json.loads(log.read_text(encoding='utf-8')) if isinstance(x,dict)))
def main():
 d=json.loads((STAGE/'raw/regional_declaration.json').read_text(encoding='utf-8'))
 first=json.loads((STAGE/'raw/region_first_result.json').read_text(encoding='utf-8'))
 assert first['budget']['spent']==1 and not first['stopped_hosts']
 index=[json.loads(x) for x in (STAGE/'region_check/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
 entry=next(x for x in index if x['url']==d['observed_start_url'])
 with gzip.open(STAGE/'region_check/responses'/entry['saved_as'],'rt',encoding='utf-8') as h:soup=BeautifulSoup(h.read(),'html.parser')
 assert any(a.get('href')==URL for a in soup.select('a[href]')),'category URL must be present as a link on saved KZ home'
 log=STAGE/'region_check/workdir/bosch_fetch_log.json';plain=requests.Session();plain.headers.update({'User-Agent':'ProductCardsSourceCensus/2.0 (bounded diagnostic probe)','Accept-Language':'ru-RU,ru;q=0.9,en;q=0.7'})
 client=PolicyAwareSession(log,allowed_hosts=tuple(d['allowed_hosts']),underlying=plain,max_bytes=d['budget']['page_cap_bytes'],min_interval_seconds=d['budget']['pacing_seconds'])
 budget=RequestBudget(max_per_row=2,max_total=d['budget']['max_real_requests_total']-first['budget']['spent']);budget.begin_row('kz_route')
 result={'url':URL,'observed_on':entry['final_url']}
 if stopped(log):result['skipped']='host stopped'
 else:
  try:
   with record_responses(STAGE/'region_check/responses'),request_budget(budget):r=fetch_with_retry(client,URL,deadline=1e12,clock=lambda:0.0)
   result.update({'status':r.status_code,'final_url':r.url,'bytes':len(r.content),'truncated':r.truncated})
  except SourceError as exc:result['error']=str(exc)[:500]
 out={'step':result,'budget_spent_this_step':budget.total,'budget_spent_cumulative':first['budget']['spent']+budget.total,'stopped_hosts':stopped(log)}
 (STAGE/'raw/region_category_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(out,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
