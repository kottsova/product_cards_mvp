"""Own-PDP specs, CFI and galleries, separate from recommendation/selector content."""
import hashlib,json,re
from urllib.parse import urljoin,urlsplit,parse_qs
from .adapters.common import RawAttribute, PhotoCandidate, clean_text
from .playstation_identity import official, codes,COLORS

def asset_colors(value):
    compact=re.sub(r'[^a-z]','',value.casefold())
    return {name for name in COLORS if name.replace(' ','') in compact}

def own_identity(soup, url):
    sku='';published=set();products=[]
    for s in soup.select('script'):
        m=re.search(r'digitalData\.product\[0\]\.productInfo\s*=\s*\{(.*?)\};',s.get_text(),re.S)
        if m and urlsplit(url).hostname=='direct.playstation.com':
            matches=re.findall(r'\bsku\s*:\s*"([^"]+)"',m[1])
            if len(set(matches))==1:sku=matches[0]
        if s.get('type')=='application/ld+json':
            try:
                data=json.loads(s.get_text())
                if isinstance(data,dict) and data.get('@type')=='Product':
                    products.append(data);published.update(codes(str(data.get('mpn',''))))
            except (ValueError,TypeError):pass
    # Own legal/model-number paragraphs; no generic CFI mentions or image filenames.
    for p in soup.select('p'):
        t=clean_text(p.get_text(' ',strip=True))
        m=re.match(r'Model Number\s*[-:]\s*(CFI-[A-Z0-9-]+)',t,re.I)
        if m:published.update(codes(m[1].rstrip('.')))
    for table in soup.select('table'):
        for row in table.select('tr'):
            cells=[clean_text(c.get_text(' ',strip=True)) for c in row.select('td,th')]
            if len(cells)==2 and cells[0]=='PDP_MODEL_NUMBER':published.update(codes(cells[1]))
    return sku,published,products

def augment_page(doc, ev, soup, url, article, expected):
    sku,published,products=own_identity(soup,url)
    ev['returned_sku']=sku;ev['published_cfi']=sorted(published)
    exact_hw=article in published and article.startswith('CFI-')
    exact_retail=bool(sku and sku.upper()==article.upper())
    ev['sku_cfi_relation']=dict(retail_sku=sku,published_cfi=sorted(published),relation='explicit_own_pdp' if sku and published else 'cfi_not_published',source_url=url)
    families=sorted(set(re.findall(r'CFI-\d{4}(?=\s+model group)',soup.get_text(' ',strip=True),re.I)))
    if families:
        ev['sku_cfi_relation']['published_family']=families
        if not published:ev['sku_cfi_relation']['relation']='family_only_not_exact_cfi'
    if exact_hw:
        ev['identity']['hardware']='official_hardware_model_code';ev['hardware_model']=article
    technical=[]
    # Product schema description is product-specific; the family footer/help text isn't.
    prose=' '.join(str(x.get('description','')) for x in products)
    for h in soup.select('h2,h3,h4'):
        label=clean_text(h.get_text(' ',strip=True)).casefold()
        if label in {'features','built-in microphone and headset jack','planar magnetic drivers','playstation link technology','bluetooth','ai-enhanced noise rejection','long battery life with quick charging','8-inch lcd screen','haptic feedback','adaptive triggers'}:
            for n in h.next_elements:
                if getattr(n,'name',None) in ('h1','h2','h3','h4'):break
                if getattr(n,'name',None) in ('p','li'):prose+=' '+clean_text(n.get_text(' ',strip=True))
    for label,pattern,value in (
        ('Haptic Feedback',r'\bhaptic feedback\b','Да'),('Adaptive Triggers',r'\badaptive triggers\b','Да'),
        ('PlayStation Link',r'\bPlayStation Link\b','Да'),('Bluetooth',r'\bBluetooth\b','Да'),
        ('Микрофон',r'\b(?:built-in|retractable) microphone\b','Встроенный'),
        ('Динамики',r'\bbuilt-in (?:stereo )?speaker','Встроенные'),
        ('Тип излучателей',r'\bplanar magnetic drivers\b','Планарные магнитные'),
        ('Шумоподавление микрофона',r'\bAI-enhanced noise rejection\b','С использованием ИИ')):
        if expected in {'ps5','pro'} and label in {'Микрофон','Динамики','Тип излучателей','Шумоподавление микрофона','Bluetooth','PlayStation Link'}:continue
        hit=re.search(pattern,prose,re.I)
        if hit and not re.search(r'not supported|does not support|not available|unsupported',prose[max(0,hit.start()-35):hit.end()+45],re.I):
            if expected in {'ps5','pro'} and label in {'Haptic Feedback','Adaptive Triggers'}:label+=' (контроллер DualSense)'
            technical.append((label,value,prose[max(0,hit.start()-60):hit.end()+100]))
    battery=re.search(r'(?:up to\s+)(\d+)\s+hours?(?:\s+of)?\s+battery',prose,re.I)
    if battery and expected in {'dualsense','portal','elite'}:technical.append(('Время работы аккумулятора','До '+battery[1]+' ч',battery[0]))
    if expected in {'ps5','pro'}:
        for label,pattern,value in (
            ('Трассировка лучей',r'\bray tracing\b','Да'),('Поддержка 4K',r'\b4K (?:TV|gaming|games)\b','Да'),
            ('Максимальная частота кадров',r'up to\s*120\s*fps','До 120 fps'),('Поддержка HDR',r'\bHDR technology\b','Да'),
            ('Tempest 3D AudioTech',r'\bTempest 3D AudioTech\b','Да')):
            m=re.search(pattern,prose,re.I)
            if m:technical.append((label,value,prose[max(0,m.start()-60):m.end()+120]))
    for label,value,raw in technical:
        ev['raw_specs'].append(dict(section='Own product features',raw_label=label,value=raw,scope='model'))
        if not any(a.name==label and a.value==value for a in doc.attributes):doc.attributes.append(RawAttribute(label,value,section='Возможности модели',value_cell=True))
    if exact_hw:
        ev['hardware_attributes']=[]
        for table in soup.select('table'):
            rows=[[clean_text(c.get_text(' ',strip=True)) for c in r.select('td,th')] for r in table.select('tr')]
            if not any(r==['PDP_MODEL_NUMBER',article] for r in rows):continue
            for row in rows:
                if len(row)!=2:continue
                label,value=row;ev['raw_specs'].append(dict(section='Own CFI product table',raw_label=label,value=value,hardware_code=article))
                if label=='PDP_WEIGHT':ev['hardware_attributes'].append(('Вес товара',value))
                if label=='PDP_DIMENSIONS':
                    d=re.search(r'H\s*([\d.]+)\s*x\s*W\s*([\d.]+)\s*x\s*D\s*([\d.]+)\s*mm',value,re.I)
                    if d:
                        for n,v in zip(('Высота товара, мм','Ширина товара, мм','Глубина товара, мм'),d.groups()):ev['hardware_attributes'].append((n,v+' мм'))
    # Published own CFI is different from input: never bind revision-only data.
    ev['hardware_mismatch']=bool(article.startswith('CFI-') and published and article not in published)
    assets=[]
    ambiguous_hardware_colors=False
    for im in soup.select('image-cluster img'):
        u=im.get('data-src') or im.get('src') or ''
        if official(u) and 'fallback' not in u.casefold():assets.append((u,im.get('alt',''),'retail'))
    for p in products:
        if exact_hw and p.get('mpn')==article:
            images=p.get('image',[]) if isinstance(p.get('image'),list) else [p.get('image')]
            all_colors=set().union(*(asset_colors(u) for u in images if isinstance(u,str)))
            declared_colors=asset_colors(str(p.get('color','')))
            ambiguous_hardware_colors=ambiguous_hardware_colors or len(all_colors)>1 and len(declared_colors)!=1
            if len(declared_colors)==1:ev['hardware_photo_color']=next(iter(declared_colors))
            for u in images:
                if u and official(u):assets.append((u,'Own Product image for '+article,'hardware'))
    # Own bundle packaging is allowed for its exact retail SKU; gameplay isn't a product photo.
    for u,alt,scope in dict.fromkeys(assets):
        wanted=next((name for name,label in COLORS.items() if ev.get('configuration_fields',{}).get('color')==label),None) if scope=='retail' else ev.get('hardware_photo_color')
        observed_colors=asset_colors(u+' '+alt)
        reason=''
        if wanted and observed_colors and wanted not in observed_colors:reason='Other explicit product color inside own gallery'
        if scope=='hardware' and ambiguous_hardware_colors:reason='Mixed color Product image list; exact variant not proved'
        own_bundle=bool(ev.get('configuration_fields',{}).get('bundle'))
        if own_bundle and re.search(r'bundle|packag|\bbox\b',u+' '+alt,re.I):
            tokens={x for x in re.findall(r'[a-z]+',ev['configuration_fields']['bundle'].casefold()) if len(x)>3 and x not in {'playstation','digital','edition','console','bundle'}}
            observed=re.sub(r'[^a-z]','', (u+' '+alt).casefold())
            if tokens and not any(t in observed for t in tokens):reason='Other named bundle packaging inside own gallery'
        if reason:
            previous=next((x for x in ev['photo_candidates'] if x['url']==u),None)
            if previous:previous['reason']=reason
            else:ev['photo_candidates'].append(dict(url=u,reason=reason))
            continue
        bad=re.search(r'gameplay|background|lifestyle|logo|badge|fallback|usb-bundle|cable-and',u+' '+alt,re.I)
        packaging=bool(re.search(r'packag|\bbox\b|contents',u+' '+alt,re.I))
        if bad or packaging and not (exact_retail and own_bundle):continue
        if not exact_retail and not (scope=='hardware' and exact_hw):continue
        if 'bundle' in (u+' '+alt).casefold() and not own_bundle:continue
        asset=hashlib.sha256(u.encode()).hexdigest()
        if asset not in ev['exact_photo_assets']:
            doc.photos.append(u);doc.photo_candidates.append(PhotoCandidate(u,asset));ev['exact_photo_assets'].append(asset)
        ev.setdefault('photo_scopes',{})[asset]=dict(scope=scope,identifier=sku if scope=='retail' else article,source_url=url,reason='Own gallery + exact order SKU' if scope=='retail' else 'Exact Product mpn + own image list')
    selected=set(doc.photos)
    ev['photo_candidates']=[x for x in ev['photo_candidates'] if x['url'] not in selected]
    return doc,ev
