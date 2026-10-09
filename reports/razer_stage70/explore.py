"""Read-only public source structure research; URLs are not runtime discovery seeds."""
import sys,json,hashlib
from pathlib import Path
import requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession,document_bytes
R=Path(__file__).parent;D=R/'observed';D.mkdir(exist_ok=True)
s=PolicyAwareSession(R/'explore_http.json',allowed_hosts=('razer.com','razerzone.com','rzr.to'),underlying=BinarySafeSession(requests.Session()),max_bytes=50_000_000,min_interval_seconds=1)
for u in sys.argv[1:]:
 try:
  z=s.get(u,timeout=20);print(z.status_code,z.url,len(z.text),flush=True)
  if z.status_code==200 and not z.truncated:
   binary=z.url.lower().endswith(('.pdf','.gz'));p=D/(hashlib.sha256(z.url.encode()).hexdigest()[:20]+('.pdf' if '.pdf' in z.url.lower() else '.bin' if binary else '.html'))
   p.write_bytes(document_bytes(z)) if binary else p.write_text(z.text,encoding='utf8')
 except Exception as e:print(type(e).__name__,str(e),flush=True)
