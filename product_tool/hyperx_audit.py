"""HyperX evidence gate using common storage and existing three-spec/gallery minimum."""
from . import jobs,card_evidence

def card_readiness(database,product_id):
    ev=card_evidence.load(database,product_id,'hyperx') or {}
    sources=jobs.get_source_pages(database,product_id)
    model=ev.get('model_relation')=='model_confirmed' or any(s['source_key']=='hyperx' and s['match_level']=='exact_variant' and not s['error'] for s in sources)
    facts=[f for f in jobs.get_resolved(database,product_id) if f['selected_source']=='hyperx' and f['status'] in {'model_confirmed_official','full_sku_official'} and not f['conflict'] and f['normalized_name'] not in {'sku','color','layout'}]
    photos=[p for p in jobs.get_photo_candidates(database,product_id) if p['source_key']=='hyperx' and p['selected'] and p['kind']=='product_gallery' and not p['excluded_reason']]
    gaps=[]
    if not model:gaps.append('model_identity_missing')
    if len(facts)<3:gaps.append('specifications_missing')
    if not photos:gaps.append('gallery_missing')
    if ev and ev.get('configuration_relation')!='exact_variant':gaps.append('configuration_unproven')
    conflicts=jobs.result_counts(database,product_id)['conflicts']
    if conflicts:gaps.append('conflicts')
    return {'verdict':'not_ready' if gaps else 'export_ready','gaps':gaps,'blocking_gaps':gaps,'advisory_gaps':['manual_unverified'] if ev.get('manual_status','Не проверена')=='Не проверена' else [],'confirmed_specs':len(facts),'official_facts':len(facts),'exact_identity':model,'identity':{'model':ev.get('model_relation'),'configuration':ev.get('configuration_relation')},'manual_status':ev.get('manual_status','Не проверена'),'conflicts':conflicts}
