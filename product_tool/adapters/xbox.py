"""Xbox public discovery through shared policy HTTP, sitemap and browser search."""
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
import zlib
from xml.etree.ElementTree import ParseError
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from .common import SourceDocument,utc_now,clean_text
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession,document_bytes
from ..lg_sitemap_discovery import parse_sitemap
from ..xbox_identity import HOSTS,ROUTES,official,family,identifier,product_url,search_kind
from ..xbox_page import parse_page,assignment

_CACHE={}

class XboxTransport(BinarySafeSession):
    """Preserve compressed sitemap bytes on the shared policy transport."""
    def get(self,url,**kwargs):
        z=super().get(url,**kwargs)
        if urlsplit(url).path.lower().endswith('.gz'):z.encoding='latin-1'
        return z

def sitemap_urls(response):
    # Shared policy fetch has already decompressed HTTP/gzip and decoded XML.
    # document_bytes() is only for binary documents, not Unicode sitemap text.
    text=response.text
    if text.startswith('ï»¿'):text=text.encode('latin1').decode('utf-8-sig')
    data=document_bytes(response) if text.startswith('\x1f\x8b') else text.encode('utf8');source=response.url.removesuffix('.gz') if text.lstrip('\ufeff \r\n').startswith('<') else response.url
    kind,urls=parse_sitemap(data,source)
    # Store stores regional URLs in standard xhtml:link alternates, not only loc.
    import gzip
    root=ET.fromstring(gzip.decompress(data) if data.startswith(b'\x1f\x8b') else data)
    urls.extend(n.get('href') for n in root.iter() if n.tag.endswith('}link') and n.get('rel')=='alternate' and official(n.get('href','')))
    return kind,list(dict.fromkeys(urls))

class XboxAdapter:
    def __init__(self,*,fetch_log_path=None,trace_callback=None,clock=time.monotonic,session=None,search_factory=None):
        self.log=Path(fetch_log_path or 'data/xbox_fetch.json');self.clock=clock;self.trace_callback=trace_callback;self.search_factory=search_factory
        self.session=session or PolicyAwareSession(self.log,allowed_hosts=HOSTS,underlying=XboxTransport(requests.Session()),min_interval_seconds=1)
        self.reports={};self.extra_documents=[];self.capture_dir=self.log.parent/'xbox_captures';self.capture_dir.mkdir(parents=True,exist_ok=True)

    def emit(self,**e):
        if self.trace_callback:self.trace_callback(dict(timestamp=utc_now(),event='xbox_discovery',**e))

    def fetch(self,url,query,provider,kind,deadline):
        if self.clock()>=deadline:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason='budget_exhausted',identity_relation='unproven');return None
        try:
            if not official(url):raise ValueError('Non-official URL rejected before fetch')
            key=(str(self.log),url);cached=_CACHE.get(key)
            z=cached[1] if cached and self.clock()-cached[0]<600 else self.session.get(url,timeout=min(12,deadline-self.clock()))
            if z.status_code!=200 or z.truncated or not official(z.url):raise ValueError(f'HTTP {z.status_code}; truncated={z.truncated}; returned={z.url}')
            binary=urlsplit(z.url).path.lower().endswith(('.pdf','.gz'))
            p=self.capture_dir/(hashlib.sha256(z.url.encode()).hexdigest()[:20]+('.bin' if binary else '.html'))
            if binary:p.write_bytes(document_bytes(z))
            else:p.write_text(z.text,encoding='utf8')
            _CACHE[key]=(self.clock(),z)
            self.emit(query=query,provider=provider,url=z.url,region=urlsplit(z.url).path.split('/')[1],source_type=kind,accepted=True,reason='Public response fetched; own identity evaluated separately',identity_relation='unproven')
            return z
        except Exception as e:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason=str(e),identity_relation='unproven');return None

    def external(self,article,name,deadline):
        from .lg_browser_search import LGBrowserSearch
        from ..census.browser_runtime import PlaywrightBrowser
        from ..census.browser_contracts import BrowserBudget
        search=(self.search_factory or (lambda:LGBrowserSearch(self.log.parent/'xbox_search.json',allowed_hosts=('www.microsoft.com','www.xbox.com','www.bing.com','bing.com','www.google.com','google.com','gstatic.com'),official_host='www.xbox.com',official_hosts=('www.xbox.com','www.microsoft.com'),driver_factory=PlaywrightBrowser,budget=BrowserBudget(deadline_seconds=20,operation_timeout_seconds=8),candidate_classifier=search_kind)))()
        search.trace_callback=lambda e:self.emit(**{k:v for k,v in e.items() if k not in {'event','timestamp'}})
        out=[]
        try:
            for provider in ('bing','google'):
                if self.clock()>=deadline:break
                query=f'site:microsoft.com "{article.split("/")[0]}" {name}'
                result=search.search_provider(provider,query);out.extend(c.url for c in result.candidates)
                self.emit(query=query,provider=provider+'_browser',url='',region='',source_type='search',accepted=bool(result.candidates),reason=result.outcome,identity_relation='candidate_only')
                if out:break
        finally:search.close()
        return out

    def find_source(self,article,*,name='',category='',region='en-US',deadline):
        article=article.strip().upper();req=identifier(article);expected=family(name);docs={};visited=set();links=[];self.extra_documents=[]
        ev=dict(requested_identifier=article,requested_identifier_type=req['type'],requested_region=region,model_key=expected,query_variants=list(dict.fromkeys([article,article.split('/')[0],name,f'{article} Xbox'])),identity={'model':'unproven','configuration':'unproven','hardware':'unproven'},identifiers={},raw_specs=[],configuration_candidates=[],photo_candidates=[],exact_photo_assets=[],photo_scopes={},manuals=[],manual_status='Не проверена',configuration_fields={},configuration_complete=False,exact_official_pdp='',support_url='',access_stops=[])
        def decision(url,provider,accepted,reason,relation='candidate_only',kind='product'):
            self.emit(query=article,provider=provider,url=url,region=urlsplit(url).path.split('/')[1] if url else region,source_type=kind,accepted=accepted,reason=reason,identity_relation=relation)
        def page_links(z):
            return [urljoin(z.url,n['href']) for n in BeautifulSoup(z.text,'html.parser').select('a[href]') if product_url(urljoin(z.url,n['href']))]
        def inspect(url,provider):
            p=urlsplit(url);url=urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
            if url in visited:return None
            visited.add(url);z=self.fetch(url,article,provider,'product',deadline)
            if not z:return None
            links.extend(page_links(z));d,p=parse_page(z.text,z.url,article,expected,region)
            if d.error:decision(z.url,provider,False,d.error,'mismatch');return z
            ev.setdefault('page_default_titles',[]).append(dict(url=z.url,title=p['page_default_title'],resolved_title=d.found_model,scope=d.source_key))
            for key in ('raw_specs','configuration_candidates','photo_candidates','exact_photo_assets'):ev[key].extend(x for x in p[key] if x not in ev[key])
            ev['photo_scopes'].update(p['photo_scopes']);ev['identity']['model']='model_confirmed'
            if d.source_key=='xbox_configuration':
                docs[d.source_key]=d;ev.update({k:p[k] for k in ('identifiers','configuration_fields','configuration_complete')});ev['identity']['configuration']=p['identity']['configuration'];ev['exact_official_pdp']=z.url
            elif d.source_key not in docs:docs[d.source_key]=d
            decision(z.url,provider,True,d.evidence,p['identity']['configuration'] if d.source_key=='xbox_configuration' else 'model_confirmed')
            return z
        regional=inspect(f'https://www.xbox.com/{region}/'+ROUTES[expected],'regional_exact') if expected in ROUTES else None
        # Read declared public catalog scripts; no per-model registry or JS execution.
        if regional:
            for n in BeautifulSoup(regional.text,'html.parser').select('script[src]'):
                u=urljoin(regional.url,n['src'])
                if not any(t in u for t in ('allAccessories-Sheet1.js','allConsoles.js')):continue
                z=self.fetch(u,article,'official_catalog','catalog',deadline)
                if not z:continue
                data=assignment(z.text,'allAccessories1') or assignment(z.text,'allConsoles')
                if not isinstance(data,dict):continue
                rows=data.get('locales',{}).get(region.lower(),[])
                ev['catalog_rows']=len(rows)
                for row in rows:
                    if not isinstance(row,dict) or family(row.get('headline',''))!=expected:continue
                    u=row.get('detailsURL','')
                    if product_url(u):links.append(u)
                    for key in ('poPid','gaPid','specPid'):
                        value=str(row.get(key,''))
                        if req['product_id'] and req['product_id'] in value.upper():
                            ev.setdefault('catalog_identifiers',[]).append(dict(field=key,value=value,source_url=z.url,title=row.get('headline',''),relation='catalog_candidate_requires_own_store_row'))
        # Shared sitemap parser, bounded hardware maps; replacement-parts are never product PDPs.
        for host,robots in (('xbox','https://www.xbox.com/robots.txt'),('store','https://www.microsoft.com/robots.txt')):
            z=self.fetch(robots,article,'official_sitemap','sitemap',deadline)
            roots=re.findall(r'^Sitemap:\s*(https://\S+)',z.text,re.I|re.M) if z else []
            root=next((u for u in roots if 'xbox.com/sitemap.xml' in u or '/store/sitemap-index.xml' in u),None)
            if not root:continue
            z=self.fetch(root,article,'official_sitemap','sitemap',deadline)
            if not z:continue
            try:
                _,children=sitemap_urls(z)
                targets=[u for u in children if 'cms-sitemap' in u][:1] if host=='xbox' else [u for u in children if 'xbox-gaming-sitemap-index' in u][:1]
                for target in targets:
                    child=self.fetch(target,article,'official_sitemap','sitemap',deadline)
                    if not child:continue
                    kind,urls=sitemap_urls(child)
                    if kind=='sitemapindex':
                        hardware=[u for u in urls if any(t in u for t in ('xbox-console','xbox-accessory','xbox-bundle'))]
                        urls=[]
                        for u in hardware[:3]:
                            m=self.fetch(u,article,'official_sitemap','sitemap',deadline)
                            if m:urls.extend(sitemap_urls(m)[1])
                    candidates=[u for u in urls if product_url(u)]
                    links.extend(candidates);ev.setdefault('sitemaps',[]).append(dict(url=target,count=len(urls),product_candidates=len(candidates)))
            except (ValueError,TypeError,ParseError,zlib.error) as e:decision(root,'official_sitemap',False,str(e),kind='sitemap')
        def rank(u):
            p=urlsplit(u).path.lower()
            if req['product_id'] and p.rstrip('/').split('/')[-1].upper()==req['product_id']:return 1000 if '/'+region.lower()+'/' in p else 800
            if family(p.replace('-',' '))!=expected or '/'+region.lower()+'/' not in p:return -1
            generic=ROUTES.get(expected,'').split('/')[-1]
            return 10+(30 if p.split('/')[-2:][0]==generic else 0)+sum(t in p for t in re.findall(r'[a-z0-9]+',name.lower()) if len(t)>2)
        # Inspect exact ID links first; other own Store pages may publish related PDP links.
        for _ in range(4):
            candidates=sorted({urlunsplit((urlsplit(u).scheme,urlsplit(u).netloc,urlsplit(u).path,urlsplit(u).query,'')) for u in links if urlsplit(u).hostname=='www.microsoft.com' and '/'+region.lower()+'/' in urlsplit(u).path.lower() and rank(u)>0} - visited,key=lambda u:(-rank(u),u))
            if not candidates or ev['exact_official_pdp']:break
            inspect(candidates[0],'microsoft_store')
        support=f'https://support.xbox.com/{region}/help/hardware-network/console/manuals-specs'
        z=self.fetch(support,article,'xbox_support','support',deadline);ev['support_url']=support if z else ''
        if z and not BeautifulSoup(z.text,'html.parser').find('h1'):
            ev['access_stops'].append(dict(url=support,reason='HTTP 200 SPA shell; article/downloads not verified'))
            decision(support,'xbox_support',False,'SPA shell is not a checked manual search','unproven','support')
        from ..xbox_documents import support_documents
        ev.update(support_documents(self,z,article,expected,deadline))
        if req['hardware_model'] and expected in {'series_x','series_s'}:
            slug=expected.replace('_','-');u=f'https://learn.microsoft.com/en-us/xbox/service-guides/{slug}-console/{slug}-device-id-and-disassembly'
            z=self.fetch(u,article,'device_support','support',deadline)
            if z:
                b=BeautifulSoup(z.text,'html.parser');body=b.select_one('main') or b;text=clean_text(body.get_text(' ',strip=True))
                proved=bool(re.search(r'\bModel\s+'+re.escape(req['hardware_model'])+r'\b',text,re.I) and family(clean_text(b.h1.text) if b.h1 else '')==expected)
                ev['manuals'].append(dict(type='Support article',title=clean_text(b.h1.text) if b.h1 else 'Service guide',url=z.url,language='English',verified=proved,relation='hardware_model_number' if proved else 'candidate'))
                if proved:ev['identity']['hardware']='official_hardware_model_number';ev['identifiers']['hardware_model_number']=req['hardware_model']
                decision(z.url,'device_support',proved,'Service-guide device model; not a User Guide and no retail/physical transfer',ev['identity']['hardware'],'support')
        # Other-region family facts do not confer regional SKU identity.
        if region.lower()!='en-us' and expected in ROUTES:inspect('https://www.xbox.com/en-US/'+ROUTES[expected],'other_official_regions')
        if not ev['exact_official_pdp']:
            try:
                for u in self.external(article,name,deadline)[:3]:
                    if product_url(u):inspect(u,'external_browser_search')
                    if ev['exact_official_pdp']:break
            except Exception as e:ev['access_stops'].append(dict(url='',reason='Shared browser runtime: '+str(e)))
        ev['configuration_scope']='retail_variant' if ev['exact_official_pdp'] else 'model_only'
        self.reports[article]=ev
        main=docs.pop('xbox_configuration',None) or docs.pop('xbox_model',None);self.extra_documents=list(docs.values())
        return main or SourceDocument('xbox_model','Xbox / Microsoft','',error='No verified own official product family')
