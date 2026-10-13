"""Offline inventory of published scoped gallery DOM, never a live success substitute."""
import sys,json,re
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
sys.stdout.reconfigure(encoding='utf8')
R=Path(__file__).parent;root=R/'baseline_live'
for arg in sys.argv[1:]:
 pid=int(arg);d=root/str(pid);x=json.loads((d/'result.json').read_text(encoding='utf8'))
 print('MODEL',pid,x['input']['brand'],x['input']['model'])
 for p in list((d/'raw_sources').glob('*.html'))+list((d/'captures').glob('*.html')):
  soup=BeautifulSoup(p.read_text(encoding='utf8'),'html.parser')
  matches=soup.select('[data-gallery] img, .product-gallery img, .hero-gallery img, .product__media img, .product-image img, [class*="gallery"] img, [class*="carousel"] img')
  if not matches:continue
  print(p.name,'imgs',len(matches))
  for n in matches[:12]:
   print(json.dumps(n.attrs,ensure_ascii=False)[:550])
  print('gallery containers',[(n.name,str(n.attrs)[:250]) for n in soup.select('[class*="gallery"], [data-gallery]')][:6])
