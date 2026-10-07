"""Restore ignored public PDF bytes; hash changes require a new content audit.
Run from repository root with PYTHONPATH=. after production requirements install.
Only previously observed official URLs are used. No credentials/profile import.
"""
from pathlib import Path
import hashlib,json,requests
from product_tool.adapters.jbl import official
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
root=Path('reports/jbl_stage63/jbl_captures');groups={}
for index in sorted(root.glob('*.documents.json')):
 for url,item in json.loads(index.read_text(encoding='utf-8')).items():
  name=item['file'];expected=item['sha256'];assert Path(name).name==name and name==expected+'.pdf' and official(url)
  groups.setdefault(expected,[]).append(url)
session=PolicyAwareSession(root.parent/'restore_fetch_log.json',allowed_hosts=('jbl.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=50_000_000)
for expected,urls in groups.items():
 target=root/(expected+'.pdf')
 if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==expected:continue
 restored=False
 # Identical historical bytes may have multiple observed regional URLs.
 for url in dict.fromkeys(urls):
  try:response=session.get(url,timeout=20)
  except Exception:continue
  if not response.ok or response.truncated:continue
  raw=response.text.encode('latin-1')
  if not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest()!=expected:continue
  target.write_bytes(raw);restored=True;break
 if not restored:raise RuntimeError(f'Historical public PDF unavailable or revised ({expected}); require a new content audit; no verification promoted')
print('Public PDF byte proofs present; worker still assesses content with current code')
