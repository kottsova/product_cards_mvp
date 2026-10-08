"""Small public-page adapter using shared HTTP, source and evidence contracts.

Routes identify product families, never individual SKUs. Returned page identity
is always checked; unsupported revisions and family options remain candidates.
"""
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from .common import SourceDocument,RawAttribute,PhotoCandidate,clean_text,utc_now
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession,document_bytes
from ..playstation_identity import official,model_key,codes,document_type,hardware_family,COLORS
from ..playstation_page import augment_page,own_identity

ROUTES={'ps5':'ps5/','pro':'ps5/ps5-pro/','dualsense':'accessories/dualsense-wireless-controller/','portal':'accessories/playstation-portal-remote-player/','elite':'accessories/pulse-elite-wireless-headset/'}
_STRUCTURE_CACHE={}

def section_values(soup):
    out=[]
    for h in soup.select('h2,h3,h4'):
        label=clean_text(h.get_text(' ',strip=True))
        if not label: continue
        if label.casefold() in {"what's in the box",'in the box'} and 'section-component' in h.parent.get('class',[]):
            values=list(dict.fromkeys(clean_text(n.get_text(' ',strip=True)) for n in h.parent.select('li') if not n.find('li')))
            if values:out.append((label,values))
            continue
        values=[]
        for n in h.next_elements:
            if getattr(n,'name',None) in ('h1','h2','h3','h4'): break
            if getattr(n,'name',None) in ('p','li') and not n.find('li'):
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
    if any(str(x.get('mpn') or '').upper()==article.upper() and article.upper().startswith('CFI-') for x in ev.get('structured_identity',[])):
        ev['identity']['hardware']='official_hardware_model_code'
        ev['hardware_model']=article.upper()
    for label,values in section_values(b):
        l=re.sub(r'\s+\d+$','',label.casefold())
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
                    if expected in {'ps5','pro'} and canonical in {'Haptic Feedback','Adaptive Triggers'}:canonical+=' (контроллер DualSense)'
                else:feature='Wi-Fi 7 (IEEE 802.11be)' if canonical=='Стандарт Wi-Fi' else value
                doc.attributes.append(RawAttribute(canonical,feature,section='Возможности модели',value_cell=True))
            else: ev['configuration_candidates'].append({**raw,'reason':'Configuration option or marketing; requires scoped canonical extraction'})
    if exact:
        capacities=set(re.findall(r'\b\d+\s*(?:GB|TB)\b',title,re.I))
        if len(capacities)==1:ev['configuration_fields']['storage']=next(iter(capacities))
        for color,label in COLORS.items():
            if color in title.casefold():ev['configuration_fields']['color']=label
        # A checked own-SKU selector, never another color's option, can label a default variant.
        for radio in b.select('input[type="radio"][checked]'):
            if not radio.get('id','').endswith(article):continue
            label=b.find('label',attrs={'for':radio.get('id')})
            text=clean_text(label.get_text(' ',strip=True)).casefold() if label else ''
            if not text and label and label.parent: text=clean_text(label.parent.get_text(' ',strip=True)).casefold()
            selector=next((p for p in radio.parents if 'productHero-option-selector' in p.get('class',[])),None)
            if selector:
                m=re.search(r'Colour:\s*(White|Midnight Black|Cosmic Red|Cobalt Blue)\b',selector.get_text(' ',strip=True),re.I)
                if m:text=m[1].casefold()
            if text in COLORS:ev['configuration_fields']['color']=COLORS[text]
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
    return augment_page(doc,ev,b,url,article,expected)

from ..playstation_specs import parse_hardware_specs

class PlayStationAdapter:
    def __init__(self,*,fetch_log_path=None,trace_callback=None,clock=time.monotonic,session=None,search_factory=None):
        self.clock=clock;self.log=Path(fetch_log_path or 'data/playstation_fetch.json');self.trace_callback=trace_callback
        self.session=session or PolicyAwareSession(self.log,allowed_hosts=('playstation.com',),underlying=BinarySafeSession(requests.Session()),min_interval_seconds=5)
        self.reports={};self.extra_documents=[];self.search_factory=search_factory;self.capture_dir=self.log.parent/'playstation_captures';self.capture_dir.mkdir(parents=True,exist_ok=True)

    def emit(self,**e):
        if self.trace_callback:self.trace_callback({'timestamp':utc_now(),'event':'playstation_discovery',**e})

    def fetch(self,url,query,provider,kind,deadline):
        if self.clock()>=deadline:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason='budget_exhausted',identity_relation='unproven');return None
        try:
            cache_key=(str(self.log),url)
            cached=_STRUCTURE_CACHE.get(cache_key) if kind in ('sitemap','support','catalog','product') else None
            z=cached[1] if cached and self.clock()-cached[0]<600 else self.session.get(url,timeout=min(10,deadline-self.clock()))
            if z.status_code!=200 or z.truncated or not official(z.url):raise ValueError(f'HTTP {z.status_code}; truncated={z.truncated}; returned={z.url}')
            self.emit(query=query,provider=provider,url=z.url,region=urlsplit(z.url).path.split('/')[1],source_type=kind,accepted=True,reason='Fetched; identity evaluated separately',identity_relation='unproven')
            name=hashlib.sha256(z.url.encode()).hexdigest()[:20]
            if urlsplit(z.url).path.lower().endswith('.pdf'):(self.capture_dir/(name+'.pdf')).write_bytes(document_bytes(z))
            else:(self.capture_dir/(name+'.html')).write_text(z.text,encoding='utf-8')
            if kind in ('sitemap','support','catalog','product'):_STRUCTURE_CACHE[cache_key]=(self.clock(),z)
            return z
        except Exception as e:
            self.emit(query=query,provider=provider,url=url,region='',source_type=kind,accepted=False,reason=str(e),identity_relation='unproven');return None

    def find_source(self,article,*,name='',category='',deadline):
        from ..playstation_lookup import find_source
        return find_source(self,article,name=name,category=category,deadline=deadline)
