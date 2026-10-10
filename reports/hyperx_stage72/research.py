"""Public, bounded policy-aware source census; not a card success/replay."""
import sys,json,time,hashlib
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.policy_fetch import PolicyAwareFetcher
from product_tool.census.endpoint_probe import ProbePolicy
from product_tool.census.sitemap_strategy import robots_sitemap_declarations,parse_catalog_document
from product_tool.fetch_history import latest_source_snapshot
R=Path(__file__).parent
(R/'raw').mkdir(exist_ok=True)
f=PolicyAwareFetcher(R/'research_fetch_log.json',policy=ProbePolicy(max_bytes=3_000_000,min_interval_seconds=1))
index=[]
def get(url):
 r=f.get(url,allowed_hosts=('hyperx.com','www.hyperx.com','uk.hyperx.com','row.hyperx.com','support.hp.com','www.hp.com'),deadline=time.monotonic()+20)
 text=r.diagnostic_text or '';sha=hashlib.sha256(text.encode()).hexdigest();path=R/'raw'/(sha+'.txt');path.write_text(text,encoding='utf8')
 index.append({'url':url,'final_url':r.final_url,'status':r.http_status,'access':r.access_status.value,'raw_path':str(path.relative_to(R)),'sha256':sha,'bytes':len(text.encode())})
 (R/'research_receipts.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf8')
 print(url,r.http_status,len(text),flush=True)
 return text
snapshot=latest_source_snapshot(R/'baseline.sqlite3',1,'hyperx')
if snapshot:(R/'raw'/'baseline.html').write_text(snapshot['content'],encoding='utf8')
root=get('https://hyperx.com/')
robots=get('https://hyperx.com/robots.txt')
maps=robots_sitemap_declarations(robots)
products=[]
for m in maps[:1]:
 kind,locs,cut=parse_catalog_document(get(m),max_urls=3000)
 for child in [u for u in locs if 'products' in u][:2]:
  _,urls,_=parse_catalog_document(get(child),max_urls=3000);products+=urls
(R/'catalog_urls.json').write_text(json.dumps(products,indent=2),encoding='utf8')
get('https://hyperx.com/pages/support')
