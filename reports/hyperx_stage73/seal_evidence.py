"""Seal public report files; binary byte hashes and DOM text hashes are distinct."""
import json,hashlib
from pathlib import Path
R=Path(__file__).parent
rows=[]
for p in sorted(R.rglob('*')):
 if not p.is_file() or p.suffix in {'.sqlite3','.pyc'} or '__pycache__' in p.parts or p.name=='evidence_manifest.json':continue
 raw=p.read_bytes();item={'path':p.relative_to(R).as_posix(),'size_bytes':len(raw),'stored_bytes_sha256':hashlib.sha256(raw).hexdigest()}
 if p.parent.name=='captures' and p.suffix=='.html':
  item['canonical_dom_text_sha256']=hashlib.sha256(p.read_text(encoding='utf8').encode()).hexdigest();assert item['canonical_dom_text_sha256']==p.stem
 if p.parent.name in {'captures','images'} and p.suffix in {'.pdf','.png','.jpg','.webp'}:assert item['stored_bytes_sha256']==p.stem
 rows.append(item)
(R/'evidence_manifest.json').write_text(json.dumps({'note':'DOM filenames hash UTF-8 DOM text with normalized newlines; Windows stored byte hash is recorded separately. PDF/image hashes are exact bytes. No runtime SQLite/profile/cookies included.','files':rows},indent=2),encoding='utf8')
print(len(rows),'public evidence files sealed')
