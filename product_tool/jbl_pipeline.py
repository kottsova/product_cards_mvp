"""JBL uses shared persistence, normalization, evidence and dealer fallback."""
from pathlib import Path
import time
from . import jobs,card_evidence,discovery_trace
from .adapters.jbl import JBLAdapter
from .adapters.dns import DnsAdapter
from .adapters.policy_session import RequestBudget,request_budget
from .adapters.common import utc_now
GAPS={'exact_sku_missing':'Точный артикул не подтверждён','specifications_missing':'Нет подтверждённых характеристик','gallery_missing':'Нет выбранного фото точного варианта','manual_unverified':'Русская пользовательская инструкция не подтверждена','conflicts':'Конфликты характеристик требуют проверки'}
VERDICTS={'not_ready':'Не готова','export_ready_with_gaps':'Готова с пробелами','export_ready':'Готова'}
def photo_verified(photo,evidence):return bool(evidence and photo['asset_key'] in evidence.get('exact_photo_assets',[]) and photo['kind']=='product_gallery')
def document_verified(doc,evidence):return bool(evidence and doc['direct_url'] in evidence.get('verified_documents',[]))
def card_readiness(database,product_id):
 ev=card_evidence.load(database,product_id,'jbl') or {};sources=jobs.get_source_pages(database,product_id)
 exact=any(s['source_key']=='jbl' and s['match_level']=='full_sku' and not s['error'] for s in sources)
 facts=[x for x in jobs.get_resolved(database,product_id) if x['full_sku_confirmed'] and not x['conflict']];conflicts=jobs.result_counts(database,product_id)['conflicts'];gaps=[]
 if not exact:gaps.append('exact_sku_missing')
 if not facts:gaps.append('specifications_missing')
 if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('gallery_missing')
 if ev.get('manual_status')!='Проверена' or not any(document_verified(d,ev) and d['language']=='Русский' for d in jobs.get_documents(database,product_id)):gaps.append('manual_unverified')
 if conflicts:gaps.append('conflicts')
 basics=exact and bool(facts) and 'gallery_missing' not in gaps
 return {'verdict':'not_ready' if not basics else 'export_ready_with_gaps' if gaps else 'export_ready','gaps':gaps,'blocking_gaps':gaps,'exact_identity':exact,'confirmed_specs':len(facts),'conflicts':conflicts,'manual_status':ev.get('manual_status','Не проверена')}
def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
 discovery_trace.initialize(database);trace=lambda event:discovery_trace.record(database,job_id,product_id,event)
 adapter=(adapter_factory or (lambda:JBLAdapter(clock=clock,fetch_log_path=Path(database).parent/'jbl_fetch_log.json',trace_callback=trace)))();adapter.trace_callback=trace;article=product['search_code'].strip().upper()
 budget=RequestBudget(max_per_row=18,max_total=18);budget.begin_row(str(product_id))
 prior={p['asset_key'] for p in jobs.get_photo_candidates(database,product_id)}
 with request_budget(budget):
  doc=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+65)
  jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
  ev=adapter.reports.get(article,{})
  if 6 in stages:jobs.save_documents(database,product_id,'jbl',adapter.find_documents(doc,article))
 card_evidence.save(database,product_id,'jbl',ev)
 if 4 in stages:
  new=[p for p in ev.get('exact_photo_assets',[]) if p not in prior]
  if new:jobs.set_photo_selection(database,product_id,[p['asset_key'] for p in jobs.get_photo_candidates(database,product_id) if p['selected']]+new,mode='exact')
 if 3 in stages:jobs.resolve_product(database,product_id)
 jobs.progress(database,job_id,1,doc.error or doc.evidence,source_url=doc.url)
 gaps=card_readiness(database,product_id)['gaps']
 if gaps:
  dns=(dns_adapter_factory or (lambda:DnsAdapter(clock=clock,fetch_log_path=Path(database).parent/'dns_fetch_log.json')))()
  dealer=dns.find_source(article,deadline=clock()+10,model_tokens=[article],brand='JBL',name=product.get('name') or article,missing_fields=gaps)
  accepted=dealer.match_level=='model_and_code_confirmed' and not dealer.error and dealer.found_model.strip().upper()==article
  ev['dealer_fallback']={'url':dealer.url,'status':dealer.match_level,'accepted':accepted,'reason':dealer.error or dealer.evidence}
  if accepted:jobs.save_source_document(database,product_id,dealer,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages);jobs.resolve_product(database,product_id)
  trace({'event':'jbl_dealer','timestamp':utc_now(),'provider':'dns','query':article,'url':dealer.url,'region':'ru','source_type':'dealer','accepted':accepted,'reason':dealer.error or dealer.evidence,'identity_relation':'exact_sku' if accepted else 'unknown'})
 card_evidence.save(database,product_id,'jbl',ev);ready=card_readiness(database,product_id);status='done' if ready['exact_identity'] and not ready['conflicts'] else 'needs_review';jobs.finish(database,job_id,status,f"JBL: {VERDICTS[ready['verdict']]}. "+'; '.join(GAPS[g] for g in ready['gaps']))
