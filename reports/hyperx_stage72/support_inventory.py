"""Bounded navigation of published support category/topic links; no guessed IDs."""
import sys,json,time,hashlib
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.policy_fetch import PolicyAwareFetcher
from product_tool.census.endpoint_probe import ProbePolicy
R=Path(__file__).parent
index=json.loads((R/'support_census.json').read_text(encoding='utf8'))[0]
root='https://supportcenter.hyperx.com/'
s=BeautifulSoup((R/index['raw_path']).read_text(encoding='utf8'),'html.parser')
f=PolicyAwareFetcher(R/'support_fetch_log.json',policy=ProbePolicy(max_bytes=3_000_000,min_interval_seconds=1))
out=[]
for a in s.select('a[href]'):
 if a.get_text(' ',strip=True) not in {'Headset','Keyboard','Mouse','Microphone','Controller'}:continue
 url=urljoin(root,a['href']);r=f.get(url,allowed_hosts=('supportcenter.hyperx.com',),deadline=time.monotonic()+20)
 html=r.diagnostic_text or '';sha=hashlib.sha256(html.encode()).hexdigest();p=R/'raw'/(sha+'.txt');p.write_text(html,encoding='utf8');bs=BeautifulSoup(html,'html.parser')
 links=[{'title':x.get_text(' ',strip=True),'url':urljoin(url,x['href'])} for x in bs.select('a[href]') if any(t in x['href'] for t in ('/topics/','/articles/'))]
 item={'url':url,'status':r.http_status,'category':a.get_text(' ',strip=True),'raw_path':str(p.relative_to(R)),'links':links}
 out.append(item);(R/'support_inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print(item['category'],r.http_status,links[:8],flush=True)
