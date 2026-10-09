"""Offline parser diagnostics on live_initial captures. Never a live success."""
import json,hashlib
from pathlib import Path
from product_tool.razer_page import parse_page
R=Path(__file__).parent;old=json.loads((R/'live_initial.json').read_text(encoding='utf8'));out=[]
for row in old['rows']:
 inp=row['input'];proofs=row['evidence']['proofs'];support=next((p for p in reversed(proofs) if '/answers/detail/' in p['url']),None);model=None;best=None
 if support:
  d,e=parse_page((R/'captures'/support['file']).read_text(encoding='utf8'),support['url'],inp['search_code'],inp['name'],inp['category']);model=e['identity'];best=(d,e)
 for p in proofs:
  if 'www.razer.com' not in p['url']:continue
  d,e=parse_page((R/'captures'/p['file']).read_text(encoding='utf8'),p['url'],inp['search_code'],inp['name'],inp['category'],model_evidence=model)
  if e['identity']['model_confirmed'] and e.get('retail_relations'):best=(d,e);break
 d,e=best;out.append({'id':row['id'],'attributes':len(d.attributes),'raw':len(e['raw_specs']),'accepted':len(e['accepted_specs']),'rejected':len(e['rejected_specs']),'photos':len(e['exact_photo_assets']),'identity':e['identity'],'relations':e.get('retail_relations',[])});print(row['id'],len(d.attributes),len(e['exact_photo_assets']),e['identity'].get('configuration_relation'))
(R/'offline_preview.json').write_text(json.dumps({'provenance':'offline parser, NOT live','rows':out},ensure_ascii=False,indent=2),encoding='utf8')
