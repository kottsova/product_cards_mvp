"""PlayStation discovery orchestration on shared HTTP/search/evidence contracts."""
import hashlib,re
from io import BytesIO
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .adapters.common import SourceDocument,RawAttribute,clean_text
from .adapters.lg_documents import document_bytes
from .playstation_identity import official,model_key,codes,document_type,hardware_family
from .playstation_discovery import query_variants,page_links,product_url,rank_link,parse_sitemap,identifier_relation,external_candidates,direct_catalog_candidates
from .playstation_page import own_identity
from .playstation_specs import cover_matches,parse_hardware_specs

def find_source(a,article,*,name='',category='',deadline):
    from .adapters.playstation import ROUTES,parse_page,COLORS
    article=article.strip().upper();requested_cfi=next(iter(codes(article)), '')
    expected=model_key(name);a.extra_documents=[]
    ev=dict(identity={'model':'unproven','hardware':'unproven','configuration':'unproven'},query_variants=query_variants(article,name),requested_identifier=article,
            requested_scope='hardware' if requested_cfi else 'retail',raw_specs=[],configuration_candidates=[],photo_candidates=[],manuals=[],manual_status='Не проверена',
            configuration_fields={},exact_photo_assets=[],photo_scopes={},support_url='',exact_official_pdp='',sku_cfi_relations=[],hardware_rows=[])
    docs={};visited=set();links=[];manuals=[];support_pages={}
    def decision(url,provider,accepted,relation,reason,kind='product',query=article):
        a.emit(query=query,provider=provider,url=url,region=urlsplit(url).path.split('/')[1] if '/' in urlsplit(url).path else '',source_type=kind,accepted=accepted,reason=reason,identity_relation=relation)
    def merge(parsed):
        for key in ('raw_specs','configuration_candidates','photo_candidates','exact_photo_assets'):
            ev[key].extend(x for x in parsed.get(key,[]) if x not in ev[key])
        ev['photo_scopes'].update(parsed.get('photo_scopes',{}))
    def inspect(url,provider):
        if url in visited:return
        visited.add(url);z=a.fetch(url,article,provider,'product',deadline)
        if not z:return
        links.extend(page_links(z.text,z.url));b=BeautifulSoup(z.text,'html.parser')
        sku,published,structured=own_identity(b,z.url)
        parsed_doc,parsed=parse_page(z.text,z.url,article,expected)
        if parsed_doc.error:
            decision(z.url,provider,False,'mismatch',parsed_doc.error);return
        ev['identity']['model']='model_confirmed'
        # A CFI link is a variant relation, not equality with a commercial order identifier.
        linked=requested_cfi and requested_cfi in published
        if linked and sku:
            rd,re=parse_page(z.text,z.url,sku,expected)
            target_colors=[label for key,label in COLORS.items() if key in name.casefold()]
            if not target_colors or re['configuration_fields'].get('color') in target_colors:
                parsed_doc,parsed=rd,re;parsed['identity']['hardware']='official_hardware_model_code';parsed['hardware_model']=requested_cfi
            else:decision(z.url,provider,False,'exact_cfi_other_variant','Published CFI matches, requested variant color not proved')
        merge(parsed)
        if sku:
            relation=parsed.get('sku_cfi_relation',{})
            if relation:
                relation['accepted_for_request']=bool(parsed_doc.source_key=='playstation' and parsed_doc.match_level=='full_sku')
                relation['requested_relation']='exact_order_sku' if parsed_doc.source_key=='playstation' else 'exact_cfi' if linked else identifier_relation(requested_cfi,next(iter(published))) if requested_cfi and len(published)==1 else 'model_only_candidate'
            if relation and relation not in ev['sku_cfi_relations']:ev['sku_cfi_relations'].append(relation)
        if published:
            ev.setdefault('observed_cfi_relations',[]).extend(dict(code=c,relation=identifier_relation(requested_cfi,c) if requested_cfi else 'retail_linked_cfi',source_url=z.url) for c in published)
        if parsed_doc.source_key=='playstation' and parsed_doc.match_level=='full_sku':
            ev['identity']['configuration']='exact_order_sku' if not requested_cfi else 'explicit_cfi_variant_sku'
            ev['configuration_fields']=parsed['configuration_fields'];ev['exact_official_pdp']=z.url;ev['retail_sku']=parsed.get('returned_sku')
            docs['playstation']=parsed_doc
            if len(published)==1:
                code=next(iter(published));ev['identity']['hardware']='official_hardware_model_code';ev['hardware_model']=code
        elif 'playstation_model' not in docs or '/en-gb/' in z.url and '/product/' not in z.url:
            docs['playstation_model']=parsed_doc
        if linked or parsed.get('hardware_model')==article:
            ev['identity']['hardware']='official_hardware_model_code';ev['hardware_model']=article
            if parsed.get('hardware_attributes'):
                hw=SourceDocument('playstation_hardware','PlayStation CFI product table',z.url,found_model=article,match_level='hardware_confirmed',evidence='Exact own Product mpn and table model code')
                hw.attributes=[RawAttribute(k,v,section='Характеристики оборудования '+article,value_cell=True) for k,v in parsed['hardware_attributes']]
                hw.photos=parsed_doc.photos;hw.photo_candidates=parsed_doc.photo_candidates
                parsed_doc.photos=[];parsed_doc.photo_candidates=[]
                docs['playstation_hardware']=hw
        decision(z.url,provider,True,'exact_order_sku' if parsed_doc.source_key=='playstation' else 'exact_cfi' if linked else 'model_confirmed',parsed_doc.evidence)
    # Regional family paths are discovery hints; returned identity is always checked.
    if expected in ROUTES:inspect('https://www.playstation.com/ru-ru/'+ROUTES[expected],'regional_official')
    index=a.fetch('https://www.playstation.com/sitemap_index.xml',article,'official_sitemap','sitemap',deadline)
    if index:
        try:
            kind,children=parse_sitemap(index.text.encode(),'https://www.playstation.com/sitemap_index.xml')
            ev['sitemap_children']=children
            for region in ('ru-ru','en-gb'):
                child=next((u for u in children if official(u) and '/'+region+'/' in u),None)
                if not child:continue
                z=a.fetch(child,article,'official_sitemap','sitemap',deadline)
                if not z:continue
                kind,urls=parse_sitemap(z.text.encode(),z.url)
                relevant=[u for u in urls if official(u) and expected==model_key(urlsplit(u).path.replace('-',' ')) and not '/support/' in u]
                links.extend(relevant)
                decision(child,'official_sitemap',True,'candidate_only',f'{kind}: {len(urls)} URLs, {len(relevant)} matching family candidates','sitemap')
        except (ValueError,TypeError) as e:decision(index.url,'official_sitemap',False,'unproven',str(e),'sitemap')
    # The Direct home and its published Site Map are catalogue entrypoints, not SKU URLs.
    region='en-us' if article.endswith('-US') or re.fullmatch(r'CFI-\d{2}15[AB]',article) else 'en-gb'
    home=a.fetch(f'https://direct.playstation.com/{region}/',article,'playstation_direct','catalog',deadline)
    if home:
        home_links=page_links(home.text,home.url);links.extend(home_links)
        maps=[u for u in home_links if urlsplit(u).hostname=='direct.playstation.com' and urlsplit(u).path.rstrip('/').endswith('/sitemap')]
        for u in maps[:1]:
            z=a.fetch(u,article,'playstation_direct','catalog',deadline)
            if z:links.extend(page_links(z.text,z.url))
        api_candidates=direct_catalog_candidates(a,home,article,name,deadline)
        for u in api_candidates[:3]:
            if rank_link(u,article,name,expected)>0:inspect(u,'playstation_direct_catalog')
            if ev['exact_official_pdp']:break
    candidates=sorted(set(u for u in links if product_url(u)),key=lambda u:(-rank_link(u,article,name,expected),u))
    for u in candidates[:4]:
        if ev['exact_official_pdp']:break
        if rank_link(u,article,name,expected)>0:inspect(u,'playstation_direct')
        if ev['exact_official_pdp']:break
    # Support discovers exact CFI links independently of retail identity.
    hardware=ev.get('hardware_model') or requested_cfi
    for region in ('ru-ru','en-gb','en-us'):
        u=f'https://www.playstation.com/{region}/support/hardware/manuals/'
        z=a.fetch(u,article,'support_manual','support',deadline)
        if not z:continue
        support_pages[region]=z
        for node in BeautifulSoup(z.text,'html.parser').select('a[href]'):
            label=clean_text(node.get_text(' ',strip=True));target=urljoin(z.url,node['href']);declared=codes(label)
            if hardware not in declared or not official(target) or not target.lower().endswith('.pdf'):continue
            fam=hardware_family(target)
            if fam and (fam==expected or expected=='ps5' and fam.startswith('ps5_')):
                item=dict(title=label,url=target,type=document_type(label),relation='official_hardware_model_code',verified=False,language='Не проверена',source_url=z.url,linked_codes=sorted(declared),region=region)
                if not any(m['url']==target for m in manuals):manuals.append(item)
                ev['identity']['hardware']='official_hardware_model_code';ev['hardware_model']=hardware;ev['hardware_family']=fam;ev['support_url']=z.url
        if region=='en-gb' and any(m['region']=='en-gb' for m in manuals):break
    # English specs and RU User Guide/Quick Start are audited separately by role.
    english=next((m for m in manuals if m['region']=='en-gb' and m['type']=='Safety Guide'),None) or next((m for m in manuals if m['region']=='en-gb' and m['type']=='User Guide'),None) or next((m for m in manuals if m['region']=='en-us' and m['type']=='Safety Guide'),None)
    checked=[]
    if english:checked.append(english)
    for role in ('User Guide','Quick Start'):
        m=next((m for m in manuals if m['type']==role and '/ru/' in m['url']),None) or next((m for m in manuals if m['type']==role and m['region']=='en-gb'),None) or next((m for m in manuals if m['type']==role),None)
        if m and m not in checked:checked.append(m)
    for m in checked:
        z=a.fetch(m['url'],article,'official_manual','manual',deadline)
        if not z:continue
        try:
            data=document_bytes(z)
            if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]:raise ValueError('Incomplete PDF')
            reader=PdfReader(BytesIO(data));pages=[p.extract_text() or '' for p in reader.pages];text='\n'.join(pages)
            valid=cover_matches(pages[0],hardware,m['linked_codes'])
            russian=bool(re.search(r'руководств\w*\s+по\s+эксплуатац|инструкц\w*|кратк\w*\s+руководств',text,re.I)) and len(re.findall(r'[А-Яа-яЁё]',text))>1000
            m.update(verified=valid,language='Русский' if russian else 'English' if re.search(r'\bSpecifications\b|Quick Start Guide',text) else 'Не проверена',sha256=hashlib.sha256(data).hexdigest(),pages=len(pages),cover_codes=sorted(codes(pages[0])))
            if m is english and valid:
                drive=None
                if re.fullmatch(r'CFI-\d{4}[AB]',hardware) and len(m['linked_codes'])==2:
                    # Official pair labels + explicit installation columns; suffix is a drive type,
                    # never a regional radio/packaging claim. The inferred binding stays in evidence.
                    drive='with_disc' if hardware.endswith('A') else 'without_disc'
                    ev['drive_row_binding']=dict(code=hardware,drive_relation=drive,source_url=m['source_url'],label=m['title'],basis='Official A/B pair; A=Disc, B=Digital; ordered installed/uninstalled columns')
                hw,raw,rejected=parse_hardware_specs(text,z.url,hardware,linked_codes=m['linked_codes'],drive_relation=drive)
                docs['playstation_hardware']=hw;ev['raw_specs'].extend(raw);ev['configuration_candidates'].extend(rejected)
                ev['hardware_rows'].append(dict(code=hardware,row_scope=drive or 'single_hardware',source_url=z.url,attributes=[dict(name=x.name,value=x.value) for x in hw.attributes]))
                ev['identity']['model']='model_confirmed';ev['hardware_spec_source']=z.url;ev['revision_scope']=hardware
        except Exception as e:m['error']=str(e)
    ev['manuals']=manuals
    ru_user=[m for m in manuals if m['type']=='User Guide' and m['verified'] and m['language']=='Русский']
    ev['manual_status']='Проверена' if ru_user else 'Не проверена'
    ev['quick_start_status']='Проверена' if any(m['type']=='Quick Start' and m['verified'] for m in manuals) else 'Не проверена'
    # Other regions/model pages are opened after support, preserving explicit discovery order.
    if expected in ROUTES:
        inspect('https://www.playstation.com/en-gb/'+ROUTES[expected],'other_official_regions')
    if not ev['exact_official_pdp']:
        found=external_candidates(a.log.parent/'playstation_search.json',article,name,lambda e:a.emit(**e),clock=a.clock,deadline=deadline,factory=getattr(a,'search_factory',None))
        for u in found[:4]:
            if product_url(u):inspect(u,'external_search_candidate')
            if ev['exact_official_pdp']:break
    if not docs and ev['identity']['hardware']!='unproven':
        docs['playstation_model']=SourceDocument('playstation_model','PlayStation hardware identity',ev['support_url'],found_model=hardware,match_level='model_confirmed',evidence='Official exact CFI linked guide')
    ev['model_key']=expected
    # A hardware-code request can be complete at hardware scope without invented retail claims.
    ev['configuration_complete']=bool(ev['identity']['hardware']!='unproven') if requested_cfi else bool(ev['exact_official_pdp'] and ev['configuration_fields'].get('bundle_contents') and (expected!='ps5' or all(ev['configuration_fields'].get(k) for k in ('storage','disc'))))
    ev['configuration_scope']='hardware_only' if requested_cfi and not ev['exact_official_pdp'] else 'retail_variant'
    if requested_cfi and ev['configuration_complete'] and not ev['exact_official_pdp']:
        ev['identity']['configuration']='exact_hardware_configuration'
    # Build a short description solely from admitted facts, never Support instructions.
    for key,d in docs.items():
        if d.attributes:
            lines=[f'{x.name}: {x.value}.' for x in d.attributes if len(x.value)<300 and x.name not in {'Питание','Рабочая температура'}]
            purpose={'ps5':'Игровая консоль PlayStation 5','pro':'Игровая консоль PlayStation 5 Pro','dualsense':'Беспроводной игровой контроллер DualSense','portal':'Устройство дистанционной игры PlayStation Portal','elite':'Беспроводная игровая гарнитура PULSE Elite'}.get(expected,'PlayStation')
            identity=d.found_model if key=='playstation' else ev.get('hardware_model','') if key=='playstation_hardware' else ''
            intro=purpose+(f'. {identity}' if identity else '')+'.'
            if key=='playstation' and ev['configuration_fields'].get('bundle') and ev['configuration_fields']['bundle'] not in intro:
                intro+=' '+ev['configuration_fields']['bundle']+'.'
            d.description='\n'.join([intro,*lines])
            ev.setdefault('description_evidence',[]).append(dict(scope=key,url=d.url,claims=lines))
    a.reports[article]=ev
    main=docs.pop('playstation',None) or docs.pop('playstation_model',None) or docs.pop('playstation_hardware',None)
    a.extra_documents=list(docs.values())
    return main or SourceDocument('playstation_model','PlayStation','',error='No verified official product identity')
