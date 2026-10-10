"""Dreame catalog/Shopify binding over existing policy, published links and search."""
import time,re,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit
import requests
from .xiaomi import XiaomiAdapter,manual_assessment as shared_manual_assessment
from .common import ProductDocument
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession,document_bytes,document_languages
from .published_page import published_links
from ..dreame_page import parse_page,official,region,matches,HOSTS,MEDIA_HOSTS,clean_model
from ..xiaomi_identity import model_name,requested_configuration,key

ROOTS=('https://global.dreametech.com/','https://www.dreametech.com/','https://de.dreametech.com/')

def manual_label_matches(wanted,label):
    label=re.sub(r'\s*(?:User Manual|User Guide|Quick Start Guide)(?:-\d+)?\s*$','',label,flags=re.I).strip()
    return any(matches(wanted,part.strip()) for part in label.split('/'))

def manual_assessment(pages,tokens):
    check,headings=shared_manual_assessment(pages,tokens)
    exact_cover=any(matches(token,line.strip()) for text in pages[:2] for line in text.splitlines() for token in tokens)
    ru_pages=[]
    for i,text in enumerate(pages):
        for line in text[:250].splitlines():
            if re.search(r'Инструкция по эксплуатации',line,re.I):
                headings.append(line);ru_pages.extend(range(i,min(i+3,len(pages))))
    operations=set(re.findall(r'нажмите|подключ|настрой|установ|заряд|очист', '\n'.join(pages),re.I))
    check['accepted']=bool(exact_cover and headings and not check['regulatory'] and (check['accepted'] or ru_pages and len(operations)>=2))
    check['kind']='instruction_confirmed' if check['accepted'] else 'safety_warranty_or_unsupported_instruction'
    check['instruction_page_indices']=sorted(set(check.get('instruction_page_indices',[])+ru_pages))
    check['guide_languages']=document_languages([pages[i] for i in check['instruction_page_indices']])
    return check,headings

class DreameAdapter(XiaomiAdapter):
    def __init__(self,*,clock=time.monotonic,fetch_log_path=Path('data/dreame_fetch_log.json'),session=None,trace_callback=None,capture_dir=None,search_provider=None):
        http=session or PolicyAwareSession(Path(fetch_log_path),allowed_hosts=MEDIA_HOSTS,underlying=BinarySafeSession(requests.Session()),max_bytes=15_000_000)
        super().__init__(clock=clock,fetch_log_path=fetch_log_path,session=http,trace_callback=trace_callback,capture_dir=capture_dir or Path(fetch_log_path).parent/'dreame_captures',search_provider=search_provider)
        self.support_inventory=[]

    def trace(self,**e):
        if '[policy_' in str(e.get('reason','')):e['observation']='policy_refusal'
        if self.trace_callback:self.trace_callback({'event':'dreame_discovery','identity_relation':'unproven',**e,'region':region(e.get('url',''))})

    def _inventory(self,root,wanted):
        p=self.fetch(root,query=wanted,provider='regional_catalog',source_type='catalog',cache=True)
        links=published_links(*p) if p else []
        self.support_inventory.extend(u for u,t in links if official(u) and re.search(r'manual|faq',u+' '+t,re.I))
        # Standard sitemap root is a discovery endpoint, never a guessed PDP.
        if not any('/products/' in u and matches(wanted,t) for u,t in links):
            sitemap=next((u for u,t in links if official(u) and 'sitemap' in u),root+'sitemap.xml')
            z=self.fetch(sitemap,query=wanted,provider='official_sitemap',source_type='sitemap',cache=True)
            if z and '<!DOCTYPE' not in z[0]:
                try:
                    tree=ET.fromstring(z[0]);locs=[x.text for x in tree.iter() if x.tag.split('}')[-1]=='loc' and x.text]
                    for u in locs:
                        if official(u) and '/products/' in u:links.append((u,''))
                    for u in [u for u in locs if official(u) and 'sitemap_products' in u][:2]:
                        child=self.fetch(u,query=wanted,provider='official_sitemap',source_type='product_sitemap',cache=True)
                        if child and '<!DOCTYPE' not in child[0]:
                            links.extend((x.text,'') for x in ET.fromstring(child[0]).iter() if x.tag.split('}')[-1]=='loc' and x.text and official(x.text))
                except ET.ParseError:self.trace(query=wanted,provider='official_sitemap',url=sitemap,source_type='sitemap',accepted=False,reason='Malformed sitemap')
        return list(dict.fromkeys(links))

    def find_source(self,article,*,name='',category='',deadline=None):
        self.deadline=deadline or self.clock()+90;self.proofs=[];self.extra_sources=[]
        wanted=model_name(name);config=requested_configuration(name);query_variants=list(dict.fromkeys([article,wanted,clean_model(wanted)]))
        self.trace(query=article,provider='normalization',url='',source_type='query_variants',accepted=False,reason='Supplier identifier separate from exact model query',query_variants=query_variants,input_configuration=config)
        market=config.get('region','Global').casefold();roots=sorted(ROOTS,key=lambda u:region(u).casefold()!=market)
        best=None
        for root in roots:
            links=self._inventory(root,wanted);candidates=[]
            for u,t in links:
                slug=urlsplit(u).path.rstrip('/').split('/')[-1].replace('-',' ')
                if official(u) and '/products/' in urlsplit(u).path and (matches(wanted,t,config) or matches(wanted,slug,config)) and u not in candidates:candidates.append(u)
            self.trace(query=wanted,provider='official_catalog',url=root,source_type='candidate_inventory',accepted=False,reason='Published links rank only; Product/title proves model',candidates=candidates[:4])
            for u in candidates[:2]:
                p=self.fetch(u,query=wanted,provider='official_pdp',source_type='pdp')
                if not p:continue
                doc,ev=parse_page(p[0],p[1],article,name,category)
                self.trace(query=wanted,provider='official_pdp',url=p[1],source_type='identity',accepted=ev['identity']['model_relation']=='model_confirmed',reason=doc.error or doc.evidence,identity_relation=ev['identity']['model_relation'])
                if ev['identity']['model_relation']=='model_confirmed':best=(doc,ev);break
            if best:break
        if not best:
            for u in list(dict.fromkeys(self.support_inventory))[:1]:self.fetch(u,query=wanted,provider='official_support',source_type='manual_inventory',cache=True)
            from .lg_browser_search import LGBrowserSearch
            hosts=tuple(urlsplit(u).hostname for u in ROOTS)
            search=self.search_provider or LGBrowserSearch(self.log,official_host=hosts[0],official_hosts=hosts,allowed_hosts=hosts+('www.google.com','google.com','gstatic.com','www.bing.com','bing.com','duckduckgo.com'),candidate_classifier=lambda u:'product' if official(u) and '/products/' in u else 'support' if official(u) and 'manual' in u else 'unknown')
            search.trace_callback=self.trace_callback
            try:
                if self.clock()<self.deadline-10:
                    query='site:dreametech.com "'+clean_model(wanted)+'"';result=search.search_provider('google',query)
                    self.trace(query=query,provider='external_browser',url='',source_type='search',accepted=False,reason=result.outcome)
                    for c in result.candidates[:2]:
                        if not official(c.url):continue
                        z=self.fetch(c.url,query=wanted,provider='external_candidate',source_type='pdp')
                        if z:
                            doc,ev=parse_page(z[0],z[1],article,name,category)
                            if ev['identity']['model_relation']=='model_confirmed':best=(doc,ev);break
            finally:
                if not self.search_provider:search.close()
        doc,ev=best if best else parse_page('','',article,name,category)
        ev['captures']=list(self.proofs);ev['live_success']=bool(best and doc.attributes);ev['observation']='live_http';self.reports[article.upper()]=ev
        return doc

    def find_documents(self,doc,article):
        self.deadline=min(self.deadline,self.clock()+12);ev=self.reports[article.upper()];documents=[];technical=False
        wanted=ev['identity']['model'];inventory=list(dict.fromkeys(self.support_inventory))
        if not inventory:ev['manual_status']='Не проверена';ev['manual_inventory_reason']='Official support navigation inaccessible';return []
        for u in inventory[:1]:
            p=self.fetch(u,query=wanted,provider='official_support',source_type='manual_inventory',cache=True)
            if not p:technical=True;continue
            published=published_links(*p)
            links=[(link,t) for link,t in published if '.pdf' in urlsplit(link).path.casefold() and manual_label_matches(wanted,t)]
            details=[(link,t) for link,t in published if official(link) and '/pages/' in urlsplit(link).path and manual_label_matches(wanted,t)]
            for detail,title in details[:1]:
                guide=self.fetch(detail,query=wanted,provider='official_support',source_type='model_manual_page',cache=True)
                if not guide:technical=True;continue
                from bs4 import BeautifulSoup
                soup=BeautifulSoup(guide[0],'html.parser');heads=[x.get_text(' ',strip=True) for x in soup.select('h1')]
                if not any(manual_label_matches(wanted,h) for h in heads):continue
                links.extend((link,title) for link,t in published_links(*guide) if '.pdf' in urlsplit(link).path.casefold())
            self.trace(query=wanted,provider='official_support',url=u,source_type='manual_inventory',accepted=False,reason='Exact model labels; type/language from document',candidates=[link for link,t in links])
            for link,t in links[:1]:
                if not any((urlsplit(link).hostname or '')==a or (urlsplit(link).hostname or '').endswith('.'+a) for a in MEDIA_HOSTS):continue
                if self.clock()>=self.deadline:technical=True;continue
                try:
                    response=self.http.get(link,timeout=min(8,max(1,self.deadline-self.clock())));raw=document_bytes(response)
                    if not response.ok or response.marker or response.truncated or not raw.startswith(b'%PDF-'):technical=True;continue
                    import pymupdf,hashlib
                    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                        if len(pdf)>600:technical=True;continue
                        pages=[x.get_text() for x in pdf]
                    check,headings=manual_assessment(pages,[wanted,clean_model(wanted)])
                    sha=hashlib.sha256(raw).hexdigest();self.capture_dir.mkdir(parents=True,exist_ok=True);(self.capture_dir/(sha+'.pdf')).write_bytes(raw)
                    ev['manuals'].append({'url':link,'source_url':u,'label':t,'assessment':check,'sha256':sha,'file':sha+'.pdf','guide_headings':headings})
                    if check['accepted']:
                        language=', '.join({'ru':'Русский','en':'Английский'}.get(x,x) for x in check['guide_languages'].get('present',[]))
                        documents.append(ProductDocument(t,language,'',str(len(raw)),link,u,wanted,wanted,u,primary=True));ev['verified_documents'].append(link)
                except (requests.RequestException,ValueError,RuntimeError):technical=True
        ev['manual_status']='Проверена' if documents else 'Не проверена' if technical else 'Проверена, не найдена';ev['captures']=list(self.proofs)
        return documents
