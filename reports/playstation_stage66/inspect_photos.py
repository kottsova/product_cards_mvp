"""Measure and save only selected exact official gallery assets."""
import hashlib,json,requests
from pathlib import Path
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession,document_bytes
from product_tool.photo_metadata import image_dimensions
r=Path('reports/playstation_stage66');x=json.loads((r/'release_acceptance.json').read_text(encoding='utf-8'));s=PolicyAwareSession(r/'photo_http.json',allowed_hosts=('playstation.com',),underlying=BinarySafeSession(requests.Session()),min_interval_seconds=5,max_bytes=8000000);out=[]
for product in x['results']:
    for p in product['photos']:
        if not p['selected']:continue
        z=s.get(p['url'],timeout=10);assert z.ok and not z.truncated;data=document_bytes(z);m=image_dimensions(data);assert m
        name='photo_'+hashlib.sha256(p['url'].encode()).hexdigest()[:20]+'.'+m[2].lower();(r/name).write_bytes(data)
        out.append(dict(article=product['input']['search_code'],url=p['url'],width=m[0],height=m[1],format=m[2],size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),file=name));print(name,m,len(data),flush=True)
(r/'photo_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
