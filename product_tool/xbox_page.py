"""Conservative extraction from own public Xbox and Store product sections."""
import hashlib,json,re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument,RawAttribute,PhotoCandidate,clean_text
from .xbox_identity import official,official_asset,family,identifier

LABELS={'cpu':'Процессор','gpu':'Графический процессор','memory':'Оперативная память','memory bandwidth':'Пропускная способность памяти','i/o throughput':'Скорость ввода-вывода','gaming resolution':'Игровое разрешение','high dynamic range':'HDR','performance target':'Частота кадров','hdmi features':'Возможности HDMI','hdmi':'HDMI','usb':'USB-порты','wireless':'Стандарт Wi-Fi','ethernet':'Ethernet','accessories radio':'Xbox Wireless','connectivity':'Подключение','compatible with':'Совместимость','system requirements':'Совместимость','battery':'Аккумулятор и время работы','audio':'Аудиоразъём','haptic feedback':'Тактильная отдача','virtual surround sound':'Spatial Sound','speakers':'Динамики','microphones':'Микрофон','impedance':'Импеданс','frequency response':'Частотный диапазон','controls':'Управление','buttons':'Кнопки'}
LABELS.update({'usable storage':'Доступное пользователю место','quick resume':'Quick Resume','smart delivery':'Smart Delivery','xbox velocity architecture':'Xbox Velocity Architecture','power':'Питание','usb-c':'USB-C'})
SECTIONS={'PROCESSOR':'Процессор и графика','MEMORY & STORAGE':'Память и накопители','VIDEO CAPABILITIES':'Видео','SOUND CAPABILITIES':'Звук','PORTS & CONNECTIVITY':'Подключение','DESIGN':'Габариты и вес'}

def assignment(text,name):
    m=re.search(re.escape(name)+r'\s*=\s*',text)
    if not m:return None
    try:return json.JSONDecoder().raw_decode(text[m.end():])[0]
    except ValueError:return None

def raw_rows(b):
    rows=[]
    # Console sections have a published, bounded technical drawer.
    for panel in b.select('.specs-drawer-panel'):
        for row in panel.select('div.row'):
            h=row.find('h3');section=clean_text(h.text) if h else 'TECH SPECS'
            for p in row.select('p.c-subheading-2'):
                strong=p.find('strong')
                if strong:
                    label=clean_text(strong.text).strip('.:');text=clean_text(p.get_text(' ',strip=True));value=text[len(clean_text(strong.text)):].strip()
                elif section=='SOUND CAPABILITIES':label='Audio formats';value=clean_text(p.text)
                else:continue
                if value:rows.append(dict(section=section,raw_label=label,value=value))
    # Accessory specs and Microsoft Store use own two-column tables.
    for table in b.select('table'):
        for tr in table.select('tr'):
            cells=tr.find_all(['th','td'],recursive=False)
            if len(cells)!=2:continue
            l=clean_text(cells[0].get_text(' ',strip=True));v=clean_text(cells[1].get_text(' ',strip=True))
            if not l or not v:continue
            # Store console cells contain several explicit label:value paragraphs.
            pairs=[]
            if cells[1].find('br') and l.upper() in SECTIONS:
                for line in cells[1].get_text('\n',strip=True).splitlines():
                    label,sep,value=clean_text(line).partition(':')
                    if sep and value.strip():pairs.append(dict(section=l,raw_label=label.strip(),value=value.strip()))
                    elif l.lower()=='sound capabilities':pairs.append(dict(section=l,raw_label='Audio formats',value=clean_text(line)))
            for p in cells[1].select('p'):
                s=p.find('strong')
                if s and ':' in s.text:
                    label=clean_text(s.text).strip('.:');value=clean_text(p.get_text(' ',strip=True))[len(clean_text(s.text)):].strip()
                    if value and not any(x['raw_label']==label for x in pairs):pairs.append(dict(section=l,raw_label=label,value=value))
            rows.extend(pairs or [dict(section='TECH SPECS',raw_label=l,value=v)])
    return list({(r['section'],r['raw_label'],r['value']):r for r in rows}.values())

def color_name(text):
    return next((c for c in ('Arctic Camo','Robot White','Carbon Black','Galaxy Black','Shock Blue','Pulse Red','Electric Volt') if c.casefold() in text.casefold()),'')

def parse_page(html,url,article,expected,region):
    b=BeautifulSoup(html,'html.parser');title=clean_text(b.h1.text) if b.h1 else ''
    d=SourceDocument('xbox_model','Xbox / Microsoft',url,found_model=title,html=html)
    ev=dict(page_default_title=title,raw_specs=[],configuration_candidates=[],photo_candidates=[],exact_photo_assets=[],photo_scopes={},configuration_fields={},identity={'model':'unproven','configuration':'unproven','hardware':'unproven'},identifiers={},configuration_complete=False)
    if not official(url) or not expected or family(title)!=expected or 'support' in (urlsplit(url).hostname or '') or '/service-guides/' in url:
        d.error='Own product family missing/mismatched or support content';return d,ev
    ev['identity']['model']='model_confirmed';d.match_level='model_confirmed'
    d.found_model={'series_x':'Xbox Series X','series_s':'Xbox Series S','controller':'Xbox Wireless Controller','elite':'Xbox Elite Wireless Controller Series 2','headset':'Xbox Wireless Headset'}[expected]
    req=identifier(article);own=None;structured=[]
    for s in b.select('script'):
        data=assignment(s.get_text(),'window.__BuyBox__')
        if isinstance(data,dict):own=data.get('product')
        if s.get('type')=='application/ld+json':
            try:
                x=json.loads(s.text)
                if isinstance(x,dict) and x.get('@type')=='Product':structured.append(x)
            except ValueError:pass
    path=urlsplit(url).path;market=path.split('/')[1] if len(path.split('/'))>1 else ''
    own_pid=str(own.get('productId','')).upper() if own else ''
    pid_proved=bool(req['product_id'] and market.lower()==region.lower() and path.rstrip('/').split('/')[-1].upper()==req['product_id'] and (own_pid==req['product_id'] or any(str(x.get('productID','')).upper()==req['product_id'] and family(x.get('name',''))==expected for x in structured)))
    sku=None
    if pid_proved and req['sku_id'] and own:
        sku=own.get('skuInfo',{}).get(req['sku_id'])
        if not sku or str(sku.get('skuId','')).upper()!=req['sku_id'] or family(sku.get('title',''))!=expected:sku=None
    exact=pid_proved and (not req['sku_id'] or sku is not None)
    # A multi-SKU Product ID alone is not its displayed default configuration.
    if exact and not req['sku_id'] and own and len(own.get('skuInfo',{}))>1:exact=False
    if exact:
        d.source_key='xbox_configuration';d.match_level='full_sku' if sku else 'configuration_confirmed'
        ev['identity']['configuration']='exact_store_sku' if sku else 'exact_store_product'
        ev['identifiers']={'store_product_id':req['product_id'],'store_sku_id':req['sku_id'] or None,'manufacturer_part_number':None,'hardware_model_number':None,'storefront':market}
        label=clean_text(sku.get('title','')) if sku else title
        # The page H1 describes its default row, not necessarily the requested SKU.
        d.found_model=label
        ev['configuration_fields']['storefront']=market
        c=color_name(label)
        if c:ev['configuration_fields']['color']=c
        caps=set(re.findall(r'\b\d+\s*(?:TB|GB)\b',label,re.I))
        if len(caps)==1:ev['configuration_fields']['storage']=next(iter(caps))
        if 'bundle' in label.lower():ev['configuration_fields']['bundle']=label
        if 'digital edition' in label.lower():ev['configuration_fields']['disc']='Digital'
    ev['raw_specs']=raw_rows(b)
    def add(label,value,section):
        if not any(x.name==label and x.value==value for x in d.attributes):d.attributes.append(RawAttribute(label,value,section=section,value_cell=True))
    for r in ev['raw_specs']:
        l=r['raw_label'].lower().strip('.:');value=r['value'];mapped=LABELS.get(l);reason='Technical field lacks safe canonical mapping'
        section=SECTIONS.get(r['section'].upper(),'Характеристики модели')
        if req['hardware_model'] and not exact and l in {'cpu','gpu','battery','wireless'}:
            ev['configuration_candidates'].append({**r,'reason':'Exact hardware revision not linked; frequency/runtime/radio revision values withheld'})
            architecture=re.search(r'\b(?:Zen|RDNA)\s+\d+\b',value,re.I) if l in {'cpu','gpu'} else None
            if architecture:add('Архитектура процессора' if l=='cpu' else 'Архитектура графического процессора',architecture[0],'Процессор и графика')
            continue
        if l in {'internal storage','storage'}:
            mapped=None;reason='Storage options do not identify a requested retail configuration'
            if exact and not re.search(r'xbox series [xs].*:',value,re.I) and len(set(re.findall(r'\b\d+\s*(?:TB|GB)\b',value,re.I)))==1:
                ev['configuration_fields']['storage']=value;add('Встроенный накопитель',value,'Конфигурация / накопитель');continue
        elif l in {'expandable storage','expansion storage'}:
            sentences=re.split(r'(?<=\.)\s+(?=Support)',value)
            for sentence in sentences:
                label='Поддержка внешних USB-накопителей' if 'usb' in sentence.lower() else 'Поддержка карты расширения'
                add(label,sentence,'Память и накопители')
            continue
        elif l=='audio formats':
            add('Аудиоформаты','; '.join(x['value'] for x in ev['raw_specs'] if x['raw_label']=='Audio formats'),'Звук');continue
        elif l in {'optical drive','disc drive'}:
            mapped=None;reason='Drive options are configuration specific'
            if exact and ':' not in value:add('Оптический привод',value,'Конфигурация');ev['configuration_fields']['disc']=value;continue
        elif l in {'weight','dimensions','size'}:
            mapped=None;reason='Physical value requires own variant/revision and explicit axis/assembly binding'
            # Single own Store SKU weight is scoped to that SKU, never a hardware-model request.
            if exact and l=='weight' and re.fullmatch(r'\d+(?:\.\d+)?\s*(?:g|kg)',value):
                add('Вес товара',value,'Габариты и вес');continue
        elif l in {'width','height','depth'}:
            mapped=None;reason='Axis requires own exact configuration'
            if exact and re.fullmatch(r'\d+(?:\.\d+)?\s*(?:mm|cm)',value):
                add({'width':'Ширина товара','height':'Высота товара','depth':'Глубина товара'}[l],value,'Габариты и вес');continue
        elif l in {'what’s in the box',"what's in the box",'in the box'}:
            mapped=None;reason='Kit contents require own exact configuration; cannot borrow model kit'
            if exact:ev['configuration_fields']['bundle_contents']=value;add('Комплектация',value,'Комплект');continue
        if mapped:
            # Prose procedures are retained as candidates, not descriptions/specs.
            if re.search(r'\b(?:manually|drivers available|swap thumbstick|firmware|troubleshoot|reset|warranty|adjust equalizer)\b',value,re.I):reason='Support/procedure content withheld'
            else:
                add(mapped,value,section)
                if l=='connectivity':
                    for token in ('Bluetooth','Xbox Wireless','USB-C'):
                        if token.casefold() in value.casefold():add(token,'Да','Подключение')
                continue
        ev['configuration_candidates'].append({**r,'reason':reason})
    if exact:
        if ev['configuration_fields'].get('bundle'):
            claims=[]
            desc=str(own.get('description','')) if own else ''
            if re.search(r'\bIncludes\b',desc,re.I):claims.append(desc)
            # Own named feature cards, excluding related-product/FAQ links.
            for h in b.select('h2.component-heading,h3.component-heading'):
                claim=clean_text(h.get_text(' ',strip=True))
                if re.match(r'^Includes\b',claim,re.I) and not h.select('a[href]'):claims.append(claim)
            if claims:
                value='; '.join(dict.fromkeys(claims));ev['configuration_fields']['bundle_contents']=value;add('Комплектация',value,'Комплект')
                ev['raw_specs'].append(dict(section='Own bundle content',raw_label='Includes',value=value))
                game=next((x for x in claims if re.search(r'^Includes .*\band bonus in-game items',x,re.I)),None)
                if game:ev['configuration_fields']['included_game']=game
                gp=re.search(r'\b\d+\s+months?\s+of\s+Game Pass\s+\w+',desc,re.I)
                if gp:ev['configuration_fields']['game_pass']=gp[0]
        for k,label in (('color','Цвет'),('storage','Встроенный накопитель'),('bundle','Название комплекта')):
            if k in ev['configuration_fields'] and not any(x.name==label for x in d.attributes):add(label,ev['configuration_fields'][k],'Конфигурация')
    # Even a SKU's gallery may contain every OTHER color. Check each asset.
    row=sku or (own if exact else None)
    images=row.get('galleryImages',[]) if row else []
    if row and row.get('displayImage'):images=[row['displayImage'],*images]
    seen=set()
    for im in images:
        u=im.get('uri','');alt=clean_text(im.get('alt',''));color=ev['configuration_fields'].get('color','')
        if not official_asset(u) or u in seen:continue
        seen.add(u);wrong=color and color.casefold() not in alt.casefold()
        # Carbon Black alt commonly says "black"; explicit own display row + black asset is sufficient.
        if color=='Carbon Black' and re.search(r'\bblack\b',alt,re.I) and not color_name(alt) in {'Galaxy Black'}:wrong=False
        own_family=family(alt)==expected
        safe=exact and own_family and not wrong and not re.search(r'\bbox\b|packag|lifestyle|gameplay|bundle|contents',alt,re.I)
        asset=hashlib.sha256(u.encode()).hexdigest()
        if safe:
            d.photos.append(u);d.photo_candidates.append(PhotoCandidate(u,asset));ev['exact_photo_assets'].append(asset)
            ev['photo_scopes'][asset]=dict(store_product_id=req['product_id'],store_sku_id=req['sku_id'],color=color,alt=alt,basis='Own Store row and per-asset family/color')
        else:ev['photo_candidates'].append(dict(url=u,reason='Other color/bundle or asset family unproven',alt=alt))
    if not row:
        for im in b.select('img'):
            u=im.get('src') or im.get('data-src') or '';alt=im.get('alt','')
            if official(u) and family(alt)==expected and not re.search('logo|icon|sketch|diagram',alt,re.I) and u not in seen:
                seen.add(u);ev['photo_candidates'].append(dict(url=u,reason='Family asset; requested color/storage/bundle relation unproven',alt=alt))
    ev['configuration_complete']=exact and (bool(ev['configuration_fields'].get('storage')) if expected.startswith('series_') else True) and (bool(ev['configuration_fields'].get('bundle_contents')) if ev['configuration_fields'].get('bundle') else True)
    d.evidence='Own public Store Product ID / SKU; typed identifiers kept separate' if exact else 'Own official family PDP; configuration candidates are not exact facts'
    d.description='\n'.join([d.found_model+'.',*[f'{x.name}: {x.value}.' for x in d.attributes if len(x.value)<180 and x.name not in {'Совместимость','Комплектация'}]])
    return d,ev
