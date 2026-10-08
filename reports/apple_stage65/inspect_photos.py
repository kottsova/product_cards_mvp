"""Measure public saved official assets; never infer dimensions from URL parameters."""
from pathlib import Path
import json,hashlib,requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
from product_tool.photo_metadata import image_dimensions
r=Path('reports/apple_stage65');x=json.loads((r/'final_acceptance.json').read_text(encoding='utf-8'));session=PolicyAwareSession(r/'photo_http.json',allowed_hosts=('cdn-apple.com','apple.com'),underlying=BinarySafeSession(requests.Session()),max_bytes=8_000_000);out=[]
for row in [x['baseline'],*x['results']]:
 for p in row['photos']:
  if not p['selected']:continue
  z=session.get(p['url'],timeout=10);assert z.ok and not z.truncated,(p['url'],z.marker)
  data=z.text.encode('latin-1');dims=image_dimensions(data);assert dims
  filename='photo_'+hashlib.sha256(p['url'].encode()).hexdigest()[:20]+'.'+dims[2].lower();(r/filename).write_bytes(data)
  out.append(dict(article=row['article'],url=p['url'],file=filename,width=dims[0],height=dims[1],format=dims[2],bytes=len(data),sha256=hashlib.sha256(data).hexdigest()));print(row['article'],dims,flush=True)
(r/'photo_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
