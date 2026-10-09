"""Compare independent live A/B and transport-only replay on one source version."""
from pathlib import Path
import hashlib,json
R=Path(__file__).parent
def read(n):return json.loads((R/(n+'.json')).read_text(encoding='utf8'))
def signature(row):
 e=row['evidence'];return dict(verdict=row['readiness']['verdict'],specs=row['readiness']['confirmed_specs'],resolved=row['resolved'],photos=sorted((p['url'],p['source_key'],p['asset_key']) for p in row['photos'] if p['selected']),identity=e['identity'],identifiers=e['identifiers'],configuration_fields=e['configuration_fields'],configuration_scope=e['configuration_scope'],relations=e['identity_relations'],manual_status=e['manual_status'])
a,b,c=[read(n) for n in ('live_final_e','live_final_f','acceptance_release')]
assert a['source_sha256']==b['source_sha256']==c['source_sha256']
assert a['source_sha256']=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product_tool').rglob('*.py')}
comparisons=[]
for x,y,z in zip(a['rows'],b['rows'],c['rows']):
 sx,sy,sz=signature(x),signature(y),signature(z)
 # IDs/timestamps of DB facts are deliberately ignored; selected values/scopes are compared.
 for s,row in zip((sx,sy,sz),(x,y,z)):
  s['resolved']=[{k:v for k,v in f.items() if k not in {'id','created_at','updated_at','checked_at'}} for f in s['resolved']]
  e=row['evidence'];s['relations']=[rel for rel in s['relations'] if rel.get('url') in {e['exact_official_pdp'],e['hardware_official_pdp']} or rel.get('relation','').startswith('Published regional catalog')]
 differences=[k for k in sx if sx[k]!=sy[k] or sx[k]!=sz[k]]
 comparisons.append(dict(row=x['input']['row_number'],live_a=x['readiness'],live_b=y['readiness'],replay=z['readiness'],differences=differences))
out=dict(phases=['live_final_e','live_final_f','acceptance_release'],source_version_identical=True,comparison='Selected facts, photo assets, identities, selected source relations and readiness; timestamps/DB IDs ignored. Unselected candidate relations may differ after bounded retries.',ready_live_a=sum(x['readiness']['verdict']=='export_ready' for x in a['rows']),ready_live_b=sum(x['readiness']['verdict']=='export_ready' for x in b['rows']),ready_replay=sum(x['readiness']['verdict']=='export_ready' for x in c['rows']),elapsed_live_a=a['elapsed_seconds'],elapsed_live_b=b['elapsed_seconds'],rows=comparisons)
(R/'stability.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print([(r['row'],r['differences']) for r in comparisons]);assert all(not r['differences'] for r in comparisons)
