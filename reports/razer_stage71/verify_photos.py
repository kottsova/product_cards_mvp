"""Measure real bytes of selected official assets; no guessed image URL transforms."""
import json,hashlib
from pathlib import Path
import requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
from product_tool.photo_metadata import image_dimensions
R=Path(__file__).parent;rows=json.loads((R/'live_final.json').read_text(encoding='utf8'))['rows'];assert len(rows)==10
session=PolicyAwareSession(R/'photo_fetch_log.json',allowed_hosts=('razer.com','razerzone.com'),underlying=BinarySafeSession(requests.Session()),max_bytes=8000000)
out=[];seen={};(R/'photos').mkdir(exist_ok=True)
for row in rows:
 for photo in row['evidence'].get('photos',[]):
  if not photo['verified']:continue
  url=photo['url'];item={'id':row['id'],'url':url,'relation':photo['relation'],'asset_key':photo['asset_key']}
  if url in seen:item.update(seen[url]);out.append(item);continue
  try:
   z=session.get(url,timeout=10);item.update(status=z.status_code,marker=z.marker)
   if z.ok and not z.truncated:
    raw=z.text.encode('latin1');dims=image_dimensions(raw);item.update(sha256=hashlib.sha256(raw).hexdigest(),dimensions=dims,bytes=len(raw),valid_image=bool(dims))
    if dims:
     file=item['sha256']+'.'+dims[2].lower();(R/'photos'/file).write_bytes(raw);item['file']=file
  except Exception as e:item['error']=str(e)[:180]
  seen[url]={k:v for k,v in item.items() if k not in {'id','url','relation','asset_key'}};out.append(item)
  (R/'photo_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(row['id'],item.get('status'),item.get('dimensions'),flush=True)
(R/'photo_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
