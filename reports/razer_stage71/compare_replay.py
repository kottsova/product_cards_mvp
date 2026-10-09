"""Offline parser equality on the FINAL live bytes; no live success simulated."""
from pathlib import Path
import json,hashlib
from product_tool.razer_page import parse_page
R=Path(__file__).parent;live=json.loads((R/'live_final.json').read_text(encoding='utf8'));out=[]
for row in live['rows']:
 ev=row['evidence'];p=row['input'];support_identity=None
 for proof in ev['proofs']:
  if '/answers/detail/' not in proof['url']:continue
  raw=(R/'captures'/proof['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['sha256']
  _,sup=parse_page(raw.decode('utf8'),proof['url'],p['search_code'],p['name'],p['category']);support_identity=sup['identity']
 proof=next(x for x in ev['proofs'] if x['url']==ev['source_url']);raw=(R/'captures'/proof['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['sha256']
 _,replay=parse_page(raw.decode('utf8'),proof['url'],p['search_code'],p['name'],p['category'],model_evidence=support_identity)
 keys=('raw_specs','accepted_specs','rejected_specs','photos','exact_photo_assets','identity','retail_relations')
 equality={k:replay.get(k)==ev.get(k) for k in keys};out.append({'id':row['id'],'source_url':proof['url'],'sha256':proof['sha256'],'equality':equality,'equal':all(equality.values())})
result={'provenance':'hash-verified OFFLINE parser comparison against final live DOM; no discovery simulated','rows':out,'all_equal':all(x['equal'] for x in out)}
(R/'replay_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print([(x['id'],x['equal'],[k for k,v in x['equality'].items() if not v]) for x in out]);assert result['all_equal']
