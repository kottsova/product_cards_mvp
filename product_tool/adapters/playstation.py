"""Small public-page adapter using shared HTTP, source and evidence contracts.

Routes identify product families, never individual SKUs. Returned page identity
is always checked; unsupported revisions and family options remain candidates.
"""
import hashlib,json,re,time
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .common import SourceDocument,RawAttribute,PhotoCandidate,clean_text,utc_now
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession,document_bytes
from ..playstation_identity import official,model_key,codes,document_type,hardware_family

ROUTES={'ps5':'ps5/','pro':'ps5/ps5-pro/','dualsense':'accessories/dualsense-wireless-controller/','portal':'accessories/playstation-portal-remote-player/','elite':'accessories/pulse-elite-wireless-headset/'}
COLORS={'midnight black':'Чёрный (Midnight Black)','white':'Белый','cosmic red':'Красный (Cosmic Red)','cobalt blue':'Синий (Cobalt Blue)'}
_STRUCTURE_CACHE={}

def section_values(soup):
    out=[]
    for h in soup.select('h2,h3,h4'):
        label=clean_text(h.get_text(' ',strip=True))
        if not label: continue
        if label.casefold() in {"what's in the box",'in the box'} and 'section-component' in h.parent.get('class',[]):
            values=list(dict.fromkeys(clean_text(n.get_text(' ',strip=True)) for n in h.parent.select('li')))
            if values:out.append((label,values))
            continue
        values=[]
        for n in h.next_elements:
            if getattr(n,'name',None) in ('h1','h2','h3','h4'): break
            if getattr(n,'name',None) in ('p','li'):
                value=clean_text(n.get_text(' ',strip=True))
                if value and value not in values: values.append(value)
        if values: out.append((label,values))
    return out

def parse_page(html,url,article,expected):
    b=BeautifulSoup(html,'html.parser');title=clean_text(b.h1.get_text(' ',strip=True)) if b.h1 else ''
    doc=SourceDocument('playstation_model','PlayStation',url,found_model=title,html=html)
    ev={'raw_specs':[],'configuration_candidates':[],'photo_candidates':[],'configuration_fields':{},'exact_photo_assets':[],'identity':{'model':'unproven','configuration':'unproven','hardware':'unproven'}}
    if not official(url) or not expected or model_key(title)!=expected or '/support/' in urlsplit(url).path:
        doc.error='Returned page model differs or is support/help content';return doc,ev
    doc.match_level='model_confirmed';ev['identity']['model']='model_confirmed'
    exact=False
    for s in b.select('script'):
        m=re.search(r'digitalData\.product\[0\]\.productInfo\s*=\s*\{(.*?)\};',s.get_text(),re.S)
        if not m: continue
        returned=re.findall(r'\bsku\s*:\s*"([^"]+)"',m[1])
        if len(returned)==1 and returned[0].upper()==article.upper() and urlsplit(url).hostname=='direct.playstation.com':
            exact=True;ev['returned_sku']=returned[0];ev['identity']['configuration']='exact_order_sku';doc.source_key='playstation';doc.match_level='full_sku'
    # JSON-LD CMS campaign IDs are not automatically retail identifiers.
    for s in b.select('script[type="application/ld+json"]'):
        try:
            x=json.loads(s.get_text())
            if isinstance(x,dict) and x.get('@type')=='Product': ev.setdefault('structured_identity',[]).append({k:x.get(k) for k in ('name','sku','mpn','productID')})
        except (ValueError,TypeError): pass
    if any(x.get('mpn','').upper()==article.upper() and article.upper().startswith('CFI-') for x in ev.get('structured_identity',[])):
        ev['identity']['hardware']='official_hardware_model_code'
        ev['hardware_model']=article.upper()
    for label,values in section_values(b):
        l=label.casefold()
        for value in values:
            raw=dict(section=label,raw_label=label,value=value);ev['raw_specs'].append(raw)
            canonical=None
            if l in {'haptic feedback','adaptive triggers'}: canonical={'haptic feedback':'Haptic Feedback','adaptive triggers':'Adaptive Triggers'}[l]
            elif l=='tempest 3d audiotech': canonical='Tempest 3D AudioTech'
            elif l=='wi-fi 7 compatible':canonical='Стандарт Wi-Fi'
            elif l in {"what's in the box",'in the box'} and exact:
                ev['configuration_fields']['bundle_contents']='; '.join(values)
                break
            if canonical:
                if canonical in {'Haptic Feedback','Adaptive Triggers','Tempest 3D AudioTech'}:
                    if re.search(r'not supported|does not support|not available|unsupported',value,re.I):
                        ev['configuration_candidates'].append({**raw,'reason':'Negative/conditional feature statement; presence not admitted'})
                        continue
                    # The named capability is a feature; prose is retained as raw
                    # evidence, not resolved as several contradictory spec values.
                    feature='Да'
                else:feature=value
                doc.attributes.append(RawAttribute(canonical,feature,section='Возможности модели',value_cell=True))
            else: ev['configuration_candidates'].append({**raw,'reason':'Configuration option or marketing; requires scoped canonical extraction'})
    if exact:
        capacities=set(re.findall(r'\b\d+\s*(?:GB|TB)\b',title,re.I))
        if len(capacities)==1:ev['configuration_fields']['storage']=next(iter(capacities))
        for color,label in COLORS.items():
            if color in title.casefold():ev['configuration_fields']['color']=label
        if 'digital edition' in title.casefold():ev['configuration_fields']['disc']='Digital'
        if 'bundle' in title.casefold():ev['configuration_fields']['bundle']=title
        ev['configuration_fields']['storefront']=urlsplit(url).path.split('/')[1]
        for key,label in (('storage','Объём накопителя'),('color','Цвет'),('disc','Оптический привод'),('bundle_contents','Комплектация')):
            if key in ev['configuration_fields']:doc.attributes.append(RawAttribute(label,ev['configuration_fields'][key],section='Конфигурация',value_cell=True))
    # Only own product assets are even candidates; recommendation photos excluded.
    for im in b.select('img'):
        u=im.get('data-src') or im.get('src') or '';alt=im.get('alt','');path=urlsplit(u).path.casefold()
        tokens={'dualsense':('dualsense',),'portal':('portal',),'elite':('pulseelite','pulse-elite'),'pro':('ps5-pro',),'ps5':('ps5','fortnite')}[expected]
        if not official(u) or not any(t in path for t in tokens) or any(t in path for t in ('logo','badge','fallback','icon')):continue
        if u in {p['url'] for p in ev['photo_candidates']} or u in doc.photos:continue
        reason='Model image; exact revision/color/bundle relation unproven'
        if re.search(r'box|packag|gameplay|background|lifestyle|contents',path+' '+alt,re.I):reason='Packaging, game, feature or accessory image'
        if re.search(r'bundle|usb cable|cable-and',path+' '+alt,re.I):reason='Other bundle or accessory configuration image'
        is_black=ev['configuration_fields'].get('color')=='Чёрный (Midnight Black)' and 'midnight-black' in path
        own=any(a.name=='image-cluster' or 'image-cluster' in a.get('class',[]) for a in im.parents)
        if exact and is_black and own and reason.startswith('Model') and model_key(alt)==expected:
            asset=hashlib.sha256(u.encode()).hexdigest();doc.photo_candidates.append(PhotoCandidate(u,asset));doc.photos.append(u);ev['exact_photo_assets'].append(asset)
        else:
            ev['photo_candidates'].append(dict(url=u,reason=reason))
    doc.evidence='Exact commercial SKU in own official PDP' if exact else 'Exact family PDP; configuration and CFI revision checked separately'
    return doc,ev

def parse_hardware_specs(text,url,code):
    """Single-hardware tables only. Combined A/B and component tables withheld."""
    doc=SourceDocument('playstation_hardware','PlayStation hardware guide',url,found_model=code,match_level='hardware_confirmed')
    raw=[];candidates=[]
    pieces=re.split(r'(?m)^Specifications\s*$',text)
    if len(pieces)<2:return doc,raw,candidates
    block=pieces[1]
    if '/ps5-docs/' in url:
        if re.search(r'/\d{4}ab/',url):return doc,raw,[dict(section='Specifications',raw_label='Combined hardware table',value=block[:6500],reason='Combined Disc/Digital table requires row-level revision routing')]
        block=block.split('Wireless controller')[0].split('DualSense')[0]
    else:block=re.split(r'GUARANTEE|Compliance|For customers',block)[0]
    labels={'CPU':'Процессор','GPU':'Графический процессор','Memory':'Оперативная память','Storage':'Объём накопителя','Maximum rated power':'Максимальная потребляемая мощность','Mass':'Вес товара','Battery capacity':'Ёмкость аккумулятора','Input power rating':'Питание'}
    label_pattern='|'.join(re.escape(x) for x in sorted(labels,key=len,reverse=True))
    lines=block.splitlines()
    dimension_context=''
    for line in lines:
        line=clean_text(line)
        if line.startswith('External dimensions'):dimension_context=line
        elif dimension_context and line.startswith('('):dimension_context+=' '+line
        elif line.startswith(('Mass','Operating temperature')):dimension_context=''
        m=re.match('('+label_pattern+r')(?::|\s)+(.*)',line)
        if m and m[2]:
            raw.append(dict(section='Specifications',raw_label=m[1],value=m[2]));doc.attributes.append(RawAttribute(labels[m[1]],m[2],section='Характеристики оборудования',value_cell=True))
        d=re.search(r'([\d.]+)\s*×\s*([\d.]+)\s*×\s*([\d.]+)\s*mm\s*\(width\s*×\s*height\s*×\s*depth\)',line)
        if d and dimension_context and not re.search(r'package|packaging|\bwith\s+(?:the\s+)?stand',dimension_context,re.I):
            raw.append(dict(section='Specifications',raw_label='External dimensions (excluding projecting parts)',value=line))
            for label,v in zip(('Ширина товара, мм','Высота товара, мм','Глубина товара, мм'),d.groups()):doc.attributes.append(RawAttribute(label,v+' мм',section='Габариты оборудования без выступающих частей',value_cell=True))
        if line and not m and not (d and dimension_context):
            item=dict(section='Specifications',raw_label='Unmapped specification line',value=line)
            raw.append(item);candidates.append({**item,'reason':'Unmapped technical line, qualifier or metadata; not a confirmed fact'})
    return doc,raw,candidates

class PlayStationAdapter:
    def __init__(self,*,fetch_log_path=None,trace_callback=None,clock=time.monotonic,session=None):
        self.clock=clock;self.log=Path(fetch_log_path or 'data/playstation_fetch.json');self.trace_callback=trace_callback
        self.session=session or PolicyAwareSession(self.log,allowed_hosts=('playstation.com',),underlying=BinarySafeSession(requests.Session()),min_interval_seconds=5)
        self.reports={};self.extra_documents=[];self.capture_dir=self.log.parent/'playstation_captures';self.capture_dir.mkdir(parents=True,exist_ok=True)

    def emit(self,**e):
        if self.trace_callback:self.trace_callback(dict(timestamp=utc_now(),event='playstation_discovery',**e))

    def fetch(self,url,query,provider,kind,deadline):
        if self.clock()>=deadline:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason='budget_exhausted',identity_relation='unproven');return None
        try:
            cache_key=(str(self.log),url)
            cached=_STRUCTURE_CACHE.get(cache_key) if kind in ('sitemap','support') else None
            z=cached[1] if cached and self.clock()-cached[0]<600 else self.session.get(url,timeout=min(10,deadline-self.clock()))
            if z.status_code!=200 or z.truncated or not official(z.url):raise ValueError(f'HTTP {z.status_code}; truncated={z.truncated}; returned={z.url}')
            self.emit(query=query,provider=provider,url=z.url,region=urlsplit(z.url).path.split('/')[1],source_type=kind,accepted=True,reason='Fetched; identity evaluated separately',identity_relation='unproven')
            name=hashlib.sha256(z.url.encode()).hexdigest()[:20]
            if urlsplit(z.url).path.lower().endswith('.pdf'):(self.capture_dir/(name+'.pdf')).write_bytes(document_bytes(z))
            else:(self.capture_dir/(name+'.html')).write_text(z.text,encoding='utf-8')
            if kind in ('sitemap','support'):_STRUCTURE_CACHE[cache_key]=(self.clock(),z)
            return z
        except Exception as e:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason=str(e),identity_relation='unproven');return None

    def find_source(self,article,*,name='',category='',deadline):
        article=article.strip().upper();expected=model_key(name);self.extra_documents=[]
        ev={'identity':{'model':'unproven','configuration':'unproven','hardware':'unproven'},'query_variants':[article,clean_text(name),f'{article} PlayStation'],'raw_specs':[],'configuration_candidates':[],'photo_candidates':[],'manuals':[],'manual_status':'Не проверена','configuration_fields':{},'exact_photo_assets':[],'support_url':'','exact_official_pdp':''}
        doc=SourceDocument('playstation_model','PlayStation','',error='No verified official product identity')
        hardware_links=[];pdp_links=[]
        def inspect_sitemap():
            z=self.fetch('https://www.playstation.com/sitemap_index.xml',article,'official_sitemap','sitemap',deadline)
            if z:
                ev['sitemap_children']=re.findall(r'<loc>([^<]+)</loc>',z.text)
                self.emit(query=article,provider='official_sitemap',url=z.url,region='',source_type='sitemap',accepted=False,reason='Index discovered; gpdc sitemap disallowed by robots, no inferred exact SKU URL',identity_relation='unproven')
        # Regional model route is a discovery hint, never an exact SKU guess.
        if expected in ROUTES:
            for region in ('ru-ru','en-gb'):
                if region=='en-gb':inspect_sitemap()
                u=f'https://www.playstation.com/{region}/{ROUTES[expected]}'
                z=self.fetch(u,article,'regional_exact' if region=='ru-ru' else 'other_official_regions','product',deadline)
                if not z:continue
                candidate,parsed=parse_page(z.text,z.url,article,expected)
                # RU extraction currently has no semantic adapter; preserve source only.
                if not candidate.error:
                    doc=candidate
                    for key in ('identity','raw_specs','configuration_candidates','photo_candidates','configuration_fields','exact_photo_assets'):ev[key]=parsed[key]
                    if parsed.get('hardware_model'):ev['hardware_model']=parsed['hardware_model']
                    ev['structured_identity']=parsed.get('structured_identity',[])
                self.emit(query=article,provider='regional_exact' if region=='ru-ru' else 'other_official_regions',url=z.url,region=region,source_type='product',accepted=not candidate.error,reason=candidate.evidence or candidate.error,identity_relation='model_confirmed' if not candidate.error else 'mismatch')
                soup=BeautifulSoup(z.text,'html.parser')
                pdp_links.extend(urljoin(z.url,a['href']) for a in soup.select('a[href]') if urlsplit(urljoin(z.url,a['href'])).hostname=='direct.playstation.com' and '/buy-' in a['href'])
                if region=='en-gb':break
        # A declared sitemap can be unavailable/disallowed; diagnostics preserve it.
        if expected not in ROUTES:inspect_sitemap()
        for region in ('ru-ru','en-gb','en-us'):
            u=f'https://www.playstation.com/{region}/support/hardware/manuals/'
            z=self.fetch(u,article,'support','support',deadline)
            if not z:continue
            for a in BeautifulSoup(z.text,'html.parser').select('a[href]'):
                label=clean_text(a.get_text(' ',strip=True));target=urljoin(z.url,a['href'])
                if article not in codes(label) or not official(target) or not target.lower().endswith('.pdf'):continue
                family=hardware_family(target)
                if not family or (expected=='ps5' and not family.startswith('ps5_')) or (expected!='ps5' and family!=expected):continue
                ev['identity']['hardware']='official_hardware_model_code';ev['hardware_model']=article;ev['hardware_family']=family;ev['support_url']=z.url
                hardware_links.append((label,target,z.url,region))
            if hardware_links:break
        if hardware_links:
            self.emit(query=article,provider='support',url=ev['support_url'],region=hardware_links[0][3],source_type='support',accepted=True,reason='Exact CFI in official linked guide label; retail SKU remains separate',identity_relation='official_hardware_model_code')
        ev['manuals']=[dict(title=l,url=u,type=document_type(l),relation='official_hardware_model_code',verified=False,language='Не проверена',source_url=s) for l,u,s,region in hardware_links]
        if hardware_links:
            label,u,support,region=next((x for x in hardware_links if document_type(x[0])=='Safety Guide'),hardware_links[0])
            # Technical facts are extracted only from an English single-hardware table.
            if region!='en-gb':
                u_gb='https://www.playstation.com/en-gb/support/hardware/manuals/'
                z=self.fetch(u_gb,article,'support','support',deadline)
                if z:
                    a=next((a for a in BeautifulSoup(z.text,'html.parser').select('a[href]') if article in codes(clean_text(a.get_text())) and document_type(a.get_text())==document_type(label) and hardware_family(urljoin(z.url,a['href']))==ev['hardware_family']),None)
                    if a:label,u,support=clean_text(a.get_text()),urljoin(z.url,a['href']),z.url
            z=self.fetch(u,article,'official_manual','manual',deadline)
            if z:
                try:
                    data=document_bytes(z)
                    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]:raise ValueError('Incomplete PDF')
                    reader=PdfReader(BytesIO(data));texts=[p.extract_text() or '' for p in reader.pages];text='\n'.join(texts)
                    ev['pdf_audit']={'url':u,'sha256':hashlib.sha256(data).hexdigest(),'pages':len(texts),'type':document_type(label),'text_model_codes':sorted(codes(text))}
                    # Cover must identify the hardware or explicitly shared console group.
                    cover=codes(texts[0]);base=re.sub(r'[AB]$','',article) if re.fullmatch(r'CFI-\d{4}[AB]',article) else article
                    if article in cover or (base in cover and len(codes(label))>1):
                        hw,raw,rejected=parse_hardware_specs(text,u,article);self.extra_documents.append(hw);ev['raw_specs'].extend(raw);ev['configuration_candidates'].extend(rejected)
                        ev['identity']['model']='model_confirmed';ev['revision_scope']=article
                        ev['hardware_spec_source']=u
                    else:ev['pdf_audit']['rejected']='Cover model mismatch; no technical facts admitted'
                except Exception as e:ev['pdf_error']=str(e)
        user_guide=next((d for d in ev['manuals'] if d['type']=='User Guide' and '/ru/' in d['url']),None)
        if user_guide:
            z=self.fetch(user_guide['url'],article,'official_manual','manual',deadline)
            if z:
                try:
                    data=document_bytes(z)
                    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]:raise ValueError('Incomplete PDF')
                    pages=[p.extract_text() or '' for p in PdfReader(BytesIO(data)).pages];text='\n'.join(pages)
                    verified=article in codes(pages[0]) and bool(re.search(r'руководств\w*\s+по\s+эксплуатац|инструкц\w*\s+по',text,re.I)) and len(re.findall(r'[А-Яа-яЁё]',text))>2500
                    user_guide.update(verified=verified,language='Русский' if verified else 'Не проверена',sha256=hashlib.sha256(data).hexdigest())
                    if verified:ev['manual_status']='Проверена'
                except Exception as e:user_guide['error']=str(e)
        # Candidate order PDPs must return the requested commercial code themselves.
        if not article.startswith('CFI-'):
            matching=[]
            for u in dict.fromkeys(pdp_links):
                # A name narrows cost, never confers identity.
                if expected=='dualsense' and 'midnight black' in name.casefold() and 'midnight-black' not in u:continue
                if 'bundle' in name.casefold() and 'bundle' not in u:continue
                matching.append(u)
            for u in matching[:4]:
                z=self.fetch(u,article,'official_link','product',deadline)
                if not z:continue
                candidate,parsed=parse_page(z.text,z.url,article,expected)
                accepted=candidate.match_level=='full_sku' and not candidate.error
                self.emit(query=article,provider='official_link',url=z.url,region=urlsplit(z.url).path.split('/')[1],source_type='product',accepted=accepted,reason=candidate.evidence or candidate.error,identity_relation='exact_order_sku' if accepted else 'other_order_or_family')
                if accepted:
                    if doc.url and not doc.error:self.extra_documents.append(doc)
                    doc=candidate
                    hardware=ev['identity'].get('hardware','unproven')
                    for key in ('identity','configuration_fields','exact_photo_assets'):ev[key]=parsed[key]
                    ev['identity']['hardware']=hardware
                    for key in ('raw_specs','configuration_candidates','photo_candidates'):ev[key].extend(parsed[key])
                    ev['exact_official_pdp']=z.url;break
        if ev['identity']['hardware']!='unproven' and doc.error:
            doc=SourceDocument('playstation_model','PlayStation hardware identity',ev['support_url'],found_model=article,match_level='model_confirmed',evidence='Official CFI hardware identity; no exact retail configuration or product description')
        # Manual content/language audit is intentionally separate from Safety/QSG.
        self.emit(query=article,provider='external_search',url='',region='',source_type='search',accepted=False,reason='No external search provider configured; no search snippet accepted as evidence',identity_relation='unproven')
        ev['model_key']=expected;ev['configuration_complete']=bool(ev['exact_official_pdp'] and ev['configuration_fields'].get('color') and (expected!='ps5' or all(ev['configuration_fields'].get(k) for k in ('storage','disc','bundle_contents'))))
        self.reports[article]=ev
        return doc
