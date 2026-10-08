"""Measure real bytes of selected own assets with the shared decoder/transport."""
import hashlib,json
from pathlib import Path
import requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession,document_bytes
from product_tool.photo_metadata import image_dimensions,MAX_IMAGE_BYTES
R=Path('reports/playstation_stage67');source=json.loads((R/'live_final.json').read_text(encoding='utf-8'))
s=PolicyAwareSession(R/'photo_http.json',allowed_hosts=('playstation.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=MAX_IMAGE_BYTES,min_interval_seconds=2)
out=[]
for row in source['results']:
 for p in row['photos']:
  if not p['selected']:continue
  u=p['url'];record=dict(article=row['input']['search_code'],url=u,source_key=p['source_key'],asset_key=p['asset_key'])
  try:
   z=s.get(u,timeout=10);data=document_bytes(z);dims=image_dimensions(data)
   if z.status_code!=200 or z.truncated or not dims:raise ValueError(f'HTTP {z.status_code}, truncated={z.truncated}, valid_image={bool(dims)}')
   w,h,fmt=dims;file='photo_'+hashlib.sha256(u.encode()).hexdigest()[:20]+'.'+fmt.lower();(R/file).write_bytes(data)
   record.update(file=file,width=w,height=h,size_bytes=len(data),format=fmt,sha256=hashlib.sha256(data).hexdigest())
   print(record['article'],w,h,len(data),fmt,flush=True)
  except Exception as e:record['error']=str(e);print(record['article'],record['error'],flush=True)
  out.append(record);(R/'photo_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(not x.get('error') for x in out)
