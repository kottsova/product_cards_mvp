from pathlib import Path
import json,requests,hashlib
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
r=Path('reports/jbl_stage63');r.mkdir(exist_ok=True);s=PolicyAwareSession(r/'probe_fetch.json',allowed_hosts=('jbl.com',),underlying=BinarySafeSession(requests.Session()));out=[]
urls=['https://id.jbl.com/en/over-ear-headphones/TUNE520BT.html','https://id.jbl.com/en/bluetooth-portables/XTREME-4.html','https://id.jbl.com/en/soundbars/BAR-500-.html']
for i,u in enumerate(urls):
 z=s.get(u,timeout=15);x={'url':u,'final_url':z.url,'status':z.status_code,'marker':z.marker}
 if z.ok:
  f=f'probe_{i}.html';(r/f).write_text(z.text,encoding='utf-8');x['file']=f;x['sha256']=hashlib.sha256((r/f).read_bytes()).hexdigest()
 out.append(x);print(x,flush=True)
(r/'probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
