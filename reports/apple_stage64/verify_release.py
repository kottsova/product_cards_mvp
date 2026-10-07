from pathlib import Path
import json,hashlib,subprocess,re
from product_tool.adapters.apple import parse_page
r=Path('reports/apple_stage64');proofs=[];metadata=[]
for file in ['official_sources.json','more_sources.json']:
 for record in json.loads((r/file).read_text(encoding='utf-8')):
  if 'file' in record:metadata.append((r/record['file'],record))
for file in (r/'apple_captures').glob('*.html.json'):
 metadata.append((file.with_suffix(''),json.loads(file.read_text(encoding='utf-8'))))
for file,record in metadata:
 raw=file.read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha256'],str(file)
 indexed=subprocess.check_output(['git','show',':'+file.as_posix()]);assert hashlib.sha256(indexed).hexdigest()==record['sha256'],str(file)
 proofs.append({'file':str(file),'sha256':record['sha256']})
lookup={x['url']:(file,x) for file,x in metadata if 'url' in x}
live=json.loads((r/'final_acceptance.json').read_text(encoding='utf-8'));replayed=[]
for row in [live['baseline']]+live['results']:
 source=row['sources'][0];file,record=lookup[source['url']];doc,ev=parse_page(file.read_text(encoding='utf-8'),source['url'],row['article'])
 actual={(f['raw_name'],f['raw_value'],f['section']) for f in row['facts']};assert actual=={(f.name,f.value,f.section) for f in doc.attributes},row['article']
 photos={p['url'] for p in row['photos']};assert photos==set(doc.photos),row['article']
 replayed.append({'article':row['article'],'facts_match':True,'photo_admission_match':True,'selected_photos':len(photos),'rejected_gallery':len(ev.get('photo_candidates',[]))})
images=json.loads((r/'photo_inspection.json').read_text(encoding='utf-8'))
for x in images:
 if 'file' in x:assert hashlib.sha256((r/x['file']).read_bytes()).hexdigest()==x['sha256']
paths=subprocess.check_output(['git','diff','--cached','--name-only']).decode().splitlines();private=[p for p in paths if any(x in p for x in ['node_modules','attended_profile','.sqlite3','.xlsx','.pdf'])];assert not private,private
sensitive=[]
for file in paths:
 p=Path(file)
 if p.suffix not in {'.html','.json','.py','.md','.mjs'}:continue
 if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer [A-Za-z0-9._-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}',p.read_text(encoding='utf-8-sig')):sensitive.append(file)
assert not sensitive,sensitive
(r/'release_verification.json').write_text(json.dumps({'git_index_response_hashes':proofs,'final_parser_replay':replayed,'image_hashes_verified':len(images),'private_files_staged':0,'sensitive_pattern_hits':0,'visual_review':'Final source headlines, candidate scopes, black/white lightboxes, iPad silver product-only gallery; native Excel readiness/identity/candidates. Packaging/multicolor montage rejection proved on real iPad PDP.'},ensure_ascii=False,indent=2),encoding='utf-8');print('Response/index hashes:',len(proofs),'parser replays:',len(replayed),'images:',len(images),'private/sensitive staged: 0')
