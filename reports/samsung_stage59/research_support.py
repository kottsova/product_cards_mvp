from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession
from urllib.parse import urlparse
import json,re
root=Path('reports/samsung_stage59')
url='https://www.samsung.com/kz_ru/support/model/WW90T554CAT/LD/'
s=PolicyAwareSession(root/'support_research_fetch_log.json',allowed_hosts=('www.samsung.com',),max_bytes=10_000_000)
r=s.get(url,timeout=18)
print('http',r.status_code,'final',r.url,'bytes',len(r.content),'marker',r.marker)
if not r.ok: raise SystemExit(1)
h=r.text; soup=BeautifulSoup(h,'html.parser')
print('canonical',[x.get('href') for x in soup.select('link[rel="canonical"]')])
print('title',soup.title.get_text(' ',strip=True) if soup.title else '')
print('visible_model',soup.get_text(' ',strip=True).count('WW90T554CAT/LD'))
print('product_specs',len(soup.select('.pdd32-product-spec__content-item')))
print('manual_markers',[(m.start(),h[m.start()-30:m.start()+40]) for m in list(re.finditer(r'"manuals"\s*:',h))[:3]])
for m in list(re.finditer(r'"manuals"\s*:',h))[:1]:
  array=h.find('[',m.end())
  try:
    manuals,_=json.JSONDecoder().raw_decode(h[array:])
    print('manuals',[(x.get('englishDescription'),x.get('fileName'),x.get('contentsTypeCode'),len(x.get('languageList') or [])) for x in manuals])
  except Exception as e: print('json_error',str(e))
