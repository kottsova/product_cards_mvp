"""Bounded read-only public-page session. Optional visible persistent Chrome.

No challenge interaction, stealth settings, cookie import, or access-stop bypass.
The same context serves search and discovered article; HTML is always fresh DOM.
"""
import hashlib,re,time
import json
import os
from datetime import datetime,timezone
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from ..adapters import access_stop,policy_fetch
from ..adapters.common import utc_now
from .browser_runtime import BrowserFailure
from .browser_contracts import BrowserBudget
from .browser_resources import admit_resource
from .attended_support import looks_like_challenge


class PublicBrowserSession:
 def __init__(self, *, allowed_hosts, fetch_log_path, profile_dir=None, visible=False,
              budget=None, max_document_bytes=3000000, playwright_factory=None, clock=time.monotonic, pause=time.sleep, resource_hosts=(), allow_readonly_graphql=False, readonly_graphql_paths=('/graphql',), use_system_ca=False):
  if not 1<=max_document_bytes<=3000000:raise ValueError('Invalid document budget')
  self.max_document_bytes=max_document_bytes
  if profile_dir is not None and not visible:raise ValueError('Persistent profile requires explicit visible mode')
  self.hosts=tuple(allowed_hosts);self.log=Path(fetch_log_path);self.profile=Path(profile_dir) if profile_dir else None;self.visible=visible
  self.resource_hosts=tuple(resource_hosts);self.allow_readonly_graphql=allow_readonly_graphql
  self.readonly_graphql_paths=tuple(readonly_graphql_paths)
  self.use_system_ca=use_system_ca
  self.budget=budget or BrowserBudget(deadline_seconds=30,operation_timeout_seconds=10,max_dom_bytes=1000000)
  self.factory=playwright_factory;self.clock=clock;self.pause=pause;self.session_id='public_browser:'+uuid4().hex
  self.context=self.page=self.browser=self.cm=None;self.counts={};self.events=[];self.status=None;self.signal='';self.started=0;self.total_navigations=0;self.created=0
 def allowed(self,url):
  try:
   p=urlsplit(url);h=p.hostname or ''
   return p.scheme=='https' and p.port in {None,443} and not p.username and not p.password and any(h==x or h.endswith('.'+x) for x in self.hosts)
  except ValueError:return False
 def start(self):
  if self.context:return
  if self.factory is None:
   from playwright.sync_api import sync_playwright
   self.factory=sync_playwright
  previous=os.environ.get('NODE_USE_SYSTEM_CA')
  try:
   if self.use_system_ca:os.environ['NODE_USE_SYSTEM_CA']='1'
   self.cm=self.factory();p=self.cm.__enter__()
  finally:
   if self.use_system_ca:
    if previous is None:os.environ.pop('NODE_USE_SYSTEM_CA',None)
    else:os.environ['NODE_USE_SYSTEM_CA']=previous
  self.created=self.clock()
  if self.profile:
   self.profile.mkdir(parents=True,exist_ok=True)
   self.context=p.chromium.launch_persistent_context(str(self.profile),channel='chrome',headless=False,accept_downloads=False,service_workers='block',viewport={'width':1400,'height':900})
  else:
   self.browser=p.chromium.launch(headless=not self.visible)
   self.context=self.browser.new_context(accept_downloads=False,service_workers='block')
  self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
  self.context.route('**/*',self.route);self.page.on('response',self.response)
  self.page.on('pageerror',lambda _:self.counts.update(javascript_errors=self.counts.get('javascript_errors',0)+1))
  self.page.on('download',lambda d:d.cancel())
  self.context.on('page',lambda p:p.close() if p is not self.page else None)
 def route(self,route):
  r=route.request;nav=r.is_navigation_request() and r.frame==self.page.main_frame
  resource_allowed=self.allowed(r.url) or (not nav and urlsplit(r.url).scheme=='https' and urlsplit(r.url).hostname in self.resource_hosts)
  readonly_post=False
  if self.allow_readonly_graphql and not nav and self.allowed(r.url) and r.method=='POST' and urlsplit(r.url).path in self.readonly_graphql_paths:
   try:
    body=json.loads(r.post_data or '{}');query=body.get('query','')
    readonly_post=isinstance(query,str) and len(query)<100000 and bool(re.match(r'\s*(?:query\b|\{)',query)) and not re.search(r'\b(?:mutation|subscription)\b',query)
   except (ValueError,TypeError,AttributeError):pass
  if not resource_allowed or re.search(r'/(?:login|register|account|cart|checkout|contact)(?:[/.]|$)',urlsplit(r.url).path,re.I) or (r.method not in {'GET','HEAD'} and not readonly_post):
   from .search_routes import redact_url
   rejected=self.counts.setdefault('rejected_requests',[])
   if len(rejected)<30:rejected.append({'url':redact_url(r.url),'method':r.method,'resource_type':r.resource_type,'reason':'host_not_allowed' if not resource_allowed else 'method_or_account_flow'})
   if nav:self.signal='interaction_blocked'
   route.abort();return
  if self.signal or self.clock()-self.started>=self.budget.deadline_seconds:
   route.abort();return
  if nav:
   self.counts['navigations']=self.counts.get('navigations',0)+1;self.total_navigations+=1
   if self.counts['navigations']>self.budget.max_navigations:self.signal='budget_exhausted';route.abort();return
  decision=admit_resource(self.counts,r.resource_type,urlsplit(r.url).path,self.budget.max_network_requests)
  if decision!='allowed':
   if nav:self.signal=decision
   route.abort();return
  route.continue_()
 def response(self,r):
  if not self.allowed(r.url):return
  main=r.request.is_navigation_request() and r.request.frame==self.page.main_frame
  if main:self.status=r.status
  if r.status==429:
   self.signal='rate_limited';self.counts['rate_limit_url']=r.url
  elif main and r.status in {401,403}:
   self.signal='http_denied';self.counts['http_denied_url']=r.url
  if r.status==429 or main and r.status in {401,403}:
   # Persist the observed denial before any DOM/driver wait can time out.
   policy_fetch.append_log_entry(self.log,{'url':r.url,'final_url':r.url,'observed_document_url':self.page.url,'status_code':r.status,'checked_at':utc_now(),'access_status':'rate_limited' if r.status==429 else 'http_denied','protection_status':'ordinary_page','source_session':self.session_id})
  # A failed ancillary request is evidence, not a denial of the document host.
  if main or r.status in {401,403,429}:self.events.append({'url':r.url,'status':r.status,'main_document':main})
 def snapshot(self, *, after_manual=False):
  html=self.page.content();url=self.page.url
  self.counts.update(document_status=self.status,document_bytes=len(html.encode('utf8')))
  # Explicit passive observation after the operator's manual navigation.
  # Never navigate around an active stop; only a newer successful document
  # response in this same session can resolve temporary challenge/rate stops.
  if after_manual and self.visible and self.signal in {'challenge_detected','rate_limited'}:
   main_success=bool(self.events and self.events[-1].get('main_document') and self.events[-1].get('status')==200)
   if main_success and self.status==200 and not looks_like_challenge(url,html,200) and len(html.encode('utf8'))<=self.max_document_bytes:
    proof={'url':url,'status_code':200,'protection_status':'ordinary_page','captured_at':datetime.now(timezone.utc).isoformat(),'source_session':self.session_id,'sha256':hashlib.sha256(html.encode('utf8')).hexdigest()}
    policy_fetch.append_log_entry(self.log,{'event':'attended_response_success','domain':urlsplit(url).hostname,'source_session':self.session_id,'proof':proof})
    self.signal=''
  if not self.allowed(url):raise BrowserFailure('foreign_redirect',self.counts)
  if looks_like_challenge(url,html,self.status):
   self.signal=self.signal or 'challenge_detected'
  if self.signal:
   status=429 if self.signal=='rate_limited' else self.status
   blocked=self.counts.get('rate_limit_url') or url
   entry={'url':blocked,'final_url':blocked,'observed_document_url':url,'status_code':status,'checked_at':utc_now(),'access_status':self.signal,'protection_status':'challenge_confirmed' if self.signal=='challenge_detected' else 'ordinary_page','source_session':self.session_id}
   if self.signal in {'rate_limited','http_denied','challenge_detected'}:policy_fetch.append_log_entry(self.log,entry)
   raise BrowserFailure(self.signal,self.counts)
  if self.status!=200:raise BrowserFailure('document_not_successful',self.counts)
  if len(html.encode('utf8'))>self.max_document_bytes:raise BrowserFailure('projection_budget_exhausted',self.counts)
  return {'url':url,'html':html,'status_code':self.status,'session_id':self.session_id,'visible':self.visible,'persistent':bool(self.profile),'counts':dict(self.counts),'response_events':list(self.events),'captured_at':utc_now(),'sha256':hashlib.sha256(html.encode('utf8')).hexdigest()}
 def call(self,command,**args):
  if command=='document_snapshot':return self.snapshot(after_manual=bool(args.get('after_manual')))
  if command!='goto':raise BrowserFailure('interaction_blocked',self.counts)
  url=args['url']
  if not self.allowed(url):raise BrowserFailure('foreign_redirect',self.counts)
  if (urlsplit(url).hostname or '') in access_stop.active_stops(policy_fetch.read_log(self.log)):raise BrowserFailure('host_stopped',self.counts)
  if self.total_navigations>=100 or self.clock()-self.created>1800:raise BrowserFailure('session_budget_exhausted',self.counts)
  self.pause(2) # Same session; bounded pacing, no retry after denied/challenge/429.
  self.started=self.clock();self.counts={};self.events=[];self.signal='';self.status=None
  try:self.page.goto(url,wait_until='domcontentloaded',timeout=self.budget.operation_timeout_seconds*1000)
  except Exception:
   if not self.signal:raise BrowserFailure('render_timeout',self.counts)
  self.page.wait_for_timeout(1200)
  return {k:v for k,v in self.snapshot().items() if k!='html'}
 def close(self):
  if self.context:self.context.close();self.context=None
  if self.browser:self.browser.close();self.browser=None
  if self.cm:self.cm.__exit__(None,None,None);self.cm=None

 def select_revision(self,pnc):
  """Read-only published menu selection with the existing snapshot guards."""
  if not re.fullmatch(r'\d{11}',pnc):raise BrowserFailure('interaction_blocked')
  self.snapshot()
  menu=self.page.locator('div[role="combobox"]').filter(has=self.page.locator(f'button[role="menuitem"][aria-label="{pnc}"]'))
  menu.locator('input[aria-hidden="false"]').click(timeout=5000)
  self.page.locator(f'button[role="menuitem"][aria-label="{pnc}"]').click(timeout=5000)
  self.page.wait_for_timeout(1200)
  return self.page.url

 def binary_transport(self,max_bytes=8000000):
  """Requests-compatible public GET facade sharing this context's cookies.

  Existing PolicyAwareSession checks hosts, redirects, cooldown and pacing.
  Playwright's API response is buffered: reject oversized declared bodies
  before reading, and enforce the byte cap on undeclared bodies afterwards.
  """
  if not 1<=max_bytes<=15000000:raise ValueError('Invalid binary budget')
  owner=self
  class Transport:
   headers={}
   last_error=''
   def get(self,url,timeout=10,**kwargs):
    import requests
    if not owner.allowed(url):raise requests.ConnectionError('foreign binary URL')
    if (urlsplit(url).hostname or '') in access_stop.active_stops(policy_fetch.read_log(owner.log)):
     raise requests.ConnectionError('host_stopped')
    owner.start()
    try:
     from urllib.parse import urljoin
     history=[];target=url
     for redirect_index in range(6):
      if not owner.allowed(target):raise ValueError('foreign binary redirect')
      if (urlsplit(target).hostname or '') in access_stop.active_stops(policy_fetch.read_log(owner.log)):raise ValueError('host_stopped before binary redirect')
      result=owner.context.request.get(target,timeout=min(10,timeout)*1000,max_redirects=0,fail_on_status_code=False,headers={'Accept-Encoding':'identity'})
      if result.status not in {301,302,303,307,308} or kwargs.get('allow_redirects') is False:break
      location=result.headers.get('location') or result.headers.get('Location')
      if not location:break
      prior=requests.Response();prior.status_code=result.status;prior.url=result.url;prior.headers.update(result.headers);prior._content=b'';history.append(prior)
      target=urljoin(result.url,location);result.dispose();del result
      if redirect_index==5:raise ValueError('binary redirect budget exhausted')
      owner.pause(1)
     length=result.headers.get('content-length','')
     if length.isdigit() and int(length)>max_bytes:raise ValueError('binary declared size exceeds budget')
     data=result.body()
     if len(data)>max_bytes:raise ValueError('binary size exceeds budget')
     response=requests.Response();response.status_code=result.status;response.url=result.url
     response.headers.update(result.headers);response._content=data;response._content_consumed=True
     response.history=history
     response.encoding='utf-8'
     return response
    except Exception as exc:
     self.last_error=str(exc)
     raise requests.ConnectionError(str(exc)) from exc
    finally:
     if 'result' in locals():result.dispose()
  return Transport()


class IsolatedPublicBrowserSession:
 """Existing public session and worker protocol with an outer wall-clock bound.

 All browser work stays in one worker/context. A stalled driver cannot hold the
 caller indefinitely; killing that owned worker does not clear access stops.
 """
 def __init__(self, *, trace_path=None, worker_factory=None, **options):
  from .browser_runtime import PlaywrightBrowser,BrowserRuntime
  import sys
  self.options=options;self.budget=options.get('budget') or BrowserBudget()
  self.options['budget']=self.budget
  self.trace_path=Path(trace_path or Path(options['fetch_log_path']).with_name('electrolux_browser_timing.jsonl'));self.trace_path.parent.mkdir(parents=True,exist_ok=True)
  self.worker_factory=worker_factory or (lambda:PlaywrightBrowser(BrowserRuntime(True,sys.executable),self.budget,options['allowed_hosts']))
  self.worker=self.worker_factory();self.worker.terminate_tree=True
  self.clock=time.monotonic;self.deadline=float('inf');self.context=None;self.status=None;self.signal='';self.total_navigations=0;self.session_id='';self.url='';self.cookies_count=0;self.trace_callback=None;self.failed=False;self.recoveries=0;self.job_context={}
 def event(self,**value):
  value={'event':'browser_timing','timestamp':utc_now(),'session_id':self.session_id,**self.job_context,**value}
  with self.trace_path.open('a',encoding='utf8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
  if self.trace_callback:self.trace_callback(value)
 def invoke(self,command,limit,**args):
  left=self.deadline-self.clock()
  if self.failed:raise BrowserFailure('session_unavailable_after_wall_timeout')
  if left<=0:raise BrowserFailure('product_budget_exhausted')
  limit=min(limit,left);start=self.clock();reason='';result={};requested_url=args.get('url',self.url)
  self.event(phase=command,state='start',url=requested_url,wall_timeout=limit,retries=0)
  try:
   result=self.worker.call(command,wall_timeout=limit,diagnostic_wall_timeout=limit,diagnostic_context=self.job_context,**args)
   self.status=result.get('status_code',self.status);self.signal=result.get('signal','');self.url=result.get('url',self.url);self.total_navigations=result.get('total_navigations',self.total_navigations);self.cookies_count=result.get('cookie_count',self.cookies_count);self.session_id=result.get('session_id',self.session_id)
   return result
  except BrowserFailure as exc:
   reason=str(exc)
   self.status=exc.counts.get('document_status',self.status);self.signal=exc.counts.get('signal','')
   if reason in {'driver_wall_timeout','driver_disconnected'} or self.worker.process and self.worker.process.poll() is not None:
    self.worker.terminate();self.failed=True;self.context=None;self.status=None;self.url='';self.cookies_count=0
   raise BrowserFailure(reason) from exc
  finally:self.event(phase=command,state='end',url=requested_url,final_url=result.get('url',self.url),elapsed=round(self.clock()-start,4),exception=reason,timeout='timeout' in reason.lower(),retries=0,challenge=result.get('signal',self.signal),browser_events=result.get('timing_events',[]),dom_state=result.get('dom_state','unknown'),network_idle_wait=False)
 def start(self):
  if self.context:return
  options={k:str(v) if isinstance(v,Path) else asdict(v) if k=='budget' else v for k,v in self.options.items()}
  options['timing_path']=str(self.trace_path)
  start=self.clock();self.event(phase='public_start',state='start',wall_timeout=18,retries=0)
  reason=''
  try:
   result=self.worker.start('public_start',wall_timeout=18,diagnostic_wall_timeout=18,options=options);self.context=True
   self.session_id=result['session_id'];self.cookies_count=result['cookie_count'];self.url=result['url']
  except BrowserFailure as exc:
   reason=str(exc);self.worker.terminate();self.failed=True;self.context=None;raise
  finally:self.event(phase='public_start',state='end',elapsed=round(self.clock()-start,4),session_id=self.session_id,exception=reason,timeout='timeout' in reason.lower())
 def call(self,command,**args):
  if command=='goto':return self.invoke('public_goto',18,**args)
  if command=='document_snapshot':return self.snapshot(**args)
  raise BrowserFailure('interaction_blocked')
 def snapshot(self,**kwargs):return self.invoke('public_snapshot',6,after_manual=bool(kwargs.get('after_manual')))
 def select_revision(self,pnc):return self.invoke('public_revision',16,pnc=pnc)['url']
 def cookie_count(self):return self.cookies_count
 def recover_for_next_product(self):
  """One technical recovery, same profile/log; no URL retry or stop clearing."""
  if not self.failed:return
  if self.recoveries>=1:raise BrowserFailure('session_recovery_budget_exhausted')
  self.worker.close();self.worker=self.worker_factory();self.worker.terminate_tree=True
  self.context=None;self.status=None;self.signal='';self.url='';self.cookies_count=0;self.failed=False;self.recoveries+=1
  self.event(phase='session_recovery',state='start',retries=self.recoveries,reason='owned worker wall timeout; next product only; host stops retained')
  reason=''
  try:self.start()
  except BrowserFailure as exc:reason=str(exc);raise
  finally:self.event(phase='session_recovery',state='end',retries=self.recoveries,exception=reason,session_id=self.session_id)
 def close(self):
  old=self.deadline;self.deadline=float('inf') # Cleanup has its own bound even after product expiry.
  if not self.failed and self.context:
   try:self.invoke('public_close',6)
   except BrowserFailure:pass
  self.worker.close();self.context=None;self.deadline=old
 def binary_transport(self,max_bytes=8000000):
  owner=self
  class Transport:
   headers={}
   def get(self,url,timeout=10,**kwargs):
    import base64,requests
    try:r=owner.invoke('public_binary',min(timeout+3,13),url=url,timeout=timeout,max_bytes=max_bytes,allow_redirects=kwargs.get('allow_redirects',True))
    except BrowserFailure as exc:raise requests.ConnectionError(str(exc)) from exc
    response=requests.Response();response.status_code=r['status_code'];response.url=r['url'];response.headers.update(r['headers']);response._content=base64.b64decode(r['body']);response._content_consumed=True;response.encoding='utf8';response.history=[]
    for x in r.get('history',[]):
     prior=requests.Response();prior.url=x['url'];prior.status_code=x['status_code'];prior.headers.update(x['headers']);prior._content=b'';response.history.append(prior)
    return response
  return Transport()
