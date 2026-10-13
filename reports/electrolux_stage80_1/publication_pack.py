"""Minimise public SSR fields without losing historical product evidence."""
import sys,json,re,hashlib,subprocess
from pathlib import Path
from bs4 import BeautifulSoup
ROOTS=[Path('reports')/x for x in ('electrolux_stage79','electrolux_stage80','electrolux_stage80_1')]
R=ROOTS[-1];pattern=re.compile(r'("(?:cookie|clientIpAddress)"\s*:\s*)"(?:\\.|[^"\\])*"',re.I)
def sanitize(text):
 text,n=pattern.subn(lambda m:m[1]+'"[redacted]"',text)
 if 'self.__next_f.push' in text:
  for script in BeautifulSoup(text,'html.parser').select('script'):
   old=script.get_text();match=re.fullmatch(r'self\.__next_f\.push\((\[.*\])\)',old,re.S)
   if not match:continue
   try:chunk=json.loads(match[1])
   except ValueError:continue
   if len(chunk)!=2 or chunk[0]!=1 or not isinstance(chunk[1],str):continue
   new,hits=pattern.subn(lambda m:m[1]+'"[redacted]"',chunk[1])
   if hits:chunk[1]=new;text=text.replace(old,'self.__next_f.push('+json.dumps(chunk,ensure_ascii=False)+')',1);n+=hits
 return text,n
updates=json.loads((R/'publication_amendments.json').read_text(encoding='utf8'))['files'] if (R/'publication_amendments.json').exists() else [];mapping={}
for root in ROOTS:
 for p in root.rglob('*.html'):
  raw=p.read_bytes();changed,n=sanitize(raw.decode('utf8'))
  if changed.encode()!=raw:
   old=hashlib.sha256(raw).hexdigest();stored=changed.encode();new=hashlib.sha256(stored).hexdigest();p.write_bytes(stored)
   entry={'file':str(p),'previous_stored_sha256':old,'stored_sha256':new,'redacted_fields':['cookie','clientIpAddress'],'matches':n};updates.append(entry);mapping[old]=entry
def amend(x):
 if isinstance(x,dict):
  if x.get('sha256') in mapping:
   e=mapping[x['sha256']];x.setdefault('original_response_sha256',x['sha256']);x['sha256']=e['stored_sha256'];x['redactions']=sorted(set(x.get('redactions',[])+e['redacted_fields']))
  return {k:'[redacted]' if k.lower() in {'cookie','clientipaddress'} and v not in (None,'','[redacted]') else amend(v) for k,v in x.items()}
 if isinstance(x,list):return [amend(v) for v in x]
 if isinstance(x,str):return sanitize(x)[0]
 return x
for root in ROOTS:
 for p in root.rglob('*.json'):
  if p.name in {'evidence_manifest.json','publication_amendments.json','committed_artifact_manifest.json'}:continue
  try:x=json.loads(p.read_text(encoding='utf-8-sig'))
  except (ValueError,UnicodeError):continue
  y=amend(x)
  if y!=x or mapping:p.write_text(json.dumps(y,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
sys.path.insert(0,str(Path.cwd()))
from product_tool.electrolux_page import parse,revision_owner,media_asset
checks=[]
for root in ROOTS:
 for phase in ('release_live','release_stability'):
  for file in (root/phase).glob('*/result.json'):
   row=json.loads(file.read_text(encoding='utf8'));ev=row['evidence'];inp=row['input']
   if not ev.get('live_success'):continue
   url=next(s['url'] for s in row['sources'] if s['source_key']=='electrolux');cap=next(c for c in ev['captures'] if c['url']==url)
   _,check=parse((file.parent/'captures'/cap['file']).read_text(encoding='utf8'),url,inp['model'],inp['input_pnc'] or '',inp['region'],inp['input_color'] or '',ev['identity'].get('catalog_relations',[]))
   extra={'revision_inventory_relation','requested_revision_identity_confirmed','requested_revision_source','requested_revision','requested_pnc_relation'}
   assert check['identity']=={k:v for k,v in ev['identity'].items() if k not in extra},file
   for kind in ('accepted_facts','rejected_facts'):
    assert len(check[kind])==len(ev[kind]),(file,kind)
    assert all({k:new[k] for k in old}==old for old,new in zip(ev[kind],check[kind])),(file,kind)
   checks.append({'file':str(file),'native_identity_and_fact_acceptance_unchanged':True})
(R/'publication_amendments.json').write_text(json.dumps({'privacy_fields_only':True,'files':updates,'fact_checks':checks},indent=2)+'\n',encoding='utf8',newline='\n')
for root in ROOTS:
 files=[p for p in root.rglob('*') if p.is_file() and p.suffix not in {'.sqlite3','.sqlite','.db','.xlsx'} and '__pycache__' not in p.parts and p.name not in {'evidence_manifest.json','committed_artifact_manifest.json'}]
 (root/'evidence_manifest.json').write_text(json.dumps({'scope':'Local evidence manifest; PDFs/logs may be Git-ignored, see committed_artifact_manifest for publication set','entries':[{'file':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]},indent=2)+'\n',encoding='utf8',newline='\n')
files=[str(p).replace(chr(92),'/') for root in ROOTS for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='committed_artifact_manifest.json']
ignored=subprocess.run(['git','check-ignore','-z','--stdin'],input=b'\0'.join(p.encode() for p in files)+b'\0',capture_output=True)
assert ignored.returncode in (0,1),ignored.stderr
excluded={p.decode() for p in ignored.stdout.split(b'\0') if p}
files=[p for p in files if p not in excluded]
(R/'committed_artifact_manifest.json').write_text(json.dumps({'scope':'Git publication set only; excludes private runtime/profile/DB, local PDF/log/export files by existing ignore rules','entries':[{'file':p,'bytes':Path(p).stat().st_size,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in sorted(files)]},indent=2)+'\n',encoding='utf8',newline='\n')
print({'additional_privacy_redactions':len(updates),'historical_and_current_fact_checks':len(checks),'publishable_files':len(files)})
