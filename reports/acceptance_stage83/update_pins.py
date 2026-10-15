"""Pin exact authorized acceptance fixes; retain every pre-existing negative guard."""
import subprocess,hashlib
from pathlib import Path
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
paths=sorted({p for p in changed+new if p.startswith(('product_tool/','tests/')) and p.endswith(('.py','.js','.html','.css')) and p!='tests/_pipeline_migration.py'})
a=Path('.gitattributes');text=a.read_text(encoding='utf8')
for rule in ('reports/acceptance_stage83/** -text','reports/acceptance_stage83/**/*.html -diff','reports/apple_production_recovery/** -text','reports/apple_production_recovery/**/*.html -diff'):
 if rule not in text:text+='\n'+rule+'\n'
for p in paths:
 rule=subprocess.check_output(['git','check-attr','eol','--',p],text=True).strip().rsplit(': ',1)[1]
 raw=Path(p).read_bytes();style=rule if rule in {'lf','crlf'} else 'crlf' if raw.count(b'\r\n')>raw.count(b'\n')/2 else 'lf'
 if rule not in {'lf','crlf'}:text+='\n'+p+' text eol='+style+'\n'
 raw=raw.replace(b'\r\n',b'\n');Path(p).write_bytes(raw if style=='lf' else raw.replace(b'\n',b'\r\n'))
a.write_text(text,encoding='utf8')
reason='Stage 83 explicitly requested production acceptance recovery: Apple model-first catalog discovery and exact configuration/photo evidence; import header roles and original-color retention; shared descriptive-primary/structured-fallback search selection without input mutation; real cross-brand batch queue through ordinary enqueue/run_once; permanent runtime/dispatch/catalog/identity/persistence/readiness trace; generic all-or-none semantic decomposition, original raw evidence, Russian value presentation and separate compatibility group; raw semantic Excel sheet. Numerical readiness thresholds, access-stop policy and identity guards retained. Stage37 UI control assertion now scopes each form independently because both batch controls are present.'
pins={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
with Path('tests/_pipeline_migration.py').open('a',encoding='utf8',newline='') as target:
 target.write('\r\n# Stage 83 user-authorized acceptance fixes, exact bytes; all historical guards retained.\r\nALL_AUTHORIZED_CHANGES.update('+repr({p:reason for p in paths})+')\r\nPINNED_SHA256.update('+repr(pins)+')\r\n')
print('Stage 83 exact pins:',len(pins))
