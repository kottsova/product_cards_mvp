"""Xiaomi uses existing worker jobs, evidence, resolution, photo and dealer policy."""
from pathlib import Path
import time
from . import jobs, card_evidence, discovery_trace, photo_metadata
from .adapters.xiaomi import XiaomiAdapter
from .adapters.dns import DnsAdapter
from .adapters.policy_session import RequestBudget, request_budget
from .adapters.common import utc_now
GAPS={'model_missing':'Точная модель не подтверждена','specifications_missing':'Недостаточно официальных характеристик','gallery_missing':'Нет фото с подтверждённым внешним видом','configuration_missing':'Конфигурация подтверждена частично','conflicts':'Конфликт характеристик','manual_unverified':'Инструкция не проверена'}

def photo_verified(photo, ev):
    return bool(ev and photo['asset_key'] in ev.get('exact_photo_assets',[]) and photo['kind']=='product_gallery')

def document_verified(doc, ev):
    return bool(ev and doc['direct_url'] in ev.get('verified_documents',[]))

def card_readiness(database, product_id):
    ev=card_evidence.load(database,product_id,'xiaomi') or {};identity=ev.get('identity',{})
    facts=[f for f in jobs.get_resolved(database,product_id) if f['selected_source'].startswith('xiaomi_') and f['status'] in {'model_confirmed_official','configuration_confirmed_official'} and not f['conflict']]
    gaps=[];conflicts=jobs.result_counts(database,product_id)['conflicts']
    if identity.get('model_relation')!='model_confirmed':gaps.append('model_missing')
    if len(facts)<3:gaps.append('specifications_missing')
    if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('gallery_missing')
    if identity.get('configuration_relation')!='configuration_confirmed':gaps.append('configuration_missing')
    if conflicts:gaps.append('conflicts')
    if ev.get('manual_status','Не проверена')=='Не проверена':gaps.append('manual_unverified')
    blocking=[g for g in gaps if g!='manual_unverified']
    return {'verdict':'not_ready' if blocking else 'export_ready','blocking_gaps':blocking,'advisory_gaps':[g for g in gaps if g not in blocking],'gaps':gaps,'confirmed_specs':len(facts),'identity':identity,'exact_identity':identity.get('model_relation')=='model_confirmed','conflicts':conflicts,'manual_status':ev.get('manual_status','Не проверена')}

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
    discovery_trace.initialize(database);trace=lambda e:discovery_trace.record(database,job_id,product_id,{'timestamp':utc_now(),**e})
    adapter=(adapter_factory or (lambda:XiaomiAdapter(clock=clock,fetch_log_path=Path(database).parent/'xiaomi_fetch_log.json')))();adapter.trace_callback=trace
    article=product['search_code'].strip().upper();budget=RequestBudget(max_per_row=24,max_total=24);budget.begin_row(str(product_id))
    with request_budget(budget):
        doc=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+90)
        jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
        for extra in adapter.extra_sources:jobs.save_source_document(database,product_id,extra,update_description=False,update_attributes=3 in stages,update_photos=False)
        if 6 in stages:jobs.save_documents(database,product_id,doc.source_key,adapter.find_documents(doc,article))
    ev=adapter.reports.get(article,{})
    if 4 in stages:
        jobs.set_photo_selection(database,product_id,[],mode='none')
        measurements=[]
        for photo in jobs.get_photo_candidates(database,product_id)[:2]:
            try:
                measured=photo_metadata.inspect_saved_photo(photo['url'],photo['source_key'],Path(database).parent/'xiaomi_image_fetch_log.json')
                jobs.save_photo_metadata(database,product_id,photo['id'],photo['url'],width=measured['width'],height=measured['height'],size_bytes=measured['size_bytes'],image_format=measured['format'])
                measurements.append({'url':photo['url'],'accepted_identity':False,**measured})
            except ValueError as exc:measurements.append({'url':photo['url'],'error':str(exc)})
        ev['image_measurements']=measurements
    card_evidence.save(database,product_id,'xiaomi',ev)
    if 3 in stages:jobs.resolve_product(database,product_id)
    r=card_readiness(database,product_id)
    if r['blocking_gaps']:
        dealer=(dns_adapter_factory or (lambda:DnsAdapter(clock=clock,fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand=product['brand'],name=product.get('name') or article,missing_fields=r['blocking_gaps'])
        # A marketing model input cannot prove a retail part through a dealer title.
        ev['dealer_fallback']={'accepted':False,'url':dealer.url,'reason':dealer.error or dealer.evidence,'match_level':dealer.match_level}
        trace({'event':'xiaomi_dealer','query':article,'provider':'dns','url':dealer.url,'region':'ru','source_type':'dealer','accepted':False,'reason':dealer.error or dealer.evidence,'identity_relation':'unproven'})
    card_evidence.save(database,product_id,'xiaomi',ev)
    jobs.finish(database,job_id,'done' if r['exact_identity'] and not r['conflicts'] else 'needs_review','Xiaomi: '+('Готова' if r['verdict']=='export_ready' else 'Не готова')+'. '+'; '.join(GAPS[g] for g in r['gaps']))
