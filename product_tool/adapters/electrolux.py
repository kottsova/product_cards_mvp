"""Small Electrolux binding: published navigation/SSR, shared transports and search."""
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,quote_plus
from bs4 import BeautifulSoup
from .common import SourceDocument,ProductDocument,utc_now
from .policy_session import PolicyAwareSession
from .sitemap_urls import sitemap_locs
from .lg_documents import BinarySafeSession,document_bytes,document_languages
from .lg_browser_search import LGBrowserSearch
from ..electrolux_page import HOSTS,MEDIA_HOSTS,key,official,catalog_links,parse,payload,components

ROUTES={'Стиральные машины':'washing-machines','Стирально-сушильные машины':'washer-dryers','Сушильные машины':'dryers','Посудомоечные машины':'dishwashers','Холодильники':'fridge-freezers','Духовые шкафы':'ovens','Варочные панели':'hobs','Пылесосы':'vacuum-cleaners'}
class ElectroluxAdapter:
 source_key='electrolux'
 def __init__(self,*,clock=time.monotonic,fetch_log_path=None,capture_dir=None,browser_session=None,session=None,external_search=None):
  self.clock=clock;self.log=Path(fetch_log_path or 'data/electrolux_fetch_log.json');self.capture_dir=Path(capture_dir or self.log.parent/'electrolux_captures');self.browser_session=browser_session;self.trace_callback=None;self.reports={};self.cache={};self.external_search=external_search;self.external_owned=False;self.last_error='';self.proofs=[]
  self.http=session or PolicyAwareSession(self.log,allowed_hosts=HOSTS,max_bytes=3000000)
  import requests
  transport=browser_session.binary_transport(max_bytes=15000000) if browser_session else requests.Session()
  self.binary=PolicyAwareSession(self.log,allowed_hosts=MEDIA_HOSTS,max_bytes=15000000,underlying=BinarySafeSession(transport),cache_suffixes=())
 def trace(self,**event):
  if self.trace_callback:self.trace_callback({'event':'electrolux_discovery','timestamp':utc_now(),**event})
 def fetch(self,url,*,provider,source_type,query,cache=False):
  if self.clock()>=self.deadline:return None
  from . import access_stop,policy_fetch
  if (urlsplit(url).hostname or '') in access_stop.active_stops(policy_fetch.read_log(self.log)):
   self.last_error='host_stopped';self.trace(query=query,provider=provider,url=url,source_type=source_type,accepted=False,reason=self.last_error,identity_relation='unproven');return None
  if cache and url in self.cache:
   self.trace(query=query,provider=provider,url=url,source_type=source_type,accepted=False,reason='same-session live catalog cache; not fresh PDP success',identity_relation='discovery_only');return self.cache[url]
  try:
   if self.browser_session:
    b=self.browser_session;b.call('goto',url=url);a=b.snapshot();html,final=a['html'],a['url'];proof={k:v for k,v in a.items() if k!='html'}
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
  roots={'UK':'https://www.electrolux.co.uk/','SE':'https://www.electrolux.se/','DE':'https://www.electrolux.de/','PL':'https://www.electrolux.pl/'}
  def check(candidates,provider):
   nonlocal best,ev
   for u,code,why in candidates[:4]:
    page=self.fetch(u,provider=provider,source_type='PDP',query=model)
    if not page:continue
    doc,report=parse(*page,model,pnc,region,color);accept=report['identity'].get('model_relation')=='model_confirmed'
    self.trace(query=model,provider=provider,url=page[1],source_type='PDP',accepted=accept,reason=doc.evidence,identity_relation=report['identity'],candidate_url=u,catalog_product_code=code,discovery_reason=why)
    if accept:best,ev=doc,report;return True
   return False
  for reg in list(dict.fromkeys([region,'UK','SE','DE'])):
   root=roots[reg];home=self.fetch(root,provider='regional_official' if reg==region else 'other_official_region',source_type='catalog_root',query=model,cache=True)
   if not home:continue
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
      if page and check(catalog_links(*page,model),'regional_exact'):break
   if check(catalog_links(*home,model),'official_catalog'):break
   soup=BeautifulSoup(home[0],'html.parser');term=ROUTES.get(category,'')
   cats=list(dict.fromkeys(urljoin(root,a['href']).split('#')[0] for a in soup.select('a[href]') if term and '/'+term+'/' in a['href'] and len(urlsplit(a['href']).path.strip('/').split('/'))<=4))
   for u in cats[:2]:
    catalog=self.fetch(u,provider='official_catalog',source_type='category',query=model,cache=True)
    if catalog and check(catalog_links(*catalog,model),'official_catalog'):break
   if ev['identity'].get('model_relation')=='model_confirmed':break
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
  if ev['identity'].get('model_relation')!='model_confirmed' and self.clock()<self.deadline:
   # Published official support inventory before the generic external fallback.
   root=roots[region];home=self.cache.get(root)
   if home:
    soup=BeautifulSoup(home[0],'html.parser');support=next((urljoin(root,a['href']) for a in soup.select('a[href]') if '/support/user-manuals/' in a['href']),None)
    if support:
     page=self.fetch(support,provider='official_support',source_type='manual_inventory',query=model,cache=True)
     if page:check(catalog_links(*page,model),'official_support')
  if ev['identity'].get('model_relation')!='model_confirmed' and self.clock()<self.deadline:
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
  ev.update(query_variants=variants,captures=list(self.proofs),live_success=ev['identity'].get('model_relation')=='model_confirmed',access_error=self.last_error)
  self.reports[article.upper()]=ev;return best
 def find_documents(self,doc,article):
  ev=self.reports[article.upper()];docs=[];technical=any(not i['identity_verified'] and i['type'] in {'User Manual','Quick Guide'} for i in ev.get('document_inventory',[]))
  for item in ev.get('document_inventory',[])[:8]:
   if not item['identity_verified']:continue
   if item['type']=='Installation Drawing':continue
   try:
    response=self.binary.get(item['url'],timeout=8);raw=document_bytes(response)
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
