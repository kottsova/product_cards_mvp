"""One published Quick Start download, separate from card/live discovery outcomes."""
import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.policy_session import PolicyAwareSession,RequestBudget,request_budget
from product_tool.adapters.lg_documents import BinarySafeSession
import requests
R=Path(__file__).parent
row=json.loads((R/'live_release.json').read_text(encoding='utf8'))['rows'][3]
guide=row['evidence']['manuals'][0];url=guide['download_candidates'][0]
session=PolicyAwareSession(R/'hyperx_fetch_log.json',allowed_hosts=('files.hyperx.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=8_000_000)
budget=RequestBudget(max_per_row=1,max_total=1);budget.begin_row('guide4')
out={'origin':'supplementary actual live official document check; not new PDP/card success','id':4,'source_article':guide['url'],'url':url,'type':'Quick Start Guide','user_guide_verified':False,'card_status_unchanged':True}
try:
 with request_budget(budget):response=session.get(url,timeout=10)
 data=response.text.encode('latin1')
 out.update(status=response.status_code,marker=response.marker,truncated=response.truncated)
 if not response.ok or response.marker or response.truncated or not data.startswith(b'%PDF'):raise ValueError('Download not a successful bounded PDF')
 path=R/'Alloy_Rise_75_Quick_Start.pdf';path.write_bytes(data);out.update(path=str(path.resolve()),sha256=hashlib.sha256(data).hexdigest(),size=len(data))
 import fitz,re
 doc=fitz.open(path);pages=[p.get_text() for p in doc];out['pages']=len(pages);out['exact_model_in_text']=any('alloy rise 75' in p.casefold() for p in pages)
 out['russian_pages']=[i+1 for i,p in enumerate(pages) if len(re.findall('[А-Яа-яЁё]',p))>200]
 out['classification']='Quick Start Guide (not User Guide or Safety)';out['verified']=out['exact_model_in_text'];out['quick_start_status']='Проверена' if out['verified'] else 'Не проверена'
 if len(pages):doc[0].get_pixmap(matrix=fitz.Matrix(1,1)).save(R/'guide_cover.png')
 if out['russian_pages']:doc[out['russian_pages'][0]-1].get_pixmap(matrix=fitz.Matrix(1,1)).save(R/'guide_ru.png')
 (R/'guide_extracted_text.txt').write_text('\n\n'.join(pages),encoding='utf8');doc.close()
except Exception as e:out.update(verified=False,error=str(e),quick_start_status='Не проверена')
(R/'document_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(out)
