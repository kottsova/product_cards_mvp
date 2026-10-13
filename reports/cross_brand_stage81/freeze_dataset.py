"""Freeze qualified categories and hard configurations before any Stage 81 live job."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone

R=Path(__file__).parent
def load(path):
 x=json.loads(Path(path).read_text(encoding='utf-8-sig'))
 return x if isinstance(x,list) else x.get('rows',x.get('models',[]))
specs=[
 ('JBL','reports/jbl_stage62/dataset_frozen.json',[0,2,3,6,7,9]),
 ('Samsung','reports/samsung_stage59/dataset_frozen.json',None),
 ('LG','reports/lg_independent_2026-10-02_stage56/dataset.json',[0,1,3,4,5,6,8,10,12,13,14]),
 ('Apple','reports/apple_stage64/dataset_frozen.json',[0,2,3,4,5,6,7,8,9]),
 ('PlayStation','reports/playstation_stage66/dataset_frozen.json',[0,3,4,5,6,7,9]),
 ('Xbox','reports/xbox_stage68/dataset.json',[0,1,4,5,6,7,9]),
 ('Razer','reports/razer_stage71/frozen_inputs.json',[0,2,3,4,5,6,7,9]),
 ('HyperX','reports/hyperx_stage73/frozen_inputs.json',[0,3,5,6,7,8,9]),
 ('Xiaomi','reports/xiaomi_stage74/dataset.json',None),
 ('Dreame','reports/dreame_stage76/dataset.json',[0,1,3,4,7,8]),
 ('Electrolux','reports/electrolux_stage78/dataset.json',None),
]
categories={'speakers':'Колонки','headphones':'Наушники','soundbar':'Саундбары','tws':'Наушники TWS','phones':'Смартфоны','laptops':'Ноутбуки','tablets':'Планшеты','watches':'Смарт-часы','consoles':'Игровые консоли','controllers':'Контроллеры','remote_players':'Устройства Remote Play','headsets':'Гарнитуры','Машины посудомоечные':'Посудомоечные машины'}
rows=[]
for brand,path,indices in specs:
 original=load(path)
 selected=original if indices is None else [original[i] for i in indices]
 if brand=='Samsung':
  extra=load('product_tool/config/coverage_planner.v1.json')
  inventory=json.loads(Path('product_tool/config/coverage_planner.v1.json').read_text(encoding='utf8'))['selected_products']['samsung']['products']
  have={categories.get(x['category'],x['category']) for x in selected}
  selected += [dict(article=x['seller_sku'],name='Samsung '+x['seller_sku'],category=x['category'],selection_reason='Previously qualified category missing from Stage 59 ten') for x in inventory if categories.get(x['category'],x['category']) not in have]
 if brand=='LG':
  selected.append(dict(article='S3WER.ALWPCOM',name='LG Styler S3WER.ALWPCOM',category='Паровые шкафы',selection_reason='Previously supported Styler scope'))
 for src in selected:
  cat=categories.get(src['category'],src['category']);name=src.get('name',src.get('catalog_name',brand+' '+src['article']))
  if brand=='Xiaomi':
   cat='Роботы-пылесосы' if 'Robot Vacuum' in name else 'Вертикальные пылесосы' if 'Vacuum Cleaner' in name else 'Телевизоры' if 'TV A Pro' in name else 'Мониторы' if 'Monitor' in name else 'Роутеры' if 'Router' in name else 'Смартфоны'
  if brand=='Xbox':cat='Гарнитуры' if 'Headset' in name else 'Контроллеры' if 'Controller' in name else 'Игровые консоли'
  if brand=='LG' and 'W1S1' in src['article']:cat='Стирально-сушильные машины'
  row=dict(id=len(rows)+1,brand=brand,dispatch_brand=src.get('brand',brand),article=src['article'],model=src.get('model',name.split(' [')[0]),name=name,category=cat,input_configuration=src.get('input_configuration',src.get('requested_configuration',src.get('configuration',{}))),region=src.get('requested_region',src.get('region','')),input_pnc=src.get('input_pnc'),input_color=src.get('input_color'),provenance=path,original_input=src)
  assert 'url' not in row
  rows.append(row)
assert len({x['brand'] for x in rows})==11
R.mkdir(parents=True,exist_ok=True)
assert not (R/'dataset.json').exists(),'Frozen dataset already exists; never resample'
x=dict(stage=81,frozen_at=datetime.now(timezone.utc).isoformat(),frozen_before_live=True,selection='Category coverage from prior qualified datasets plus Samsung selected category inventory and LG Styler; older/newer, difficult regional/config inputs retained; no PDP URLs injected',manual_budget='No stage 6, no additional guide search or PDF fetch',rows=rows)
raw=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8');(R/'dataset.json').write_bytes(raw);(R/'dataset.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii')
coverage={b:sorted({p['category'] for p in rows if p['brand']==b}) for b,_,_ in specs}
(R/'category_coverage_frozen.json').write_text(json.dumps({'brands':coverage,'unique_categories':sorted({p['category'] for p in rows}),'inputs':len(rows)},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({'inputs':len(rows),'brands':11,'categories':len({p['category'] for p in rows}),'sha256':hashlib.sha256(raw).hexdigest()})
