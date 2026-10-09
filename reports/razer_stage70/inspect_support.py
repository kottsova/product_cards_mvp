from bs4 import BeautifulSoup
from pathlib import Path
import json
s=BeautifulSoup(Path(__file__).with_name('observed').joinpath('support_6124.html').read_text(encoding='utf8'),'html.parser')
t=s.find('table');print(str(t)[:4000]);print('PARENTS',[(x.name,x.get('id'),x.get('class')) for x in t.parents][:6])
for a in s.select('a[href]'):
 text=a.get_text(' ',strip=True);url=a['href']
 if any(x in (text+' '+url).lower() for x in ['app/answers/list','support/home','pc/gaming','gaming-mice','deathadder-v3']):print(text[:120],url)
for f in s.select('form'):print('FORM',str(f)[:1800])
