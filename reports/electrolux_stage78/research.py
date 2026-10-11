import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from bs4 import BeautifulSoup
R=Path(__file__).parent
urls=sys.argv[1:] or ['https://www.electrolux.co.uk/laundry/laundry/washing-machines/front-loader-washing-machine/efi61141b/','https://www.electrolux.co.uk/','https://www.electrolux.co.uk/sitemap.xml']
b=PublicBrowserSession(allowed_hosts=('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl','electrolux-medialibrary.com','electroluxmedia.com','electrolux-ui.com'),fetch_log_path=R/'browser_fetch_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10))
try:
 b.start()
 for u in urls:
  try:
   b.call('goto',url=u);a=b.snapshot();n=hashlib.sha256(u.encode()).hexdigest()[:12];(R/(n+'.html')).write_bytes(a['html'].encode('utf8'));(R/(n+'.json')).write_bytes(json.dumps({k:v for k,v in a.items() if k!='html'},indent=2).encode('utf8'));s=BeautifulSoup(a['html'],'html.parser');print(u,a['status_code'],len(a['html']),flush=True)
   if 'efi61141b' in u:
    print('SCRIPTS',[(x.get('type'),x.get('id'),len(x.get_text())) for x in s.select('script')],flush=True)
    for x in s.find_all(string=lambda x:x and 'Product number (PNC)' in x)[:3]:print('SPEC',str(x.parent.parent)[:1400],flush=True)
    print('ASSETS',[(x.get_text(' ',strip=True),x.get('href')) for x in s.select('a[href]') if any(t in x.get('href','').lower() for t in ['asset','pdf','manual','energy'])][:20],flush=True)
   if u.endswith('sitemap.xml'):print(s.get_text()[:500],flush=True)
  except Exception as e:print(type(e).__name__,str(e),flush=True)
finally:b.close()
