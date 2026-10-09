"""Compact Xbox adapter integration, using existing jobs/evidence/resolution."""
import json,time
from pathlib import Path
from . import jobs,card_evidence,discovery_trace
from .adapters.xbox import XboxAdapter
from .adapters.dns import DnsAdapter
from .adapters.common import SourceDocument,utc_now

GAPS={'model_identity_missing':'Модель не подтверждена','configuration_unresolved':'Точный SKU / конфигурация не подтверждены','specifications_missing':'Не хватает проверенных характеристик','exact_photo_missing':'Нет подтверждённого фото варианта','conflicts':'Есть конфликт характеристик','manual_unverified':'Пользовательская инструкция не проверена'}
SCOPES={'model_confirmed':'Модель подтверждена','exact_store_sku':'Точный SKU Store','exact_store_product':'Точная конфигурация Store','published_catalog_configuration':'Конфигурация каталога подтверждена Store','official_hardware_model_number':'Опубликованный hardware model number','unproven':'Не подтверждено'}

def photo_verified(photo,ev):
    scope=(ev or {}).get('photo_scopes',{}).get(photo['asset_key'],{})
    return bool(ev and photo['asset_key'] in ev.get('exact_photo_assets',[]) and photo.get('kind')=='product_gallery' and (photo.get('source_key')=='xbox_configuration' or photo.get('source_key')=='xbox_hardware' and ev.get('hardware_complete') and scope.get('kind')=='hardware_render' and scope.get('hardware_model_number')==ev.get('identifiers',{}).get('hardware_model_number')))

def card_readiness(database,product_id):
    ev=card_evidence.load(database,product_id,'xbox') or {};i=ev.get('identity',{});gaps=[]
    if i.get('model')!='model_confirmed':gaps.append('model_identity_missing')
    if not ev.get('configuration_complete') and not ev.get('hardware_complete'):gaps.append('configuration_unresolved')
    facts=[r for r in jobs.get_resolved(database,product_id) if r['status'] in {'full_sku_official','model_confirmed_official','configuration_confirmed_official','hardware_confirmed_official'} and not r['conflict'] and r['normalized_name'] not in {'color','комплектация','название_комплекта'}]
    if len(facts)<3:gaps.append('specifications_missing')
    if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('exact_photo_missing')
    if jobs.result_counts(database,product_id)['conflicts']:gaps.append('conflicts')
    advisory=['manual_unverified'] if ev.get('manual_status')!='Проверена' else []
    return dict(verdict='not_ready' if gaps else 'export_ready',blocking_gaps=gaps,advisory_gaps=advisory,gaps=gaps+advisory,identity=i,configuration_scope=ev.get('configuration_scope','unproven'),configuration_fields=ev.get('configuration_fields',{}),manual_status=ev.get('manual_status','Не проверена'),confirmed_specs=len(facts),instruction={'russian':ev.get('manual_status')=='Проверена'},official_exact_regions=[ev.get('requested_region')] if ev.get('exact_official_pdp') else [])

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
    discovery_trace.initialize(database);trace=lambda e:discovery_trace.record(database,job_id,product_id,e)
    a=(adapter_factory or (lambda:XboxAdapter(fetch_log_path=Path(database).parent/'xbox_fetch.json',trace_callback=trace,clock=clock)))()
    try:hints=json.loads(product.get('original_values_json') or '{}')
    except ValueError:hints={}
    article=product['search_code'];doc=a.find_source(article,name=product.get('name',''),category=product.get('category',''),region=hints.get('requested_region','en-US'),deadline=clock()+180)
    sources=[doc,*a.extra_documents];ev=a.reports.get(article.upper(),{})
    for key in ('xbox_model','xbox_configuration','xbox_hardware'):
        if key not in {s.source_key for s in sources}:sources.append(SourceDocument(key,'Xbox / Microsoft','',error='Источник не подтверждён в текущем запуске'))
    for source in sources:jobs.save_source_document(database,product_id,source,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
    card_evidence.save(database,product_id,'xbox',ev)
    if 4 in stages:jobs.set_photo_selection(database,product_id,ev.get('exact_photo_assets',[]),mode='exact')
    if 3 in stages:jobs.resolve_product(database,product_id)
    ready=card_readiness(database,product_id)
    if ready['blocking_gaps']:
        dealer=(dns_adapter_factory or (lambda:DnsAdapter(fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand='Xbox',name=product.get('name') or article,missing_fields=ready['blocking_gaps'])
        ev['dealer_fallback']=dict(url=dealer.url,status=dealer.match_level,accepted=False,reason=dealer.error or dealer.evidence,scope='dealer_separate_exact_review_required')
        jobs.save_source_document(database,product_id,dealer,update_description=False,update_attributes=False,update_photos=False);card_evidence.save(database,product_id,'xbox',ev)
        trace(dict(timestamp=utc_now(),event='xbox_dealer',query=article,provider='dns',url=dealer.url,region='ru',source_type='dealer',accepted=False,reason=dealer.error or dealer.evidence,identity_relation='unproven'))
    jobs.finish(database,job_id,'error' if not doc.url and doc.error else 'done' if ready['verdict']=='export_ready' else 'needs_review','Xbox: '+('; '.join(GAPS[g] for g in ready['blocking_gaps']) or 'Готова'))
