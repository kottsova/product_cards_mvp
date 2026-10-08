"""PlayStation integration on the common worker/storage/normalization pipeline."""
import time
from pathlib import Path
from . import jobs,card_evidence,discovery_trace,storage
from .adapters.playstation import PlayStationAdapter
from .adapters.dns import DnsAdapter
from .adapters.common import utc_now

GAPS={'model_identity_missing':'Модель не подтверждена','configuration_unresolved':'Конфигурация, цвет или комплект не подтверждены','specifications_missing':'Не хватает проверенных характеристик','exact_photo_missing':'Нет подтверждённого фото варианта','conflicts':'Есть конфликт характеристик','manual_unverified':'Пользовательская инструкция не проверена','retail_configuration_unverified':'Розничный SKU, цвет и комплект не подтверждены; доступны только данные оборудования CFI'}

def photo_verified(photo,ev):
    return bool(ev and photo['asset_key'] in ev.get('exact_photo_assets',[]) and photo.get('source_key') in {'playstation','playstation_hardware'} and photo.get('kind')=='product_gallery')

def card_readiness(database,product_id):
    ev=card_evidence.load(database,product_id,'playstation') or {};gaps=[];identity=ev.get('identity',{})
    if identity.get('model')!='model_confirmed':gaps.append('model_identity_missing')
    if not ev.get('configuration_complete'):gaps.append('configuration_unresolved')
    confirmed=[x for x in jobs.get_resolved(database,product_id) if x['status'] in ('full_sku_official','model_confirmed_official','hardware_confirmed_official') and not x['conflict'] and x['normalized_name'] not in {'color','комплектация','bundle','region','storefront'}]
    if len(confirmed)<3:gaps.append('specifications_missing')
    if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('exact_photo_missing')
    if jobs.result_counts(database,product_id)['conflicts']:gaps.append('conflicts')
    advisory=(['manual_unverified'] if ev.get('manual_status')!='Проверена' else [])+(['retail_configuration_unverified'] if ev.get('configuration_scope')=='hardware_only' else [])
    return dict(verdict='not_ready' if gaps else 'export_ready',blocking_gaps=gaps,advisory_gaps=advisory,identity=identity,configuration_scope=ev.get('configuration_scope','unproven'),configuration_fields=ev.get('configuration_fields',{}),manual_status=ev.get('manual_status','Не проверена'),confirmed_specs=len(confirmed),gaps=gaps+advisory,official_exact_regions=['playstation'] if ev.get('exact_official_pdp') else [],instruction={'russian':ev.get('manual_status')=='Проверена'})

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
    discovery_trace.initialize(database);trace=lambda e:discovery_trace.record(database,job_id,product_id,e)
    adapter=(adapter_factory or (lambda:PlayStationAdapter(fetch_log_path=Path(database).parent/'playstation_fetch.json',trace_callback=trace,clock=clock)))()
    article=product['search_code'];doc=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+210)
    sources=[doc,*adapter.extra_documents]
    ev=adapter.reports.get(article.upper(),{})
    # An order code can keep its name while its published CFI changes. Historical
    # hardware is retained in evidence, never resolved against the new CFI.
    previous=next((s for s in jobs.get_source_pages(database,product_id) if s['source_key']=='playstation_hardware'),None)
    current=ev.get('hardware_model')
    if previous and current and previous.get('found_model')!=current:
        ev['superseded_hardware']=dict(source=previous,facts=[f for f in jobs.get_facts(database,product_id) if f['source_key']=='playstation_hardware'],reason='Current own PDP publishes a different exact CFI')
        with storage._connection(database) as db:
            db.execute("UPDATE source_pages SET error=?, match_level='unknown' WHERE product_id=? AND source_key='playstation_hardware'",('CFI differs from current official identity',product_id))
    # A failed/re-routed fetch cannot retain old confirmed facts from a prior run.
    from .adapters.common import SourceDocument
    for key in ('playstation','playstation_model','playstation_hardware'):
        if key not in {s.source_key for s in sources}:sources.append(SourceDocument(key,'PlayStation','',error='Источник не подтверждён в текущем запуске'))
    for source in sources:
        jobs.save_source_document(database,product_id,source,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
    card_evidence.save(database,product_id,'playstation',ev)
    if 4 in stages:jobs.set_photo_selection(database,product_id,ev.get('exact_photo_assets',[]),mode='exact')
    if 3 in stages:jobs.resolve_product(database,product_id)
    ready=card_readiness(database,product_id)
    if ready['blocking_gaps']:
        dealer=(dns_adapter_factory or (lambda:DnsAdapter(fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand='PlayStation',name=product.get('name') or article,missing_fields=ready['blocking_gaps'])
        ev['dealer_fallback']=dict(url=dealer.url,status=dealer.match_level,accepted=False,reason=dealer.error or dealer.evidence,scope='Dealer evidence requires separate exact configuration review')
        jobs.save_source_document(database,product_id,dealer,update_description=False,update_attributes=False,update_photos=False)
        card_evidence.save(database,product_id,'playstation',ev)
        trace(dict(timestamp=utc_now(),event='playstation_dealer',query=article,provider='dns',url=dealer.url,region='ru',source_type='dealer',accepted=False,reason=dealer.error or dealer.evidence,identity_relation='unproven'))
    jobs.finish(database,job_id,'error' if not doc.url and doc.error else 'done' if ready['verdict']=='export_ready' else 'needs_review','PlayStation: '+('; '.join(GAPS[g] for g in ready['blocking_gaps']) or 'Готова'))
