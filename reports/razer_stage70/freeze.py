"""Freeze representative inputs once, before the first adapted run."""
import json,hashlib
from pathlib import Path
R=Path(__file__).parent
rows=[
 ('RZ01-0512','Razer Viper V3 Pro','Мыши',{}),
 ('RZ01-0514','Razer DeathAdder V3 HyperSpeed','Мыши',{}),
 ('RZ03-0500','Razer BlackWidow V4 75%','Клавиатуры',{'switch':'Orange','layout':'US'}),
 ('RZ03-0339','Razer Huntsman Mini','Клавиатуры',{'switch':'Linear','layout':'US'}),
 ('RZ04-0453','Razer BlackShark V2 Pro (2023)','Гарнитуры',{}),
 ('RZ04-0443','Razer Barracuda X (2022)','Гарнитуры',{'color':'Quartz'}),
 ('RZ09-0528','Razer Blade 16 (2025)','Ноутбуки',{'GPU':'RTX 5080','RAM':'32 GB','storage':'1 TB'}),
 ('RZ06-0520','Razer Wolverine V3 Pro','Контроллеры',{}),
 ('RZ01-0512','Razer Viper V3 Pro','Мыши',{'color':'White'}),
 ('RZ03-0500','Razer BlackWidow V4 75%','Клавиатуры',{'switch':'Orange','layout':'UK','region':'en-GB','color':'White'})]
data={'stage':70,'frozen_before_first_adapted_run':True,'baseline_excluded':True,'note':'Eight distinct models plus two deliberately difficult color/layout configurations. Model codes are inputs, not invented retail SKUs. Requested options remain unconfirmed until exact evidence.','rows':[{'id':i,'article':a,'model':n,'name':n+' ['+'; '.join(k+'='+v for k,v in c.items())+']' if c else n,'category':cat,'region':c.get('region','en-US'),'configuration':c} for i,(a,n,cat,c) in enumerate(rows,1)]}
target=R/'frozen_inputs.json';assert not target.exists();raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();target.write_bytes(raw);(R/'frozen_inputs.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii');print(hashlib.sha256(raw).hexdigest())
