"""Record visual role/language checks separately from automated parser status."""
from pathlib import Path
import json
R=Path(__file__).parent;renders=json.loads((R/'document_render.json').read_text(encoding='utf8'))
out=dict(method='Independent full PDFium render; visual cover and Russian body inspection; no automatic language-status promotion',documents=renders,console_ru_safety=dict(status='Проверена',language='Русский',role='Safety/Regulatory',cover='Руководство по продукту и нормативным актам, ограниченная гарантия и соглашение'),accessories_and_elite=dict(cover_role='Safety/Regulatory',cover='Product and Regulatory Guide, Limited Warranty & Agreement',relation='Official family index; no exact retail kit inference'),user_guide=dict(status='Не проверена',reason='No confirmed User Guide in checked family index; full exact-model User Guide/Quick Start search and legacy-font automatic language verification incomplete'),quick_start=dict(status='Не проверена',reason='No confirmed separate Quick Start in checked family index; not an exhaustive search'),readiness_blocker=False)
out['accessories_and_elite']['russian_body']='Visually checked page96/page65: safety/warranty for Xbox One accessories; not an exact current-model User Guide'
(R/'manual_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
