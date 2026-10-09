"""Small Razer adapter over the existing policy, sitemap and browser transports."""
import hashlib,json,re,time,os
from pathlib import Path
from urllib.parse import quote,urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from .common import SourceDocument,ProductDocument,utc_now
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession
from ..lg_sitemap_discovery import parse_sitemap
from ..razer_page import parse_page,official
from ..razer_identity import model_name,key,components
from ..census.browser_runtime import discover_runtime,PlaywrightBrowser,BrowserFailure
from ..census.browser_contracts import BrowserBudget
HOSTS=('razer.com','razerzone.com')
# Public catalog endpoint declared in the official robots.txt, never product seeds.
SITEMAP='https://sitemap-xml.razer.com/pro-sitemaps-4237407.php?sn=sitemap1.xml'
class RazerAdapter:
 def __init__(self,*,clock=time.monotonic,fetch_log_path=Path('data/razer_fetch_log.json'),session=None,trace_callback=None,capture_dir=None,search_provider=None,browser_factory=None):
  self.clock=clock;self.log=Path(fetch_log_path);self.http=session or PolicyAwareSession(self.log,allowed_hosts=HOSTS,clock=clock,underlying=BinarySafeSession(requests.Session()),max_bytes=15_000_000);self.trace_callback=trace_callback;self.reports={};self.capture_dir=Path(capture_dir) if capture_dir else self.log.parent/'razer_captures';self.search_provider=search_provider;self.browser_factory=browser_factory
 def trace(self,**item):
  if self.trace_callback:self.trace_callback({'event':'razer_discovery','timestamp':utc_now(),'identity_relation':'unproven',**item})
 def capture(self,url,html,provider):
  self.capture_dir.mkdir(parents=True,exist_ok=True);raw=html.encode('utf8');sha=hashlib.sha256(raw).hexdigest();(self.capture_dir/(sha+'.html')).write_bytes(raw)
  return {'url':url,'provider':provider,'sha256':sha,'file':sha+'.html'}
 def render_support(self,url,query):
  # Normal public JS render only. No retry after any browser challenge/403/429.
  from . import policy_fetch,access_stop
  if (urlsplit(url).hostname or '') in access_stop.active_stops(policy_fetch.read_log(self.log)):
   self.trace(provider='official_support_browser',query=query,url=url,region='global',source_type='render',accepted=False,reason='host_stopped');return None
  driver=(self.browser_factory() if self.browser_factory else PlaywrightBrowser(discover_runtime(),BrowserBudget(deadline_seconds=20,operation_timeout_seconds=8),('mysupport.razer.com','assets2.razerzone.com','assets.razerzone.com')))
  try:
   driver.start();driver.call('goto',url=url,queries=[query],render_mode='render_existing_search_result',search_result_hosts=['mysupport.razer.com']);state=driver.call('document_snapshot');html=state.pop('html');self.trace(provider='official_support_browser',query=query,url=state['url'],region='global',source_type='render',accepted=False,reason='Public JS document rendered; identity checked separately',browser=state);return state['url'],html,self.capture(state['url'],html,'live_browser')
  except BrowserFailure as exc:
   reason=str(exc)
   if reason in {'rate_limited','challenge_detected'}:
    blocked_url=str(exc.counts.get('rate_limit_url') or url);policy_fetch.append_log_entry(self.log,{'url':blocked_url,'final_url':blocked_url,'status_code':429 if reason=='rate_limited' else 200,'checked_at':utc_now(),'access_status':'rate_limited' if reason=='rate_limited' else 'captcha_or_blocked','protection_status':'ordinary_page' if reason=='rate_limited' else 'challenge_confirmed','source_session':'razer_shared_browser'})
   self.trace(provider='official_support_browser',query=query,url=url,region='global',source_type='render',accepted=False,reason=reason,counts=exc.counts);return None
  finally:driver.close()
 def find_source(self,article,*,name='',category='',deadline=None):
  article=article.upper().strip();deadline=deadline or self.clock()+90;proofs=[];best=None;query=model_name(name)
  if not components(article)['family_prefix']:return SourceDocument('razer_model','Razer Official','',error='Invalid RZ code')
  # No route generated from a product slug or a known audit reference URL.
  self.trace(provider='regional_exact',query=article,url='https://www.razer.com/',region='requested',source_type='catalog',accepted=False,reason='No published exact-SKU search route; continue with official catalog')
  cache=self.capture_dir/'catalog.json';urls=[];observation='live_http'
  try:
   saved=json.loads(cache.read_text(encoding='utf8'))
   if time.time()-saved['timestamp']<86400 and saved['sitemap']==SITEMAP:urls=saved['urls'];observation='catalog_cache'
  except (OSError,ValueError,KeyError):pass
  if not urls:
   z=self.http.get(SITEMAP,timeout=min(10,max(1,deadline-self.clock())))
   if z.ok and not z.truncated:
    _,urls=parse_sitemap(z.text.encode('utf8'),SITEMAP);proofs.append(self.capture(SITEMAP,z.text,'live_http'));cache.write_text(json.dumps({'timestamp':time.time(),'sitemap':SITEMAP,'urls':urls}),encoding='utf8')
   else:self.trace(provider='official_sitemap',query=query,url=SITEMAP,region='global',source_type='sitemap',accepted=False,reason=z.marker or str(z.status_code))
  candidates=[u for u in urls if official(u) and key(urlsplit(u).path.rsplit('/',1)[-1])==key(query)]
  self.trace(provider='official_sitemap',query=query,url=SITEMAP,region='global',source_type='sitemap',accepted=False,reason='Catalog candidates require page identity',observation=observation,candidates=candidates[:8])
  # Actual loc URLs first; other official regional locs come next, bounded.
  for url in candidates[:3]:
   if self.clock()>=deadline-45:break
   z=self.http.get(url,timeout=6)
   self.trace(provider='official_catalog' if urlsplit(url).path.count('/')<=2 else 'other_official_regions',query=query,url=url,region=urlsplit(url).path.split('/')[1],source_type='pdp',accepted=False,reason=z.marker or str(z.status_code))
   if z.ok and not z.truncated:
    doc,ev=parse_page(z.text,z.url,article,name,category);proofs.append(self.capture(z.url,z.text,'live_http'))
    if ev['identity']['model_confirmed']:best=(doc,ev);break
  # Observed official search route from the site's own Search Support handler.
  search_url='https://mysupport.razer.com/app/answers/list/kw/'+quote(article,safe='')
  search=self.render_support(search_url,article) if self.clock()<deadline-20 else None
  support_urls=[]
  if search:
   final,html,proof=search;proofs.append(proof);soup=BeautifulSoup(html,'html.parser')
   for a in soup.select('a[href]'):
    label=a.get_text(' ',strip=True);url=urljoin(final,a['href'])
    if official(url) and '/answers/detail/' in url and re.search(r'Support\s*(?:&|and)\s*FAQs',label,re.I):
     from ..razer_identity import model_relation
     relation=model_relation(article,name,label);accept=relation['model_confirmed'];self.trace(provider='official_support_search',query=article,url=url,region='global',source_type='support_candidate',accepted=accept,reason=relation['reason'],identity_relation=relation['model_relation'])
     if accept:support_urls.append(url)
  for url in list(dict.fromkeys(support_urls))[:1]:
   if self.clock()>=deadline-5:break
   rendered=self.render_support(url,article)
   if rendered:
    final,html,proof=rendered;proofs.append(proof);doc,ev=parse_page(html,final,article,name,category);accept=ev['identity']['model_confirmed'];self.trace(provider='official_support',query=article,url=final,region='global',source_type='support',accepted=accept,reason=ev['identity']['reason'],identity_relation=ev['identity']['model_relation'])
    if accept:best=(doc,ev)
  if not support_urls and self.clock()<deadline-25:
   # Broaden the official query before external fallback; never guess article IDs.
   broadened=self.render_support('https://mysupport.razer.com/app/answers/list/kw/'+quote(query,safe=''),query)
   if broadened:
    final,html,proof=broadened;proofs.append(proof)
    from ..razer_identity import model_relation
    for a in BeautifulSoup(html,'html.parser').select('a[href]'):
     label=a.get_text(' ',strip=True);target=urljoin(final,a['href']);relation=model_relation(article,name,label)
     if not official(target) or '/answers/detail/' not in target or not relation['model_confirmed'] or not re.search(r'Support\s*(?:&|and)\s*FAQs',label,re.I):continue
     self.trace(provider='official_support_search',query=query,url=target,region='global',source_type='support_candidate',accepted=True,reason=relation['reason'],identity_relation='model_confirmed')
     rendered=self.render_support(target,query)
     if rendered:
      final,html,proof=rendered;proofs.append(proof);doc,ev=parse_page(html,final,article,name,category)
      if ev['identity']['model_confirmed']:best=(doc,ev)
     break
  if best is None:
   # Existing source-neutral browser search only after official miss.
   from .lg_browser_search import LGBrowserSearch
   searcher=self.search_provider or LGBrowserSearch(self.log,official_host='mysupport.razer.com',official_hosts=('www.razer.com','mysupport.razer.com'),allowed_hosts=('razer.com','razerzone.com','google.com','gstatic.com','bing.com','duckduckgo.com'),candidate_classifier=lambda u:'support' if official(u) and '/answers/detail/' in u else 'product' if official(u) else '',budget=BrowserBudget(deadline_seconds=15,operation_timeout_seconds=5))
   searcher.trace_callback=self.trace_callback
   try:
    for provider in ('google','bing'):
     if self.clock()>=deadline:break
     result=searcher.search_provider(provider,f'site:razer.com "{query}" "{article}"');self.trace(provider=provider,query=result.query,url='',region='global',source_type='external_search',accepted=False,reason=result.outcome)
     for candidate in result.candidates[:2]:
      if 'mysupport.razer.com' not in candidate.url:continue
      rendered=self.render_support(candidate.url,article)
      if rendered:
       final,html,proof=rendered;doc,ev=parse_page(html,final,article,name,category);proofs.append(proof)
       if ev['identity']['model_confirmed']:best=(doc,ev);break
     if best:break
   finally:searcher.close()
  if best is None:best=(SourceDocument('razer_model','Razer Official','',error='Official exact model not discovered'),{'identity':{'model_relation':'unproven','configuration_relation':'unproven','exact_sku':False},'raw_specs':[],'accepted_specs':[],'rejected_specs':[],'photos':[],'exact_photo_assets':[],'manuals':[],'verified_documents':[],'manual_status':'Не проверена'})
  doc,ev=best;ev.update(proofs=proofs,query_variants=[article,query],requested_configuration=__import__('product_tool.razer_identity',fromlist=['requested_configuration']).requested_configuration(name));self.reports[article]=ev;return doc
 def find_documents(self,document,article):
  from io import BytesIO
  from pypdf import PdfReader
  ev=self.reports[article];found=[];checked=ev['identity'].get('model_confirmed',False)
  for item in ev.get('manuals',[]):
   if item['language']!='Русский' or item['type'] not in {'User Guide','Quick Start'}:continue
   try:
    z=self.http.get(item['url'],timeout=10)
    if not z.ok or z.truncated:checked=False;item['error']=z.marker or str(z.status_code);continue
    raw=z.text.encode('latin1');reader=PdfReader(BytesIO(raw));text=' '.join(p.extract_text() or '' for p in reader.pages[:80]);model=ev['identity']['model']
    relation=key(model.replace(' (2023)','').replace(' (2022)','').replace(' (2025)','')) in key(text[:12000]);ru=len(re.findall('[а-яА-Я]',text))>100
    item.update(verified=bool(relation and ru and raw.startswith(b'%PDF-')),model_verified=relation,russian_verified=ru,pages=len(reader.pages),sha256=hashlib.sha256(raw).hexdigest())
    self.capture_dir.mkdir(parents=True,exist_ok=True);file=item['sha256']+'.pdf';(self.capture_dir/file).write_bytes(raw);item['file']=file
    if item['verified']:ev['verified_documents'].append(item['url']);found.append(ProductDocument(item['title'],'Русский','','',item['url'],document.url,article,model,document.url,True))
    else:checked=False
   except Exception as exc:checked=False;item['error']=str(exc)[:160]
  ev['manual_status']='Проверена' if found else 'Проверена, не найдена' if checked else 'Не проверена';ev['manual_check_complete']=checked;return found
