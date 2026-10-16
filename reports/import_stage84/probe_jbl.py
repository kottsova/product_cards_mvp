import sys,json
from pathlib import Path
from urllib.parse import quote,urljoin
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.jbl import JBLAdapter,official
out=Path(__file__).parent;a=JBLAdapter(fetch_log_path=Path('data/jbl_fetch_log.json'))
results=[]
for term in ('Tune 520BT','Tune520BT'):
 url='https://id.jbl.com/en/search?q='+quote(term);z=a.http.get(url,timeout=8)
 file=out/('jbl_search_'+str(len(results))+'.html');file.write_text(z.text,encoding='utf8')
 soup=BeautifulSoup(z.text,'html.parser')
 links=[dict(url=urljoin(z.url,n.get('href','')),text=n.get_text(' ',strip=True),title=n.get('title',''),classes=n.get('class',[])) for n in soup.select('a[href]') if '520' in str(n)]
 results.append(dict(query=term,url=z.url,status=z.status_code,marker=z.marker,bytes=len(z.text),h1=[h.get_text(' ',strip=True) for h in soup.select('h1')],tiles=len(soup.select('.product-tile')),links=links[:20],text=soup.get_text(' ',strip=True)[-2500:]))
(out/'jbl_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=False),flush=True)
