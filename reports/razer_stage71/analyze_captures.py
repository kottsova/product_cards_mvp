import json,re,sys
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).parent
for p in (R/'captures').glob('*.html'):
 if p.stat().st_size>4000000:continue
 raw=p.read_text(encoding='utf8');s=BeautifulSoup(raw,'html.parser');h=s.select_one('h1');print('\nFILE',p.name,p.stat().st_size,'TITLE',s.title.get_text() if s.title else '', 'H1',h.get_text(' ',strip=True) if h else '')
 print('codes',list(dict.fromkeys(re.findall(r'RZ\d{2}-[\w-]+',raw)))[:25])
 for n in s.select('script[type="application/ld+json"],script[type="application/json"]'):
  text=n.string or n.get_text();print('JSON',n.attrs,text[:5000])
 for selector in ('[data-arr]','.tech-specs','#tech-specs','[class*="gallery"]','[class*="tech-spec"]'):
  nodes=s.select(selector);print('selector',selector,len(nodes));print(str(nodes[0])[:1500] if nodes else '')
 for pattern in ('productMedia','primaryImage','sku','gallery','PRODUCT','imageUrls','variant','technicalSpecs','hydration','productState'):
  matches=list(re.finditer(re.escape(pattern),raw,re.I));print('pattern',pattern,'count',len(matches))
  if matches:print(raw[max(0,matches[-1].start()-120):matches[-1].start()+650])
