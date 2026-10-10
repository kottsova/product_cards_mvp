"""Fresh public support search through published SearchAction, no guessed endpoint."""
import sys,json
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.search_routes import detect_routes
R=Path(__file__).parent;out=[]
b=PublicBrowserSession(allowed_hosts=('hyperx.com','supportcenter.hyperx.com','files.hyperx.com'),fetch_log_path=R/'hyperx_fetch_log.json',profile_dir=Path('data/hyperx_stage73_chrome_profile'),visible=True,resource_hosts=('prod-care-community-cdn.sprinklr.com','prod.cdata.app.sprinklr.com'),allow_readonly_graphql=True,readonly_graphql_paths=('/schema/community',))
try:
 b.start();b.call('goto',url='https://supportcenter.hyperx.com/');root=b.call('document_snapshot')
 route=next(r for r in detect_routes(root['html'],root['url'],allowed_hosts=('supportcenter.hyperx.com',)) if r.executable)
 for i,q in ((1,'Cloud Alpha 2 Wireless'),(7,'Pulsefire Haste 2 Wireless'),(8,'QuadCast 2')):
  b.call('goto',url=route.query_url(q));b.page.wait_for_timeout(2500);state=b.call('document_snapshot');html=state.pop('html');(R/f'support_rendered_search_{i}.html').write_text(html,encoding='utf8');s=BeautifulSoup(html,'html.parser')
  links=[{'title':a.get_text(' ',strip=True),'url':urljoin(state['url'],a['href'])} for a in s.select('a[href]') if any(v in a['href'] for v in ('/articles/','/topics/'))]
  for tag in s(['script','style','header','footer']):tag.decompose()
  item={'id':i,'query':q,'browser':state,'links':links,'text':s.get_text(' ',strip=True)[-3500:]};out.append(item);print(i,links,item['text'][-2000:],flush=True)
finally:b.close();(R/'support_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
