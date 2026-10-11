"""Public evidence only; preserve hashes and explicitly record privacy redactions."""
import json,re,hashlib,subprocess
from pathlib import Path
R=Path(__file__).parent
pattern=re.compile(r'("(?:cookie|clientIpAddress)"\s*:\s*)"(?:\\.|[^"\\])*"',re.I)
redactions=json.loads((R/'redactions.json').read_text(encoding='utf8'))['files'] if (R/'redactions.json').exists() else []
mapping={}
for p in R.rglob('*.html'):
 raw=p.read_bytes();text=raw.decode('utf8');changed,n=pattern.subn(lambda m:m[1]+'"[redacted]"',text)
 if n and changed.encode('utf8')!=raw:
  stored=changed.encode('utf8');old=hashlib.sha256(raw).hexdigest();new=hashlib.sha256(stored).hexdigest();p.write_bytes(stored);entry={'file':str(p.relative_to(R)),'original_response_sha256':old,'stored_sha256':new,'redacted_fields':['cookie','clientIpAddress'],'matches':n};redactions.append(entry);mapping[old]=entry
def amend(x):
 if isinstance(x,dict):
  if x.get('sha256') in mapping:
   record=mapping[x['sha256']];x['original_response_sha256']=x['sha256'];x['sha256']=record['stored_sha256'];x['redactions']=record['redacted_fields']
  return {k:amend(v) for k,v in x.items()}
 if isinstance(x,list):return [amend(v) for v in x]
 if isinstance(x,str):return pattern.sub(lambda m:m[1]+'"[redacted]"',x)
 return x
for p in R.rglob('*.json'):
 if p.name=='redactions.json':continue
 raw=p.read_bytes()
 try:x=json.loads(raw.decode('utf-8-sig'))
 except (ValueError,UnicodeError):continue
 original=json.dumps(x,ensure_ascii=False,sort_keys=True);y=amend(x)
 if original!=json.dumps(y,ensure_ascii=False,sort_keys=True):p.write_bytes((json.dumps(y,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
(R/'redactions.json').write_bytes((json.dumps({'scope':'new Stage 78 public HTML/SSR only; cookie/IP values removed, product data unchanged','files':redactions},indent=2)+'\n').encode('utf8'))
# Verify every final accepted fact/document identity remains identical after redaction.
import sys
sys.path.insert(0,str(R.resolve().parents[1]))
from product_tool.electrolux_page import parse
for file in (R/'qualified_live').glob('*/result.json'):
 row=json.loads(file.read_text(encoding='utf8'));ev=row['evidence'];inp=row['input']
 if not ev.get('live_success'):continue
 url=next(s['url'] for s in row['sources'] if s['source_key']=='electrolux')
 capture=next(p for p in ev['captures'] if p['url']==url)
 doc,check=parse((file.parent/'captures'/capture['file']).read_text(encoding='utf8'),url,inp['model'],inp['input_pnc'] or '',inp['region'],inp['input_color'] or '')
 assert check['identity']==ev['identity'],inp['id']
 assert check['accepted_facts']==ev['accepted_facts'],inp['id']
private={'.sqlite3','.sqlite','.db','.xlsx'}
files=[p for p in R.rglob('*') if p.is_file() and p.suffix not in private and '__pycache__' not in p.parts and p.name!='evidence_manifest.json']
files.append(R/'Electrolux_Stage78.xlsx')
manifest={'stage':78,'public_artifacts_only':True,'excluded':'runtime SQLite/input workbooks/profile/cookie values','entries':[{'file':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
(R/'evidence_manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf8'));print({'files':len(files),'redacted_html':len(redactions),'all_final_product_facts_and_identity_unchanged':True})
