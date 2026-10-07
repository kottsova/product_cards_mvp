"""Lenovo source adapter using the shared HTTP policy and official support tree.

URLs and request parameters are discovery candidates, never identity proof.
Only a returned structured Model plus non-empty configuration Description can
establish exact MTM. Family/options remain separate evidence metadata.
"""
from __future__ import annotations
import json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,quote
from bs4 import BeautifulSoup
from .common import SourceDocument,RawAttribute,PhotoCandidate,ProductDocument,clean_text,utc_now
from .policy_session import PolicyAwareSession

HOSTS=('lenovo.com','pcsupport.lenovo.com','support.lenovo.com','psref.lenovo.com','download.lenovo.com','psrefstuff.lenovo.com','static.pub')
OPTION=re.compile(r'\b(up to|starting (?:at|from)|optional|varies|depending|available options|maximum|supports? up to)\b|\s+or\s+',re.I)
TYPES=('User Guide','Hardware Maintenance Manual','Setup Guide','Safety/Warranty Guide','Regulatory Notice')
_CATALOG={}

def code(value):
    return clean_text(value).upper()

def queries(article,name=''):
    article=code(article)
    return [f'site:lenovo.com "{article}"',f'site:psref.lenovo.com "{article}"',f'site:pcsupport.lenovo.com "{article}"',f'Lenovo "{article}" {name}'.strip()]

def object_after(html,marker):
    m=re.search(marker,html)
    if not m:return {}
    start=html.find('{',m.end())
    if start<0:return {}
    try:return json.JSONDecoder().raw_decode(html[start:])[0]
    except (ValueError,TypeError):return {}

def support_identity(info,article):
    found=code(info.get('Model',''))
    description=info.get('Description','')
    structured_fields=re.findall(r'(?:^|:\s*:\s*)(Processor|Memory|Operating System|Hard Drive|Graphics|Monitor|Display|Battery|Camera|Ports|Dimensions|Weight)\s*:',description,re.I)
    exact=found==code(article) and len(set(x.casefold() for x in structured_fields))>=2 and not re.search(r'CTO|XXXX',found)
    return {'relation':'exact_mtm' if exact else 'family_model' if info.get('ProductName') else 'unknown',
            'requested':code(article),'returned_model':found,'machine_type':found[:4] if found else '',
            'model_name':info.get('ProductName',''),'configuration_body_present':len(set(structured_fields))>=2,
            'configuration_resolved':exact,'reason':'structured Model and configuration Description' if exact else 'No returned exact configuration facts; request/URL is not proof'}

def split_specs(info,relation):
    facts=[]; candidates=[]
    for fragment in re.split(r'\s*:\s*:\s*',info.get('Description','')):
        if ':' not in fragment:continue
        label,value=fragment.split(':',1);label,value=clean_text(label),clean_text(value)
        if not label or not value or re.fullmatch(r'\d+x',value) or label.casefold() in {'included warranty','warranty','service','bios','drivers'}:continue
        raw={'section':'Configuration','raw_label':label,'value':value}
        capability=bool(re.search(r'\b(max(?:imum)?|options|support(?:ed)?)\b',label,re.I))
        if relation!='exact_mtm' or OPTION.search(value) or capability:
            candidates.append({**raw,'scope':'family_option' if relation!='exact_mtm' else 'conditional_configuration','reason':'family source or qualified/alternative value'})
        else:facts.append(RawAttribute(label,value,'Configuration'))
    return facts,candidates

def catalog_paths(text,article):
    start=text.find('[{')
    if start<0:return []
    try:tree=json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError:return []
    found=[]
    def walk(nodes,path):
        for node in nodes:
            here=path+[node]
            if code(node.get('n',''))==code(article)[:4] and len(here)==4:
                slug='/'.join(re.sub(r'[\\/ ]','-',x['n'].strip()).lower() for x in here)
                found.append({'path':slug,'product_id':node['k'],'family_id':here[-2]['k'],'family':here[-2].get('l',''),'image':next((x.get('i') for x in reversed(here) if x.get('i')),'')})
            walk(node.get('o',[]),here)
    walk(tree,[])
    return found

def typed_manual(title):
    text=title.casefold()
    if 'hardware maintenance' in text:return 'Hardware Maintenance Manual'
    if 'regulatory' in text:return 'Regulatory Notice'
    if 'safety' in text or 'warranty' in text:return 'Safety/Warranty Guide'
    if 'setup' in text:return 'Setup Guide'
    if 'user guide' in text or 'user manual' in text:return 'User Guide'
    return ''

class LenovoAdapter:
    source_key='lenovo_support'
    site_name='Lenovo Support'
    def __init__(self,*,clock=time.monotonic,fetch_log_path=Path('data/lenovo_fetch_log.json'),session=None,trace_callback=None,search_provider=None):
        self.clock=clock;self.http=session or PolicyAwareSession(fetch_log_path,allowed_hosts=HOSTS,clock=clock)
        self.trace_callback=trace_callback;self.search_provider=search_provider;self.reports={};self.documents=[]
    def trace(self,**event):
        if self.trace_callback:self.trace_callback({'event':'lenovo_discovery','timestamp':utc_now(),**event})
    def get(self,url,article,kind,region,deadline):
        if self.clock()>=deadline:
            self.trace(query=article,provider='official_http',url=url,region=region,source_type=kind,accepted=False,reason='deadline_exhausted',identity_relation='unknown');return None
        r=self.http.get(url,timeout=min(10,max(.1,deadline-self.clock())))
        self.trace(query=article,provider='official_http',url=url,final_url=r.url,region=region,source_type=kind,accepted=False,reason=r.marker or ('candidate_body_received' if r.ok else f'HTTP {r.status_code}'),identity_relation='unknown')
        return r if r.ok else None
    def find_source(self,article,*,name='',category='',deadline):
        article=code(article)
        report={'article':article,'query_variants':queries(article,name),'sources':[],'configuration_candidates':[],'manuals':[],'manual_status':'Не проверена','configuration_identity':{},'photos_relation':'family_model','gaps':[]}
        self.reports[article]=report;self.documents=[]
        # Regional exact storefront route first. A redirect to family is not exact.
        regional=f'https://www.lenovo.com/kz/ru/p/{quote(article.lower())}'
        r=self.get(regional,article,'product','kz',deadline)
        if r:
            store=self.store_evidence(r,article)
            report['sources'].append(store)
            report['configuration_candidates']+=store.get('configuration_candidates',[])
        # PSREF is an independent official specification reference, not automatically PDP.
        psref=f'https://psref.lenovo.com/Detail/?M={quote(article)}'
        r=self.get(psref,article,'psref','global',deadline)
        if r:
            report['sources'].append({'url':r.url,'type':'psref','relation':'unknown','reason':'SPA shell or unparsed body; M parameter does not prove model relation'})
        choices=[]
        for region,language in (('kz','ru'),('us','en')):
            url=f'https://pcsupport.lenovo.com/api/products/{region}/{language}.js'
            cached=_CATALOG.get(url)
            if cached is None:
                r=self.get(url,article,'support_catalog',region,deadline)
                if r:cached=r.text;_CATALOG[url]=cached
            if cached:
                choices=[{**p,'region':region,'language':language} for p in catalog_paths(cached,article)]
            if choices:
                if region == "kz":choices += [{**p,"region":"us","language":"en"} for p in choices]
                break
        best=SourceDocument(self.source_key,self.site_name,'',error='Official exact MTM configuration not resolved')
        for candidate in choices[:2]:
            base=f"https://pcsupport.lenovo.com/{candidate['region']}/{candidate['language']}/products/{candidate['path']}"
            r=self.get(base+'/'+article.lower(),article,'support',candidate['region'],deadline)
            if not r:continue
            info=object_after(r.text,r'var\s+ds_productinfo\s*=')
            identity=support_identity(info,article)
            attrs,options=split_specs(info,identity['relation']);report['configuration_candidates']+=options
            report['sources'].append({'url':r.url,'type':'support','relation':identity['relation'],'identity':identity})
            report['configuration_identity']=identity
            image=candidate.get('image','')
            photos=[PhotoCandidate(image,image,'product_gallery',excluded_reason='family_model_only')] if image and 'ProdImageLaptops/laptops-and-netbooks' not in image else []
            best=SourceDocument(self.source_key,self.site_name,r.url,found_model=identity['returned_model'],match_level='full_sku' if identity['configuration_resolved'] else 'base_model',evidence=json.dumps(identity,ensure_ascii=False),attributes=attrs,photo_candidates=photos,html=r.text)
            self.trace(query=article,provider='support_catalog',url=r.url,region=candidate['region'],source_type='support',accepted=identity['configuration_resolved'],reason=identity['reason'],identity_relation=identity['relation'])
            self.manual_candidates(base,candidate,article,deadline,report)
            if identity['configuration_resolved']:break
        if best.match_level!='full_sku' and self.clock()<deadline:
            r=self.get(f'https://www.lenovo.com/us/en/p/{quote(article.lower())}',article,'product','us',deadline)
            if r:
                store=self.store_evidence(r,article);report['sources'].append(store)
                report['configuration_candidates']+=store.get('configuration_candidates',[])
        if best.match_level!='full_sku' and self.search_provider is None and self.clock()<deadline:
            self.search_provider=self.shared_search
        if best.match_level!='full_sku' and self.search_provider and self.clock()<deadline:
            for item in self.search_provider(queries(article,name),deadline=deadline):
                url=item.get('url','') if isinstance(item,dict) else item.url
                if (urlsplit(url).hostname or '') not in {'www.lenovo.com','psref.lenovo.com','pcsupport.lenovo.com','support.lenovo.com'}:continue
                r=self.get(url,article,'web_candidate','other',deadline)
                if not r:continue
                if 'support.lenovo.com' in urlsplit(url).hostname:
                    info=object_after(r.text,r'var\s+ds_productinfo\s*=');identity=support_identity(info,article)
                    if identity['configuration_resolved']:
                        attrs,options=split_specs(info,'exact_mtm');report['configuration_candidates']+=options;report['configuration_identity']=identity
                        best=SourceDocument(self.source_key,self.site_name,r.url,found_model=article,match_level='full_sku',evidence=json.dumps(identity),attributes=attrs,html=r.text)
                        break
                else:report['sources'].append(self.store_evidence(r,article))
        elif best.match_level!='full_sku':
            self.trace(query=queries(article,name)[-1],provider='external_search',url='',region='global',source_type='search',accepted=False,reason='shared_search_provider_not_available' if not self.search_provider else 'deadline_exhausted',identity_relation='unknown')
        report['gaps']=['exact_gallery_not_confirmed','russian_user_guide_not_verified']+([] if best.match_level=='full_sku' else ['exact_configuration_not_resolved'])
        return best
    def shared_search(self,query_plan,*,deadline):
        from .lg_browser_search import LGBrowserSearch
        search=LGBrowserSearch(self.http.log_path.with_name("lenovo_browser_search_log.json"),
                official_host="www.lenovo.com", official_hosts=("www.lenovo.com","psref.lenovo.com","pcsupport.lenovo.com","support.lenovo.com"),
                allowed_hosts=("www.lenovo.com","lenovo.com","psref.lenovo.com","pcsupport.lenovo.com","support.lenovo.com","www.google.com","google.com","gstatic.com","www.bing.com","bing.com","duckduckgo.com"))
        search.trace_callback=self.trace_callback
        try:
            for query in query_plan[:2]:
                if self.clock()>=deadline:break
                result=search.search_provider("google",query)
                for candidate in result.candidates:yield candidate
                if result.outcome in {"runtime_unavailable","challenge_detected","rate_limited","http_denied"}:break
        finally:search.close()

    def store_evidence(self,response,article):
        soup=BeautifulSoup(response.text,'html.parser');structured=[]
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                value=json.loads(script.get_text());items=value if isinstance(value,list) else [value]
                structured += [x for x in items if isinstance(x,dict) and x.get('@type')=='Product']
            except ValueError:pass
        returned=[code(x.get('mpn','')) for x in structured]
        # Store is retained as candidate metadata. Family technical options must not enter exact facts.
        pdp=object_after(response.text,r'var\s+\$pdpAllData\s*=')
        candidates=[]
        def walk(obj,section='Family specifications'):
            if isinstance(obj,dict):
                label=obj.get('headline') or obj.get('label') or obj.get('name')
                value=obj.get('text') or obj.get('value')
                if isinstance(label,str) and isinstance(value,str):
                    text=BeautifulSoup(value,'html.parser').get_text(' ',strip=True)
                    if text:candidates.append({'section':section,'raw_label':label,'value':text,'scope':'family_option','reason':'Unselected storefront configuration; no exact MTM proof'})
                for key,value in obj.items():
                    if key not in {'productFeatures','navigation','subseriesHero'}:walk(value,section)
            elif isinstance(obj,list):
                for value in obj:walk(value,section)
        walk(pdp.get('techSpecs') or pdp.get('techSpec') or {})
        return {'url':response.url,'type':'product','relation':'exact_part_number' if article in returned and 'CTO' not in article else 'family_model' if returned else 'unknown','returned_mpn':returned,'configuration_confirmed':False,'family_options':pdp.get('techSpecs',{}),'configuration_candidates':candidates,'reason':'Storefront options retained as metadata; no selected configuration extraction'}
    def manual_candidates(self,base,candidate,article,deadline,report):
        region,language=candidate['region'],candidate['language']
        url=f"https://pcsupport.lenovo.com/{region}/{language}/api/v4/contents/productmultlanguagelist?pids={candidate['family_id']}&types=Manual,SG&countries={region}&language={language}"
        r=self.get(url,article,'manual_index',region,deadline)
        if not r:return
        try:data=r.json()
        except ValueError:return
        def walk(obj):
            if isinstance(obj,dict):
                title=str(obj.get('Title') or obj.get('title') or obj.get('Name') or obj.get('name') or '')
                dtype=typed_manual(title)
                if dtype:
                    links=[]
                    def urls(x):
                        if isinstance(x,str) and x.startswith('https://') and (urlsplit(x).hostname or '').endswith('lenovo.com'):links.append(x)
                        elif isinstance(x,dict):
                            for v in x.values():urls(v)
                        elif isinstance(x,list):
                            for v in x:urls(v)
                    urls(obj)
                    for link in dict.fromkeys(links):
                        title_language=re.match(r'\((English|Russian|Arabic|Chinese|French|German|Spanish|Italian|Japanese|Korean)\)',title,re.I)
                        language={'english':'en','russian':'ru','arabic':'ar','chinese':'zh','french':'fr','german':'de','spanish':'es','italian':'it','japanese':'ja','korean':'ko'}.get(title_language.group(1).casefold(),'unknown') if title_language else 'unknown'
                        report['manuals'].append({'type':dtype,'title':title,'language':language,'url':link,'relation':'family_model','verified':False,'reason':'Index candidate; content/language/model relation not verified'})
                for value in obj.values():walk(value)
            elif isinstance(obj,list):
                for value in obj:walk(value)
        walk(data)
        report["manuals"]=list({(x["type"],x["url"]):x for x in report["manuals"]}.values())
    def find_documents(self,document,article):
        return [] # Typed unverified links remain in evidence, never verified instructions.
