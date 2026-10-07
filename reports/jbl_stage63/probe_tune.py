from pathlib import Path
import requests,json,hashlib
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
r=Path('reports/jbl_stage63');s=PolicyAwareSession(r/'recovery_fetch.json',allowed_hosts=('jbl.com',),underlying=BinarySafeSession(requests.Session()));out=[]
for n,u in enumerate(['https://kh.jbl.com/over-ear-headphones/TUNE520BT.html','https://id.jbl.com/en/over-ear-headphones/JBLT520BTBLK.html','https://ca.jbl.com/en_CA/TUNE520BT.html']):
 z=s.get(u,timeout=12);x={'url':u,'final_url':z.url,'status':z.status_code,'marker':z.marker}
 if z.ok:
  f=f'tune_{n}.html';(r/f).write_text(z.text,encoding='utf-8');x['file']=f;x['sha256']=hashlib.sha256((r/f).read_bytes()).hexdigest();b=BeautifulSoup(z.text,'html.parser');x['sku']=[a.get('content') or a.get_text(strip=True) for a in b.select('[itemprop=sku]')];x['root']=bool(b.select_one('.product-wrapper[data-pid], .product-info.product-detail'))
 out.append(x);print(x,flush=True)
(r/'tune_probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
