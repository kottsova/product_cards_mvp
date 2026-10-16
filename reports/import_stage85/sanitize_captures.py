"""Retain raw DOM locally; commit a redacted inspection copy and both hashes."""
import hashlib,json,re
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;raw_dir=root/'data/stage85_raw';raw_dir.mkdir(exist_ok=True);manifest=[]
for p in sorted(out.glob('sulpak_*dom.html')):
 raw=p.read_bytes();(raw_dir/p.name).write_bytes(raw);soup=BeautifulSoup(raw.decode('utf8'),'html.parser')
 for node in soup.select('input'):
  if re.search(r'token|csrf|session|auth',node.get('name',''),re.I):node['value']='[REDACTED]'
 for node in soup.select('[data-sitekey]'):node['data-sitekey']='[REDACTED public CAPTCHA site key]'
 for script in soup.select('script'):
  if script.get('type','').lower() not in {'application/ld+json','application/json'} and not script.get('src'):
   script.string='/* Inline script retained in local raw capture; omitted from committed inspection copy. */'
 redacted=str(soup).encode('utf8');p.write_bytes(redacted)
 manifest.append(dict(file=p.name,raw_file='data/stage85_raw/'+p.name,raw_sha256=hashlib.sha256(raw).hexdigest(),inspection_sha256=hashlib.sha256(redacted).hexdigest(),redactions='Hidden tokens, public CAPTCHA site keys and non-data inline scripts; Product JSON-LD/title/content/canonical retained'))
(out/'capture_redactions.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
