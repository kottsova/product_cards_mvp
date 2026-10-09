"""Razer uses existing jobs, evidence, resolution and dealer fallback."""
from pathlib import Path
import time
from . import jobs,card_evidence,discovery_trace
from .adapters.razer import RazerAdapter
from .adapters.dns import DnsAdapter
from .adapters.policy_session import RequestBudget,request_budget
from .adapters.common import utc_now
GAPS={'model_missing':'Точная модель не подтверждена','specifications_missing':'Недостаточно подтверждённых характеристик','gallery_missing':'Нет фото подтверждённого цвета и раскладки','configuration_missing':'Запрошенная конфигурация не подтверждена','conflicts':'Есть конфликты','manual_unverified':'Русская инструкция не проверена'}
def photo_verified(photo,ev):return bool(ev and photo['asset_key'] in ev.get('exact_photo_assets',[]) and photo['kind']=='product_gallery')
def document_verified(doc,ev):return bool(ev and doc['direct_url'] in ev.get('verified_documents',[]))
def card_readiness(database,product_id):
 ev=card_evidence.load(database,product_id,'razer') or {};i=ev.get('identity',{});facts=[f for f in jobs.get_resolved(database,product_id) if f['status'] in {'model_confirmed_official','configuration_confirmed_official','full_sku_official'} and not f['conflict'] and f['selected_source'].startswith('razer_')];conflicts=jobs.result_counts(database,product_id)['conflicts'];gaps=[]
 if i.get('model_relation')!='model_confirmed':gaps.append('model_missing')
 if len(facts)<3:gaps.append('specifications_missing')
 if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('gallery_missing')
 if ev.get('requested_configuration') and i.get('configuration_relation') not in {'full_sku','configuration_confirmed'}:gaps.append('configuration_missing')
 if conflicts:gaps.append('conflicts')
 if ev.get('manual_status')=='Не проверена':gaps.append('manual_unverified')
 blocking=[g for g in gaps if g!='manual_unverified'];return {'verdict':'not_ready' if blocking else 'export_ready','gaps':gaps,'blocking_gaps':blocking,'advisory_gaps':[g for g in gaps if g not in blocking],'confirmed_specs':len(facts),'identity':i,'exact_identity':i.get('model_relation')=='model_confirmed','conflicts':conflicts,'manual_status':ev.get('manual_status','Не проверена')}
def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
 discovery_trace.initialize(database);trace=lambda e:discovery_trace.record(database,job_id,product_id,{'timestamp':utc_now(),**e})
 adapter=(adapter_factory or (lambda:RazerAdapter(clock=clock,fetch_log_path=Path(database).parent/'razer_fetch_log.json',trace_callback=trace)))();adapter.trace_callback=trace;article=product['search_code'].strip().upper();budget=RequestBudget(max_per_row=24,max_total=24);budget.begin_row(str(product_id))
 with request_budget(budget):
  doc=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+90);jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
  if 6 in stages:jobs.save_documents(database,product_id,doc.source_key,adapter.find_documents(doc,article))
 ev=adapter.reports.get(article,{});card_evidence.save(database,product_id,'razer',ev)
 if 3 in stages:jobs.resolve_product(database,product_id)
 if 4 in stages and ev.get('exact_photo_assets'):jobs.set_photo_selection(database,product_id,ev['exact_photo_assets'],mode='exact')
 r=card_readiness(database,product_id);jobs.progress(database,job_id,1,doc.error or doc.evidence,source_url=doc.url)
 if r['blocking_gaps']:
  dealer=(dns_adapter_factory or (lambda:DnsAdapter(clock=clock,fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[article],brand='Razer',name=product.get('name') or article,missing_fields=r['blocking_gaps'])
  # A dealer must prove the full commercial part, not just a hardware/model prefix.
  from .razer_identity import components
  accepted=components(article)['full_part'] and dealer.match_level=='model_and_code_confirmed' and dealer.found_model.upper()==article and not dealer.error
  ev['dealer_fallback']={'accepted':bool(accepted),'url':dealer.url,'reason':dealer.error or dealer.evidence,'match_level':dealer.match_level};trace({'event':'razer_dealer','provider':'dns','query':article,'url':dealer.url,'region':'ru','source_type':'dealer','accepted':bool(accepted),'reason':dealer.error or dealer.evidence,'identity_relation':'full_sku' if accepted else 'unproven'})
  if accepted:jobs.save_source_document(database,product_id,dealer,update_description=False,update_attributes=3 in stages,update_photos=4 in stages);jobs.resolve_product(database,product_id)
 card_evidence.save(database,product_id,'razer',ev);r=card_readiness(database,product_id);jobs.finish(database,job_id,'done' if r['exact_identity'] and not r['conflicts'] else 'needs_review','Razer: '+('Готова' if r['verdict']=='export_ready' else 'Не готова')+'. '+'; '.join(GAPS[g] for g in r['gaps']))
