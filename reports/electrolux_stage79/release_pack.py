"""Public evidence: explicit cookie/IP redactions, intact product relations."""
import json,re,hashlib,sys
from pathlib import Path
R=Path(__file__).parent
pattern=re.compile(r'("(?:cookie|clientIpAddress)"\s*:\s*)"(?:\\.|[^"\\])*"',re.I)
redactions=json.loads((R/'redactions.json').read_text())['files'] if (R/'redactions.json').exists() else [];mapping={}
for p in R.rglob('*.html'):
 raw=p.read_bytes();changed,n=pattern.subn(lambda m:m[1]+'"[redacted]"',raw.decode('utf8'))
 if changed.encode()!=raw:
  stored=changed.encode();old=hashlib.sha256(raw).hexdigest();new=hashlib.sha256(stored).hexdigest();p.write_bytes(stored);entry={'file':str(p.relative_to(R)),'original_response_sha256':old,'stored_sha256':new,'redacted_fields':['cookie','clientIpAddress'],'matches':n};redactions.append(entry);mapping[old]=entry
def amend(x):
 if isinstance(x,dict):
  if x.get('sha256') in mapping:
   e=mapping[x['sha256']];x.update(original_response_sha256=x['sha256'],sha256=e['stored_sha256'],redactions=e['redacted_fields'])
  return {k:amend(v) for k,v in x.items()}
 if isinstance(x,list):return [amend(v) for v in x]
 if isinstance(x,str):return pattern.sub(lambda m:m[1]+'"[redacted]"',x)
 return x
for p in R.rglob('*.json'):
 if p.name=='redactions.json':continue
 try:x=json.loads(p.read_text(encoding='utf-8-sig'))
 except (ValueError,UnicodeError):continue
 before=json.dumps(x,ensure_ascii=False,sort_keys=True);y=amend(x)
 if before!=json.dumps(y,ensure_ascii=False,sort_keys=True):p.write_bytes((json.dumps(y,ensure_ascii=False,indent=2)+'\n').encode())
(R/'redactions.json').write_bytes((json.dumps({'scope':'Stage 79 public SSR cookie/IP only; original response and sanitized stored hashes retained','files':redactions},indent=2)+'\n').encode())
sys.path.insert(0,str(R.resolve().parents[1]))
from product_tool.electrolux_page import parse,revision_owner,media_asset
for phase in ['affected_final','qualified_live','stability_live','revision_final','release_live','release_stability']:
 for file in (R/phase).glob('*/result.json'):
  row=json.loads(file.read_text(encoding='utf8'));ev=row['evidence'];inp=row['input']
  if not ev.get('live_success'):continue
  url=next(s['url'] for s in row['sources'] if s['source_key']=='electrolux');capture=next(p for p in ev['captures'] if p['url']==url)
  _,check=parse((file.parent/'captures'/capture['file']).read_text(encoding='utf8'),url,inp['model'],inp['input_pnc'] or '',inp['region'],inp['input_color'] or '',ev['identity'].get('catalog_relations',[]))
  assert check['identity']=={k:v for k,v in ev['identity'].items() if k not in {'revision_inventory_relation','requested_revision_identity_confirmed','requested_revision_source','requested_revision','requested_pnc_relation'}},inp['id']
  assert check['accepted_facts']==ev['accepted_facts'],inp['id']
  if ev.get('requested_revision',{}).get('confirmed'):
   revision=ev['requested_revision'];proof=next(c for c in ev['captures'] if c['url']==revision['url']);owner=revision_owner((file.parent/'captures'/proof['file']).read_text(encoding='utf8'),revision['url'],inp['model'],inp['input_pnc']);assert owner['confirmed'] and owner['pnc']==revision['pnc']
   for g in ev['gallery_inventory']:
    if g.get('revision_owner_image'):assert media_asset(g['url'])==media_asset(owner['gallery'][0]['url'])
private={'.sqlite3','.sqlite','.db','.xlsx'}
files=[p for p in R.rglob('*') if p.is_file() and p.suffix not in private and '__pycache__' not in p.parts and p.name!='evidence_manifest.json']
if (R/'Electrolux_Stage79.xlsx').exists():files.append(R/'Electrolux_Stage79.xlsx')
(R/'evidence_manifest.json').write_bytes((json.dumps({'stage':79,'public_artifacts_only':True,'excluded':'runtime SQLite/input XLSX/persistent profiles/cookie values','entries':[{'file':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]},indent=2)+'\n').encode())
print({'files':len(files),'redacted_html':len(redactions),'qualified_product_facts_and_identity_unchanged':True})
