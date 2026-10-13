"""Electrolux binding over ordinary jobs, normalization, evidence, photos and export."""
import json,time
from pathlib import Path
from . import jobs,card_evidence,discovery_trace,photo_metadata
from .adapters.electrolux import ElectroluxAdapter
from .adapters.dns import DnsAdapter
from .adapters.policy_session import RequestBudget,request_budget
GAPS={'model_missing':'Точная модель не подтверждена','product_relation_partial':'PNC / revision / регион / отделка подтверждены частично','specifications_missing':'Недостаточно официальных характеристик','gallery_missing':'Нет byte-verified фото подходящего варианта','conflicts':'Конфликт значений','manual_unverified':'Инструкция не проверена (не блокирует готовность)'}
GAPS['product_specs_partial']='Revision identity подтверждена; связь технических данных базовой PDP с revision не доказана'
def photo_verified(photo,ev):return photo['asset_key'] in (ev or {}).get('model_gallery_assets',[]) and photo['kind']=='product_gallery'
def document_verified(doc,ev):return doc['direct_url'] in (ev or {}).get('verified_documents',[])
def card_readiness(database,product_id):
 ev=card_evidence.load(database,product_id,'electrolux') or {};i=ev.get('identity',{});g=[]
 facts=[f for f in jobs.get_resolved(database,product_id) if f['selected_source']=='electrolux' and f['status'] in {'model_confirmed_official','full_sku_official'} and not f['conflict']]
 if i.get('model_relation')!='model_confirmed':g.append('model_missing')
 if not i.get('configuration_confirmed'):g.append('product_specs_partial' if i.get('requested_revision_identity_confirmed') else 'product_relation_partial')
 if len(facts)<3:g.append('specifications_missing')
 if not any(p['selected'] and photo_verified(p,ev) for p in jobs.get_photo_candidates(database,product_id)):g.append('gallery_missing')
 conflicts=jobs.result_counts(database,product_id)['conflicts']
 if conflicts:g.append('conflicts')
 advisory=['manual_unverified'] if ev.get('manual_status','Не проверена')=='Не проверена' else []
 return {'verdict':'not_ready' if g else 'export_ready','blocking_gaps':g,'advisory_gaps':advisory,'gaps':g+advisory,'identity':i,'confirmed_specs':len(facts),'manual_status':ev.get('manual_status','Не проверена'),'conflicts':conflicts,'exact_identity':i.get('model_relation')=='model_confirmed','readiness_scope':'published regional product / exact supplied PNC when present'}
def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
 discovery_trace.initialize(database);a=(adapter_factory or (lambda:ElectroluxAdapter(clock=clock,fetch_log_path=Path(database).parent/'electrolux_fetch_log.json')))();a.trace_callback=lambda e:discovery_trace.record(database,job_id,product_id,e)
 article=product['search_code'].strip().upper();original=product.get('original_values',{})
 if not original:
  try:original=json.loads(product.get('original_values_json','{}'))
  except ValueError:original={}
 config=json.loads(product.get('identity_json') or '{}').get('input_configuration',{})
 region=config.get('region') or (original.get('Регион') if isinstance(original,dict) else '') or 'UK'
 color=config.get('color') or (original.get('Цвет') if isinstance(original,dict) else '') or ''
 budget=RequestBudget(max_per_row=24,max_total=24);budget.begin_row(str(product_id))
 a.product_deadline=clock()+150
 if a.browser_session and hasattr(a.browser_session,'trace_callback'):
  a.browser_session.trace_callback=a.trace_callback;a.browser_session.job_context={'job_id':job_id,'product_id':product_id}
 a.trace(provider='timing',source_type='job_start',url='',state='start',product_budget=150,navigation_budget=18,candidate_budget=24,document_budget=12,image_batch_budget=24)
 try:
  with request_budget(budget):
   if a.browser_session and hasattr(a.browser_session,'recover_for_next_product'):a.browser_session.recover_for_next_product()
   with a.stage('discovery',100):doc=a.find_source(article,name=product.get('name',''),category=product.get('category',''),region=region,color=color,deadline=clock()+100)
   ev=a.reports[article]
   with a.stage('persistence'):jobs.save_source_document(database,product_id,doc,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
   if 6 in stages:
    with a.stage('documents',35):documents=a.find_documents(doc,article)
    with a.stage('persistence'):jobs.save_documents(database,product_id,'electrolux',documents)
   else:a.trace(provider='timing',source_type='documents',url='',state='skipped',reason='stage not requested')
   ev['image_measurements']=[];selected=[]
   if 4 in stages:
    gallery=[p for p in ev.get('gallery_inventory',[]) if p['kind']=='product_gallery']
    # Exact-revision owner render takes precedence over unproven base-PDP derivatives.
    gallery=[p for p in gallery if p['eligible']] if ev.get('requested_revision',{}).get('confirmed') else sorted(gallery,key=lambda p:not p['eligible'])
    image_deadline=min(a.product_deadline,clock()+24)
    a.trace(provider='timing',source_type='photos',url='',state='start',budget_seconds=24)
    for photo in gallery[:2]:
     try:
      if clock()>=image_deadline:raise ValueError('Image batch/product budget exhausted')
      transport=a.photo_transport() if a.browser_session else None
      with a.stage('image',min(13,image_deadline-clock())):m=photo_metadata.inspect_saved_photo(photo['url'],'electrolux',a.log,**({'underlying':transport} if transport else {}))
      if m['width']<400 or m['height']<300:raise ValueError('Below unchanged product photo threshold')
      saved=next(p for p in jobs.get_photo_candidates(database,product_id) if p['asset_key']==photo['asset_key'])
      jobs.save_photo_metadata(database,product_id,saved['id'],photo['url'],width=m['width'],height=m['height'],size_bytes=m['size_bytes'],image_format=m['format'])
      if photo['eligible']:selected.append(photo['asset_key'])
      ev['image_measurements'].append({'url':photo['url'],'accepted':True,'identity_confirmed':photo['eligible'],'selection':'confirmed' if photo['eligible'] else 'candidate; identity remains partial',**m})
     except Exception as exc:ev['image_measurements'].append({'url':photo['url'],'accepted':False,'error':str(exc)})
    a.trace(provider='timing',source_type='photos',url='',state='end',budget_exhausted=clock()>=image_deadline)
   else:a.trace(provider='timing',source_type='photos',url='',state='skipped',reason='stage not requested')
   with a.stage('persistence'):
    ev['model_gallery_assets']=selected;jobs.set_photo_selection(database,product_id,selected);card_evidence.save(database,product_id,'electrolux',ev)
    if 3 in stages:jobs.resolve_product(database,product_id)
   r=card_readiness(database,product_id)
   # Common dealer fallback after official identity miss. Never promote a dealer variant
   # into official PNC-scoped facts or replace an available official PDP for optional manual.
   if ev['identity'].get('model_relation')!='model_confirmed' and not ev.get('technical_failure'):
    dealer=(dns_adapter_factory or (lambda:DnsAdapter(clock=clock,fetch_log_path=Path(database).parent/'dns_fetch_log.json')))().find_source(article,deadline=clock()+10,model_tokens=[ev['identity'].get('model','')],brand='Electrolux',name=product.get('name',''),missing_fields=r['blocking_gaps'])
    ev['dealer_fallback']={'url':dealer.url,'accepted':False,'reason':dealer.error or dealer.evidence,'match_level':dealer.match_level};a.trace(query=article,provider='dns',url=dealer.url,source_type='dealer',region='RU',accepted=False,reason=dealer.error or dealer.evidence,identity_relation='candidate_only');card_evidence.save(database,product_id,'electrolux',ev)
   with a.stage('persistence'):
    jobs.finish(database,job_id,'done' if r['exact_identity'] and not r['conflicts'] and not ev.get('technical_failure') else 'needs_review','Electrolux: '+r['verdict']+'; '+('; '.join(GAPS[g] for g in r['gaps']) or 'пробелов нет')+('; '+ev['technical_failure'] if ev.get('technical_failure') else ''))
 finally:
  a.trace(provider='timing',source_type='job_finish',url='',state='end',product_budget_exhausted=clock()>=a.product_deadline)
  a.close()
