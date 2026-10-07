from pathlib import Path
from urllib.parse import quote,urljoin
import json,requests
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
r=Path('reports/jbl_stage63');s=PolicyAwareSession(r/'native_search_fetch.json',allowed_hosts=('jbl.com',),underlying=BinarySafeSession(requests.Session()));out=[]
for n,q in enumerate(['Xtreme 4','Bar 500']):
 u='https://id.jbl.com/en/search?q='+quote(q);z=s.get(u,timeout=12);p=r/f'native_search_{n}.html';p.write_text(z.text,encoding='utf-8');b=BeautifulSoup(z.text,'html.parser');links=[urljoin(z.url,a['href']) for a in b.select('a[href]') if any(t in a['href'].upper() for t in ['XTREME-4','BAR-500-'])];x={'query':q,'url':z.url,'status':z.status_code,'marker':z.marker,'file':p.name,'observed_links':list(dict.fromkeys(links))};out.append(x);print(x,flush=True)
(r/'native_search_probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
