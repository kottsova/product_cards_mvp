"""Freeze ten new Stage 72 rows before their first worker run; no PDP seeds."""
import json,hashlib
from pathlib import Path
R=Path(__file__).parent
rows=[
 (1,'AJ5C7AA','HyperX Cloud Alpha 2 Wireless','Гарнитуры'),
 (2,'7G8F3AA','HyperX Cloud Mini Wired','Гарнитуры'),
 (3,'77Z46AA','HyperX Cloud III Wireless','Гарнитуры'),
 (4,'7G7A4AA#ABA','HyperX Alloy Rise 75 [color=Black;layout=US Layout;switch=HyperX Red - Linear]','Клавиатуры'),
 (5,'56R64AA#ABA','HyperX Alloy Origins 65 [color=Black;layout=US Layout;switch=HyperX Aqua - Tactile]','Клавиатуры'),
 (6,'6N0A7AA','HyperX Pulsefire Haste 2 Wired','Мыши'),
 (7,'6N0A9AA','HyperX Pulsefire Haste 2 Wireless','Мыши'),
 (8,'872V1AA','HyperX QuadCast 2 [color=Black]','Микрофоны'),
 (9,'6L366AA','HyperX Clutch Gladiate Wired','Контроллеры'),
 (10,'4P5D6AX#ACB','HyperX Alloy Origins 65 [color=Black;layout=RU Layout;switch=HyperX Red - Linear]','Клавиатуры'),
]
path=R/'frozen_inputs.json'
assert not path.exists()
path.write_text(json.dumps({'stage':72,'baseline_excluded':'9A273AA','no_seeded_pdp_urls':True,'rows':[dict(id=i,article=a,name=n,category=c) for i,a,n,c in rows]},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(R/'frozen_inputs.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'\n',encoding='utf8')
print((R/'frozen_inputs.sha256').read_text())
