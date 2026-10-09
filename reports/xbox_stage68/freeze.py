"""Freeze inputs once, after baseline and before adapted ordinary run_once."""
import json,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).parent
assert (R/'baseline.json').exists() and not (R/'dataset.json').exists()
rows=[
 ('Xbox Series X','Xbox Series X 1TB Carbon Black Disc','commercial_configuration','en-US'),
 ('Xbox Series S 512GB','Xbox Series S 512GB Robot White','commercial_configuration','en-US'),
 ('8R02LKF9Q26R','Xbox Series S 1TB Robot White','store_product_id','en-US'),
 ('8XN59CRBSQGZ/KPRJ','Xbox Wireless Controller Robot White','store_product_id/store_sku_id','en-US'),
 ('8QRF79K7JSR6/ZHP2','Xbox Wireless Controller Arctic Camo Special Edition','store_product_id/store_sku_id','en-US'),
 ('8RSN7J6375GG/99WM','Xbox Elite Wireless Controller Series 2','store_product_id/store_sku_id','en-US'),
 ('9203Q8W23LHN/HFXZ','Xbox Wireless Headset','store_product_id/store_sku_id','en-US'),
 ('8N1BB8DSBKNT','Xbox Series X Diablo IV Bundle','store_product_id','en-US'),
 ('8ZB8Z8MM10V0','Xbox Series S Starter Bundle','store_product_id','en-US'),
 ('1883','Xbox Series S hardware model 1883','hardware_model_number','en-GB'),
]
out=dict(stage=68,frozen_at=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),baseline_identifier='1882',rule='Inputs are immutable. Names are query hints, never proof. No PDP URL or per-SKU registry supplied to worker.',rows=[dict(row=i,article=a,name=n,identifier_type=t,requested_region=reg,brand='Xbox',category='consoles' if 'Series X' in n or 'Series S ' in n else 'accessories') for i,(a,n,t,reg) in enumerate(rows,1)])
p=R/'dataset.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(R/'dataset.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'\n',encoding='ascii')
print('Frozen',len(rows),'inputs',hashlib.sha256(p.read_bytes()).hexdigest())
