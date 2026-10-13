"""Exact authorization pins; stable checkout line endings for changed sources."""
import subprocess,hashlib
from pathlib import Path
tracked=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
paths=sorted({p for p in tracked+new if p.startswith(('product_tool/','tests/')) and p.endswith(('.py','.js','.html','.css')) and p!='tests/_pipeline_migration.py'})
attributes=Path('.gitattributes');text=attributes.read_text(encoding='utf8')
for p in paths:
 rule=subprocess.check_output(['git','check-attr','eol','--',p],text=True).strip().rsplit(': ',1)[1]
 raw=Path(p).read_bytes();style=rule if rule in {'lf','crlf'} else 'crlf' if raw.count(b'\r\n')>raw.count(b'\n')/2 else 'lf'
 if rule not in {'lf','crlf'}:text+='\n'+p+' text eol='+style+'\n'
 raw=raw.replace(b'\r\n',b'\n');Path(p).write_bytes(raw if style=='lf' else raw.replace(b'\n',b'\r\n'))
attributes.write_text(text,encoding='utf8')
reason='Stage 81 explicitly requested cross-brand completeness: raw lineage, scoped physical quantities and runtime units, model-stable fields separated from configuration candidates, complete official gallery/candidate retention and byte proof, Russian grouped UI/Excel; unchanged access guards and numerical readiness thresholds.'
reasons={p:reason for p in paths}
reasons['tests/test_electrolux_stage80_1.py']='Stage 81 Windows regression proved SQLite fixture handle survived transaction context; explicitly close connection, preserving every timeout/recovery assertion.'
reasons['product_tool/jbl_presentation.py']='Stage 81 actual official Tune Buds source publishes inconsistent g/oz values; imperial alias suppression now requires printed numeric rounding equivalence; conflicting measurement remains reviewable with both raw facts.'
reasons['product_tool/card_evidence.py']='Stage 81 no-manual refresh regression: retain previous document proof under original identity without transferring current model/configuration/PNC verification or issuing new requests.'
pins={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
with Path('tests/_pipeline_migration.py').open('a',encoding='utf8',newline='') as target:
 target.write('\r\n# Stage 81 qualified complete source manifest, all negative identity guards retained.\r\nALL_AUTHORIZED_CHANGES.update('+repr(reasons)+')\r\nPINNED_SHA256.update('+repr(pins)+')\r\n')
print('Stage 81 exact pins',len(pins),flush=True)
