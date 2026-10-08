"""Apple audit integration reuses worker jobs, evidence, normalization and DNS."""
import time
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
 cat=MODELS.get(ev.get('model_key'),('','','',''))[2];config=ev.get('configuration_fields',{})
 required={'iphone':('storage','color'),'ipad':('storage','color','connectivity'),'mac':('storage','memory','gpu','color'),'watch':('case_size','connectivity','material','color'),'airpods':()}.get(cat,())
 if any(not config.get(field) for field in required):gaps.append('required_configuration_override_missing')
 confirmed=[x for x in facts if (x['full_sku_confirmed'] or x['status']=='model_confirmed_official') and not x['conflict']]
 if len(confirmed)<5:gaps.append('specifications_missing')
 if not any(x['selected'] and x['asset_key'] in ev.get('exact_photo_assets',[]) for x in jobs.get_photo_candidates(database,product_id)):gaps.append('exact_variant_photo_missing')
 if jobs.result_counts(database,product_id)['conflicts']:gaps.append('conflicts')
 return {'verdict':'not_ready' if gaps else 'export_ready','blocking_gaps':gaps,'advisory_gaps':['manual_unverified'] if ev.get('manual_status')!='Проверена' else [],'identity':ev.get('identity',{}),'manual_status':ev.get('manual_status','Не проверена'),'confirmed_specs':len(confirmed),'model_specs':sum(x['status']=='model_confirmed_official' for x in confirmed),'configuration_fields':ev.get('configuration_fields',{})}

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
 discovery_trace.initialize(database);trace=lambda e:discovery_trace.record(database,job_id,product_id,e)
 adapter=(adapter_factory or (lambda:AppleAdapter(fetch_log_path=Path(database).parent/'apple_fetch.json',trace_callback=trace,clock=clock)))();article=product['search_code'];doc=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+90)
 jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
 model=getattr(adapter,'model_document',None)
 if model:jobs.save_source_document(database,product_id,model,update_description=False,update_attributes=3 in stages,update_photos=4 in stages)
 ev=adapter.reports.get(article.upper(),{});card_evidence.save(database,product_id,'apple',ev)
 if 4 in stages and ev.get('exact_photo_assets'):jobs.set_photo_selection(database,product_id,ev['exact_photo_assets'],mode='exact')
 if 3 in stages:jobs.resolve_product(database,product_id)
 ready=card_readiness(database,product_id)
 if ready['blocking_gaps']:
  dealer=(dns_adapter_factory or (lambda:DnsAdapter(fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand='Apple',name=product.get('name') or article,missing_fields=ready['blocking_gaps'])
  ev['dealer_fallback']={'url':dealer.url,'status':dealer.match_level,'accepted':False,'reason':dealer.error or dealer.evidence,'scope':'Unresolved commercial configuration; dealer must be reviewed separately'};card_evidence.save(database,product_id,'apple',ev)
  trace({'timestamp':utc_now(),'event':'apple_dealer','provider':'dns','query':article,'url':dealer.url,'region':'ru','source_type':'dealer','accepted':False,'reason':dealer.error or dealer.evidence,'identity_relation':'unproven'})
 jobs.finish(database,job_id,'error' if not doc.url and doc.error else 'done' if ready['verdict']=='export_ready' else 'needs_review','Apple: '+('Готова' if ready['verdict']=='export_ready' else 'Не готова')+'; '+', '.join(ready['blocking_gaps']))
