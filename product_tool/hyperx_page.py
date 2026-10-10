"""Conservative refinement of the existing HyperX/Shopify parser; raw facts retained."""
import re
from dataclasses import asdict,replace
from urllib.parse import urlsplit, urlunsplit
from bs4 import BeautifulSoup
from .adapters.hyperx import ScopedAttribute,format_attribute_scope,_variant_photos,_spec_attributes
from .adapters.structured_page import extract_dom_spec_table,extract_shopify_product,extract_main_gallery

SENSITIVE=re.compile(r'(?i)\b(color|colour|layout|switch|operation style|actuation|travel|operating force|life span|weight|width|height|depth|length|dimensions|bundle|sku|part number|revision)\b')

def tokens(value):
    return re.findall(r'[a-z0-9]+',value.casefold())

def canonical_photo_url(value):
    """HyperX's published Shopify media alias; keep version/size parameters.

    Both forms occur for the same media IDs in the live product gallery.
    Scope to this storefront's tenant, never merge arbitrary CDN filenames.
    """
    parts=urlsplit(value)
    prefix='/s/files/1/0561/8345/5901/files/'
    if parts.hostname=='cdn.shopify.com' and parts.path.startswith(prefix):
        return urlunsplit(('https','hyperx.com','/cdn/shop/files/'+parts.path[len(prefix):],parts.query,parts.fragment))
    return value

def requested(name):
    block=re.search(r'\[([^]]+)\]',name)
    return dict(pair.split('=',1) for pair in block.group(1).split(';') if '=' in pair) if block else {}

def model_matches(name,title):
    ignore={'hyperx','gaming','mechanical','keyboard','headset','usb','microphone','mouse','wired','controller','xbox','licensed'}
    wanted=[t for t in tokens(name.split('[',1)[0]) if t not in ignore]
    actual=[t for t in tokens(title) if t not in ignore]
    # A generation or connectivity qualifier in either direction is significant.
    return bool(wanted and wanted==actual)

def refine_page(parsed,html,url,code,name):
    doc=parsed.document;soup=BeautifulSoup(html,'html.parser')
    title=next((f.value for f in parsed.extracted_fields if f.name=='name' and f.role=='json_ld'),'')
    product=extract_shopify_product(html,url)
    target=product.variant_by_sku(code) if product else None
    exact=doc.match_level=='exact_variant'
    model=exact or model_matches(name,title)
    # A SKU/name disagreement is a catalog-input conflict, never silently ignored.
    if exact and name and not model_matches(name,title):
        model=False;exact=False
    options=dict(target.options) if target and exact else {}
    req=requested(name)
    mismatches=[k for k,v in req.items() if not any(k.casefold()==label.casefold() and ' '.join(v.casefold().split())==' '.join(value.casefold().split()) for label,value in options.items())]
    config=exact and not mismatches
    selected=bool(exact and (not product or product.selected_sku.upper()==code.upper()))
    tables=soup.select('table.tech-specs-table')
    raw=extract_dom_spec_table(''.join(str(t) for t in tables) if tables else html,url)
    runtime_claims=[]
    audio_claims=[]
    commercial=name.split('[',1)[0].replace('HyperX ','').strip()
    if commercial:
        for paragraph in soup.select('.overview-description p'):
            text=paragraph.get_text(' ',strip=True)
            match=re.search(re.escape(commercial)+r'\s+(?:features|supports|offers)\s+(?:upgraded\s+)?(\d+)-bit,\s*(\d+(?:\.\d+)?)\s*kHz recording',text,re.I)
            if not match:continue
            for label,value in (('Recording Bit-Depth',match[1]+'-bit'),('Recording Sample Rate',match[2]+' kHz')):
                audio_claims.append({'section':'Microphone recording','raw_label':label,'value':value,'url':url,'evidence':match[0],'scope':'model','claim_type':'official_explicit_audio_spec'})
    # Explicit mode/value claims in a battery feature block; unrelated prose
    # and unqualified headline maxima never imply Bluetooth/RGB conditions.
    for heading in soup.find_all(['h2','h3','h4']):
        if not re.search(r'battery life',heading.get_text(' ',strip=True),re.I):continue
        paragraph=heading.find_next_sibling('p')
        if paragraph is None:continue
        text=paragraph.get_text(' ',strip=True)
        match=re.search(r'up to (\d+) hours in (2\.4\s*GHz|Bluetooth) mode(?: or (\d+) hours with simultaneous connection)?',text,re.I)
        if not match:continue
        mode=re.sub(r'\s+','',match[2])
        runtime_claims.append({'section':'Battery runtime modes','raw_label':f'Battery Life ({mode})','value':f'Up to {match[1]} hours','url':url,'evidence':text,'scope':'model','claim_type':'official_explicit_runtime_claim'})
        if match[3]:runtime_claims.append({'section':'Battery runtime modes','raw_label':'Battery Life (simultaneous connection)','value':f'{match[3]} hours','url':url,'evidence':text,'scope':'model','claim_type':'official_explicit_runtime_claim'})
    scoped_names=[a.name for a in _spec_attributes(raw)]
    accepted=[];rejected=[];attributes=[]
    variable_switch=bool(product and len({dict(v.options).get('Switch','') for v in product.variants})>1)
    microphone_blocks={f.block for f in raw if f.name.casefold()=='element' and 'microphone' in f.value.casefold()}
    wired_only=bool(re.search(r'\bWired\b',name,re.I) and not re.search(r'\bWireless\b',name,re.I))
    digital_audio=any(f.name.casefold()=='usb specification' for f in raw)
    for f,label in zip(raw,scoped_names):
        item={'section':f.section,'raw_label':f.name,'value':f.value,'url':url,'evidence':f.evidence}
        component_section='Microphone Specifications' if f.block in microphone_blocks or re.search(r'\b(?:boom|built[- ]in)\s+mic\b',f.name,re.I) else f.section
        if not model:reason='model_identity_unproven'
        elif wired_only and f.name.casefold() in {'battery life','charge time','battery type','bluetooth version','wireless range'}:reason='wireless_fact_without_wired_configuration_relation'
        elif wired_only and 'headset' in title.casefold() and not digital_audio and f.name.casefold()=='bit-depth':reason='digital_audio_spec_without_wired_audio_relation'
        elif f.name.casefold() in {'unit price','price','availability'}:reason='commercial_widget'
        elif SENSITIVE.search(f.name) and (not selected or not config):reason='selected_variant_not_requested'
        elif variable_switch and not selected and 'Switch' in f.section:reason='switch_variant_not_selected'
        elif f.name.casefold()=='operation style' and options.get('Switch') and (('tactile' in options['Switch'].casefold() and 'linear' in f.value.casefold()) or ('linear' in options['Switch'].casefold() and 'tactile' in f.value.casefold())):reason='official_switch_style_conflict'
        elif f.confirmation!='confirmed':reason='prose_not_specification'
        else:reason=''
        if reason:rejected.append({**item,'reason':reason});continue
        scope='variant' if SENSITIVE.search(f.name) else 'model'
        # Component belongs in the semantic key, not merely in a UI heading.
        if 'microphone' in component_section.casefold() and 'microphone' not in label.casefold() and any(x in label.casefold() for x in ('frequency','sensitivity','impedance')):label+=' (microphone)'
        attributes.append(ScopedAttribute(label,f.value,section=component_section,scope=scope))
        accepted.append({**item,'accepted_label':label,'accepted_section':component_section,'scope':scope})
    if exact and target and config:
        attributes.extend(ScopedAttribute(k,v,section='Variant configuration',scope='variant') for k,v in [('SKU',target.sku),*target.options])
    extra_claims=list({i['raw_label']:i for i in runtime_claims+audio_claims}.values())
    for item in extra_claims:
        if model:
            attributes.append(ScopedAttribute(item['raw_label'],item['value'],section=item['section'],scope='model'))
            accepted.append({**item,'accepted_label':item['raw_label']})
        else:rejected.append({**item,'reason':'model_identity_unproven'})
    # Family name gives no color/layout gallery relation. Existing media assignment remains conservative.
    photos,_=_variant_photos(config,product,target,extract_main_gallery(html,url),[])
    photos=[replace(photo,url=canonical_photo_url(photo.url),asset_key=canonical_photo_url(photo.asset_key)) for photo in photos]
    doc.match_level='exact_variant' if config and model else 'model_confirmed' if model else 'mismatch'
    doc.attributes=attributes if model else []
    doc.photo_candidates=photos
    doc.photos=[p.url for p in photos if not p.excluded_reason]
    scope=format_attribute_scope([a for a in doc.attributes if a.scope=='variant'],[a for a in doc.attributes if a.scope=='model'])
    doc.evidence=scope+'; model_relation='+('model_confirmed' if model else 'unverified')+'; configuration_relation='+('exact_variant' if config else 'unverified')
    reason='exact SKU and declared options' if config else 'exact model; requested SKU/options not proved' if model else 'SKU/model conflict or wrong family'
    relations=[]
    if product:
        relations.append({'type':'storefront_product_id','value':product.product_id,'url':url})
        for v in product.variants:
            relations.append({'type':'merchant_sku','value':v.sku,'base':v.sku.split('#')[0],'regional_suffix':v.sku.split('#')[1] if '#' in v.sku else '', 'shopify_variant_id':v.variant_id,'options':dict(v.options),'accepted':bool(config and v==target),'relation':'exact_variant' if config and v==target else 'family_option_candidate','url':v.url or url})
    report={'model_name':title,'input_code':code,'model_relation':'model_confirmed' if model else 'unverified','configuration_relation':'exact_variant' if config and model else 'unverified','requested_configuration':req,'configuration_gaps':mismatches,'reason':reason,'identity_relations':relations,'raw_specs':[{'section':f.section,'raw_label':f.name,'value':f.value} for f in raw]+extra_claims,'accepted_specs':accepted,'rejected_specs':rejected,'runtime_modes':list({i['raw_label']:i for i in runtime_claims}.values()),'audio_specs':audio_claims,'runtime_limitations':'Unqualified table runtime retains unspecified mode; no Bluetooth-only or RGB mode inferred.','exact_photo_assets':[p.asset_key for p in photos if p.kind=='product_gallery' and not p.excluded_reason],'photos':[asdict(p) for p in photos],'manual_status':'Не проверена','manuals':[],'dealer_fallback':{}}
    return doc,report
