"""Lenovo integration with shared jobs, normalization, evidence and resolution."""
from pathlib import Path
import time
from . import jobs,card_evidence,discovery_trace
from .adapters.lenovo import LenovoAdapter
from .adapters.common import utc_now
from .adapters.dns import DnsAdapter
from .adapters.policy_session import RequestBudget,request_budget

def card_readiness(database,product_id):
    evidence=card_evidence.load(database,product_id,'lenovo') or {}
    sources=jobs.get_source_pages(database,product_id)
    exact=any(s['source_key']=='lenovo_support' and s['match_level']=='full_sku' and not s['error'] for s in sources)
    resolved=[r for r in jobs.get_resolved(database,product_id) if r['full_sku_confirmed'] and not r['conflict']]
    conflicts=jobs.result_counts(database,product_id)['conflicts']
    gaps=[]
    if not exact:gaps.append('exact_configuration_not_resolved')
    if not resolved:gaps.append('exact_specifications_missing')
    if not any(photo_verified(p,evidence) for p in jobs.get_photo_candidates(database,product_id)):gaps.append('exact_gallery_not_confirmed')
    if evidence.get('manual_status')!='Проверена':gaps.append('russian_user_guide_not_verified')
    if conflicts:gaps.append('unresolved_conflicts')
    basics=exact and bool(resolved) and 'exact_gallery_not_confirmed' not in gaps
    return {'verdict':'not_ready' if not basics else 'export_ready_with_gaps' if gaps else 'export_ready','gaps':gaps,'blocking_gaps':gaps,'real_conflicts':conflicts,'exact_configuration':exact,'exact_facts':len(resolved),'manual_status':evidence.get('manual_status','Не проверена')}

def photo_verified(photo,evidence):
    # An official family/gallery image alone does not establish color/configuration.
    return bool(evidence and photo['asset_key'] in evidence.get('exact_photo_assets',[]) and photo['kind']=='product_gallery')

def document_verified(document,evidence):
    return bool(evidence and document['direct_url'] in evidence.get('verified_documents',[]))

def run_job(database,job_id,product_id,product,*,stages,adapter_factory=None,dns_adapter_factory=None,clock=time.monotonic):
    discovery_trace.initialize(database)
    trace=lambda event:discovery_trace.record(database,job_id,product_id,event)
    adapter=(adapter_factory or (lambda:LenovoAdapter(clock=clock,fetch_log_path=Path(database).parent/'lenovo_fetch_log.json',trace_callback=trace)))()
    adapter.trace_callback=trace
    article=product['search_code'].strip().upper()
    budget=RequestBudget(max_per_row=14,max_total=14);budget.begin_row(str(product_id))
    with request_budget(budget):
        document=adapter.find_source(article,name=product.get('name',''),category=product.get('category',''),deadline=clock()+75)
    jobs.save_source_document(database,product_id,document,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
    evidence=adapter.reports.get(article,{})
    card_evidence.save(database,product_id,'lenovo',evidence)
    jobs.progress(database,job_id,1,f"Lenovo {article}: {document.match_level}; {document.error or document.evidence}",source_url=document.url,level='warning' if document.match_level!='full_sku' else 'info')
    if 3 in stages:jobs.resolve_product(database,product_id)
    # Stage selection never clears unrequested saved documents.
    if 6 in stages:jobs.save_documents(database,product_id,adapter.source_key,adapter.find_documents(document,article))
    missing=card_readiness(database,product_id)['gaps']
    if missing:
        dns=(dns_adapter_factory or (lambda:DnsAdapter(clock=clock,fetch_log_path=Path(database).parent/'dns_fetch_log.json')))()
        dealer=dns.find_source(article,deadline=clock()+10,model_tokens=[article],brand='Lenovo',name=product.get('name') or article,missing_fields=missing)
        confirmed=dealer.match_level=='model_and_code_confirmed' and not dealer.error and dealer.found_model.strip().upper()==article
        evidence['dealer_fallback']={'url':dealer.url,'status':dealer.match_level,'accepted':confirmed,'reason':dealer.error or dealer.evidence,'identity_relation':'exact_part_number' if confirmed else 'unknown'}
        if confirmed:
            jobs.save_source_document(database,product_id,dealer,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)
            if 3 in stages:jobs.resolve_product(database,product_id)
        trace({'event':'lenovo_dealer','timestamp':utc_now(),'provider':'dns','query':article,'url':dealer.url,'region':'ru','source_type':'dealer','accepted':confirmed,'reason':dealer.error or dealer.evidence,'identity_relation':'exact_part_number' if confirmed else 'unknown'})
    card_evidence.save(database,product_id,'lenovo',evidence)
    ready=card_readiness(database,product_id)
    status='done' if ready['exact_configuration'] and not ready['real_conflicts'] else 'needs_review'
    jobs.finish(database,job_id,status,f"Lenovo {article}: job={status}; card={ready['verdict']}; gaps={', '.join(ready['gaps'])}.")
