from pathlib import Path
import json,hashlib,requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
from product_tool.photo_metadata import image_dimensions
r=Path('reports/apple_stage64');d=json.loads((r/'final_acceptance.json').read_text(encoding='utf-8'));s=PolicyAwareSession(r/'photo_fetch.json',allowed_hosts=('cdn-apple.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=8000000);out=[]
for row in [d['baseline']]+d['results']:
 if not row['photos']:continue
 for n,photo in enumerate([x for x in row['photos'] if x['selected']],1):
  previous={x['url']:x for x in json.loads((r/'photo_inspection.json').read_text(encoding='utf-8'))} if (r/'photo_inspection.json').exists() else {}
  if photo['url'] in previous and previous[photo['url']].get('file'):
   out.append(previous[photo['url']]);continue
  z=s.get(photo['url'],timeout=10)
  if not z.ok:out.append({'article':row['article'],'url':photo['url'],'status':z.status_code,'marker':z.marker});continue
  raw=z.text.encode('latin-1');size=image_dimensions(raw);file='photo_'+row['article'].replace('/','_')+'_'+str(n)+('.png' if size[2]=='PNG' else '.jpg');(r/file).write_bytes(raw);out.append({'article':row['article'],'url':photo['url'],'file':file,'status':200,'bytes':len(raw),'dimensions':size,'sha256':hashlib.sha256(raw).hexdigest()});print(row['article'],n,size,flush=True)
(r/'photo_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
