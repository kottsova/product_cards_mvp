"""Exact-model Dreame binding; raw facts precede component and canonical mapping."""
import hashlib,json,re
from dataclasses import asdict
from urllib.parse import urljoin,urlsplit,urlunsplit,parse_qsl,urlencode
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument,RawAttribute,PhotoCandidate
from .adapters.published_page import embedded_objects,records
from .xiaomi_identity import key,model_name,requested_configuration,fact_scope

HOSTS=('dreametech.com','dreame.tech')
MEDIA_HOSTS=HOSTS+('cdn.shopify.com',)
SECTIONS={'robot':'Робот','device':'Устройство','station':'База / станция','handheld':'Ручной пылесос','packaging':'Упаковка','bundle':'Комплектация'}

def official(url):
    p=urlsplit(url);h=p.hostname or ''
    return p.scheme=='https' and not p.username and not p.password and any(h==a or h.endswith('.'+a) for a in HOSTS)

def media_asset_key(url):
    """Collapse only Shopify resize aliases; retain revision, crop and other transforms."""
    p=urlsplit(url)
    if '/cdn/shop/' in p.path or p.hostname=='cdn.shopify.com' and '/s/files/' in p.path:
        path=re.sub(r'_(?:\d+x\d*|x\d+)(?=\.[A-Za-z0-9]+$)','',p.path)
        query=urlencode(sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k not in {'width','height'}))
        url=urlunsplit((p.scheme,p.netloc,path,query,''))
    return hashlib.sha256(url.encode()).hexdigest()[:24]

def region(url):
    h=urlsplit(url).hostname or ''
    return {'global.dreametech.com':'Global','www.dreametech.com':'US','de.dreametech.com':'DE','uk.dreametech.com':'UK','www.dreame.tech':'CN'}.get(h,'')

def clean_model(text):
    text=re.split(r'\s+[|–]\s+',str(text),maxsplit=1)[0].strip()
    text=re.sub(r'^Dreame\s+','',text,flags=re.I)
    text=re.sub(r'\s+(?:Wet (?:and|&) Dry Vacuum|Robot Vacuum(?: Cleaner)?|Cordless (?:Stick )?Vacuum(?: Cleaner)?|Saugroboter)\s*$','',text,flags=re.I)
    return text.strip()

def matches(wanted,title,config=None):
    a,b=key(clean_model(wanted)),key(clean_model(title))
    bundle=(config or {}).get('bundle','')
    # A printed commercial suffix can establish model + that suffix, not its contents.
    return bool(a and (a==b or bundle and b==a+key(bundle)))

def component(label,heading='',default='device'):
    text=(label+' '+heading).casefold()
    if re.search(r'package list|accessory pack|bundle contents|комплект',text):return 'bundle'
    if re.search(r'package|packing|packaging|упаков',text):return 'packaging'
    if re.search(r'handheld|hand-held|ручной',text):return 'handheld'
    if re.search(r'base station|\bstation\b|\bdock\b|powerdock|auto dust collection|auto mop self-cleaning|станци',text):return 'station'
    if re.search(r'\brobot\b|робот',text):return 'robot'
    return default

def _heading(node,root):
    for parent in [node,*node.parents]:
        if getattr(parent,'attrs',None) and parent.get('data-component'):return parent['data-component']
        direct=parent.find(class_='common-title',recursive=False) if hasattr(parent,'find') else None
        if direct:return direct.get_text(' ',strip=True)
        if parent is root:break
        header=parent.find('span',recursive=False) if hasattr(parent,'find') else None
        if header and header.find('b') and re.fullmatch(r'Robot Vacuum|Base Station|Handheld Vacuum',header.get_text(' ',strip=True),re.I):return header.get_text(' ',strip=True)
        h=parent.find(['h2','h3','h4'],recursive=False) if hasattr(parent,'find') else None
        if h:return h.get_text(' ',strip=True)
    native=root.select_one('.common-title')
    if native:return native.get_text(' ',strip=True)
    h=node.find_previous(['h2','h3','h4'])
    return h.get_text(' ',strip=True) if h and h in root.descendants else ''

def raw_rows(soup,products):
    rows=[];seen=set()
    def add(label,value,heading=''):
        label=label.strip().rstrip(':');value=value.strip()
        if label and value and len(label)<120 and len(value)<5000 and (label,value,heading) not in seen:
            seen.add((label,value,heading));rows.append({'name':label,'value':value,'section':heading})
    for p in products:
        for f in p.get('additionalProperty',[]) if isinstance(p.get('additionalProperty'),list) else []:
            if isinstance(f,dict):add(str(f.get('name','')),str(f.get('value','')),str(f.get('propertyID','')))
    roots=soup.select('[id*="spec" i], [class*="specification" i], .specs, [class*="specs-" i], [data-specifications], .common-spec-content, .spec-content')
    for heading in soup.select('.common-title'):
        if re.fullmatch(r'Robot Vacuum|Base Station|Handheld Vacuum|Vacuuming|Mopping|Runtime|Auto Mop Self-Cleaning|Auto Dust Collection|Intelligence|Others',heading.get_text(' ',strip=True),re.I):roots.append(heading.parent)
    root_ids={id(r) for r in roots}
    roots=[r for r in roots if not any(id(a) in root_ids for a in r.parents)]
    for root in roots:
        native_pairs=[b.parent for b in root.select('b, .item.common-subtitle > div > span:first-child') if len(b.parent.find_all(recursive=False))==2 and b.parent.find_all(recursive=False)[0] is b and b.parent.find_all(recursive=False)[1].name=='span']
        for row in [*root.select('tr, li, .spec-item, .specs-item, .specification-item, [data-spec-row], .row-item'),*native_pairs]:
            cells=row.find_all(['th','td'],recursive=False) if row.name=='tr' else row.find_all(recursive=False)
            if len(cells)==2:
                label=cells[0].get_text(' ',strip=True);value='\n'.join(cells[1].stripped_strings);heading=_heading(row,root)
                if not label and value and rows and rows[-1]['section']==heading:rows[-1]['value']+='\n'+value
                else:add(label,value,heading)
        for term in root.select('dt'):
            value=term.find_next_sibling('dd')
            if value:add(term.get_text(' ',strip=True),'\n'.join(value.stripped_strings),_heading(term,root))
    return rows

def derived_fields(row,scope):
    """Derive only explicit axes/modes, keeping the complete original row in evidence."""
    name,value=row['name'],row['value'];out=[]
    if re.search(r'runtime|working time|время работы',name,re.I):
        lines=re.split(r'\n|;\s*|/\s*(?=(?:Eco|Standard|Turbo|Max|Vacuum only)\b)',value,flags=re.I)
        if len(lines)>1 and all(re.search(r'min|minutes|мин',x,re.I) for x in lines):
            for line in lines:
                mode=re.search(r'\(([^)]+)\)|\b(Eco|Standard|Turbo|Max|Vacuum only|Wet and Dry)\b',line,re.I)
                if not mode:return []
                mode=mode[1] or mode[2];cs=component(mode,default=scope)
                out.append(RawAttribute('Maximum Runtime — '+mode,line,SECTIONS[cs]))
            return out
    if re.search(r'water tank',name,re.I):
        lines=re.split(r'\n|\s*\|\s*',value)
        if len(lines)>1 and all(re.match(r'^(?:Standing|Lie[- ]Flat):\s*\d',line,re.I) for line in lines):
            return [RawAttribute(name+' — '+line.split(':',1)[0],line.split(':',1)[1].strip(),SECTIONS[scope]) for line in lines]
    if re.search(r'dimensions|габарит',name,re.I):
        order=re.search(r'\(([LWDH])\s*[x×/]\s*([LWDH])\s*[x×/]\s*([LWDH])\)',name,re.I)
        triple=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(mm|cm)\s*',value,re.I)
        if order and triple and len(set(order.groups()))==3:
            for axis,number in zip(order.groups(),triple.groups()[:3]):
                label={'W':'Width','H':'Height','D':'Depth','L':'Depth'}[axis.upper()]
                out.append(RawAttribute(label,str(float(number)*(10 if triple[4].lower()=='cm' else 1)).removesuffix('.0')+' mm',SECTIONS[scope]))
    return out

def parse_page(html,url,article,name,category=''):
    soup=BeautifulSoup(html,'html.parser');wanted=model_name(name);config=requested_configuration(name)
    objects=[x for obj in embedded_objects(html) for x in records(obj)]
    products=[x for x in objects if x.get('@type')=='Product' or isinstance(x.get('@type'),list) and 'Product' in x['@type']]
    primary_titles=[x.get_text(' ',strip=True) for x in soup.select('main h1, h1.product-title, h1.product__title') if x.get_text(' ',strip=True)]
    titles=primary_titles
    meta_identity={x.get('property'):x.get('content','') for x in soup.select('meta[property]')}
    # Native campaign H1s can be slogans. Model-bearing H1s remain authoritative:
    # an explicit near variant (e.g. Z30 Slim on /z30) must never be overridden.
    model_h1=any(re.search(r'\bDreame\b|\b[A-Za-z]+\d+(?:[A-Za-z]+)?\b',t,re.I) for t in primary_titles)
    if not model_h1 and meta_identity.get('og:type')=='product' and matches(wanted,meta_identity.get('og:title',''),config) and urlsplit(meta_identity.get('og:url','')).path==urlsplit(url).path and soup.title and matches(wanted,soup.title.get_text(' ',strip=True),config):
        titles=[meta_identity['og:title']]
    # The document title can be used only on an official product path, never on a catalog.
    if not primary_titles and '/products/' in urlsplit(url).path and soup.title:titles=[soup.title.get_text(' ',strip=True)]
    if not titles:titles=[x.get('name','') for x in products if x.get('url') and urlsplit(urljoin(url,x['url'])).path==urlsplit(url).path]
    exact=official(url) and '/products/' in urlsplit(url).path and any(matches(wanted,t,config) for t in titles)
    identity={'model':wanted,'model_relation':'model_confirmed' if exact else 'unproven','readiness_scope':'model','source_region':region(url),'retail_sku':None,'configuration_relation':'input_only','identifier_kind':'marketing_model' if key(clean_model(article))==key(clean_model(wanted)) else 'opaque_code'}
    if identity['identifier_kind']=='opaque_code':config['supplier_part_number']=article
    ev={'identity':identity,'input_configuration':config,'requested_configuration':config,'raw_specs':[],'original_raw_specs':[],'accepted_specs':[],'rejected_specs':[],'model_gallery_candidates':[],'model_numbers':[],'manuals':[],'verified_documents':[],'manual_status':'Не проверена','published_identity_fields':[{'name':p.get('name'),'model':p.get('model'),'sku':p.get('sku'),'productID':p.get('productID')} for p in products],'pdp_url':url if exact else ''}
    doc=SourceDocument('dreame_model','Dreame Official',url,found_model=wanted if exact else '',match_level='model_confirmed' if exact else 'unknown',html=html,evidence='Exact official model; supplier configuration separate' if exact else '',error='' if exact else 'Exact official Dreame model not proven')
    if not exact:return doc,ev
    selected=[p for p in products if matches(wanted,p.get('name',''),config)]
    raw=raw_rows(soup.select_one('main') or soup,selected);ev['original_raw_specs']=raw
    default='robot' if any('robot' in str(p.get('name','')).casefold() for p in selected) or 'робот' in category.casefold() else 'device'
    accepted_keys=set()
    for row in raw:
        label,value=row['name'],row['value'];cs=component(label,row['section'],default);fs=fact_scope(label,value,row['section'])
        reason=''
        if fs!='model':reason='Explicit configuration/region variation; not a model-wide fact'
        if re.search(r'package|contents|accessor|included|комплект',label,re.I):cs='bundle';reason='Published package inventory, not general model specifications'
        if re.search(r'purchased separately|optional accessory',value,re.I):reason='Optional accessory specification; not a standard model/bundle fact'
        if cs=='robot' and re.search(r'water tank|water.*tank|detergent tank|dust bag',label,re.I) and not re.search(r'robot|onboard|on-board',label+' '+row['section'],re.I):reason='Tank component not explicit; robot/station relation unresolved'
        enriched={**row,'section':SECTIONS[cs],'source_section':row['section'],'component':cs,'scope':fs,'reason':reason};ev['raw_specs'].append(enriched)
        if re.fullmatch(r'Product Name|Model|Product Model',label,re.I):continue
        if reason:ev['rejected_specs'].append(enriched);continue
        attrs=derived_fields(row,cs) or [RawAttribute(label,value,SECTIONS[cs])]
        unique=[]
        for attr in attrs:
            signature=(attr.name, re.sub(r'\s+','',attr.value).replace(';',''),attr.section)
            if signature not in accepted_keys:unique.append(attr);accepted_keys.add(signature)
        doc.attributes.extend(unique);ev['accepted_specs'].append({**enriched,'derived_fields':[asdict(x) for x in unique],'duplicate_presentation':not bool(unique)})
    # Explicit branded capabilities are technical features even when their
    # surrounding PDP prose is promotional. Admit presence only, not the
    # advertising performance percentages; retain the entire raw statement.
    feature_seen=set()
    for heading in soup.select('main h2,main h3,main .common-title'):
        if heading.find_parent(['nav','aside','table']):continue
        container=heading.find_parent(class_='text-wrapper') or heading.parent
        text=container.get_text(' ',strip=True)
        for match in re.finditer(r'\b(MopExtend(?:™)?(?:\s+RoboSwing)?|SideReach(?:™)?|ProLeap(?:™)?|VersaLift(?:™)?|HyperStream(?:™)?|HyperMind(?:™)?)',text):
            feature=match[1]
            if feature in feature_seen:continue
            feature_seen.add(feature)
            record={'name':feature,'value':text,'section':'Особенности модели','source_section':heading.get_text(' ',strip=True),'component':default,'scope':'model','kind':'feature_presence','reason':''}
            ev['raw_specs'].append(record)
            if re.search(r'not supported|without '+re.escape(feature)+r'|optional|sold separately',text,re.I):
                ev['rejected_specs'].append({**record,'reason':'Conditional or negative feature statement'});continue
            attr=RawAttribute(feature,'Есть','Особенности модели',value_cell=True)
            doc.attributes.append(attr);ev['accepted_specs'].append({**record,'derived_fields':[asdict(attr)],'admission':'Explicit model-owned capability presence; no marketing percentage admitted'})
    gallery=[]
    for p in selected:
        images=p.get('image',[]);images=images if isinstance(images,list) else [images]
        gallery.extend((x.get('contentUrl') or x.get('url') if isinstance(x,dict) else x,str(p.get('color') or ''),'official_product_gallery',True) for x in images)
    for img in soup.select('main .product-gallery img, main [data-product-gallery] img, main .product__media img'):
        color=img.get('data-color') or (img.find_parent(attrs={'data-color':True}) or {}).get('data-color','')
        gallery.append((img.get('data-src') or img.get('src'),color,'official_product_gallery',True))
    # Shopify's native model metadata publishes several images without JSON-LD.
    # Bind metadata to both the current URL and exact model, never recommendations.
    meta={x.get('property'):x.get('content','') for x in soup.select('meta[property]')}
    if meta.get('og:type')=='product' and matches(wanted,meta.get('og:title',''),config) and urlsplit(meta.get('og:url','')).path==urlsplit(url).path:
        gallery.extend((x.get('content'),'','model_metadata_gallery',True) for x in soup.select('meta[property="og:image:secure_url"]'))
    for item in soup.select('main .common-item-container .right-box .item[data-index]'):
        title=item.select_one('.title');label=title.get_text(' ',strip=True) if title else ''
        model_render=matches(wanted,label,config)
        for img in item.select('img[data-src]'):
            gallery.append((img['data-src'],'','model_render' if model_render else 'accessory_or_bundle',model_render))
    ev['native_media_inventory']=[]
    for img in soup.select('main img'):
        if img.find_parent('noscript'):continue
        image=img.get('data-src') or img.get('src','')
        role='feature_visual'
        if 'no-image' in image:role='placeholder'
        elif any('common-icon-item' in a.get('class',[]) for a in img.parents):role='feature_icon'
        elif any('common-item-container' in a.get('class',[]) for a in img.parents):role='package_inventory'
        alt=img.get('alt','')
        model_slug=re.sub(r'[^a-z0-9]+','-',clean_model(wanted).casefold()).strip('-')
        filename=urlsplit(image).path.rsplit('/',1)[-1].casefold()
        named=bool(model_slug and re.match(re.escape(model_slug)+r'(?:[-_.]|$)',filename)) or matches(wanted,alt,config)
        recommendation=any(re.search(r'recommend|related|upsell|cross-sell',str(a.get('class',[])),re.I) for a in img.parents)
        owned=role=='feature_visual' and named and not recommendation
        ev['native_media_inventory'].append({'url':urljoin(url,image),'role':role,'accepted':owned,'alt':alt,'ownership':'Exact model name in published media label/path and owned main DOM' if owned else 'unproven'})
        if owned:gallery.append((image,'','official_model_visual',True))
    ev['native_feature_headings']=[x.get_text(' ',strip=True) for x in soup.select('main h2') if x.get_text(' ',strip=True)]
    seen=set();ev['gallery_asset_aliases']=[]
    for image,color,role,eligible in gallery:
        if not isinstance(image,str):continue
        image=urljoin(url,image);h=urlsplit(image).hostname or ''
        if urlsplit(image).scheme!='https' or not any(h==a or h.endswith('.'+a) for a in MEDIA_HOSTS) or 'no-image' in image:continue
        asset=media_asset_key(image)
        if asset in seen:
            ev['gallery_asset_aliases'].append({'url':image,'asset_key':asset,'accepted':False,'reason':'Shopify resize alias of an already published model gallery asset'});continue
        seen.add(asset);different=bool(color and config.get('color') and color.casefold()!=config['color'].casefold())
        doc.photo_candidates.append(PhotoCandidate(image,asset,kind='candidate' if different or not eligible else 'official_model_visual' if role=='official_model_visual' else 'product_gallery',excluded_reason='Explicit other color variant' if different else 'Accessory/bundle-specific image' if not eligible else ''))
        ev['model_gallery_candidates'].append({'url':image,'asset_key':asset,'source_url':url,'model_relation':'unproven' if different or not eligible else 'model_confirmed','official_color':color,'supplier_color_relation':'different' if different else 'unproven','role':role,'accepted':False,'reason':'Other published color' if different else 'Accessory/bundle inventory; candidate only' if not eligible else 'Exact-model published gallery; byte verification pending'})
    return doc,ev
