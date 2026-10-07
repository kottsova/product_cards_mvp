from pathlib import Path
import json,hashlib
from product_tool.adapters.policy_session import PolicyAwareSession
r=Path('reports/apple_stage64');s=PolicyAwareSession(r/'official_fetch.json',allowed_hosts=('apple.com',));out=[]
urls=['https://support.apple.com/en-us/122240','https://support.apple.com/en-us/121202','https://support.apple.com/en-us/121552','https://support.apple.com/en-us/121029','https://support.apple.com/en-us/121204','https://support.apple.com/ru-ru/guide/ipad/welcome/ipados','https://support.apple.com/ru-ru/guide/watch/welcome/watchos','https://support.apple.com/ru-ru/guide/airpods/welcome/web','https://www.apple.com/uk/iphone-16/specs/','https://www.apple.com/iphone/compare/']
for i,u in enumerate(urls):
 z=s.get(u,timeout=10);x={'url':u,'final_url':z.url,'status':z.status_code,'marker':z.marker}
 if z.ok:
  f=f'more_{i}.html';(r/f).write_text(z.text,encoding='utf-8');x.update(file=f,sha256=hashlib.sha256((r/f).read_bytes()).hexdigest())
 out.append(x);(r/'more_sources.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(x,flush=True)
