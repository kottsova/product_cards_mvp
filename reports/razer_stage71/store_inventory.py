import json
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.razer_page import parse_page
R=Path(__file__).parent
rows=json.loads((R/'frozen_inputs.json').read_text(encoding='utf8'))['rows'];out=[]
for file in (R/'captures').glob('*.html'):
 if file.stat().st_size>4000000:continue
 raw=file.read_text(encoding='utf8');s=BeautifulSoup(raw,'html.parser');node=s.select_one('#ng-state')
 if not node:continue
 state=json.loads(node.string);variants=state.get('razerProductMarketingData',{}).get('variants',[])
 item={'file':file.name,'title':s.title.get_text() if s.title else '', 'keys':list(state),'nodes':[]}
 for v in variants:
  item['nodes'].append({'code':v.get('code'),'base':v.get('baseProductName'),'name':v.get('name'),'options':[q for g in v.get('variantOptions',[]) for q in g.get('variantOptionQualifiers',[])],'features':[(g.get('name'),[x.get('name') for x in g.get('features',[])]) for g in v.get('classifications',[])]})
 for row in rows:
  if any(str(v.get('code','')).startswith(row['article']) for v in variants):
   url='https://www.razer.com/'+state.get('razerProductMarketingData',{}).get('locale','us-en')+'/gaming-example'
   d,e=parse_page(raw,url,row['article'],row['name'],row['category']);print(row['id'],file.name[:12],item['title'],len(d.attributes),len(e['exact_photo_assets']),e['identity'].get('configuration_relation'),flush=True)
 out.append(item)
(R/'store_inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
