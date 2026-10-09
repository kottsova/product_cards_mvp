"""Read Stage 68 public evidence without changing its frozen data or reports."""
import json,hashlib
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.xbox_page import assignment,raw_rows
from product_tool.adapters.xbox import sitemap_urls
from product_tool.adapters.policy_session import PolicyResponse
R=Path(__file__).parent;OLD=R.parent/'xbox_stage68'
out={'dataset_sha256':hashlib.sha256((OLD/'dataset.json').read_bytes()).hexdigest(),'pages':[]}
logs=json.loads((OLD/'explore_http.json').read_text(encoding='utf8'))+json.loads((OLD/'xbox_fetch.json').read_text(encoding='utf8'))
for slug in ['8wj714n3rbtl','942j774tp9jn','8n1bb8dsbknt','8r02lkf9q26r']:
 for log in logs:
  url=log.get('final_url') or log['url']
  if slug not in url.lower() or log.get('status_code')!=200:continue
  digest=hashlib.sha256(url.encode()).hexdigest()[:20]
  p=next((d/(digest+'.html') for d in [OLD/'observed',OLD/'xbox_captures'] if (d/(digest+'.html')).exists()),None)
  if not p:continue
  b=BeautifulSoup(p.read_text(encoding='utf8'),'html.parser');buy=next((assignment(s.get_text(),'window.__BuyBox__') for s in b.select('script') if assignment(s.get_text(),'window.__BuyBox__')),None)
  forms=[dict(action=f.get('action'),method=f.get('method'),fields=[dict(name=n.get('name'),type=n.get('type')) for n in f.select('input')]) for f in b.select('form') if 'search' in str(f).lower()]
  out['pages'].append(dict(url=url,file=str(p),title=b.h1.get_text(' ',strip=True) if b.h1 else '',buybox=buy,raw=raw_rows(b),forms=forms))
  break
for log in logs:
 url=log.get('final_url') or log['url']
 if 'xbox-bundle-01.xml' not in url or log.get('status_code')!=200:continue
 p=OLD/'observed'/(hashlib.sha256(url.encode()).hexdigest()[:20]+'.html')
 if p.exists():
  _,urls=sitemap_urls(PolicyResponse(url,200,p.read_text(encoding='utf8')));out['bundle_map']=dict(url=url,total=len(urls),matches=[u for u in urls if 'diablo' in u.lower() or '8n1bb8dsbknt' in u.lower()])
  break
(R/'stage68_diagnosis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
for p in out['pages']:
 own=(p['buybox'] or {}).get('product',{})
 print(p['title'],p['url'],'keys',list(own),'SKUs',[(k,v.get('title'),list(v)) for k,v in own.get('skuInfo',{}).items()],'forms',p['forms'],'raw',[(r['raw_label'],r['value']) for r in p['raw']],flush=True)
print(out.get('bundle_map'))
