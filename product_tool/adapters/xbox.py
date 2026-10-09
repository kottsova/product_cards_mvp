"""Xbox public discovery through shared policy HTTP, sitemap and browser search."""
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit,quote
import requests
import zlib
from xml.etree.ElementTree import ParseError
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from .common import SourceDocument,SourceError,utc_now,clean_text,fetch_with_retry
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession,document_bytes
from ..lg_sitemap_discovery import parse_sitemap
from ..xbox_identity import HOSTS,ROUTES,official,family,identifier,product_url,search_kind,canonical_product_url
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
        i=getattr(self,'current_identity',{})
        if self.trace_callback:self.trace_callback(dict(timestamp=utc_now(),event='xbox_discovery',model_identity=i.get('model','unproven'),hardware_identity=i.get('hardware','unproven'),retail_identity=i.get('configuration','unproven'),**e))

    def fetch(self,url,query,provider,kind,deadline):
        if self.clock()>=deadline:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason='budget_exhausted',identity_relation='unproven');return None
        try:
            if not official(url):raise ValueError('Non-official URL rejected before fetch')
            key=(str(self.log),url);cached=_CACHE.get(key)
            hit=bool(cached and self.clock()-cached[0]<600)
            class TracedSession:
                def get(inner,u,**kwargs):
                    self.emit(query=query,provider=provider,url=u,region=urlsplit(u).path.split('/')[1],source_type=kind,accepted=False,reason='HTTP attempt; bounded shared retry for network/5xx only',identity_relation='unproven')
                    response=self.session.get(u,**kwargs)
                    if response.status_code==429:raise SourceError('HTTP 429: access stop respected; no retry or transport switch')
                    return response
            z=cached[1] if hit else fetch_with_retry(TracedSession(),url,deadline=deadline,clock=self.clock,timeout=12)
            if z.status_code!=200 or z.truncated or not official(z.url):raise ValueError(f'HTTP {z.status_code}; truncated={z.truncated}; returned={z.url}')
            binary=urlsplit(z.url).path.lower().endswith(('.pdf','.gz'))
            p=self.capture_dir/(hashlib.sha256(z.url.encode()).hexdigest()[:20]+('.bin' if binary else '.html'))
            if binary:p.write_bytes(document_bytes(z))
            else:p.write_text(z.text,encoding='utf8')
            _CACHE[key]=(self.clock(),z)
            self.emit(query=query,provider=provider,url=z.url,region=urlsplit(z.url).path.split('/')[1],source_type=kind,accepted=True,reason='Public response fetched; own identity evaluated separately',identity_relation='unproven',cache_hit=hit)
            return z
        except Exception as e:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason=str(e),identity_relation='unproven');return None

    def external(self,article,name,deadline):
        from .lg_browser_search import LGBrowserSearch
        from ..census.browser_runtime import PlaywrightBrowser
        from ..census.attended_google import AttendedGoogleBrowser
        from ..census.browser_contracts import BrowserBudget
        search=(self.search_factory or (lambda:LGBrowserSearch(self.log.parent/'xbox_search.json',allowed_hosts=('www.microsoft.com','www.xbox.com','www.bing.com','bing.com','www.google.com','google.com','gstatic.com'),official_host='www.xbox.com',official_hosts=('www.xbox.com','www.microsoft.com'),driver_factory=PlaywrightBrowser,budget=BrowserBudget(deadline_seconds=20,operation_timeout_seconds=8),candidate_classifier=search_kind)))()
        search.trace_callback=lambda e:self.emit(**{k:v for k,v in e.items() if k not in {'event','timestamp'}})
        out=[]
        try:
            for provider in ('bing','google'):
                if self.clock()>=deadline:break
                if provider=='google' and self.search_factory is None:
                    search.close()
                    search=LGBrowserSearch(self.log.parent/'xbox_search.json',allowed_hosts=('www.microsoft.com','www.xbox.com','www.google.com','google.com','gstatic.com','consent.google.com'),official_host='www.xbox.com',official_hosts=('www.xbox.com','www.microsoft.com'),driver_factory=lambda runtime,budget,allowed_hosts:AttendedGoogleBrowser(runtime,budget,allowed_hosts,profile_dir=self.log.parent/'attended_profile',output_dir=self.log.parent/'attended_search',fetch_log_path=self.log.parent/'xbox_search.json',max_wait_seconds=60,official_hosts=('www.xbox.com','www.microsoft.com')),budget=BrowserBudget(deadline_seconds=60,operation_timeout_seconds=8),candidate_classifier=search_kind,allow_attended_challenge=True)
                    search.trace_callback=lambda e:self.emit(**{k:v for k,v in e.items() if k not in {'event','timestamp'}})
                query=f'site:microsoft.com "{article.split("/")[0]}" {name}'
                result=search.search_provider(provider,query);out.extend(c.url for c in result.candidates)
                self.emit(query=query,provider=provider+'_browser',url='',region='',source_type='search',accepted=bool(result.candidates),reason=result.outcome,identity_relation='candidate_only')
                if result.outcome in {'rate_limited','challenge_detected','host_stopped'}:self.emit(query=query,provider=provider+'_browser',url='',region='',source_type='search',accepted=False,reason='attended_required; bounded manual challenge flow only; rate-limit stop is retained',identity_relation='unproven')
                if out:break
        finally:search.close()
        return out

    def find_source(self,article,*,name='',category='',region='en-US',deadline):
        article=article.strip().upper();req=identifier(article);expected=family(name);docs={};visited=set();links=[];bindings=[];link_labels={};self.extra_documents=[]
        ev=dict(requested_identifier=article,requested_identifier_type=req['type'],requested_region=region,model_key=expected,query_variants=list(dict.fromkeys([article.split('/')[0],name,re.sub(r'(\d)\s*(TB|GB)',r'\1 \2',name,flags=re.I),f'{article} Xbox'])),identity={'model':'unproven','configuration':'unproven','hardware':'unproven'},identifiers={},raw_specs=[],accepted_specs=[],attribute_scopes={},identity_relations=[],configuration_candidates=[],photo_candidates=[],exact_photo_assets=[],photo_scopes={},manuals=[],manual_status='Не проверена',configuration_fields={},configuration_complete=False,hardware_complete=False,exact_official_pdp='',hardware_official_pdp='',support_url='',access_stops=[])
        if req['hardware_model']:
            # Hardware numbers often surface replacement parts; also search the requested model.
            normalized=clean_text(re.sub(r'\bhardware\s+(?:model\s+)?(?:number\s+)?'+re.escape(req['hardware_model'])+r'\b','',name,flags=re.I))
            ev['query_variants']=list(dict.fromkeys([normalized,article,*ev['query_variants']]))
        self.current_identity=ev['identity']
        def decision(url,provider,accepted,reason,relation='candidate_only',kind='product'):
            self.emit(query=article,provider=provider,url=url,region=urlsplit(url).path.split('/')[1] if url else region,source_type=kind,accepted=accepted,reason=reason,identity_relation=relation)
        def page_links(z):
            found=[]
            for n in BeautifulSoup(z.text,'html.parser').select('a[href]'):
                u=urljoin(z.url,n['href'])
                if product_url(u):
                    found.append(u);key=canonical_product_url(u);label=clean_text(n.get_text(' ',strip=True))
                    if family(label)==expected or key not in link_labels:link_labels[key]=label
            return found
        def inspect(url,provider):
            url=canonical_product_url(url)
            if url in visited:return None
            z=self.fetch(url,article,provider,'product',deadline)
            if not z:return None
            visited.add(url);links.extend(page_links(z));d,p=parse_page(z.text,z.url,article,expected,region,name=name,catalog_bindings=bindings)
            if d.error:decision(z.url,provider,False,d.error,'mismatch');return z
            ev.setdefault('page_default_titles',[]).append(dict(url=z.url,title=p['page_default_title'],resolved_title=d.found_model,scope=d.source_key))
            for key in ('raw_specs','accepted_specs','identity_relations','configuration_candidates','photo_candidates','exact_photo_assets'):ev[key].extend(x for x in p[key] if x not in ev[key])
            ev['attribute_scopes'].update(p['attribute_scopes']);ev['photo_scopes'].update(p['photo_scopes']);ev['identity']['model']='model_confirmed'
            if d.source_key=='xbox_configuration':
                docs[d.source_key]=d;ev.update({k:p[k] for k in ('identifiers','configuration_fields','configuration_complete')});ev['identity']['configuration']=p['identity']['configuration'];ev['exact_official_pdp']=z.url
            elif d.source_key=='xbox_hardware':
                docs[d.source_key]=d;ev['identifiers'].update(p['identifiers']);ev['identity']['hardware']=p['identity']['hardware'];ev['hardware_complete']=p['hardware_complete'];ev['hardware_official_pdp']=z.url
            elif d.source_key not in docs:docs[d.source_key]=d
            decision(z.url,provider,True,d.evidence,p['identity']['configuration'] if d.source_key=='xbox_configuration' else p['identity']['hardware'] if d.source_key=='xbox_hardware' else 'model_confirmed')
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
                        if identifier(value)['product_id']:
                            bindings.append(dict(field=key,value=value,source_url=z.url,title=row.get('headline',''),storage=row.get('storage',''),color=row.get('color',''),feature=row.get('feature',''),region=region,relation='catalog_candidate_requires_own_store_row'))
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
            if (family(p.replace('-',' '))!=expected and family(link_labels.get(canonical_product_url(u),''))!=expected) or '/'+region.lower()+'/' not in p:return -1
            generic=ROUTES.get(expected,'').split('/')[-1]
            return 10+(30 if p.split('/')[-2:][0]==generic else 0)+sum(t in p for t in re.findall(r'[a-z0-9]+',name.lower()) if len(t)>2)-(20 if '/configure/' in p else 0)
        # Inspect exact ID links first; other own Store pages may publish related PDP links.
        def store_candidates(provider,limit=4):
            attempted=set()
            for _ in range(limit):
                candidates=sorted({canonical_product_url(u) for u in links if urlsplit(u).hostname=='www.microsoft.com' and '/'+region.lower()+'/' in urlsplit(u).path.lower() and rank(u)>0} - visited-attempted,key=lambda u:(-rank(u),u))
                if not candidates or ev['exact_official_pdp'] or ev['hardware_complete']:break
                u=candidates[0];attempted.add(u);inspect(u,provider)
        store_candidates('microsoft_store')
        if not ev['exact_official_pdp'] and not ev['hardware_complete']:
            home=self.fetch('https://www.microsoft.com/'+region.lower(),article,'official_search_declaration','catalog',deadline)
            template=None
            if home:
                home_soup=BeautifulSoup(home.text,'html.parser')
                for s in home_soup.select('script[type="application/ld+json"]'):
                    try:data=json.loads(s.text)
                    except ValueError:continue
                    action=data.get('potentialAction',{}) if isinstance(data,dict) else {}
                    target=action.get('target',{}) if isinstance(action,dict) else {}
                    t=target.get('urlTemplate','') if isinstance(target,dict) else target
                    if action.get('@type')=='SearchAction' and official(t) and '{search_term_string}' in t and '/'+region.lower()+'/' in t.lower():template=t;break
                if not template:
                    node=home_soup.find(attrs={'searchurl':True,'queryparametername':True})
                    if node and node.get('queryparametername')=='q' and official(node['searchurl']) and '/'+region.lower()+'/search/' in node['searchurl'].lower():template=node['searchurl']+'?q={search_term_string}'
            if template:
                for q in ev['query_variants'][:3 if req['hardware_model'] else 2]:
                    search=self.fetch(template.replace('{search_term_string}',quote(q)),q,'official_search','search',deadline)
                    if search:links.extend(page_links(search));store_candidates('official_search_result')
                    if ev['exact_official_pdp'] or ev['hardware_complete']:break
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
        if not ev['exact_official_pdp'] and not ev['hardware_complete']:
            try:
                for u in self.external(article,name,deadline)[:3]:
                    if product_url(u):inspect(u,'external_browser_search')
                    if ev['exact_official_pdp']:break
            except Exception as e:ev['access_stops'].append(dict(url='',reason='Shared browser runtime: '+str(e)))
        ev['configuration_scope']='retail_variant' if ev['exact_official_pdp'] else 'hardware_only' if ev['hardware_complete'] else 'model_only'
        self.reports[article]=ev
        main=docs.pop('xbox_configuration',None) or docs.pop('xbox_hardware',None) or docs.pop('xbox_model',None);self.extra_documents=list(docs.values())
        return main or SourceDocument('xbox_model','Xbox / Microsoft','',error='No verified own official product family')
