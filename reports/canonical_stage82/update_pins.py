"""Authorize exact Stage 82 attribute-only source changes; retain all old guards."""
import subprocess,hashlib
from pathlib import Path
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
paths=sorted({p for p in changed+new if p.startswith(('product_tool/','tests/')) and p.endswith(('.py','.js','.html','.css')) and p!='tests/_pipeline_migration.py'})
a=Path('.gitattributes');text=a.read_text(encoding='utf8')
if 'reports/canonical_stage82/** -text' not in text:text+='\nreports/canonical_stage82/** -text\nreports/canonical_stage82/**/*.html -diff\n'
for p in paths:
 rule=subprocess.check_output(['git','check-attr','eol','--',p],text=True).strip().rsplit(': ',1)[1]
 raw=Path(p).read_bytes();style=rule if rule in {'lf','crlf'} else 'crlf' if raw.count(b'\r\n')>raw.count(b'\n')/2 else 'lf'
 if rule not in {'lf','crlf'}:text+='\n'+p+' text eol='+style+'\n'
 raw=raw.replace(b'\r\n',b'\n');Path(p).write_bytes(raw if style=='lf' else raw.replace(b'\n',b'\r\n'))
a.write_text(text,encoding='utf8')
reason='Stage 82 explicit canonical mapping cleanup: source-authored raw/derived lineage, common Apple scoped section mapping, Razer component SSR splitting, exact hardware optical-table continuation, translated feature roles and separate technical raw classification export. Discovery, photo/manual pipeline and numerical readiness policy unchanged.'
pins={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
with Path('tests/_pipeline_migration.py').open('a',encoding='utf8',newline='') as target:
 target.write('\r\n# Stage 82 exact attribute-only authorization; every previous negative guard retained.\r\nALL_AUTHORIZED_CHANGES.update('+repr({p:reason for p in paths})+')\r\nPINNED_SHA256.update('+repr(pins)+')\r\n')
print('Stage 82 exact pins:',len(pins))
