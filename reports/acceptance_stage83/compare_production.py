"""Compare actual UI and direct observations with equal pre-existing evidence."""
import json,hashlib,sys
from pathlib import Path
out=Path(__file__).parent;root=out.parents[1]
batch=json.loads((out/'cross_batch_final.json').read_text(encoding='utf8'))
ui_phase=sys.argv[1] if len(sys.argv)>1 else 'cross_brand_final'
direct_phase=sys.argv[2] if len(sys.argv)>2 else 'direct_shared_history'
result_name=sys.argv[3] if len(sys.argv)>3 else 'production_parity'
results=[]
def facts(x):return sorted((f['source_key'],f['normalized_name'],f['normalized_value'],f['unit']) for f in x['facts'])
def canonical(x):return sorted((r['category_attribute_key'],(r.get('resolved') or {}).get('display_value'),(r.get('resolved') or {}).get('status'),bool((r.get('resolved') or {}).get('conflict'))) for r in x['canonical'])
def sources(x):return sorted((s['source_key'],s['url'],s['found_model'],s['match_level']) for s in x['sources'] if s['url'] and s['source_key'] not in {'dns','sulpak'})
def dispatch(x):return [(t['brand'],t['effective_article'],t['stages']) for t in x['trace'] if t.get('event')=='production_dispatch']
def providers(x):return sorted({t['provider'] for t in x['trace'] if t.get('provider') and t.get('source_type') not in {'manual_inventory','manual','document'}})
for p in batch['products']:
 pid=p['id'];a=json.loads((out/ui_phase/f'{pid}.json').read_text(encoding='utf8'));b=json.loads((out/direct_phase/f'{pid}.json').read_text(encoding='utf8'))
 checks={k:fn(a)==fn(b) for k,fn in dict(dispatch=dispatch,discovery_providers=providers,official_identity=sources,normalized_facts=facts,canonical_output=canonical).items()}
 checks.update(semantic_evidence=a['semantics']==b['semantics'],readiness=a['readiness']==b['readiness'])
 differences={k:dict(ui=fn(a),direct=fn(b)) for k,fn in dict(dispatch=dispatch,discovery_providers=providers,official_identity=sources,normalized_facts=facts,canonical_output=canonical).items() if not checks[k]}
 if not checks['readiness']:differences['readiness']=dict(ui=a['readiness'],direct=b['readiness'])
 row=dict(id=pid,brand=p['brand'],article=p['search_code'],checks=checks,pass_=all(checks.values()),differences=differences,ui_verdict=a['readiness']['verdict'],direct_verdict=b['readiness']['verdict'])
 results.append(row)
result=dict(observation='actual live, default factories, same imported cells and original prior verified evidence; new per-product sources in both DBs',rows=results,passed=all(r['pass_'] for r in results))
(out/(result_name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
initial=json.loads((out/'initial_state.json').read_text(encoding='utf8'))
lg=[e for e in initial['lg'] if e['product']['id'] in {101,109}]
for e in lg:
 p=e['product'];e['product']={k:p[k] for k in ('id','batch_id','row_number','brand','name','search_code','alternate_code','category')}
(out/'original_lg_failure.json').write_text(json.dumps(dict(observation='Actual user DB captured before fixes; unrelated supplier rows/cells omitted',rows=lg),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(passed=result['passed'],rows=[dict(id=r['id'],checks=r['checks'],pass_=r['pass_']) for r in results]),ensure_ascii=False),flush=True)
