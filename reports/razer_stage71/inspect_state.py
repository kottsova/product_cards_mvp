import json,sys
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).parent
p=next(x for x in (R/'captures').glob('*.html') if x.stat().st_size in range(1700000,2100000))
s=BeautifulSoup(p.read_text(encoding='utf8'),'html.parser');state=json.loads(s.select_one('#ng-state').string)
print('TOP KEYS',list(state))
def walk(x,path=''):
 if isinstance(x,dict):
  if isinstance(x.get('code'),str) and x['code'].startswith('RZ'):
   print('PRODUCT',path,json.dumps({k:v for k,v in x.items() if k not in {'description','stock','price','volumePrices','categories','classifications'}},ensure_ascii=False)[:12500]);print('OTHER',json.dumps({k:v for k,v in x.items() if k in {'classifications','description'}},ensure_ascii=False)[:8000])
  else:
   for k,v in x.items():walk(v,path+'/'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x):walk(v,path+'/'+str(i))
walk(state)
