"""Follow a published inventory menu, then fresh GET its observed target."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from bs4 import BeautifulSoup
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.electrolux_page import MEDIA_HOSTS
R=Path(__file__).parent;rows=[json.loads((R/'qualified_live'/str(i)/'result.json').read_text(encoding='utf8')) for i in (10,6)]
b=PublicBrowserSession(allowed_hosts=MEDIA_HOSTS,fetch_log_path=R/'revision_route_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10));records=[]
try:
 b.start()
 for row in rows:
  ev=row['evidence'];inv=ev['pnc_inventory'];codes=[r['pnc'] for r in inv['relations'] if r['pnc_base']==ev['identity']['pnc_base']][:2]
  for pnc in codes:
   record={'model':row['input']['model'],'pnc':pnc,'origin':'actual live research, published inventory menu; no spec equivalence inferred','inventory_url':inv['url']}
   try:
    b.call('goto',url=inv['url']);b.page.locator('div[role="combobox"]').filter(has=b.page.locator(f'button[role="menuitem"][aria-label="{pnc}"]')).locator('input[aria-hidden="false"]').click(timeout=10000);b.page.locator(f'button[role="menuitem"][aria-label="{pnc}"]').click(timeout=10000);b.page.wait_for_timeout(1500);target=b.page.url;record['menu_observed_target']=target
    if not b.allowed(target):raise ValueError('Foreign menu target')
    b.call('goto',url=target);a=b.snapshot();n=hashlib.sha256((row['input']['model']+pnc).encode()).hexdigest()[:12];(R/(n+'_revision.html')).write_bytes(a['html'].encode());record.update({k:v for k,v in a.items() if k!='html'});record['file']=n+'_revision.html';s=BeautifulSoup(a['html'],'html.parser');record['headings']=[h.get_text(' ',strip=True) for h in s.select('h1,h2,h3')];record['document_links']=[{'label':a.get_text(' ',strip=True),'url':a['href']} for a in s.select('a[href]') if any(t in a['href'].lower() for t in ['pdf','manual','document','fiche'])];record['text_excerpt']=s.get_text(' ',strip=True)[-6500:];print({k:record.get(k) for k in ['model','pnc','menu_observed_target','status_code','headings','document_links']},flush=True)
   except Exception as e:record['error']=str(e);print(record,flush=True)
   records.append(record)
finally:
 b.close();(R/'revision_route_research.json').write_bytes((json.dumps(records,ensure_ascii=False,indent=2)+'\n').encode())
