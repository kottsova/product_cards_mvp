"""Publishable evidence: cookie/IP redactions, immutable fact verification."""
import json,re,hashlib,sys
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).parent
pattern=re.compile(r'("(?:cookie|clientIpAddress)"\s*:\s*)"(?:\\.|[^"\\])*"',re.I)
redactions=[];mapping={}
for p in R.rglob('*.html'):
 raw=p.read_bytes();changed,n=pattern.subn(lambda m:m[1]+'"[redacted]"',raw.decode('utf8'))
 # Native Flight JSON is quoted once more inside the script argument.
 for script in BeautifulSoup(changed,'html.parser').select('script'):
  old_text=script.get_text();match=re.fullmatch(r'self\.__next_f\.push\((\[.*\])\)',old_text,re.S)
  if not match:continue
  try:chunk=json.loads(match[1])
  except ValueError:continue
  if len(chunk)!=2 or chunk[0]!=1 or not isinstance(chunk[1],str):continue
  updated,hits=pattern.subn(lambda m:m[1]+'"[redacted]"',chunk[1])
  if hits:
   chunk[1]=updated;changed=changed.replace(old_text,'self.__next_f.push('+json.dumps(chunk,ensure_ascii=False)+')',1);n+=hits
 if changed.encode()!=raw:
  stored=changed.encode();old=hashlib.sha256(raw).hexdigest();new=hashlib.sha256(stored).hexdigest();p.write_bytes(stored)
  entry={'file':str(p.relative_to(R)),'original_response_sha256':old,'stored_sha256':new,'redacted_fields':['cookie','clientIpAddress'],'matches':n};redactions.append(entry);mapping[old]=entry
def amend(x):
 if isinstance(x,dict):
  if x.get('sha256') in mapping:
   e=mapping[x['sha256']];x.update(original_response_sha256=x['sha256'],sha256=e['stored_sha256'],redactions=e['redacted_fields'])
  return {k:amend(v) for k,v in x.items()}
 if isinstance(x,list):return [amend(v) for v in x]
 if isinstance(x,str):return pattern.sub(lambda m:m[1]+'"[redacted]"',x)
 return x
for p in R.rglob('*.json'):
 if p.name in {'redactions.json','evidence_manifest.json'}:continue
 try:x=json.loads(p.read_text(encoding='utf-8-sig'))
 except (ValueError,UnicodeError):continue
 y=amend(x)
 if x!=y or mapping:p.write_text(json.dumps(y,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
(R/'redactions.json').write_text(json.dumps({'scope':'Public SSR cookie/IP only; original response and sanitized stored SHA retained','files':redactions},indent=2)+'\n',encoding='utf8',newline='\n')
sys.path.insert(0,str(R.resolve().parents[1]))
from product_tool.electrolux_page import parse,revision_owner,media_asset
checks=[]
for phase in ('control_qualified','release_live','release_stability'):
 for file in (R/phase).glob('*/result.json'):
  row=json.loads(file.read_text(encoding='utf8'));ev=row['evidence'];inp=row['input']
  assert ev['live_success']
  url=next(s['url'] for s in row['sources'] if s['source_key']=='electrolux');cap=next(p for p in ev['captures'] if p['url']==url)
  _,check=parse((file.parent/'captures'/cap['file']).read_text(encoding='utf8'),url,inp['model'],inp['input_pnc'] or '',inp['region'],inp['input_color'] or '',ev['identity'].get('catalog_relations',[]))
  extra={'revision_inventory_relation','requested_revision_identity_confirmed','requested_revision_source','requested_revision','requested_pnc_relation'}
  assert check['identity']=={k:v for k,v in ev['identity'].items() if k not in extra},(phase,inp['id'],'identity')
  assert check['accepted_facts']==ev['accepted_facts'],(phase,inp['id'],'accepted facts')
  assert check['rejected_facts']==ev['rejected_facts'],(phase,inp['id'],'rejected facts')
  if ev.get('requested_revision',{}).get('confirmed'):
   rev=ev['requested_revision'];proof=next(c for c in ev['captures'] if c['url']==rev['url']);owner=revision_owner((file.parent/'captures'/proof['file']).read_text(encoding='utf8'),rev['url'],inp['model'],inp['input_pnc']);assert owner['confirmed'] and owner['pnc']==rev['pnc']
   for g in ev['gallery_inventory']:
    if g.get('revision_owner_image'):assert media_asset(g['url'])==media_asset(owner['gallery'][0]['url'])
  checks.append({'phase':phase,'id':inp['id'],'identity_and_raw_fact_acceptance_unchanged':True})
(R/'redaction_validation.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf8',newline='\n')
private={'.sqlite3','.sqlite','.db','.xlsx'}
files=[p for p in R.rglob('*') if p.is_file() and p.suffix not in private and '__pycache__' not in p.parts and p.name!='evidence_manifest.json']
if (R/'Electrolux_Stage80.xlsx').exists():files.append(R/'Electrolux_Stage80.xlsx')
manifest={'stage':80,'public_artifacts_only':True,'excluded':'runtime DB/input workbooks/persistent profiles/cookie values','entries':[{'file':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
(R/'evidence_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8',newline='\n')
print({'files':len(files),'redacted_html':len(redactions),'qualified_rows_reparsed':len(checks)})
