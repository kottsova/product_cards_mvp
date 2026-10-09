"""Bounded read-only public-page session. Optional visible persistent Chrome.

No challenge interaction, stealth settings, cookie import, or access-stop bypass.
The same context serves search and discovered article; HTML is always fresh DOM.
"""
import hashlib,re,time
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
              budget=None, max_document_bytes=3000000, playwright_factory=None, clock=time.monotonic, pause=time.sleep):
  if not 1<=max_document_bytes<=3000000:raise ValueError('Invalid document budget')
  self.max_document_bytes=max_document_bytes
  if profile_dir is not None and not visible:raise ValueError('Persistent profile requires explicit visible mode')
  self.hosts=tuple(allowed_hosts);self.log=Path(fetch_log_path);self.profile=Path(profile_dir) if profile_dir else None;self.visible=visible
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
  self.cm=self.factory();p=self.cm.__enter__();self.created=self.clock()
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
  if not self.allowed(r.url) or re.search(r'/(?:login|register|account|cart|checkout|contact)(?:[/.]|$)',urlsplit(r.url).path,re.I) or r.method not in {'GET','HEAD'}:
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
