"""Public read-only exploration; not a seeded production discovery result."""
import sys,hashlib,json
from pathlib import Path
import requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.xbox import XboxTransport
from product_tool.adapters.lg_documents import document_bytes
R=Path(__file__).parent;D=R/'observed';D.mkdir(exist_ok=True)
s=PolicyAwareSession(R/'explore_http.json',allowed_hosts=('microsoft.com','xbox.com','xboxlive.com','xboxservices.com','aka.ms'),underlying=XboxTransport(requests.Session()),min_interval_seconds=1)
for u in sys.argv[1:]:
 try:
  z=s.get(u,timeout=25);print(z.status_code,z.url,len(z.text),flush=True)
  if z.status_code==200:
   binary=z.url.lower().endswith(('.pdf','.gz'));p=D/(hashlib.sha256(z.url.encode()).hexdigest()[:20]+('.pdf' if z.url.lower().endswith('.pdf') else '.bin' if binary else '.html'))
   p.write_bytes(document_bytes(z)) if binary else p.write_text(z.text,encoding='utf8')
 except Exception as e:print(type(e).__name__,str(e),flush=True)
