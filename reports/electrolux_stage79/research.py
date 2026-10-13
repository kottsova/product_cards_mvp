"""Actual attended Chrome research, never injected as discovery seeds."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from bs4 import BeautifulSoup
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.electrolux_page import payload,components
R=Path(__file__).parent
b=PublicBrowserSession(allowed_hosts=('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl','electrolux.com','electroluxgroup.eu','electrolux.bynder.com','electrolux-ui.com'),fetch_log_path=R/'research_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10))
records=[]
try:
 b.start()
 for u in sys.argv[1:]:
  record={'requested_url':u,'origin':'actual live research; not production discovery'}
  try:
   b.call('goto',url=u);a=b.snapshot();n=hashlib.sha256(u.encode()).hexdigest()[:12]
   (R/(n+'.html')).write_bytes(a['html'].encode());record.update({k:v for k,v in a.items() if k!='html'});record['file']=n+'.html'
   s=BeautifulSoup(a['html'],'html.parser');record['title']=s.title.get_text() if s.title else '';record['pnc_menu']=[x.get('aria-label') for x in s.select('button[role="menuitem"][aria-label]')]
   record['model_links']=[{'text':x.get_text(' ',strip=True),'url':x['href']} for x in s.select('a[href]') if any(t in x['href'].lower() for t in ['efi61141b','eod6c46k2','/model/','/support/user-manuals/'])][:60]
   record['owners']=[{'name':c.get('name'),'props':c.get('props',{})} for c in components(payload(a['html'])) if c.get('name')=='TopArea']
   record['text_excerpt']=s.get_text(' ',strip=True)[:3000]
   (R/(n+'.json')).write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
   print({k:record.get(k) for k in ['requested_url','url','status_code','title','pnc_menu','model_links']},flush=True)
  except Exception as e:record['error']=str(e);print(record,flush=True)
  records.append(record)
finally:
 b.close();(R/'research_last.json').write_bytes(json.dumps(records,ensure_ascii=False,indent=2).encode())
