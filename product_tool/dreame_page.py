"""Exact-model Dreame binding; raw facts precede component and canonical mapping."""
import hashlib,json,re
from dataclasses import asdict
from urllib.parse import urljoin,urlsplit
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
    if re.search(r'base station|\bstation\b|\bdock\b|powerdock|станци',text):return 'station'
    if re.search(r'\brobot\b|робот',text):return 'robot'
    return default

def _heading(node,root):
    for parent in [node,*node.parents]:
        if getattr(parent,'attrs',None) and parent.get('data-component'):return parent['data-component']
        if parent is root:break
        h=parent.find(['h2','h3','h4'],recursive=False) if hasattr(parent,'find') else None
        if h:return h.get_text(' ',strip=True)
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
    roots=soup.select('[id*="spec" i], [class*="specification" i], .specs, [class*="specs-" i], [data-specifications]')
    for root in roots[:30]:
        for row in root.select('tr, li, .spec-item, .specs-item, .specification-item, [data-spec-row]'):
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
        lines=re.split(r'\n|[;/]\s*(?=(?:Eco|Standard|Turbo|Max|Vacuum only)\b)',value,flags=re.I)
        if len(lines)>1 and all(re.search(r'min|minutes|мин',x,re.I) for x in lines):
            for line in lines:
                mode=re.search(r'\(([^)]+)\)|\b(Eco|Standard|Turbo|Max|Vacuum only|Wet and Dry)\b',line,re.I)
                if not mode:return []
                mode=mode[1] or mode[2];cs=component(mode,default=scope)
                out.append(RawAttribute('Maximum Runtime — '+mode,line,SECTIONS[cs]))
            return out
    if re.search(r'water tank',name,re.I):
        lines=value.splitlines()
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
    primary_titles=[x.get_text(' ',strip=True) for x in soup.select('main h1, h1.product-title, h1.product__title')]
    titles=primary_titles
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
    for row in raw:
        label,value=row['name'],row['value'];cs=component(label,row['section'],default);fs=fact_scope(label,value,row['section'])
        reason=''
        if fs!='model':reason='Explicit configuration/region variation; not a model-wide fact'
        if re.search(r'package|contents|accessor|included|комплект',label,re.I):cs='bundle';reason='Published package inventory, not general model specifications'
        if cs=='robot' and re.search(r'(?:clean|dirty|used|fresh) water tank|detergent tank|dust bag',label,re.I) and not re.search(r'robot|onboard|on-board',label+' '+row['section'],re.I):reason='Tank component not explicit; robot/station relation unresolved'
        enriched={**row,'section':SECTIONS[cs],'source_section':row['section'],'component':cs,'scope':fs,'reason':reason};ev['raw_specs'].append(enriched)
        if re.fullmatch(r'Product Name|Model|Product Model',label,re.I):continue
        if reason:ev['rejected_specs'].append(enriched);continue
        attrs=derived_fields(row,cs) or [RawAttribute(label,value,SECTIONS[cs])]
        doc.attributes.extend(attrs);ev['accepted_specs'].append({**enriched,'derived_fields':[asdict(x) for x in attrs]})
    gallery=[]
    for p in selected:
        images=p.get('image',[]);images=images if isinstance(images,list) else [images]
        gallery.extend((x.get('contentUrl') or x.get('url') if isinstance(x,dict) else x,str(p.get('color') or '')) for x in images)
    for img in soup.select('main .product-gallery img, main [data-product-gallery] img, main .product__media img'):
        color=img.get('data-color') or (img.find_parent(attrs={'data-color':True}) or {}).get('data-color','')
        gallery.append((img.get('src') or img.get('data-src'),color))
    seen=set()
    for image,color in gallery[:50]:
        if not isinstance(image,str):continue
        image=urljoin(url,image);h=urlsplit(image).hostname or ''
        if urlsplit(image).scheme!='https' or not any(h==a or h.endswith('.'+a) for a in MEDIA_HOSTS) or image in seen:continue
        seen.add(image);asset=hashlib.sha256(image.encode()).hexdigest()[:24];different=bool(color and config.get('color') and color.casefold()!=config['color'].casefold())
        doc.photo_candidates.append(PhotoCandidate(image,asset,kind='candidate' if different else 'product_gallery',excluded_reason='Explicit other color variant' if different else ''))
        ev['model_gallery_candidates'].append({'url':image,'asset_key':asset,'source_url':url,'model_relation':'unproven' if different else 'model_confirmed','official_color':color,'supplier_color_relation':'different' if different else 'unproven','role':'official_product_gallery','accepted':False,'reason':'Other published color' if different else 'Exact-model published gallery; byte verification pending'})
    return doc,ev
