"""Replay observed responses/actual search traces, never a manually seeded registry."""
import hashlib,json
from pathlib import Path
from product_tool.adapters.lg_browser_search import BrowserCandidate,BrowserSearchResult
R=Path('reports/playstation_stage67')
class CapturedSession:
 def __init__(self):
  self.responses={}
  for root in (Path('reports/playstation_stage66'),R):
   for file in root.glob('*http.json'):
    for v in json.loads(file.read_text(encoding='utf-8')):
     if v.get('status_code') is not None:self.responses[v['url']]=v
   p=root/'playstation_fetch.json'
   if p.exists():
    for v in json.loads(p.read_text(encoding='utf-8')):
     if v.get('status_code') is not None:self.responses[v['url']]=v
 def get(self,url,**kwargs):
  v=self.responses.get(url,{});final=v.get('final_url') or url;key=hashlib.sha256(final.encode()).hexdigest()[:20]
  suffix='.pdf' if final.lower().endswith('.pdf') else '.html'
  paths=[root/sub/(key+suffix) for root in (R,Path('reports/playstation_stage66')) for sub in ('playstation_captures','observed')]
  p=next((p for p in paths if p.exists()),None)
  text=p.read_bytes().decode('latin-1') if p and suffix=='.pdf' else p.read_text(encoding='utf-8') if p else ''
  return type('Response',(),dict(url=final,text=text,status_code=200 if p else 404,truncated=False))()
class CapturedSearch:
 def __init__(self):self.trace_callback=None
 def search_provider(self,provider,query):
  found=[];outcome='no_candidates'
  path=R/'live.json'
  if path.exists():
   for r in json.loads(path.read_text(encoding='utf-8'))['results']:
    for e in r['trace']:
     if e.get('query')!=query or e.get('provider') not in (provider,provider+'_browser'):continue
     if e.get('event')=='result' and e.get('decision')=='candidate':found.append(BrowserCandidate(e['url'],e.get('candidate_type','product'),query=query,provider=provider))
     if e.get('event')=='query_outcome':outcome=e.get('outcome',outcome)
  return BrowserSearchResult('global',query,'candidates_found' if found else outcome,tuple(found))
 def close(self):pass
