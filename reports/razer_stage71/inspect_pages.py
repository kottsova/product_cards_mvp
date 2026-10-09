import json
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.razer_page import parse_page
R=Path(__file__).parent
for file in (R/'observed').glob('*.html'):
 s=BeautifulSoup(file.read_text(encoding='utf8'),'html.parser')
 print(file.name,s.title.get_text() if s.title else '')
 for a in s.select('a[href]'):
  if '/answers/detail/' in a['href'] and 'Support' in a.get_text():print(a.get_text(' ',strip=True),a['href'])
old=json.loads((R.parent/'razer_stage70/first_pass.json').read_text(encoding='utf8'))
row=old['rows'][4];p=next(x for x in reversed(row['evidence']['proofs']) if '/answers/detail/' in x['url']);raw=(R.parent/'razer_stage70/captures'/p['file']).read_text(encoding='utf8');s=BeautifulSoup(raw,'html.parser');print(str(s.select_one('#at-a-glance'))[:15000])
d,e=parse_page(raw,p['url'],row['input']['search_code'],row['input']['name'],row['input']['category']);print('after',len(e['raw_specs']),len(e['accepted_specs']),[(x.name,x.value) for x in d.attributes])
