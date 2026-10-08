"""Read-only official discovery reconnaissance, no SKU URL seeds."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
import requests

ROOT=Path('reports/playstation_stage67');ROOT.mkdir(exist_ok=True)
def main():
 session=PolicyAwareSession(ROOT/'explore_http.json',allowed_hosts=('playstation.com',),underlying=BinarySafeSession(requests.Session()),min_interval_seconds=2)
 results=[]
 for url in sys.argv[1:]:
  try:
   z=session.get(url,timeout=15);data=z.content
   key=hashlib.sha256(z.url.encode()).hexdigest()[:20]
   (ROOT/'observed').mkdir(exist_ok=True)
   (ROOT/'observed'/(key+'.html')).write_text(z.text,encoding='utf-8')
   b=BeautifulSoup(z.text,'html.parser')
   links=list(dict.fromkeys(urljoin(z.url,a['href']) for a in b.select('a[href]')))
   locs=re.findall(r'<loc>([^<]+)</loc>',z.text)
   out=dict(url=url,returned=z.url,status=z.status_code,bytes=len(data),h1=[x.get_text(' ',strip=True) for x in b.select('h1')],locs=locs,links=links,cfi_context=re.findall(r'.{0,100}CFI-.{0,150}',b.get_text(' ',strip=True)),scripts=[x.get('src') for x in b.select('script[src]')])
   results.append(out);print(json.dumps({k:v for k,v in out.items() if k not in ('links','locs','scripts')},ensure_ascii=False),flush=True)
   print('sitemaps',locs[:8],'relevant links',[x for x in links if any(t in x for t in ('sitemap','buy-','shop-','product/'))][:35],flush=True)
  except Exception as e:results.append(dict(url=url,error=str(e)));print(url,str(e),flush=True)
 (ROOT/'exploration.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
