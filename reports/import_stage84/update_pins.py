"""Pin exact authorized acceptance fixes; retain every pre-existing negative guard."""
import subprocess,hashlib
from pathlib import Path
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
paths=sorted({p for p in changed+new if p.startswith(('product_tool/','tests/')) and p.endswith(('.py','.js','.html','.css')) and p!='tests/_pipeline_migration.py'})
a=Path('.gitattributes');text=a.read_text(encoding='utf8')
for rule in ('reports/import_stage84/** -text','reports/import_stage84/**/*.html -diff'):
 if rule not in text:text+='\n'+rule+'\n'
for p in paths:
 rule=subprocess.check_output(['git','check-attr','eol','--',p],text=True).strip().rsplit(': ',1)[1]
 raw=Path(p).read_bytes();style=rule if rule in {'lf','crlf'} else 'crlf' if raw.count(b'\r\n')>raw.count(b'\n')/2 else 'lf'
 if rule not in {'lf','crlf'}:text+='\n'+p+' text eol='+style+'\n'
 raw=raw.replace(b'\r\n',b'\n');Path(p).write_bytes(raw if style=='lf' else raw.replace(b'\n',b'\r\n'))
a.write_text(text,encoding='utf8')
reason='Stage 84 user-authorized three-column input interpretation: title-derived model/category/configuration hints with confidence/provenance; brand-column authority, supplier article separate, original cells preserved; alias headers and unedited preview confirmation; extracted models reach ordinary production adapters. JBL published master inventory routes to revalidated coherent Product SKU/MPN and exact color, without promoting supplier identifiers. Ambiguous input blocks readiness and confirmed photos. Existing identity guards, access-stop policy and numerical thresholds retained.'
pins={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
with Path('tests/_pipeline_migration.py').open('a',encoding='utf8',newline='') as target:
 target.write('\r\n# Stage 84 user-authorized input interpretation, exact bytes; all historical guards retained.\r\nALL_AUTHORIZED_CHANGES.update('+repr({p:reason for p in paths})+')\r\nPINNED_SHA256.update('+repr(pins)+')\r\n')
print('Stage 84 exact pins:',len(pins))
