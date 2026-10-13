"""Bounded binary XML research via the existing browser transport."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
from bs4 import BeautifulSoup
R=Path(__file__).parent
b=PublicBrowserSession(allowed_hosts=('electrolux.co.uk',),fetch_log_path=R/'inventory_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10))
try:
 b.start();http=PolicyAwareSession(R/'inventory_log.json',allowed_hosts=('electrolux.co.uk',),underlying=BinarySafeSession(b.binary_transport(max_bytes=15000000)),max_bytes=15000000,cache_suffixes=())
 for u in sys.argv[1:]:
  r=http.get(u,timeout=10);raw=r.content;locs=__import__('re').findall(rb'<loc>([^<]+)</loc>',raw);locs=[x.decode() for x in locs];d={'url':u,'status':r.status_code,'marker':r.marker,'size':len(raw),'first':locs[:3],'last':locs[-3:],'matches':[x for x in locs if any(t.lower() in x.lower() for t in ['EFI61141B','EOD6C46K2','EOF6P46X','EF7742OBI'])]}
  n=hashlib.sha256(u.encode()).hexdigest()[:12];(R/(n+'.xml')).write_bytes(raw);(R/(n+'_xml.json')).write_bytes(json.dumps(d,indent=2).encode());print(d,flush=True)
finally:b.close()
