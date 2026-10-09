"""Policy-aware public source survey; no product lookup registry."""
import sys,json,hashlib
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession,document_bytes
R=Path('reports/xbox_stage68');C=R/'observed';C.mkdir(exist_ok=True)
s=PolicyAwareSession(R/'explore_http.json',allowed_hosts=('xbox.com','microsoft.com','aka.ms','xboxservices.com','xboxlive.com','s-microsoft.com'),underlying=BinarySafeSession(requests.Session()),min_interval_seconds=1)
for u in sys.argv[1:]:
 try:
  z=s.get(u,timeout=15);key=hashlib.sha256(z.url.encode()).hexdigest()[:20]
  suffix='.pdf' if '.pdf' in z.url.lower() else '.html'
  p=C/(key+suffix)
  if suffix=='.pdf':p.write_bytes(document_bytes(z))
  else:p.write_text(z.text,encoding='utf-8')
  b=BeautifulSoup(z.text if suffix=='.html' else '','html.parser')
  print(json.dumps(dict(requested=u,url=z.url,status=z.status_code,truncated=z.truncated,chars=len(z.text),file=str(p),title=b.title.get_text() if b.title else '',h1=[x.get_text(' ',strip=True) for x in b.select('h1')][:3],scripts=[x.get('src') for x in b.select('script[src]')][:15],json=[dict(id=x.get('id'),type=x.get('type'),chars=len(x.get_text())) for x in b.select('script') if x.get('type') in ('application/json','application/ld+json')][:8]),ensure_ascii=False),flush=True)
 except Exception as e:print(u,type(e).__name__,str(e),flush=True)
