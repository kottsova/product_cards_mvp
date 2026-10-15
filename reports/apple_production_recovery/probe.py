import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession
root=Path(__file__).parent
s=PolicyAwareSession(root/'probe_fetch.json',allowed_hosts=('apple.com',))
for n,u in enumerate(['https://www.apple.com/iphone/','https://support.apple.com/en-us/search?query=iPhone%2018%20Pro','https://www.apple.com/shop/buy-iphone/iphone-18-pro']):
 z=s.get(u,timeout=15); (root/f'probe_{n}.html').write_text(z.text,encoding='utf-8'); b=BeautifulSoup(z.text,'html.parser')
 print(json.dumps(dict(url=z.url,status=z.status_code,marker=z.marker,bytes=len(z.content),h1=[x.get_text(' ',strip=True) for x in b.select('h1')],links=[dict(text=a.get_text(' ',strip=True),href=a.get('href')) for a in b.select('a[href]') if any(t in a.get('href','').lower() for t in ('18-pro','148590'))]),ensure_ascii=False))
