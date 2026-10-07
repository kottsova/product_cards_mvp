from pathlib import Path
import json,requests,hashlib
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
r=Path('reports/jbl_stage63');q=json.loads((r/'qa_ui_excel.json').read_text(encoding='utf-8'));s=PolicyAwareSession(r/'ui_batch/jbl_fetch_log.json',allowed_hosts=('jbl.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=8000000);out=[]
for m in q['photos_measured']:
 z=s.get(m['url'],timeout=10)
 if not z.ok or z.truncated:continue
 raw=z.text.encode('latin-1');name='photo_'+m['article']+'.png';(r/name).write_bytes(raw);out.append({'url':m['url'],'file':name,'sha256':hashlib.sha256(raw).hexdigest(),**m})
(r/'photo_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print('Saved original official PNGs',len(out))
