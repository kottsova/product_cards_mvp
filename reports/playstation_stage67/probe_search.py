"""Save public sanitized projections from the existing bounded browser transport."""
import json
from pathlib import Path
from product_tool.adapters.lg_browser_search import LGBrowserSearch
from product_tool.census.browser_runtime import PlaywrightBrowser
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.playstation_discovery import search_kind
R=Path('reports/playstation_stage67')
class RecordingBrowser(PlaywrightBrowser):
 def call(self,*args,**kwargs):
  result=super().call(*args,**kwargs)
  if args and args[0]=='goto':(R/('search_projection_'+str(len(list(R.glob('search_projection_*.json'))))+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  return result
events=[]
with LGBrowserSearch(R/'playstation_search.json',allowed_hosts=('www.playstation.com','direct.playstation.com','www.bing.com','bing.com','duckduckgo.com','www.google.com','google.com','gstatic.com'),official_host='www.playstation.com',official_hosts=('www.playstation.com','direct.playstation.com'),driver_factory=RecordingBrowser,budget=BrowserBudget(deadline_seconds=30,operation_timeout_seconds=10),candidate_classifier=search_kind) as b:
 b.trace_callback=events.append
 for provider in ('bing','duckduckgo'):
  q='site:direct.playstation.com "Fortnite" "Flowering Chaos"'
  r=b.search_provider(provider,q);print(provider,r.outcome,[(c.url,c.label) for c in r.candidates],flush=True)
(R/'search_probe_trace.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
