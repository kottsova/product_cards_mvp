"""Published support routes and HP part-number evidence; not a discovery success."""
import sys,json,time,hashlib
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.policy_fetch import PolicyAwareFetcher
from product_tool.census.endpoint_probe import ProbePolicy
from product_tool.census.discovery import detect_internal_search
R=Path(__file__).parent
f=PolicyAwareFetcher(R/'support_fetch_log.json',policy=ProbePolicy(max_bytes=3_000_000,min_interval_seconds=1))
out=[]
urls=['https://supportcenter.hyperx.com','https://www.hp.com/us-en/newsroom/press-releases/2023/hyperx-announces-cloud-iii-gaming-headset.html','https://hyperx.com/blogs/press/hyperx-alloy-origins-65-mechanical-gaming-keyboard-now-shipping-with-colorway-customizations']
for url in urls:
 r=f.get(url,allowed_hosts=('supportcenter.hyperx.com','www.hp.com','hyperx.com'),deadline=time.monotonic()+20)
 text=r.diagnostic_text or '';sha=hashlib.sha256(text.encode()).hexdigest();p=R/'raw'/(sha+'.txt');p.write_text(text,encoding='utf8')
 s=BeautifulSoup(text,'html.parser')
 routes=[x.to_dict() for x in detect_internal_search(text,r.final_url or url,allowed_hosts=('supportcenter.hyperx.com','www.hp.com','hyperx.com'))]
 links=[{'title':a.get_text(' ',strip=True),'url':a['href']} for a in s.select('a[href]') if any(x in a['href'].casefold() for x in ('guide','manual','pdf','support','download'))]
 scripts=[{'id':n.get('id'),'type':n.get('type'),'src':n.get('src'),'length':len(n.get_text())} for n in s.select('script')]
 item={'url':url,'final_url':r.final_url,'status':r.http_status,'access':r.access_status.value,'error':r.error,'raw_path':str(p.relative_to(R)),'sha256':sha,'search_routes':routes,'links':links,'scripts':scripts}
 out.append(item);(R/'support_census.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print(url,r.http_status,'routes',len(routes),'links',links[:3],flush=True)
