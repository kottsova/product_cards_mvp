from pathlib import Path
import json,hashlib,re
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession,record_responses
root=Path('reports/lenovo_stage61');out=root/'manual_pages';out.mkdir(exist_ok=True)
s=PolicyAwareSession(root/'manual_fetch_log.json',allowed_hosts=('support.lenovo.com','pcsupport.lenovo.com','download.lenovo.com'),max_bytes=20000000)
rows=json.loads(Path('reports/lenovo_stage60/final_pass.json').read_text(encoding='utf-8'))['results']+[json.loads(Path('reports/lenovo_stage60/baseline_after.json').read_text(encoding='utf-8'))]
urls={}
for r in rows:
 for m in r['evidence']['manuals']:
  if m['type']=='User Guide' and not 'Linux' in m['title']:urls.setdefault(m['url'],[]).append(r['article'])
results=[]
with record_responses(root/'manual_responses'):
 for url,articles in urls.items():
  r=s.get(url,timeout=12);name=hashlib.sha256(url.encode()).hexdigest()[:15]+('.pdf' if '.pdf' in url else '.html');(out/name).write_bytes(r.content)
  item={'url':url,'articles':articles,'status':r.status_code,'marker':r.marker,'file':name,'bytes':len(r.content),'links':[]}
  if '.pdf' not in url and r.ok:
   soup=BeautifulSoup(r.text,'html.parser');item['links']=[{'text':a.get_text(' ',strip=True),'url':a.get('href')} for a in soup.select('a[href]') if 'pdf' in a.get('href','') or any(t in a.get_text().lower() for t in ('russian','русск','language'))]
  results.append(item);(root/'manual_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(articles,r.status_code,len(r.content),name,flush=True)
