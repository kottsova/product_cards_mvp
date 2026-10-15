"""Model-first recovery using published Apple catalog links and native scoped cells.

Supplier/hardware identifiers never become a commercial order number here.
"""
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .adapters.common import SourceDocument, RawAttribute, PhotoCandidate, clean_text
from .apple_identity import plain, append_qualified_sections


def iphone_model(text):
    match = re.search(r'\biphone\s*(\d{1,2})(e)?(?:\s+(pro\s+max|pro|plus|air))?\b', plain(text))
    if not match:
        return ''
    return 'iPhone ' + match[1] + (match[2] or '') + (' ' + match[3].title() if match[3] else '')


def compact(text):
    return re.sub(r'[^a-z0-9]', '', plain(text))


def parse_native_specs(html, url, model):
    """Admit exact model cells or explicitly shared colspan cells, never first-column guesses."""
    from .adapters.apple import official
    soup = BeautifulSoup(html, 'html.parser')
    title = clean_text(soup.h1.get_text(' ', strip=True)) if soup.h1 else ''
    doc = SourceDocument('apple_model', 'Apple model Tech Specs', url, found_model=model, html=html)
    audit = dict(url=url, model_name=model, raw_specs=[], admitted=[], candidates=[], rejected_cells=[])
    family = model.removesuffix(' Max')
    if not official(url) or iphone_model(title) not in {model, family} or not re.search(r'tech(?:nical)?\s+spec', plain(title)):
        doc.error = 'Native Tech Specs model/generation mismatch'
        return doc, audit
    groups = []
    if soup.select('h3.gb-header'):
        from .apple_identity import sections
        if iphone_model(title) != model:
            doc.error='Support Tech Specs exact model mismatch'
            return doc,audit
        doc.match_level='model_confirmed'
        doc.evidence='Exact model Support Tech Specs; configuration options excluded'
        return append_qualified_sections(doc,audit,sections(html)[1],'iphone',{})
    sections = {'Color': 'Finish', 'Capacity': 'Capacity'}
    for section in soup.select('.techspecs-section'):
        header = section.select_one('.techspecs-rowheader')
        if not header:
            continue
        header = BeautifulSoup(str(header), 'html.parser')
        for sup in header.select('sup'):
            sup.decompose()
        label = clean_text(header.get_text(' ', strip=True))
        label = sections.get(label, label)
        for row in section.select('.techspecs-row'):
            cells = row.find_all(class_='techspecs-column', recursive=False)
            for cell in cells:
                headings = [clean_text(h.get_text(' ', strip=True)) for h in cell.select('.techspecs-small-heading')]
                owners = {iphone_model(h) for h in headings if iphone_model(h)}
                if not owners:
                    owners={iphone_model(f.get('aria-label','')) for f in cell.select('figure[aria-label]') if iphone_model(f.get('aria-label',''))}
                shared = cell.get('aria-colspan') == '2' and not owners
                exact = owners == {model}
                if not (shared or exact):
                    audit['rejected_cells'].append(dict(section=label, owners=sorted(owners), reason='other/unresolved model column'))
                    continue
                values = []
                if label == 'Size and Weight':
                    for caption in cell.select('figcaption.diagram-text'):
                        values.append(clean_text(caption.get_text(' ', strip=True)))
                    weight = cell.select_one('.weight-wrapper')
                    if weight:
                        values.append('Weight: ' + clean_text(' '.join(p.get_text(' ', strip=True) for p in weight.select('p.weight-copy'))))
                else:
                    for node in cell.select('li, p'):
                        if node.find_parent('li') or node.find_parent('figcaption'):
                            continue
                        node = BeautifulSoup(str(node), 'html.parser')
                        for sup in node.select('sup'):
                            sup.decompose()
                        text = clean_text(node.get_text(' ', strip=True))
                        if label=='External Buttons and Connectors' and headings and not owners:
                            text=headings[0]+': '+text
                        if node.select_one('.model-caption'):
                            # Rounded-corner rectangle measurement is not the advertised diagonal.
                            audit['candidates'].append(dict(section=label,raw_label=label,value=text,reason='Rounded-corner explanatory measurement; not a second nominal diagonal'))
                            continue
                        if text and text not in values:
                            values.append(text)
                if values:
                    groups.append((label, values, cell))
    if not groups:
        doc.error = 'No exact/shared native specification cells'
        return doc, audit
    doc.match_level = 'model_confirmed'
    doc.evidence = 'Published exact-model columns and explicitly shared colspan cells; other model columns excluded'
    grouped={}
    for label,values,node in groups:
        target=grouped.setdefault(label,[])
        target.extend(v for v in values if v not in target)
    append_qualified_sections(doc, audit, [(label,values,None) for label,values in grouped.items()], 'iphone', {})
    return doc, audit


def find_model_source(adapter, article, name, deadline):
    """Discover catalog -> linked PDP -> linked specs/store with bounded existing HTTP transport."""
    from .adapters.apple import official, selection
    model = iphone_model(name)
    ev = dict(identity={'model': 'unproven', 'configuration': 'unproven', 'variant': 'unproven',
                        'part_number': '', 'hardware_model_numbers': []},
              input_article=article, input_name=name, model_name=model, model_category='iphone',
              configuration_fields={}, configuration_candidates=[], photo_candidates=[], exact_photo_assets=[],
              manual_status='Не проверена', manuals=[], discovery_status='discovery_started')
    adapter.reports[article] = ev
    best = SourceDocument('apple', 'Apple model discovery', '', error='No official model source found')
    def fetch(url, stage, query):
        if adapter.clock() >= deadline:
            adapter.emit(event='apple_navigation_skipped', stage=stage, url=url, reason='row_deadline')
            return None
        adapter.emit(event='apple_navigation_start', stage=stage, url=url, query=query, provider='official_http')
        z = adapter.session.get(url, timeout=min(10, max(.1, deadline-adapter.clock())))
        digest = hashlib.sha256(z.url.encode()).hexdigest()
        if z.ok and z.text:
            body = adapter.capture_dir / (digest+'.html')
            body.write_text(z.text, encoding='utf-8')
            body.with_suffix('.json').write_text(json.dumps(dict(url=z.url, status=z.status_code,
                 sha256=hashlib.sha256(body.read_bytes()).hexdigest(), query=query, provider='official_http'), ensure_ascii=False), encoding='utf-8')
        adapter.emit(event='apple_navigation_end', stage=stage, url=z.url, query=query, provider='official_http',
                     accepted=z.ok and bool(z.text), reason=z.marker or f'HTTP {z.status_code}')
        return z if z.ok and z.text and official(z.url) else None
    if not model:
        ev['discovery_status'] = 'discovery_not_started'
        best.error = 'No usable marketing model in input; supply model name or commercial part number'
        adapter.emit(event='discovery_not_started', query=name, reason=best.error, accepted=False)
        return best
    ev['query_variants'] = [model, article, f'site:apple.com "{model}" tech specs']
    adapter.emit(event='apple_model_normalization', query=name, model_identity=model, hardware_identity=article,
                 retail_identity='unproven', accepted=True, reason='Marketing model independent of commercial SKU')
    catalog = fetch('https://www.apple.com/iphone/', 'catalog', model)
    candidates = []
    if catalog:
        soup = BeautifulSoup(catalog.text, 'html.parser')
        slug = model.lower().replace(' ', '-').removesuffix('-max')
        for anchor in soup.select('a[href]'):
            url = urljoin(catalog.url, anchor['href'])
            if official(url) and urlsplit(url).path.strip('/') == slug and url not in candidates:
                candidates.append(url)
                adapter.emit(event='apple_model_candidate', query=model, provider='official_catalog', url=url,
                             source_type='model_pdp', accepted=True, reason='Published exact family catalog link; model columns still require verification')
    # The shared external fallback uses an Apple classifier, never the Lenovo default.
    if not candidates and adapter.clock() < deadline:
        from .adapters.lg_browser_search import LGBrowserSearch
        from .census.browser_contracts import BrowserBudget
        hosts = ('www.apple.com', 'apple.com', 'support.apple.com')
        remaining = max(.1, deadline-adapter.clock())
        search = LGBrowserSearch(adapter.log.with_name('apple_browser_search_log.json'), official_host='www.apple.com',
            official_hosts=hosts, allowed_hosts=hosts+('www.google.com','google.com','gstatic.com'), clock=adapter.clock,
            candidate_classifier=apple_candidate_type, budget=BrowserBudget(deadline_seconds=min(20,remaining), operation_timeout_seconds=min(10,remaining)))
        try:
            result = search.search_provider('google', f'site:apple.com "{model}" tech specs')
            adapter.emit(event='apple_model_external_search', query=model, provider='shared_google', reason=result.outcome, accepted=False)
            candidates = [c.url for c in result.candidates[:2]]
        finally:
            search.close()
    for url in candidates[:2]:
        pdp = fetch(url, 'model_pdp', model)
        if not pdp:
            continue
        soup = BeautifulSoup(pdp.text, 'html.parser')
        titles = [clean_text(h.get_text(' ', strip=True)) for h in soup.select('h1,h2.product-name-title')]
        family = model.removesuffix(' Max')
        if not any(iphone_model(t) in {model, family} for t in titles):
            ev['discovery_status'] = 'source_found_but_identity_rejected'
            adapter.emit(event=ev['discovery_status'], url=pdp.url, query=model, accepted=False, reason='PDP title/generation differs', found_titles=titles)
            continue
        links = [(urljoin(pdp.url,a['href']), clean_text(a.get_text(' ',strip=True))) for a in soup.select('a[href]')]
        specs_urls = list(dict.fromkeys(u for u,t in links if official(u) and ('tech specs' in plain(t) or urlsplit(u).path.rstrip('/').endswith('/specs'))))
        if urlsplit(pdp.url).path.rstrip('/').endswith('/specs') or urlsplit(pdp.url).hostname=='support.apple.com':
            specs_urls.insert(0,pdp.url)
        for spec_url in specs_urls[:2]:
            spec = pdp if spec_url == pdp.url else fetch(spec_url, 'model_specs', model)
            if not spec:
                continue
            doc,audit = parse_native_specs(spec.text,spec.url,model)
            adapter.emit(event='apple_model_specs', query=model, provider='official_linked_specs', url=spec.url,
                         source_type='model_tech_specs', accepted=not doc.error, reason=doc.error or doc.evidence,
                         model_identity=model, raw_fields=len(audit['raw_specs']), accepted_fields=len(doc.attributes),
                         rejected_cells=len(audit['rejected_cells']))
            if not doc.error:
                adapter.model_document=doc
                ev.update(model_evidence=audit, discovery_status='extraction_empty' if not doc.attributes else 'discovery_completed')
                ev['identity']['model']='model_confirmed'
                best=SourceDocument('apple','Apple model PDP',pdp.url,found_model=model,html=pdp.text,
                                    match_level='model_confirmed',evidence='Published catalog/PDP/model-scoped Tech Specs chain')
                break
            ev['discovery_status']='source_found_but_identity_rejected'
        slug=family.lower().replace(' ','-')
        store_urls=list(dict.fromkeys(u for u,t in links if official(u) and (
            urlsplit(u).path.rstrip('/').endswith('/shop/buy-iphone/'+slug) or
            urlsplit(u).path.rstrip('/').endswith('/shop/goto/buy_iphone/'+slug.replace('-','_')))))
        if ev['identity']['model']=='model_confirmed':
            if store_urls:
                store=fetch(store_urls[0],'configuration_overlay',model)
                if store:
                    overlay_store(adapter,best,ev,selection(BeautifulSoup(store.text,'html.parser')),store.url,article,name,model)
            break
    if ev['identity']['model']!='model_confirmed':
        ev['discovery_status'] = ev['discovery_status'] if ev['discovery_status']=='source_found_but_identity_rejected' else 'official_source_not_found'
        adapter.emit(event=ev['discovery_status'], query=model, accepted=False, reason=best.error)
    if adapter.manuals_enabled and ev['identity']['model']=='model_confirmed':
        # Optional guide inventory stays bounded and separate from model readiness.
        guide=fetch('https://support.apple.com/ru-ru/guide/iphone/welcome/ios','documents',model)
        if guide and re.search(r'руководство\s+пользователя\s+iphone',plain(BeautifulSoup(guide.text,'html.parser').get_text(' ',strip=True))):
            ev['manual_status']='Проверена'
            ev['manuals']=[dict(type='User Guide',title='Руководство пользователя iPhone',url=guide.url,
                language='Русский',relation='iPhone platform guide; not exact hardware/retail manual',verified=True)]
    return best


def apple_candidate_type(url):
    from .adapters.apple import official
    if not official(url):
        return 'unknown'
    path=urlsplit(url).path
    if urlsplit(url).hostname=='support.apple.com' and re.search(r'/\d{6}(?:/|$)',path):
        return 'support'
    return 'product' if re.search(r'/iphone-[\w-]+(?:/specs)?/?$',path) or '/shop/' in path else 'unknown'


def overlay_store(adapter,doc,ev,payload,url,article,name,model):
    """Options prove supported model configurations, not supplier SKU or regional radio identity."""
    requested=dict(getattr(adapter,'input_configuration',{}) or {})
    capacity=re.search(r'\b(\d+)\s*(GB|TB|ГБ|ТБ)\b',name,re.I)
    if capacity:requested.setdefault('storage',capacity[1]+{'ГБ':'GB','ТБ':'TB'}.get(capacity[2].upper(),capacity[2].upper()))
    color=str(requested.get('color','')).strip().casefold()
    color={'серебристый':'silver','серебряный':'silver','черный':'black','чёрный':'black','белый':'white'}.get(color,color)
    if not color:
        color=next((c for c in ('silver','black','white','burgundy','glacier') if re.search(r'\b'+c+r'\b',plain(name))), '')
    ev['input_configuration']=requested
    records=[x for x in payload.get('products',[]) if compact(x.get('familyType',''))==compact(model)]
    hardware=re.fullmatch(r'A\d{4}',article,re.I)
    if hardware:
        related=[x for x in records if re.fullmatch(re.escape(article)+r'_energy_compliance',x.get('energyComplianceKey',''),re.I)]
        if related:
            records=related
            ev['hardware_relations']=[dict(input_hardware=article, published_key=x.get('energyComplianceKey'),
                part_number=x.get('partNumber'),model=x.get('familyType'),url=url,
                relation='published Store energy compliance key; no regional radio/configuration inference') for x in records]
            ev['identity']['hardware']='published_store_key'
        else:
            ev['hardware_relation_unresolved']=article
            adapter.emit(event='apple_configuration_overlay',url=url,accepted=False,reason='Requested hardware has no published same-model Store relation; model specs retained',hardware_identity=article)
            return
    storage=compact(requested.get('storage',''))
    matched=[x for x in records if storage and compact(x.get('dimensionCapacity',''))==storage and color and x.get('dimensionColor','').casefold()==color]
    ev['retail_candidates']=sorted({x.get('partNumber','') for x in matched if x.get('partNumber')})
    if not matched:
        adapter.emit(event='apple_configuration_overlay',url=url,accepted=False,reason='No exact model + requested capacity/color record; options remain candidates',model_identity=model)
        return
    ev['configuration_fields']={'storage':requested['storage'],'color':color}
    ev['configuration_proofs']=[dict(field=f,value=v,url=url,proof='Explicit model capacity/color selection records; supplier SKU and region unproven') for f,v in ev['configuration_fields'].items()]
    ev['identity'].update(configuration='model_configuration_supported',variant='exact_model_color')
    ev['configuration_complete']=True
    # Save these supported selection values with model scope, never full_sku.
    doc.attributes.extend([RawAttribute('Объём накопителя',requested['storage'],section='Configuration',value_cell=True),RawAttribute('Цвет',color,section='Configuration',value_cell=True)])
    for record in matched:
        key=record.get('imageKey','');image=payload.get('imageDictionary',{}).get(key,{})
        if compact(model) not in compact(key) or color not in plain(key) or '-max-' in key.lower() and not model.endswith(' Max'):
            continue
        for source in image.get('sources',[]):
            u=source.get('srcSet','');host=urlsplit(u).hostname or ''
            if not host.endswith('.cdn-apple.com') or not re.search(r'^https://',u) or key not in urlsplit(u).path:
                continue
            asset=hashlib.sha256(u.encode()).hexdigest()
            if asset in ev['exact_photo_assets']:continue
            doc.photo_candidates.append(PhotoCandidate(u,asset));doc.photos.append(u);ev['exact_photo_assets'].append(asset)
    ev['photo_scope']='exact_model_color from explicit Store selection; no supplier retail identity claim'
    adapter.emit(event='apple_configuration_overlay',url=url,accepted=True,reason='Explicit same-model capacity/color records; commercial identity remains unproven',model_identity=model,hardware_identity=ev['identity'].get('hardware','unproven'),retail_identity='candidate',candidate_part_numbers=ev['retail_candidates'])
    adapter.emit(event='apple_photos',url=url,accepted=bool(ev['exact_photo_assets']),reason=ev['photo_scope'],photos=len(ev['exact_photo_assets']))
