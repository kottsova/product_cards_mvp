"""Audit ordinary UI import separately from live readiness and offline tests."""
import json,hashlib
from pathlib import Path
out=Path(__file__).parent;root=out.resolve().parents[1]
load=lambda p:json.loads((out/p).read_text(encoding='utf8'))
batch=load('batch.json');ui=load('ui_final84_retry.json');initial=load('live_initial/summary.json');final=load('live_final84_retry/summary.json')
source=load('input.json');sha=hashlib.sha256((out/'Ordinary_3_columns.xlsx').read_bytes()).hexdigest()
checks={
 'exactly_three_input_columns':len(source['headers'])==3,
 'all_eight_preview_rows_imported':len(batch['products'])==8,
 'no_user_field_edits':ui['user_edits']==0,
 'original_workbook_unchanged':sha==ui['file_sha256']==hashlib.sha256((root/'data/uploads'/(batch['id']+'.xlsx')).read_bytes()).hexdigest(),
 'five_default_production_jobs':len(final)==5,
 'actual_official_data_for_all_five':all(r['specs']>0 and r['sources'] for r in final),
 'models_and_articles_separate':all(r['model'] and r['model']!=r['supplier_article'] for r in final),
 'all_five_cards_ready':sum(r['readiness']=='export_ready' for r in final)==5,
}
examples=[];fingerprints=set()
for row in final:
 detail=load('live_final84_retry/'+str(row['id'])+'.json');p=detail['product'];interpretation=p['input_interpretation'];fingerprints.add(detail['runtime']['source_fingerprint'])
 checks['model_first_'+p['brand']]=p['search_queries'][0]['query']==p['model']
 checks['raw_cells_'+p['brand']]=json.loads(p['original_values_json'])==source['rows'][p['row_number']-2]
 checks['actual_run_'+p['brand']]=detail['observation']=='actual_UI_default_factories_no_provider_injection' and bool(detail['job']['started_at'])
 examples.append(dict(brand=p['brand'],name=p['name'],model=p['model'],category=p['category'],supplier_article=p['supplier_article'],configuration=interpretation['configuration'],search_queries=p['search_queries']))
 if p['brand']=='JBL':
  ev=detail['evidence'];checks['opaque_JBL_article_not_official_sku']=ev['identity']['model_confirmed'] and not ev['identity']['exact_sku'] and not ev['identity']['supplier_sku_confirmed']
  checks['JBL_published_inventory_revalidated']=any(t.get('provider')=='official_master_inventory' and t.get('accepted') for t in detail['trace'])
 if p['brand']=='Apple':
  misses=[t for t in detail['trace'] if t.get('stage')=='configuration_overlay' and t.get('event')=='apple_navigation_end']
  checks['Apple_actual_store_overlay_completed']=any(t.get('accepted') for t in misses) and row['readiness']=='export_ready' and row['photos']>0
checks['single_production_source_fingerprint']=len(fingerprints)==1
ambiguous=batch['products'][-1]['input_interpretation']
checks['ambiguity_not_guessed']=not ambiguous['model'] and ambiguous['fields']['model']['confidence']=='ambiguous' and ambiguous['model_candidates']==['S3WER','S5BB'] and 'color' not in ambiguous['configuration_hints']
regression=load('final_regression.json') if (out/'final_regression.json').exists() else None
if regression:checks['full_regression']=regression['exit_code']==0 and regression['production_tree_unchanged']
assert all(checks.values()),checks
report=dict(stage=84,verdict='PASS' if regression else 'pending_full_regression',scope='three-column import and real production dispatch; card readiness reported separately',checks=checks,input_sha256=sha,batch_id=batch['id'],source_fingerprint=next(iter(fingerprints)),live_official_data='5/5',live_ready='5/5',known_external_limitation='Earlier Apple Store HTTP 503 observations remain preserved; final fresh Store request succeeded and configuration/photo evidence is confirmed. Precise remote cause of historical 503 is unknown.',initial=initial,final=final,examples=examples,regression=regression,offline_tests_are_not_live_evidence=True)
(out/'qualification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(verdict=report['verdict'],checks=len(checks),live_data=report['live_official_data'],ready=report['live_ready'])))
