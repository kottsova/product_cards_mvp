import sys,json
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.jbl import JBLAdapter
out=Path(__file__).parent;a=JBLAdapter(fetch_log_path=Path('data/jbl_fetch_log.json'));results=[]
for url in ('https://id.jbl.com/','https://global.jbl.com/'):
 z=a.http.get(url,timeout=8);(out/('jbl_root_'+str(len(results))+'.html')).write_text(z.text,encoding='utf8');s=BeautifulSoup(z.text,'html.parser')
 results.append(dict(url=z.url,status=z.status_code,marker=z.marker,forms=[dict(action=f.get('action'),inputs=[dict(name=n.get('name'),placeholder=n.get('placeholder')) for n in f.select('input')]) for f in s.select('form')],links=[dict(url=urljoin(z.url,n['href']),text=n.get_text(' ',strip=True)[:100]) for n in s.select('a[href]') if any(x in str(n).lower() for x in ('520','search','headphones'))][:20]))
(out/'jbl_roots.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(results,ensure_ascii=False),flush=True)
