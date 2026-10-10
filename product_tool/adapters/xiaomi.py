"""Small mi.com binding: published catalog links, existing policy and external fallback."""
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
import requests
from .common import SourceDocument, ProductDocument, PhotoCandidate, utc_now
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession, document_bytes, assess_document, document_languages
from .published_page import published_links
from bs4 import BeautifulSoup
from ..xiaomi_identity import model_name, key, requested_configuration, region
from ..xiaomi_page import parse_page
HOSTS = ('mi.com', 'appmifile.com', 'mi-fds.com', 'fds.api.xiaomi.com')

def official(url):
    p = urlsplit(url); h = p.hostname or ''
    return p.scheme == 'https' and (h == 'mi.com' or h.endswith('.mi.com')) and not p.username

def manual_assessment(pages, tokens):
    check=assess_document(pages,tokens)
    headings=[]
    guide_pages=[]
    for index,text in enumerate(pages):
        head=text[:250]
        if 'Package Contents' in head:continue
        for line in head.splitlines():
            if re.search(r'User Manual|Quick Start Guide|User Guide|Руководство пользователя|Краткое руководство',line,re.I) and not re.search(r'\bscan\b|\bview\b|\bQR\b|отскан|просмотр',line,re.I):
                headings.append(line);guide_pages.extend(range(index,min(index+3,len(pages))))
    operations=set(re.findall(r'\b(?:connect|press|reset|setup|install|configure|clean|charging)\b|нажмите|подключ|настрой|установ', '\n'.join(pages),re.I))
    check['accepted']=bool(headings and check['model_evidence']=='exact' and not check['regulatory'] and (check['accepted'] or len(operations)>=2))
    check['kind']='instruction_confirmed' if check['accepted'] else 'safety_warranty_or_unsupported_instruction'
    check['instruction_page_indices']=sorted(set(guide_pages))
    check['guide_languages']=document_languages([pages[i] for i in check['instruction_page_indices']])
    return check,headings

class XiaomiAdapter:
    def __init__(self, *, clock=time.monotonic, fetch_log_path=Path('data/xiaomi_fetch_log.json'), session=None, trace_callback=None, capture_dir=None, search_provider=None):
        self.clock = clock; self.log = Path(fetch_log_path)
        self.http = session or PolicyAwareSession(self.log, allowed_hosts=HOSTS, underlying=BinarySafeSession(requests.Session()), max_bytes=15_000_000)
        self.trace_callback = trace_callback; self.capture_dir = Path(capture_dir or self.log.parent/'xiaomi_captures')
        self.reports = {}; self.catalog_cache = {}; self.search_provider = search_provider
        self.extra_sources = []; self.deadline = 0

    def trace(self, **e):
        if self.trace_callback: self.trace_callback({'timestamp': utc_now(), 'event': 'xiaomi_discovery', 'identity_relation': 'unproven', **e})

    def fetch(self, url, *, query='', provider='official', source_type='document', cache=False):
        if cache and url in self.catalog_cache:
            self.trace(query=query, provider=provider, url=url, region=region(url), source_type=source_type, accepted=False, reason='Session catalog cache; product data still fetched live', observation='catalog_cache')
            return self.catalog_cache[url]
        if self.clock() >= self.deadline: return ''
        try:
            r = self.http.get(url, timeout=min(15, max(1, self.deadline-self.clock())))
            accepted = r.ok and not r.truncated and not r.marker
            self.trace(query=query, provider=provider, url=url, region=region(url), source_type=source_type, accepted=False, reason='HTTP '+str(r.status_code)+'; identity checked separately' if accepted else r.marker or str(r.status_code), observation='live_http')
            if not accepted: return ''
            raw = r.text.encode('utf8'); digest = hashlib.sha256(raw).hexdigest()
            self.capture_dir.mkdir(parents=True, exist_ok=True); (self.capture_dir/(digest+'.html')).write_bytes(raw)
            self.proofs.append({'url':url, 'final_url':r.url, 'sha256':digest, 'file':digest+'.html', 'observation':'live_http'})
            if r.url.rstrip('/') != url.rstrip('/'):
                self.trace(query=query, provider=provider, url=r.url, region=region(r.url), source_type='redirect', accepted=False, reason='Final URL retained; requested region must be rechecked')
            if cache: self.catalog_cache[url] = (r.text, r.url)
            return r.text, r.url
        except requests.RequestException as exc:
            self.trace(query=query, provider=provider, url=url, region=region(url), source_type=source_type, accepted=False, reason=str(exc))
            return ''

    def find_source(self, article, *, name='', category='', deadline=None):
        self.deadline = deadline or self.clock()+90; self.proofs = []; self.extra_sources = []
        wanted = model_name(name); opts = requested_configuration(name); market = opts.get('region','Global').casefold()
        roots = [f'https://www.mi.com/{market}/'] if market in {'ru','uk','de','fr','global','cn'} else []
        if not roots:
            self.trace(query=article, provider='regional_exact', url='', region=market, source_type='catalog', accepted=False, reason='No exact EEA regional root or retail relation; Global is fallback only')
        roots += [u for u in ('https://www.mi.com/global/','https://www.mi.com/uk/') if u not in roots]
        best = None
        for root in roots:
            page = self.fetch(root, query=article, provider='regional_catalog', source_type='catalog', cache=True)
            if not page: continue
            html, final = page
            links = published_links(html, final)
            catalog = next((u for u,t in links if official(u) and '/sitemap/' in u), '')
            if catalog:
                p = self.fetch(catalog, query=wanted, provider='official_sitemap', source_type='html_sitemap', cache=True)
                if p: links += published_links(*p)
            candidates = []
            for u,t in links:
                path = urlsplit(u).path.strip('/').split('/')
                if official(u) and len(path)==3 and path[1]=='product' and (key(path[2])==key(wanted) or key(t)==key(wanted)) and u not in candidates:
                    candidates.append(u)
            self.trace(query=wanted, provider='official_sitemap', url=catalog or root, region=region(root), source_type='candidate_inventory', accepted=False, reason='Only published href/SSR URLs; names/slugs rank candidates, title proves model', candidates=candidates[:4])
            for url in candidates[:2]:
                p = self.fetch(url, query=wanted, provider='official_pdp', source_type='pdp')
                if not p: continue
                doc, ev = parse_page(p[0],p[1],article,name,category)
                if ev['identity']['model_relation'] != 'model_confirmed':
                    self.trace(query=wanted, provider='official_pdp', url=p[1], region=region(p[1]), source_type='identity', accepted=False, reason=doc.error); continue
                ev['pdp_url'] = p[1]
                specs = next((u for u,t in published_links(*p) if official(u) and '/specs' in u and key(urlsplit(u).path.strip('/').split('/')[-2])==key(wanted)), '')
                if specs:
                    z = self.fetch(specs, query=wanted, provider='official_specs', source_type='specs')
                    if z:
                        parsed, evidence = parse_page(z[0],z[1],article,name,category)
                        if evidence['identity']['model_relation']=='model_confirmed':
                            doc, ev = parsed, evidence; ev['pdp_url']=p[1]
                # Published PDP images remain candidates until their appearance relation is proven.
                soup=BeautifulSoup(p[0],'html.parser')
                for img in soup.select('img.xm-img')[:80]:
                    image=img.get('src') or img.get('data-src') or ''
                    host=urlsplit(image).hostname or ''
                    if urlsplit(image).scheme!='https' or not host.endswith('.appmifile.com'):continue
                    asset=hashlib.sha256(image.encode()).hexdigest()[:24]
                    if asset in {x.asset_key for x in doc.photo_candidates}:continue
                    doc.photo_candidates.append(PhotoCandidate(image,asset,kind='candidate',excluded_reason='Exact color/appearance/bundle not proven'))
                    ev['photo_candidates'].append({'url':image,'asset_key':asset,'source_url':p[1],'alt':img.get('alt',''),'kind':'official_pdp_image_candidate','accepted':False,'reason':'Render/lifestyle distinction and exact appearance require gallery evidence'})
                best = (doc,ev)
                self.trace(query=wanted, provider='official_pdp', url=doc.url, region=region(doc.url), source_type='identity', accepted=True, reason='Exact official title; retail variant remains independently scoped', identity_relation='model_confirmed', model_identity=wanted, hardware_identity=ev['model_numbers'], retail_identity=ev['identity']['configuration_relation'])
                break
            if best: break
        if not best:
            support=self.fetch('https://www.mi.com/global/support/user-guide/',query=wanted,provider='official_support',source_type='manual_inventory',cache=True)
            if support:self.trace(query=wanted,provider='official_support',url=support[1],region=region(support[1]),source_type='discovery',accepted=False,reason='Official guide inventory checked; it does not substitute for exact PDP/spec identity')
            # Shared browser provider binding; protection is handled by the existing attended lifecycle.
            from .lg_browser_search import LGBrowserSearch
            search = self.search_provider or LGBrowserSearch(self.log, official_host='www.mi.com', official_hosts=('www.mi.com','mi.com'), allowed_hosts=('www.mi.com','mi.com','www.google.com','google.com','gstatic.com','www.bing.com','bing.com','duckduckgo.com'), candidate_classifier=lambda u:'product' if official(u) and '/product/' in u else 'support' if official(u) and '/support/' in u else 'unknown')
            search.trace_callback = self.trace_callback
            try:
                if self.clock() < self.deadline-10:
                    result = search.search_provider('google', 'site:mi.com "'+wanted+'"')
                    for c in result.candidates[:2]:
                        z=self.fetch(c.url,query=wanted,provider='external_candidate',source_type='pdp')
                        if z:
                            doc,ev=parse_page(z[0],z[1],article,name,category)
                            if ev['identity']['model_relation']=='model_confirmed': best=(doc,ev);break
            finally:
                if not self.search_provider: search.close()
        if not best:
            doc,ev=parse_page('', '', article,name,category);doc.error='Official exact model not found within safe discovery budget'
        else: doc,ev=best
        ev['captures']=list(self.proofs); ev['live_success']=bool(best and doc.attributes);ev['observation']='live_http'
        region_names={x['name'] for x in ev['accepted_specs'] if x['scope']=='region'}
        if region_names:
            attrs=[x for x in doc.attributes if x.name in region_names];doc.attributes=[x for x in doc.attributes if x.name not in region_names]
            self.extra_sources.append(SourceDocument('xiaomi_region','Xiaomi Official — '+ev['identity']['source_region'],doc.url,found_model=doc.found_model,match_level='configuration_confirmed',evidence='Exact source market matches requested market; no SKU asserted',attributes=attrs,html=doc.html))
        self.reports[article.upper()] = ev
        return doc

    def find_documents(self, doc, article):
        ev=self.reports[article.upper()];wanted=ev['identity']['model'];documents=[];technical=False;seen=set()
        for root in ('https://www.mi.com/ru/support/user-guide/','https://www.mi.com/uk/support/user-guide/'):
            p=self.fetch(root,query=wanted,provider='official_support',source_type='manual_inventory',cache=True)
            if not p: technical=True;continue
            matches=[(u,t) for u,t in published_links(*p) if key(t)==key(wanted) and '.pdf' in urlsplit(u).path.casefold()]
            self.trace(query=wanted,provider='official_support',url=p[1],region=region(p[1]),source_type='manual_inventory',accepted=False,reason='Exact model inventory; document type/language checked from PDF',candidates=[u for u,t in matches])
            for u,t in matches[:1]:
                if u in seen:continue
                seen.add(u)
                h=urlsplit(u).hostname or ''
                if not any(h==a or h.endswith('.'+a) for a in HOSTS):continue
                if self.clock()>=self.deadline:technical=True;continue
                try:
                    r=self.http.get(u,timeout=15);raw=document_bytes(r)
                    if not r.ok or r.marker or r.truncated or not raw.startswith(b'%PDF-'):technical=True;continue
                    import pymupdf
                    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                        if len(pdf)>600:technical=True;continue
                        pages=[x.get_text() for x in pdf]
                    if sum(map(len,pages))>2_000_000:technical=True;continue
                    tokens=[wanted, wanted.removeprefix('Xiaomi ')]+[x['value'] for x in ev['model_numbers']]
                    check,guide_heads=manual_assessment(pages,tokens)
                    sha=hashlib.sha256(raw).hexdigest();self.capture_dir.mkdir(parents=True,exist_ok=True);(self.capture_dir/(sha+'.pdf')).write_bytes(raw)
                    ev['manuals'].append({'url':u,'source_url':p[1],'label':t,'sha256':sha,'file':sha+'.pdf','assessment':check,'guide_headings':guide_heads,'observation':'live_http','kind':'User Guide / Quick Start' if check['accepted'] else 'Safety/Warranty or unconfirmed instruction'})
                    # Literal regulatory model labels; never decode numeric codes or promote to SKU.
                    for value in dict.fromkeys(re.findall(r'(?mi)^(?:Model|Модель):\s*([A-Z0-9-]{5,})\s*$', '\n'.join(pages))):
                        if value not in {x['value'] for x in ev['model_numbers']}:
                            ev['model_numbers'].append({'kind':'hardware_model_number','value':value,'model':wanted,'source_url':u,'retail_sku_relation':'unproven','relation':'Exact-model official inventory + literal PDF Model label'})
                    if check['accepted']:
                        languages=check['guide_languages'].get('present',[])
                        language=', '.join({'ru':'Русский','en':'Английский','zh':'Китайский','ar':'Арабский','uk':'Украинский','kk':'Казахский'}.get(x,x) for x in languages)
                        documents.append(ProductDocument(t+' — '+('Quick Start Guide' if any('Quick Start' in h for h in guide_heads) else 'User Guide / Руководство'),language,'',str(len(raw)),u,p[1],wanted,wanted,p[1],primary=not documents));ev['verified_documents'].append(u)
                except (requests.RequestException,ValueError,RuntimeError) as exc:
                    technical=True;ev['manuals'].append({'url':u,'error':str(exc),'source_url':p[1]})
        ev['manual_status']='Проверена' if documents else 'Не проверена' if technical else 'Проверена, не найдена'
        if ev['identity']['identifier_kind']=='opaque_code':
            matched=any(x['value'].casefold()==article.casefold() for x in ev['model_numbers'])
            ev['identity']['hardware_relation']='hardware_confirmed' if matched else 'unproven'
        ev['captures']=list(self.proofs)
        return documents
