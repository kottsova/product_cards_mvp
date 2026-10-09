"""Conservative extraction from own public Xbox and Store product sections."""
import hashlib,json,re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument,RawAttribute,PhotoCandidate,clean_text
from .xbox_identity import official,official_asset,family,identifier,hue,storage_size,retail_request

LABELS={'cpu':'Процессор','gpu':'Графический процессор','memory':'Оперативная память','memory bandwidth':'Пропускная способность памяти','i/o throughput':'Скорость ввода-вывода','gaming resolution':'Игровое разрешение','high dynamic range':'HDR','performance target':'Частота кадров','hdmi features':'Возможности HDMI','hdmi':'HDMI','usb':'USB-порты','wireless':'Стандарт Wi-Fi','ethernet':'Ethernet','accessories radio':'Xbox Wireless','connectivity':'Подключение','compatible with':'Совместимость','system requirements':'Совместимость','battery':'Аккумулятор и время работы','audio':'Аудиоразъём','haptic feedback':'Тактильная отдача','virtual surround sound':'Spatial Sound','speakers':'Динамики','microphones':'Микрофон','impedance':'Импеданс','frequency response':'Частотный диапазон','controls':'Управление','buttons':'Кнопки'}
LABELS.update({'usable storage':'Доступное пользователю место','quick resume':'Quick Resume','smart delivery':'Smart Delivery','xbox velocity architecture':'Xbox Velocity Architecture','power':'Питание','usb-c':'USB-C'})
LABELS.update({'process':'Техпроцесс','assignable buttons':'Назначаемые кнопки','xbox accessories app requirements':'Совместимость с Xbox Accessories'})
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
                    elif pairs:pairs[-1]['value']+=' '+clean_text(line)
            for p in cells[1].select('p'):
                s=p.find('strong')
                if s and ':' in s.text:
                    label=clean_text(s.text).strip('.:');value=clean_text(p.get_text(' ',strip=True))[len(clean_text(s.text)):].strip()
                    if value and not any(x['raw_label']==label for x in pairs):pairs.append(dict(section=l,raw_label=label,value=value))
            rows.extend(pairs or [dict(section='TECH SPECS',raw_label=l,value=v)])
    return list({(r['section'],r['raw_label'],r['value']):r for r in rows}.values())

def color_name(text):
    return next((c for c in ('Arctic Camo','Robot White','Carbon Black','Galaxy Black','Shock Blue','Pulse Red','Electric Volt') if c.casefold() in text.casefold()),hue(text).title())

def parse_page(html,url,article,expected,region,*,name='',catalog_bindings=()):
    b=BeautifulSoup(html,'html.parser');title=clean_text(b.h1.text) if b.h1 else ''
    d=SourceDocument('xbox_model','Xbox / Microsoft',url,found_model=title,html=html)
    ev=dict(page_default_title=title,raw_specs=[],accepted_specs=[],attribute_scopes={},identity_relations=[],configuration_candidates=[],photo_candidates=[],exact_photo_assets=[],photo_scopes={},configuration_fields={},identity={'model':'unproven','configuration':'unproven','hardware':'unproven'},identifiers={},configuration_complete=False,hardware_complete=False)
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
    ev['raw_specs']=raw_rows(b)
    own_valid=bool(market.lower()==region.lower() and re.fullmatch(r'[A-Z0-9]{12}',own_pid) and path.rstrip('/').split('/')[-1].upper()==own_pid)
    published_models={m for r in ev['raw_specs'] if r['raw_label'].casefold() in {'support period','model','model number','hardware model'} for m in re.findall(r'\bModel(?: Number)?\s+(\d{4})\b',r['value'],re.I)} if own_valid else set()
    manufacturer_parts={str(x.get('mpn')) for x in structured if x.get('mpn') and str(x.get('productID','')).upper()==own_pid} if own_valid else set()
    pid_proved=bool(req['product_id'] and market.lower()==region.lower() and path.rstrip('/').split('/')[-1].upper()==req['product_id'] and (own_pid==req['product_id'] or any(str(x.get('productID','')).upper()==req['product_id'] and family(x.get('name',''))==expected for x in structured)))
    sku=None
    if pid_proved and req['sku_id'] and own:
        sku=own.get('skuInfo',{}).get(req['sku_id'])
        if not sku or str(sku.get('skuId','')).upper()!=req['sku_id'] or family(sku.get('title',''))!=expected:sku=None
    exact=pid_proved and (not req['sku_id'] or sku is not None)
    # A multi-SKU Product ID alone is not its displayed default configuration.
    if exact and not req['sku_id'] and own and len(own.get('skuInfo',{}))>1:exact=False
    binding=None
    if not exact and req['type']=='commercial_configuration' and name and own_valid:
        wanted=retail_request(article,name)
        stores={storage_size(r['value']) for r in ev['raw_specs'] if r['raw_label'].casefold() in {'storage','internal storage'}}-{None}
        for c in catalog_bindings:
            pid=identifier(c.get('value',''))
            candidate=(own or {}).get('skuInfo',{}).get(pid['sku_id'])
            if pid['product_id']!=own_pid or c.get('region','').casefold()!=region.casefold() or not official(c.get('source_url','')) or family(c.get('title',''))!=expected or not candidate or str(candidate.get('skuId','')).upper()!=pid['sku_id'] or family(candidate.get('title',''))!=expected:continue
            profile=dict(storage=storage_size(c.get('storage','')),color=hue(c.get('color','')),disc=str(c.get('feature','')).title(),bundle='bundle' in c.get('title','').casefold())
            if not (wanted['storage'] or wanted['color'] or wanted['disc']):continue
            if wanted['bundle']!=profile['bundle'] or any(wanted[k] and wanted[k]!=profile[k] for k in ('storage','color','disc')):continue
            if profile['storage'] not in stores:continue
            if wanted['disc']=='Disc' and not any('blu' in r['value'].casefold() for r in ev['raw_specs'] if 'drive' in r['raw_label'].casefold()):continue
            binding=c;sku=candidate;exact=True;break
    hardware=bool(req['hardware_model'] and published_models=={req['hardware_model']})
    if own_valid:
        ev['identity_relations'].append(dict(type='store_product',product_id=own_pid,sku_ids=list(own.get('skuInfo',{})),hardware_model_numbers=sorted(published_models),manufacturer_parts=sorted(manufacturer_parts),region=market,url=url,relation='hardware_model_to_retail_candidates' if hardware else 'own_store_product',unique_hardware_configuration=False))
    if exact:
        d.source_key='xbox_configuration';d.match_level='full_sku' if sku else 'configuration_confirmed'
        ev['identity']['configuration']='published_catalog_configuration' if binding else 'exact_store_sku' if sku else 'exact_store_product'
        ev['identifiers']={'store_product_id':own_pid or req['product_id'],'store_sku_id':str(sku.get('skuId','')) if sku else req['sku_id'] or None,'manufacturer_part_number':None,'hardware_model_number':None,'storefront':market}
        if len(manufacturer_parts)==1:ev['identifiers']['manufacturer_part_number']=next(iter(manufacturer_parts))
        if len(published_models)==1:ev['identifiers']['hardware_model_number']=next(iter(published_models));ev['identity']['hardware']='official_hardware_model_number'
        label=clean_text(sku.get('title','')) if sku else title
        # The page H1 describes its default row, not necessarily the requested SKU.
        d.found_model=label
        ev['configuration_fields']['storefront']=market
        c=color_name(label)
        if binding and not c:c=binding.get('color','').title()
        if c:ev['configuration_fields']['color']=c
        caps=set(re.findall(r'\b\d+\s*(?:TB|GB)\b',label,re.I))
        if len(caps)==1:ev['configuration_fields']['storage']=next(iter(caps))
        if 'bundle' in label.lower():ev['configuration_fields']['bundle']=label
        if 'digital edition' in label.lower():ev['configuration_fields']['disc']='Digital'
        if binding:
            if binding.get('feature','').casefold()=='digital':ev['configuration_fields']['disc']='Digital'
            ev['identity_relations'].append({**binding,'relation':'Published regional catalog PID/SKU + own Store SKU and matching specs; commercial input is not an SKU'})
            d.match_level='configuration_confirmed'
    elif hardware:
        d.source_key='xbox_hardware';d.match_level='hardware_confirmed';ev['identity']['hardware']='official_hardware_model_number';ev['identifiers']={'hardware_model_number':req['hardware_model']};ev['hardware_complete']=True
    current_raw=None
    def add(label,value,section):
        if not any(x.name==label and x.value==value for x in d.attributes):d.attributes.append(RawAttribute(label,value,section=section,value_cell=True))
        scope='retail' if label in {'Цвет','Комплектация','Название комплекта'} else 'hardware_configuration' if label in {'Встроенный накопитель','Оптический привод','Вес товара','Ширина товара','Высота товара','Глубина товара'} else 'model'
        ev['attribute_scopes'][label]=scope
        ev['accepted_specs'].append(dict(section=section,raw_label=current_raw['raw_label'] if current_raw else 'Own variant / catalog / bundle',raw_value=current_raw['value'] if current_raw else value,label=label,value=value,scope=scope,source_url=url))
    for r in ev['raw_specs']:
        current_raw=r
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
            if exact and l=='weight':
                metric=re.fullmatch(r'\d+(?:\.\d+)?\s*lbs?\s*\((\d+(?:\.\d+)?)\s*(kg|g)\)',value,re.I)
                if metric:add('Вес товара',metric[1]+' '+metric[2].lower(),'Габариты и вес');continue
        elif l in {'width','height','depth'}:
            mapped=None;reason='Axis requires own exact configuration'
            if exact and re.fullmatch(r'\d+(?:\.\d+)?\s*(?:mm|cm)',value):
                add({'width':'Ширина товара','height':'Высота товара','depth':'Глубина товара'}[l],value,'Габариты и вес');continue
        elif l in {'what’s in the box',"what's in the box",'in the box',"what's included"}:
            mapped=None;reason='Kit contents require own exact configuration; cannot borrow model kit'
            if exact:ev['configuration_fields']['bundle_contents']=value;add('Комплектация',value,'Комплект');continue
        if l=='system requirements' and mapped:
            value=re.split(r'\bDrivers available\b',value,flags=re.I)[0].strip()
            if value!=r['value']:ev['configuration_candidates'].append({**r,'reason':'Compatibility prefix accepted; driver procedure suffix withheld'})
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
    current_raw=None
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
    row=sku or (own if exact or hardware else None)
    images=row.get('galleryImages',[]) if row else []
    if row and row.get('displayImage'):images=[row['displayImage'],*images]
    seen=set()
    for im in images:
        u=im.get('uri','');alt=clean_text(im.get('alt',''));color=ev['configuration_fields'].get('color','')
        if not official_asset(u) or u in seen:continue
        seen.add(u);asset_color=color_name(alt);wrong=bool(color and asset_color and hue(color)!=hue(asset_color)) or bool(color and len((own or {}).get('skuInfo',{}))>1 and color.casefold() not in alt.casefold())
        if color=='Arctic Camo' and asset_color and asset_color!='Arctic Camo':wrong=True
        # Carbon Black alt commonly says "black"; explicit own display row + black asset is sufficient.
        if color=='Carbon Black' and re.search(r'\bblack\b',alt,re.I) and asset_color in {'','Black','Carbon Black'}:wrong=False
        accessory_only=expected.startswith('series_') and re.search(r'\b(?:controller|headset)\b',alt,re.I) and not re.search(r'\bconsole\b|\bwith\b|\b(?:front|rear|side)[ -]angle',alt,re.I)
        own_family=not accessory_only and (family(alt)==expected or expected.startswith('series_') and 'console' in alt.casefold() and re.search(r'\b'+expected.replace('_',' ')+r'\b',alt,re.I))
        bundle=ev['configuration_fields'].get('bundle','');asset_bundle='bundle' in alt.casefold()
        bundle_words=[w for w in re.findall(r'[a-z0-9]+',bundle.casefold()) if w not in {'xbox','series','x','s','bundle'}]
        same_bundle=bool(bundle and asset_bundle and all(w in alt.casefold() for w in bundle_words))
        safe=(exact or hardware) and own_family and not wrong and (same_bundle or not re.search(r'\bbox\b|packag|lifestyle|gameplay|bundle|contents',alt,re.I))
        asset=hashlib.sha256(u.encode()).hexdigest()
        if safe:
            d.photos.append(u);d.photo_candidates.append(PhotoCandidate(u,asset));ev['exact_photo_assets'].append(asset)
            ev['photo_scopes'][asset]=dict(store_product_id=own_pid,store_sku_id=ev['identifiers'].get('store_sku_id'),hardware_model_number=req['hardware_model'] if hardware else None,color=color,alt=alt,kind='hardware_render' if hardware else 'bundle_gallery' if bundle else 'exact_color' if color else 'retail_gallery',basis='Own Store row, hardware relation and per-asset family/color/bundle; no kit inference')
        else:ev['photo_candidates'].append(dict(url=u,reason='Other color/bundle or asset family unproven',alt=alt))
    if not row:
        for im in b.select('img'):
            u=im.get('src') or im.get('data-src') or '';alt=im.get('alt','')
            if official(u) and family(alt)==expected and not re.search('logo|icon|sketch|diagram',alt,re.I) and u not in seen:
                seen.add(u);ev['photo_candidates'].append(dict(url=u,reason='Family asset; requested color/storage/bundle relation unproven',alt=alt))
    ev['configuration_complete']=exact and (bool(ev['configuration_fields'].get('storage')) if expected.startswith('series_') else True) and (bool(ev['configuration_fields'].get('bundle_contents')) if ev['configuration_fields'].get('bundle') else True)
    d.evidence='Own public Store Product ID / SKU; typed identifiers kept separate' if exact else 'Own Store explicitly publishes requested hardware model; retail variants remain candidates' if hardware else 'Own official family PDP; configuration candidates are not exact facts'
    d.description='\n'.join([d.found_model+'.',*[f'{x.name}: {x.value}.' for x in d.attributes if len(x.value)<180 and x.name not in {'Совместимость','Комплектация'}]])
    return d,ev
