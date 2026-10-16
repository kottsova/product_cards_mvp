"""Apple audit integration reuses worker jobs, evidence, normalization and DNS."""
import time,json
from pathlib import Path
from . import jobs,card_evidence,discovery_trace
from .adapters.apple import AppleAdapter
from .adapters.dns import DnsAdapter
from .adapters.common import utc_now

def card_readiness(database,product_id):
 ev=card_evidence.load(database,product_id,'apple') or {};facts=jobs.get_resolved(database,product_id);gaps=[]
 if ev.get('identity',{}).get('model')!='model_confirmed':gaps.append('model_identity_missing')
 if not ev.get('configuration_complete'):gaps.append('configuration_fields_unresolved')
 from .apple_identity import MODELS
 cat=MODELS.get(ev.get('model_key'),('','','',''))[2] or ev.get('model_category','');config=ev.get('configuration_fields',{})
 required={'iphone':('storage','color'),'ipad':('storage','color','connectivity'),'mac':('storage','memory','gpu','color'),'watch':('case_size','connectivity','material','color'),'airpods':()}.get(cat,())
 if any(not config.get(field) for field in required):gaps.append('required_configuration_override_missing')
 confirmed=[x for x in facts if (x['full_sku_confirmed'] or x['status']=='model_confirmed_official') and not x['conflict']]
 if len(confirmed)<5:gaps.append('specifications_missing')
 if not any(x['selected'] and x['asset_key'] in ev.get('exact_photo_assets',[]) for x in jobs.get_photo_candidates(database,product_id)):gaps.append('exact_variant_photo_missing')
 if jobs.result_counts(database,product_id)['conflicts']:gaps.append('conflicts')
 if ev.get('input_model_ambiguous'):gaps.append('input_model_ambiguous')
 return {'verdict':'not_ready' if gaps else 'export_ready','blocking_gaps':gaps,'advisory_gaps':['manual_unverified'] if ev.get('manual_status')!='Проверена' else [],'identity':ev.get('identity',{}),'manual_status':ev.get('manual_status','Не проверена'),'confirmed_specs':len(confirmed),'model_specs':sum(x['status']=='model_confirmed_official' for x in confirmed),'configuration_fields':ev.get('configuration_fields',{}),'discovery_status':ev.get('discovery_status','discovery_not_started')}

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
 discovery_trace.initialize(database)
 def trace(e):
  discovery_trace.record(database,job_id,product_id,e)
  stage=e.get('stage')
  stage=6 if stage=='documents' else 4 if e['event'].startswith('apple_photo') else 3 if e['event'] in {'apple_model_specs','apple_extraction'} else 1
  label=e['event'];reason=e.get('reason','')
  jobs.progress(database,job_id,stage,f"Apple: {label}; {reason}",source_url=e.get('url',''),level='warning' if e.get('accepted') is False else 'info')
 trace(dict(timestamp=utc_now(),event='apple_dispatch',reason='worker selected Apple pipeline',input_name=product.get('name',''),input_article=product.get('search_code',''),alternate_code=product.get('alternate_code','')))
 adapter=(adapter_factory or (lambda:AppleAdapter(fetch_log_path=Path(database).parent/'apple_fetch.json',trace_callback=trace,clock=clock)))()
 if hasattr(adapter,'manuals_enabled'):adapter.manuals_enabled=6 in stages
 identity=product.get('identity',{}) or product.get('identity_json',{}) or {}
 if isinstance(identity,str):identity=json.loads(identity)
 adapter.input_configuration=identity.get('variant_attributes',{})
 article=product['search_code']
 trace(dict(timestamp=utc_now(),event='discovery_not_started',reason='adapter constructed; calling discovery next'))
 doc=adapter.find_source(article,name=product.get('discovery_name') or product.get('name',''),category=product.get('category',''),deadline=clock()+90)
 trace(dict(timestamp=utc_now(),event='apple_adapter_return',url=doc.url,reason=doc.error or doc.evidence,accepted=not doc.error,match_level=doc.match_level))
 jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
 model=getattr(adapter,'model_document',None)
 if model:jobs.save_source_document(database,product_id,model,update_description=False,update_attributes=3 in stages,update_photos=4 in stages)
 ev=adapter.reports.get(article.strip().upper(),{})
 from .input_interpretation import attach_input_evidence
 attach_input_evidence(ev,product)
 if 'discovery_status' not in ev:ev['discovery_status']='discovery_completed' if model and model.attributes else 'extraction_empty' if doc.url and not doc.error else 'official_source_not_found'
 trace(dict(timestamp=utc_now(),event='apple_extraction',url=model.url if model else doc.url,reason='Extraction completed before readiness',model_specs=len(model.attributes) if model else 0,order_specs=len(doc.attributes),accepted=bool((model and model.attributes) or doc.attributes)))
 trace(dict(timestamp=utc_now(),event='apple_persistence',reason='Official source facts/photos and identity saved; unresolved input remains configuration',source_url=doc.url))
 card_evidence.save(database,product_id,'apple',ev)
 if 4 in stages and ev.get('exact_photo_assets'):jobs.set_photo_selection(database,product_id,ev['exact_photo_assets'],mode='exact')
 if 4 in stages and ev.get('model_category') and ev.get('exact_photo_assets'):
  from .photo_metadata import inspect_saved_photo
  for photo in jobs.get_photo_candidates(database,product_id):
   if photo['asset_key'] not in ev['exact_photo_assets']:continue
   try:
    measured=inspect_saved_photo(photo['url'],photo['source_key'],Path(database).parent/'apple_image_fetch.json',full_verification=True,save_dir=Path(database).parent/'official_images')
    from .photo_inventory import persist_measurement
    persist_measurement(database,product_id,photo,measured)
    ev.setdefault('photos',[]).append(dict(url=photo['url'],asset_key=photo['asset_key'],official_color=ev['configuration_fields'].get('color',''),relation=ev.get('photo_scope','exact model/color')))
    ev.setdefault('photo_measurements',[]).append(dict(url=photo['url'],**measured))
    trace(dict(timestamp=utc_now(),event='apple_photo_verified',url=photo['url'],reason='Actual image bytes decoded',accepted=True,**measured))
   except ValueError as exc:trace(dict(timestamp=utc_now(),event='apple_photo_verification_failed',url=photo['url'],reason=str(exc),accepted=False))
  card_evidence.save(database,product_id,'apple',ev)
 if 3 in stages:jobs.resolve_product(database,product_id)
 ready=card_readiness(database,product_id)
 trace(dict(timestamp=utc_now(),event='readiness_failed' if ready['blocking_gaps'] else 'readiness_passed',reason=', '.join(ready['blocking_gaps']) or 'Specs, configuration and exact photo relations sufficient',discovery_status=ev['discovery_status'],accepted=not ready['blocking_gaps']))
 if ready['blocking_gaps']:
  dealer=(dns_adapter_factory or (lambda:DnsAdapter(fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand='Apple',name=product.get('name') or article,missing_fields=ready['blocking_gaps'])
  ev['dealer_fallback']={'url':dealer.url,'status':dealer.match_level,'accepted':False,'reason':dealer.error or dealer.evidence,'scope':'Unresolved commercial configuration; dealer must be reviewed separately'};card_evidence.save(database,product_id,'apple',ev)
  trace({'timestamp':utc_now(),'event':'apple_dealer','provider':'dns','query':article,'url':dealer.url,'region':'ru','source_type':'dealer','accepted':False,'reason':dealer.error or dealer.evidence,'identity_relation':'unproven'})
 status='error' if not doc.url and doc.error and ev['discovery_status']=='discovery_not_started' else 'done' if ready['verdict']=='export_ready' else 'needs_review'
 jobs.finish(database,job_id,status,'Apple: '+('Готова' if ready['verdict']=='export_ready' else ev['discovery_status'] if ev['discovery_status']!='discovery_completed' else 'readiness_failed')+'; '+', '.join(ready['blocking_gaps']))
