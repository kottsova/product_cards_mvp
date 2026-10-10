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
    return bool(ev and photo['asset_key'] in ev.get('model_gallery_assets',ev.get('exact_photo_assets',[])) and photo['kind']=='product_gallery')

def document_verified(doc, ev):
    return bool(ev and doc['direct_url'] in ev.get('verified_documents',[]))

def card_readiness(database, product_id, *, family='xiaomi'):
    ev=card_evidence.load(database,product_id,family) or {};identity=ev.get('identity',{})
    facts=[f for f in jobs.get_resolved(database,product_id) if f['selected_source'].startswith(family+'_') and f['status'] in {'model_confirmed_official','configuration_confirmed_official'} and not f['conflict']]
    gaps=[];conflicts=jobs.result_counts(database,product_id)['conflicts']
    if identity.get('model_relation')!='model_confirmed':gaps.append('model_missing')
    if len(facts)<3:gaps.append('specifications_missing')
    if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('gallery_missing')
    if conflicts:gaps.append('conflicts')
    if ev.get('manual_status','Не проверена')=='Не проверена':gaps.append('manual_unverified')
    blocking=[g for g in gaps if g!='manual_unverified']
    return {'verdict':'not_ready' if blocking else 'export_ready','blocking_gaps':blocking,'advisory_gaps':[g for g in gaps if g not in blocking],'gaps':gaps,'confirmed_specs':len(facts),'identity':identity,'readiness_scope':'model','input_configuration':ev.get('input_configuration',ev.get('requested_configuration',{})),'exact_identity':identity.get('model_relation')=='model_confirmed','conflicts':conflicts,'manual_status':ev.get('manual_status','Не проверена')}

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic,family='xiaomi'):
    discovery_trace.initialize(database);trace=lambda e:discovery_trace.record(database,job_id,product_id,{'timestamp':utc_now(),**e})
    adapter=(adapter_factory or (lambda:XiaomiAdapter(clock=clock,fetch_log_path=Path(database).parent/'xiaomi_fetch_log.json')))();adapter.trace_callback=trace
    article=product['search_code'].strip().upper();budget=RequestBudget(max_per_row=24,max_total=24);budget.begin_row(str(product_id))
    with request_budget(budget):
        doc=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+90)
        jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
        for extra in adapter.extra_sources:jobs.save_source_document(database,product_id,extra,update_description=False,update_attributes=3 in stages,update_photos=False)
        if 6 in stages:jobs.save_documents(database,product_id,doc.source_key,adapter.find_documents(doc,article))
    ev=adapter.reports.get(article,{})
    import json
    ev.setdefault('input_configuration',dict(ev.get('requested_configuration',{})))
    if ev.get('identity',{}).get('identifier_kind')=='opaque_code':ev['input_configuration']['supplier_part_number']=product['search_code']
    ev['input_configuration_original_values']=json.loads(product.get('original_values_json') or '[]')
    if 4 in stages:
        jobs.set_photo_selection(database,product_id,[],mode='none')
        measurements=[];verified=[]
        eligible={x['asset_key'] for x in ev.get('model_gallery_candidates',[]) if x.get('model_relation')=='model_confirmed'}|set(ev.get('exact_photo_assets',[]))
        for photo in [p for p in jobs.get_photo_candidates(database,product_id) if p['kind']=='product_gallery' and p['asset_key'] in eligible][:4]:
            try:
                measured=photo_metadata.inspect_saved_photo(photo['url'],photo['source_key'],Path(database).parent/(family+'_image_fetch_log.json'))
                if measured['width']<400 or measured['height']<300 or not 0.2<=measured['width']/measured['height']<=5:raise ValueError('Logo/icon or insufficient product image dimensions')
                jobs.save_photo_metadata(database,product_id,photo['id'],photo['url'],width=measured['width'],height=measured['height'],size_bytes=measured['size_bytes'],image_format=measured['format'])
                verified.append(photo['asset_key']);measurements.append({'url':photo['url'],'accepted_identity':True,'identity_scope':'model','supplier_color_relation':'unproven',**measured})
            except ValueError as exc:measurements.append({'url':photo['url'],'error':str(exc)})
        ev['image_measurements']=measurements
        ev['model_gallery_assets']=verified
        for relation in ev.get('model_gallery_candidates',[]):
            relation['accepted']=relation['asset_key'] in verified
            if relation['accepted']:relation['reason']='Official exact-model gallery; bytes verified; no supplier color claim'
        jobs.set_photo_selection(database,product_id,verified)
    card_evidence.save(database,product_id,family,ev)
    if 3 in stages:jobs.resolve_product(database,product_id)
    r=card_readiness(database,product_id,family=family)
    if r['blocking_gaps']:
        dealer=(dns_adapter_factory or (lambda:DnsAdapter(clock=clock,fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand=product['brand'],name=product.get('name') or article,missing_fields=r['blocking_gaps'])
        # A marketing model input cannot prove a retail part through a dealer title.
        ev['dealer_fallback']={'accepted':False,'url':dealer.url,'reason':dealer.error or dealer.evidence,'match_level':dealer.match_level}
        trace({'event':family+'_dealer','query':article,'provider':'dns','url':dealer.url,'region':'ru','source_type':'dealer','accepted':False,'reason':dealer.error or dealer.evidence,'identity_relation':'unproven'})
    card_evidence.save(database,product_id,family,ev)
    jobs.finish(database,job_id,'done' if r['exact_identity'] and not r['conflicts'] else 'needs_review',family.title()+': '+('Готова' if r['verdict']=='export_ready' else 'Не готова')+'. '+'; '.join(GAPS[g] for g in r['gaps']))
