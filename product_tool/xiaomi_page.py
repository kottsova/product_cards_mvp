"""Xiaomi DOM binding over shared public specification primitives."""
from dataclasses import asdict
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument, RawAttribute, PhotoCandidate
from .adapters.published_page import two_column_specs
from .xiaomi_identity import model_name, model_matches, requested_configuration, region, region_matches, fact_scope

def charging_fields(attr):
    """Split only explicitly printed capacities/rates; never infer mode from a wattage."""
    fields=[]
    for line in attr.value.splitlines():
        line=line.strip()
        if not line or line.startswith('*'):continue
        if re.search(r'\d+\s*mAh\b',line,re.I):label='Battery capacity'
        elif re.search(r'\d+\s*W\b',line,re.I):
            label='Reverse charging' if re.search(r'reverse',line,re.I) else 'Wireless charging' if re.search(r'wireless',line,re.I) else 'Wired charging' if re.search(r'HyperCharge|wired',line,re.I) else ''
        elif line.startswith('Supports '):label='Charging protocols'
        elif re.search('charging port',line,re.I):label='Charging port'
        elif 'Surge' in line:label='Battery technology'
        else:label=''
        if label:fields.append(RawAttribute(label,line,'Питание и аккумулятор'))
    return fields

def parse_page(html, url, article, name, category=''):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    wanted = model_name(name)
    exact = model_matches(wanted, title)
    opts = requested_configuration(name)
    source_region = region(url)
    ev = {'identity': {'model': wanted, 'lineage': wanted.split()[0], 'model_relation': 'model_confirmed' if exact else 'unproven', 'configuration_relation': 'partial', 'source_region': source_region, 'requested_region': opts.get('region', ''), 'retail_sku': None}, 'requested_configuration': opts, 'raw_specs': [], 'accepted_specs': [], 'rejected_specs': [], 'model_numbers': [], 'photo_candidates': [], 'exact_photo_assets': [], 'verified_documents': [], 'manual_status': 'Не проверена', 'manuals': []}
    from .xiaomi_identity import key
    ev['identity'].update(requested_identifier=article,identifier_kind='marketing_model' if key(article)==key(wanted) else 'opaque_code',hardware_relation='unproven')
    doc = SourceDocument('xiaomi_model', 'Xiaomi Official', url, found_model=wanted if exact else '', match_level='model_confirmed' if exact else 'mismatch', evidence='Official title: '+title, html=html)
    if not exact:
        doc.error = 'Different model, lineage, generation or connectivity'
        return doc, ev
    # Only the published specs document is eligible, never PDP marketing/navigation.
    if '/specs' not in url:
        return doc, ev
    raw = two_column_specs(html, text_selector='span.xm-text[data-key^="spec_"]')
    repeated={x.name for x in raw if len({a.section for a in raw if a.name==x.name})>1}
    for attr in raw:
        if attr.name == 'Colours': attr = RawAttribute('Display colours', attr.value, attr.section)
        row = asdict(attr); scope = 'configuration' if 'package' in attr.section.casefold() else fact_scope(attr.name); row['scope'] = scope
        ev['raw_specs'].append(row)
        if re.fullmatch(r'(?:Product )?Model(?: Number)?', attr.name, re.I) and re.fullmatch(r'[A-Z0-9-]+', attr.value.strip()):
            ev['model_numbers'].append({'kind': 'hardware_model_number', 'value': attr.value, 'model': wanted, 'source_url': url, 'retail_sku_relation': 'unproven'})
        elif re.fullmatch(r'(?:Omni )?Station Model',attr.name,re.I) and re.fullmatch(r'[A-Z0-9-]+',attr.value.strip()):
            ev['model_numbers'].append({'kind':'hardware_model_number','component':'station','value':attr.value,'model':wanted,'source_url':url,'retail_sku_relation':'unproven'})
        reason = ''
        if scope == 'configuration': reason = 'Family options/package inventory do not prove requested retail configuration'
        elif scope == 'region' and not region_matches(opts.get('region', ''), source_region): reason = 'Source market does not prove requested market'
        elif re.search(r'\bvary by markets\b', attr.value, re.I): reason = 'Explicit market-dependent value needs a local configuration relation'
        elif re.search(r'\bdimensions\b|\bweight\b', attr.name, re.I) and re.search(r'Black|White|Green|Silver|Leather|colour|color', attr.value, re.I): reason = 'Dimensions/weight vary by appearance; exact color relation required'
        elif re.search(r'station|dock|base', attr.name+' '+attr.section, re.I) and opts.get('bundle'): reason = 'Station/base revision requires exact bundle evidence'
        if reason:
            ev['rejected_specs'].append({**row, 'reason': reason})
        else:
            section = 'База / станция' if re.search(r'station|dock', attr.name+' '+attr.section, re.I) else 'Габариты и вес' if re.search(r'dimensions|weight', attr.name, re.I) else 'Питание и аккумулятор' if re.search(r'battery|charging|power|voltage', attr.name, re.I) else {'Display':'Экран','Design':'Конструкция','Material':'Материалы','Speaker':'Аудио','Processor':'Процессор','Rear camera':'Основная камера','Front Camera':'Фронтальная камера','Ports':'Порты'}.get(attr.section,'Характеристики модели')
            qualified=attr.name+' ('+attr.section+')' if attr.name in repeated and section!='База / станция' else attr.name
            derived=charging_fields(attr) if attr.name=='Battery & Charging' else []
            doc.attributes.extend(derived or [RawAttribute(qualified, attr.value, section)])
            if derived:row['derived_fields']=[asdict(x) for x in derived]
            ev['accepted_specs'].append({**row, 'section': section})
    ev['identity']['configuration_relation'] = 'configuration_confirmed' if ev['identity']['identifier_kind']=='marketing_model' and set(opts) <= {'region'} and region_matches(opts.get('region', ''), source_region) else 'partial'
    # Image URLs on a specs page are model-bound candidates; color/layout/bundle still needs evidence.
    for img in soup.select('img'):
        image = img.get('data-src') or img.get('src') or ''
        host=urlsplit(image).hostname or ''
        if urlsplit(image).scheme!='https' or not host.endswith('.appmifile.com') or image.lower().endswith('.svg'):
            continue
        asset = image.rsplit('/', 1)[-1]
        if asset in {p.asset_key for p in doc.photo_candidates}: continue
        doc.photo_candidates.append(PhotoCandidate(image, asset, kind='candidate', excluded_reason='Model image; exact color/bundle appearance not proven'))
        ev['photo_candidates'].append({'url': image, 'asset_key': asset, 'source_url': url, 'kind': 'model_render_candidate', 'accepted': False, 'reason': 'Exact appearance not proven'})
    return doc, ev
