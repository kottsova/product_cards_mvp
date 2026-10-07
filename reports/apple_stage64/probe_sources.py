from pathlib import Path
import json,hashlib
from product_tool.adapters.policy_session import PolicyAwareSession
r=Path('reports/apple_stage64');s=PolicyAwareSession(r/'official_fetch.json',allowed_hosts=('apple.com',));out=[]
urls=['https://www.apple.com/shop/product/fw123ll/a','https://support.apple.com/en-us/122209','https://support.apple.com/en-us/121031','https://support.apple.com/en-us/108044','https://www.apple.com/iphone-16/specs/','https://www.apple.com/shop/buy-iphone/iphone-16','https://support.apple.com/ru-ru/guide/iphone/welcome/ios','https://support.apple.com/ru-ru/guide/macbook-air/welcome/mac','https://www.apple.com/sitemap.xml','https://www.apple.com/robots.txt']
for i,u in enumerate(urls):
 z=s.get(u,timeout=10);x={'url':u,'final_url':z.url,'status':z.status_code,'marker':z.marker}
 if z.ok:
  f=f'official_{i}.html';(r/f).write_text(z.text,encoding='utf-8');x.update(file=f,sha256=hashlib.sha256((r/f).read_bytes()).hexdigest())
 out.append(x);(r/'official_sources.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(x,flush=True)
