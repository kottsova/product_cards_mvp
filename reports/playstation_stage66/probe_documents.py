import hashlib,json,requests
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from pypdf import PdfReader
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession,document_bytes
r=Path('reports/playstation_stage66');s=PolicyAwareSession(r/'document_http.json',allowed_hosts=('playstation.com',),underlying=BinarySafeSession(requests.Session()),min_interval_seconds=5)
out=[]
b=BeautifulSoup((r/'manuals_gb.html').read_text(encoding='utf-8'),'html.parser')
for code in ('CFI-1216A','CFI-1216B','CFI-2016A/B','CFI-7021','CFI-ZCT1W','CFI-Y1016'):
 a=next((a for a in b.select('a[href]') if code in a.get_text() and ('Safety' in a.get_text() if code.startswith(('CFI-1','CFI-2','CFI-7')) else 'Instruction' in a.get_text())),None)
 if not a:continue
 u=urljoin('https://www.playstation.com',a['href']);z=s.get(u,timeout=10)
 try:
  data=document_bytes(z);reader=PdfReader(BytesIO(data));text='\n'.join(p.extract_text() or '' for p in reader.pages);stem=code.replace('/','_')
  (r/(stem+'.pdf')).write_bytes(data);(r/(stem+'_text.txt')).write_text(text,encoding='utf-8')
  out.append(dict(code=code,url=u,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),pages=len(reader.pages),text=text));print(code,len(data),text[text.lower().find('specifications'):text.lower().find('specifications')+4500],flush=True)
 except Exception as e:out.append(dict(code=code,url=u,error=str(e)));print(code,e,flush=True)
 (r/'document_structure.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
