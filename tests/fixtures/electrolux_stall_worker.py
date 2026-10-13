"""Offline synchronous page.goto fault through the ordinary public worker.

No sockets/browser requests: the native page is a parser fixture, not live
evidence. The first selected goto never returns; later processes are healthy.
"""
import json,os,sys,time,runpy
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'product_tool/census'))
from product_tool.census.public_browser import PublicBrowserSession
from tests.test_electrolux_stage78 import native,URL
FAULT=Path(os.environ['ELECTROLUX_QUALIFICATION_FAULT_DIR'])

class Page:
 def __init__(self,context):self.context=context;self.url='about:blank';self.main_frame=object();self.handlers={}
 def on(self,name,fn):self.handlers.setdefault(name,[]).append(fn)
 def goto(self,url,**kw):
  if not (FAULT/'fault.json').exists():
   if os.environ.get('ELECTROLUX_QUALIFICATION_RATE_BEFORE_STALL'):
    req=SimpleNamespace(is_navigation_request=lambda:True,frame=self.main_frame)
    for fn in self.handlers.get('response',[]):fn(SimpleNamespace(url=url,status=429,request=req))
   (FAULT/'fault.json').write_text(json.dumps({'origin':'offline injected synchronous page.goto','pid':os.getpid(),'url':url}))
   while True:time.sleep(60) # Ignore the native timeout deliberately.
  self.url=url
  req=SimpleNamespace(is_navigation_request=lambda:True,frame=self.main_frame)
  for fn in self.handlers.get('response',[]):fn(SimpleNamespace(url=url,status=200,request=req))
  for fn in self.handlers.get('domcontentloaded',[]):fn()
 def content(self):
  return native() if self.url==URL else '<a href="'+URL+'">EOF6P46X</a>'
 def wait_for_timeout(self,ms):pass
 def close(self):pass
class Context:
 def __init__(self):
  self.pages=[Page(self)];self.identity='offline-context-'+str(os.getpid())
  with (FAULT/'contexts.jsonl').open('a') as f:f.write(json.dumps({'id':self.identity,'created':True})+'\n')
 def route(self,*a):pass
 def on(self,*a):pass
 def cookies(self):return []
 def close(self):
  with (FAULT/'contexts.jsonl').open('a') as f:f.write(json.dumps({'id':self.identity,'closed':True})+'\n')
class Manager:
 def __enter__(self):
  return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=lambda *a,**kw:Context()))
 def __exit__(self,*a):pass
original=PublicBrowserSession.__init__
def injected_init(self,**options):
 original(self,**options,playwright_factory=Manager,pause=lambda _:None)
PublicBrowserSession.__init__=injected_init
runpy.run_path(str(ROOT/'product_tool/census/browser_worker.py'),run_name='__main__')
