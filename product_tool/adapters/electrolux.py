"""Small Electrolux binding: published navigation/SSR, shared transports and search."""
import hashlib,json,re,time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin,urlsplit,quote_plus
from bs4 import BeautifulSoup
from .common import SourceDocument,ProductDocument,utc_now
from .policy_session import PolicyAwareSession
from .sitemap_urls import sitemap_locs
from .lg_documents import BinarySafeSession,document_bytes,document_languages
from .lg_browser_search import LGBrowserSearch
from ..electrolux_page import HOSTS,MEDIA_HOSTS,key,official,catalog_links,parse,payload,components,inventory,revision_owner,media_asset,evidence_graph

ROUTES={'Стиральные машины':'washing-machines','Стирально-сушильные машины':'washer-dryers','Сушильные машины':'dryers','Посудомоечные машины':'dishwashers','Холодильники':'fridge-freezers','Духовые шкафы':'ovens','Варочные панели':'hobs','Пылесосы':'vacuum-cleaners'}
class ElectroluxAdapter:
 source_key='electrolux'
 def __init__(self,*,clock=time.monotonic,fetch_log_path=None,capture_dir=None,browser_session=None,session=None,external_search=None):
  self.clock=clock;self.log=Path(fetch_log_path or 'data/electrolux_fetch_log.json');self.capture_dir=Path(capture_dir or self.log.parent/'electrolux_captures');self.browser_session=browser_session;self.trace_callback=None;self.reports={};self.cache={};self.external_search=external_search;self.external_owned=False;self.last_error='';self.proofs=[]
  self.http=session or PolicyAwareSession(self.log,allowed_hosts=HOSTS,max_bytes=3000000)
  self.inventory_catalog={}
  self.product_deadline=float('inf');self.phase_deadline=float('inf')
  import requests
  transport=browser_session.binary_transport(max_bytes=15000000) if browser_session else requests.Session()
  self.binary=PolicyAwareSession(self.log,allowed_hosts=MEDIA_HOSTS,max_bytes=15000000,underlying=BinarySafeSession(transport),cache_suffixes=())
 def trace(self,**event):
  record={'event':'electrolux_discovery','timestamp':utc_now(),**event}
  b=self.browser_session
  if b and getattr(b,'trace_path',None):
   record.update(session_id=b.session_id,**getattr(b,'job_context',{}))
   with b.trace_path.open('a',encoding='utf8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
  if self.trace_callback:self.trace_callback(record)
 @contextmanager
 def stage(self,name,seconds=None):
  start=self.clock();old=self.phase_deadline
  self.phase_deadline=min(old,self.product_deadline,start+seconds) if seconds else min(old,self.product_deadline)
  if self.browser_session and hasattr(self.browser_session,'deadline'):self.browser_session.deadline=self.phase_deadline
  self.trace(provider='timing',source_type=name,url='',state='start',budget_seconds=seconds,product_remaining=max(0,self.product_deadline-start))
  error=''
  try:yield
  except Exception as exc:error=str(exc);raise
  finally:
   self.trace(provider='timing',source_type=name,url='',state='end',elapsed=round(self.clock()-start,4),exception=error,budget_exhausted=self.clock()>=self.phase_deadline)
   self.phase_deadline=old
   if self.browser_session and hasattr(self.browser_session,'deadline'):self.browser_session.deadline=min(old,self.product_deadline)
 def fetch(self,url,*,provider,source_type,query,cache=False):
  if self.clock()>=min(self.deadline,self.phase_deadline,self.product_deadline):
   self.last_error='Discovery/candidate budget exhausted; existence not determined';self.trace(provider=provider,source_type=source_type,url=url,query=query,accepted=False,reason=self.last_error);return None
  from . import access_stop,policy_fetch
  if (urlsplit(url).hostname or '') in access_stop.active_stops(policy_fetch.read_log(self.log)):
   self.last_error='host_stopped';self.trace(query=query,provider=provider,url=url,source_type=source_type,accepted=False,reason=self.last_error,identity_relation='unproven');return None
  if cache and url in self.cache:
   self.trace(query=query,provider=provider,url=url,source_type=source_type,accepted=False,reason='same-session live catalog cache; not fresh PDP success',identity_relation='discovery_only');return self.cache[url]
  try:
   if self.browser_session:
    b=self.browser_session;warning=''
    from ..census.browser_runtime import BrowserFailure
    try:b.call('goto',url=url)
    except BrowserFailure as exc:
     if str(exc)!='render_timeout' or b.status!=200 or b.signal:raise
     warning='Already received main 200; bounded snapshot revalidation, no extra navigation'
    a=b.snapshot();html,final=a['html'],a['url'];proof={k:v for k,v in a.items() if k!='html'}
    if warning:proof['navigation_warning']=warning
   else:
    a=self.http.get(url,timeout=min(10,max(1,self.deadline-self.clock())))
    if not a.ok or a.marker or a.truncated:raise ValueError('HTTP '+str(a.status_code)+' '+a.marker)
    html,final=a.text,a.url;proof={'url':final,'status_code':a.status_code,'captured_at':utc_now(),'sha256':hashlib.sha256(html.encode()).hexdigest()}
   if not official(final):raise ValueError('foreign redirect')
   self.capture_dir.mkdir(parents=True,exist_ok=True);sha=hashlib.sha256(html.encode()).hexdigest();(self.capture_dir/(sha+'.html')).write_bytes(html.encode());proof.update(file=sha+'.html',requested_url=url,observation='actual_live');self.proofs.append(proof)
   self.trace(query=query,provider=provider,url=final,region=(urlsplit(final).hostname or ''),source_type=source_type,accepted=False,reason='Actual live response; identity checked separately',identity_relation='discovery_only',requested_url=url)
   result=(html,final)
   if cache:self.cache[url]=result
   return result
  except Exception as exc:
   self.last_error=str(exc);self.trace(query=query,provider=provider,url=url,source_type=source_type,accepted=False,reason=self.last_error,identity_relation='unproven');return None
 def find_source(self,article,*,name='',category='',region='UK',deadline=None,color=''):
  self.deadline=deadline or self.clock()+90;self.proofs=[];self.last_error='';pnc=key(article) if re.fullmatch(r'[\d\s]{9,15}',article) else ''
  model=article if not pnc else next(iter(re.findall(r'\b[A-Z][A-Z0-9-]*\d[A-Z0-9-]*\b',name.upper())),'')
  variants=list(dict.fromkeys([model,model.upper(),pnc]));self.trace(query=article,provider='normalization',url='',source_type='query_variants',accepted=False,reason='Model and PNC are separate queries; revision never padded',identity_relation='input',variants=variants)
  best=SourceDocument(self.source_key,'Electrolux official','',evidence='Exact official PDP not found');ev={'identity':{'model':model,'model_relation':'unproven','requested_pnc':pnc,'requested_region':region},'manual_status':'Не проверена','model_gallery_assets':[],'verified_documents':[]}
  roots={'UK':'https://www.electrolux.co.uk/','IE':'https://www.electrolux.ie/','SE':'https://www.electrolux.se/','DE':'https://www.electrolux.de/','PL':'https://www.electrolux.pl/'}
  attempted=set();homes={};partial_score=-1;catalog_relations=[]
  def check(candidates,provider,catalog_url=''):
   nonlocal best,ev,partial_score
   candidates=sorted(candidates,key=lambda x:0 if pnc and key(x[1])==pnc else 1 if pnc and key(x[1])[:9]==pnc[:9] else 2)
   for u,code,why in list(dict.fromkeys(candidates))[:4]:
    if why=='native official catalog productData' and re.fullmatch(r'\d{9}',str(code)) and official(catalog_url):
     catalog_relations.append({'model':model,'product_code':str(code),'region':next((r for r,root in roots.items() if urlsplit(root).hostname==urlsplit(catalog_url).hostname),''),'source_url':catalog_url,'source_type':'native_catalog_productData'})
    if u in attempted:continue
    attempted.add(u)
    with self.stage('candidate',24):
     page=self.fetch(u,provider=provider,source_type='PDP',query=model)
     if not page:continue
     with self.stage('extraction',8):doc,report=parse(*page,model,pnc,region,color,catalog_relations)
    accept=report['identity'].get('model_relation')=='model_confirmed'
    self.trace(query=model,provider=provider,url=page[1],source_type='PDP',accepted=accept,reason=doc.evidence,identity_relation=report['identity'],candidate_url=u,catalog_product_code=code,discovery_reason=why)
    if accept:
     identity=report['identity'];score=3 if identity.get('configuration_confirmed') else 2 if pnc and identity.get('pnc_base')==pnc[:9] and identity.get('region')==region else 1
     if score>partial_score:best,ev,partial_score=doc,report,score
     if score==3:return True
   return False
  # Breadth before depth: one stale regional route must not consume other regions' budget.
  for reg in list(dict.fromkeys([region,'UK','IE','SE','DE','PL'])):
   root=roots[reg];home=self.fetch(root,provider='regional_official' if reg==region else 'other_official_region',source_type='catalog_root',query=model,cache=True)
   if not home:continue
   homes[reg]=home
   if reg==region:
    soup=BeautifulSoup(home[0],'html.parser')
    search_url=next((urljoin(root,a['href']) for a in soup.select('a[href]') if urlsplit(a['href']).path.rstrip('/')=='/search'),None)
    if not search_url:
     search_name=next((c.get('props',{}).get('globalSearchSettings',{}).get('searchPageName') for c in components(payload(home[0])) if c.get('props',{}).get('globalSearchSettings',{}).get('searchPageName')),None)
     if search_name and re.fullmatch(r'[a-z-]+',search_name):search_url=urljoin(root,search_name+'/')
    if search_url:
     search_page=self.fetch(search_url,provider='regional_exact',source_type='official_search',query=model,cache=True)
     if search_page and BeautifulSoup(search_page[0],'html.parser').select_one('input[name="q"]'):
      page=self.fetch(search_url.rstrip('/')+'/?q='+quote_plus(model),provider='regional_exact',source_type='official_search',query=model)
      if page and check(catalog_links(*page,model),'regional_exact',page[1]):break
   if check(catalog_links(*home,model),'official_catalog',home[1]):break
   soup=BeautifulSoup(home[0],'html.parser');term=ROUTES.get(category,'')
   cats=list(dict.fromkeys(urljoin(root,a['href']).split('#')[0] for a in soup.select('a[href]') if term and '/'+term+'/' in a['href'] and len(urlsplit(a['href']).path.strip('/').split('/'))<=4))
   for u in cats[:2]:
    catalog=self.fetch(u,provider='official_catalog',source_type='category',query=model,cache=True)
    if catalog and check(catalog_links(*catalog,model),'official_catalog',catalog[1]):break
   if ev['identity'].get('configuration_confirmed'):break
   if not pnc and ev['identity'].get('model_relation')=='model_confirmed':break
   if len(pnc)==11 and ev['identity'].get('product_code')==pnc[:9] and ev['identity'].get('region')==region:break
  # Same-base publication is retained as partial, not routed to another PNC/revision.
  if ev['identity'].get('model_relation')!='model_confirmed' or pnc and ev['identity'].get('pnc_base')!=pnc[:9]:
   for reg,home in homes.items():
    root=roots[reg]
   # Read only published sitemap locations; no product-slug construction.
    robots=self.fetch(urljoin(root,'robots.txt'),provider='official_sitemap',source_type='robots',query=model,cache=True)
    if robots:
     for site in re.findall(r'Sitemap:\s*(https://[^\s<]+)',BeautifulSoup(robots[0],'html.parser').get_text(' ',strip=True),re.I)[:1]:
      page=self.fetch(site,provider='official_sitemap',source_type='sitemap',query=model,cache=True)
      if page:
       locs=sitemap_locs(page[0]) or [x.get_text(strip=True) for x in BeautifulSoup(page[0],'html.parser').find_all('loc')]
       if check([(u,'','published sitemap') for u in locs if key(model) in key(u) and official(u)],'official_sitemap'):break
       for child in [u for u in locs if official(u) and urlsplit(u).path.endswith('.xml')][:2]:
        child_page=self.fetch(child,provider='official_sitemap',source_type='sitemap_child',query=model,cache=True)
        if child_page:
         child_locs=sitemap_locs(child_page[0]) or [x.get_text(strip=True) for x in BeautifulSoup(child_page[0],'html.parser').find_all('loc')]
         if check([(u,'','published child sitemap') for u in child_locs if key(model) in key(u) and official(u)],'official_sitemap'):break
    if ev['identity'].get('configuration_confirmed'):break
  if ev['identity'].get('model_relation')!='model_confirmed' and self.clock()<self.deadline and not getattr(self.browser_session,'failed',False):
   # Published official support inventory before the generic external fallback.
   root=roots[region];home=self.cache.get(root)
   if home:
    soup=BeautifulSoup(home[0],'html.parser');support=next((urljoin(root,a['href']) for a in soup.select('a[href]') if '/support/user-manuals/' in a['href']),None)
    if support:
     page=self.fetch(support,provider='official_support',source_type='manual_inventory',query=model,cache=True)
     if page:check(catalog_links(*page,model),'official_support')
  if ev['identity'].get('model_relation')!='model_confirmed' and self.clock()<self.deadline and not getattr(self.browser_session,'failed',False):
   # Existing generic search; its host/challenge guards remain enabled.
   search=self.external_search
   if search is None:
    search=LGBrowserSearch(self.log.parent/'electrolux_external_log.json',allowed_hosts=HOSTS+('www.google.com','google.com','gstatic.com','www.bing.com','bing.com','duckduckgo.com'),official_hosts=HOSTS,candidate_classifier=lambda u:'product' if official(u) else 'other',clock=self.clock);self.external_search=search;self.external_owned=True
   search.trace_callback=self.trace_callback
   try:
    for provider in ('google','bing'):
     query='site:'+urlsplit(roots[region]).hostname+' Electrolux '+model+((' '+pnc) if pnc else '')
     result=search.search_provider(provider,query)
     if check([(c.url,'','generic external fallback after official miss') for c in result.candidates if official(c.url)],provider):break
   except Exception as exc:self.trace(query=model,provider='external',url='',source_type='search',accepted=False,reason=str(exc),identity_relation='unproven')
  if ev['identity'].get('model_relation')=='model_confirmed':
   ev['pnc_inventory']=self.find_inventory(best,model,pnc)
   ev['identity']['revision_inventory_relation']=ev['pnc_inventory'].get('requested_relation','unproven')
   if len(pnc)==11 and ev['pnc_inventory'].get('requested_relation')=='published_exact_revision':
    ev['requested_revision']=self.find_revision(ev['pnc_inventory'],model,pnc,region)
    revision=ev['requested_revision']
    if revision.get('confirmed'):
     ev['identity'].update(requested_revision_identity_confirmed=True,requested_revision_source=revision['url'],requested_revision=pnc[9:],requested_pnc_relation='native_model_pnc_revision_confirmed; base PDP technical equivalence unproven')
     for photo in revision['gallery']:
      photo['eligible']=not color
      derivatives=[g for g in ev['gallery_inventory'] if media_asset(photo['url']) and media_asset(g['url'])==media_asset(photo['url']) and g['kind']=='product_gallery']
      if derivatives:
       for derivative in derivatives:
        derivative.update(eligible=not color,published_product_code=derivative['product_code'],product_code=pnc,revision_owner_image=photo['url'],relation_url=revision['url'],relation='Exact revision appliance.image and published PDP derivative share asset UUID/file; no region/finish or specification equivalence inferred')
       revision.setdefault('shared_gallery_assets',[]).extend({'owner_image':photo['url'],'published_derivative':g['url'],'asset_identity':media_asset(g['url'])} for g in derivatives)
       continue
      ev['gallery_inventory'].insert(0,photo)
      from .common import PhotoCandidate
      best.photo_candidates.insert(0,PhotoCandidate(photo['url'],photo['asset_key'],kind=photo['kind']));best.photos.insert(0,photo['url'])
  ev['pnc_evidence_graph']=evidence_graph(ev,best.url)
  if getattr(self.browser_session,'failed',False):
   ev['technical_failure']='driver_wall_timeout_or_disconnect; context discarded; evidence availability unknown'
   best.error=ev['technical_failure']
  ev.update(query_variants=variants,captures=list(self.proofs),live_success=ev['identity'].get('model_relation')=='model_confirmed',access_error=self.last_error)
  self.reports[article.upper()]=ev;return best
 def find_revision(self,inv,model,pnc,region):
  """Follow the published visible menu; fetch its observed URL, never synthesize it."""
  result={'confirmed':False,'technical_equivalence':False,'gallery':[]}
  if not self.browser_session or self.clock()>=self.deadline:return result
  from . import access_stop,policy_fetch
  b=self.browser_session;target=inv['url']
  if (urlsplit(target).hostname or '') in access_stop.active_stops(policy_fetch.read_log(self.log)):return result
  try:
   current=getattr(b,'url','') or b.page.url
   if current!=target and not self.fetch(target,provider='official_revision',source_type='model_pnc_inventory',query=pnc):return result
   observed=b.select_revision(pnc)
   if not official(observed):raise ValueError('Foreign revision menu target')
   page=self.fetch(observed,provider='official_revision',source_type='exact_revision_appliance',query=pnc)
   if page:
    result=revision_owner(*page,model,pnc)
    source_region=next((r for h,r in [('electrolux.co.uk','UK'),('electrolux.ie','IE'),('electrolux.se','SE'),('electrolux.de','DE'),('electrolux.pl','PL')] if (urlsplit(page[1]).hostname or '').endswith(h)),'')
    if region and source_region!=region:result.update(confirmed=False,gallery=[],reason='Requested revision region unproven')
    self.trace(query=pnc,provider='official_revision',url=page[1],source_type='exact_revision_appliance',accepted=result['confirmed'],reason='Native appliance owner checked; subordinate part facts/documents excluded',identity_relation=result,menu_inventory_url=target)
  except Exception as exc:result['error']=str(exc);self.trace(query=pnc,provider='official_revision',url=target,source_type='exact_revision_appliance',accepted=False,reason=str(exc),identity_relation='unproven')
  return result
 def find_inventory(self,doc,model,pnc):
  """Resolve exact model URLs from published shop sitemap, no model URL synthesis."""
  result={'relations':[],'requested_relation':'unproven','technical_equivalence':False}
  s=BeautifulSoup(doc.html,'html.parser');shop=next((urljoin(doc.url,a['href']) for a in s.select('a[href]') if (urlsplit(urljoin(doc.url,a['href'])).hostname or '').startswith('shop.') and urlsplit(a['href']).path in {'','/'} and official(urljoin(doc.url,a['href']))),None)
  if not shop:return result
  if shop not in self.inventory_catalog:
   links={};children=[];robots=self.fetch(urljoin(shop,'robots.txt'),provider='official_inventory',source_type='robots',query=model,cache=True)
   if robots:
    sites=re.findall(r'Sitemap:\s*(https://[^\s<]+)',BeautifulSoup(robots[0],'html.parser').get_text(' ',strip=True),re.I)
    if sites:
     page=self.fetch(sites[0],provider='official_inventory',source_type='sitemap',query=model,cache=True)
     children=[x.get_text(strip=True) for x in BeautifulSoup(page[0],'html.parser').find_all('loc') if '/sitemap/Model/' in x.get_text()] if page else []
   self.inventory_catalog[shop]={'links':links,'pending':children[:14]}
  state=self.inventory_catalog[shop];links=state['links']
  if key(model) not in links:
     while state['pending']:
      u=state['pending'][0]
      if not official(u) or self.clock()>=self.deadline:break
      try:
       response=self.binary.get(u,timeout=8);raw=document_bytes(response)
       if not response.ok or response.marker or response.truncated or len(raw)>3000000:raise ValueError('Inventory XML transport/budget')
       from xml.etree import ElementTree as ET
       xml=ET.fromstring(raw)
       for loc in xml.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        target=loc.text or ''
        if official(target) and '/model/m/' in urlsplit(target).path:
         from urllib.parse import unquote
         links[key(unquote(urlsplit(target).path.rstrip('/').rsplit('/',1)[-1]))]=target
       sha=hashlib.sha256(raw).hexdigest();self.capture_dir.mkdir(parents=True,exist_ok=True);(self.capture_dir/(sha+'.xml')).write_bytes(raw)
       self.proofs.append({'url':u,'file':sha+'.xml','sha256':sha,'status_code':response.status_code,'captured_at':utc_now(),'observation':'actual_live_inventory_xml'})
       self.trace(query=model,provider='official_inventory',url=u,source_type='model_sitemap',accepted=False,reason='Fresh bounded XML inventory; model URL discovery only',identity_relation='discovery_only')
       state['pending'].pop(0)
       if key(model) in links:break
      except Exception as exc:self.trace(query=model,provider='official_inventory',url=u,source_type='model_sitemap',accepted=False,reason=str(exc),identity_relation='unproven');break
  target=links.get(key(model))
  if target:
   page=self.fetch(target,provider='official_inventory',source_type='model_pnc_inventory',query=model)
   if page:
    result=inventory(*page,model,pnc);self.trace(query=model,provider='official_inventory',url=page[1],source_type='model_pnc_inventory',accepted=bool(result['relations']),reason='Published model/PNC existence only; technical equivalence not inferred',identity_relation=result)
  return result
 def find_documents(self,doc,article):
  ev=self.reports[article.upper()];docs=[];technical=any(not i['identity_verified'] and i['type'] in {'User Manual','Quick Guide'} for i in ev.get('document_inventory',[]))
  for item in ev.get('document_inventory',[])[:8]:
   if not item['identity_verified']:continue
   if item['type']=='Installation Drawing':continue
   if self.clock()>=min(self.phase_deadline,self.product_deadline):item.update(verified=False,error='Document batch/product budget exhausted');technical=True;continue
   try:
    with self.stage('document_fetch',12):response=self.binary.get(item['url'],timeout=min(8,max(.1,self.phase_deadline-self.clock())));raw=document_bytes(response)
    if not response.ok or response.marker or response.truncated or not raw.startswith(b'%PDF-'):raise ValueError('Document transport/type not verified')
    import pymupdf
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
     if len(pdf)>600:raise ValueError('PDF page budget')
     texts=[page.get_text() for page in pdf]
    text='\n'.join(texts)
    if len(text)>2000000:raise ValueError('PDF text budget')
    sha=hashlib.sha256(raw).hexdigest();self.capture_dir.mkdir(parents=True,exist_ok=True);(self.capture_dir/(sha+'.pdf')).write_bytes(raw)
    languages=document_languages(texts)['present'];item.update(bytes_verified=True,sha256=sha,file=sha+'.pdf',language=','.join(languages) or 'Язык не определён',model_in_pdf=key(doc.found_model) in key(text),pnc_in_pdf=ev['identity'].get('pnc_base','') in key(text))
    # A published exact-PNC document relation suffices; some guides cover a family.
    item['verified']=True;ev['verified_documents'].append(item['url'])
    docs.append(ProductDocument(item['type']+' — '+item['title'],item['language'],item.get('date',''),str(len(raw)),item['url'],doc.url,doc.found_model,ev['identity'].get('product_code',''),doc.url,primary=item['type']=='User Manual'))
   except Exception as exc:item.update(verified=False,error=str(exc));technical=True
  ev['manual_status']='Проверена' if any(i.get('verified') and i['type'] in {'User Manual','Quick Guide'} for i in ev.get('document_inventory',[])) else 'Не проверена' if technical or not ev.get('document_inventory') else 'Проверена, не найдена'
  return docs
 def close(self):
  if self.external_owned and self.external_search:self.external_search.close()
 def photo_transport(self):
  owner=self;transport=self.browser_session.binary_transport(max_bytes=8000000)
  class CapturingTransport:
   headers={}
   def get(self,url,**kwargs):
    response=transport.get(url,**kwargs)
    if response.status_code==200:
     raw=response.content;sha=hashlib.sha256(raw).hexdigest();owner.capture_dir.mkdir(parents=True,exist_ok=True);(owner.capture_dir/(sha+'.img')).write_bytes(raw)
    return response
  return CapturingTransport()

@contextmanager
def controlled_browser_adapter(root,profile):
 """Opt-in existing worker binding; visible persistent session and diagnostics."""
 from ..census.public_browser import IsolatedPublicBrowserSession
 from ..census.browser_contracts import BrowserBudget
 root=Path(root)
 browser=IsolatedPublicBrowserSession(allowed_hosts=MEDIA_HOSTS,fetch_log_path=root/'electrolux_fetch_log.json',profile_dir=profile,visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10))
 adapter=None
 try:
  browser.start()
  adapter=ElectroluxAdapter(fetch_log_path=root/'electrolux_fetch_log.json',capture_dir=root/'electrolux_captures',browser_session=browser)
  yield adapter
 finally:
  if adapter:adapter.close()
  browser.close()
