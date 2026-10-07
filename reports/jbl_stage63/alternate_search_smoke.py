from pathlib import Path
import json,time
from product_tool.adapters.lg_browser_search import LGBrowserSearch
from product_tool.census.browser_contracts import BrowserBudget
r=Path('reports/jbl_stage63');trace=[];hosts=('www.jbl.com','jbl.com','id.jbl.com','uk.jbl.com','global.jbl.com','ca.jbl.com','kh.jbl.com');out=[]
s=LGBrowserSearch(r/'alternate_search_log.json',official_host='www.jbl.com',official_hosts=hosts,allowed_hosts=hosts+('www.bing.com','bing.com','duckduckgo.com','www.google.com','google.com','gstatic.com'),budget=BrowserBudget(deadline_seconds=25,operation_timeout_seconds=10));s.trace_callback=trace.append
try:
 for provider in ['bing','duckduckgo']:
  start=time.monotonic();z=s.search_provider(provider,'site:jbl.com JBL Xtreme 4');out.append({'provider':provider,'query':z.query,'outcome':z.outcome,'duration':round(time.monotonic()-start,2),'candidates':[vars(x) for x in z.candidates]});print(provider,z.outcome,len(z.candidates),flush=True)
finally:s.close()
(r/'alternate_search_smoke.json').write_text(json.dumps({'results':out,'trace':trace},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
