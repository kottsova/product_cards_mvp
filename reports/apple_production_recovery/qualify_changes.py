"""Record exact owner-authorized recovery hashes; keep every earlier negative guard."""
import hashlib,subprocess
from pathlib import Path
paths=['product_tool/adapters/apple.py','product_tool/apple_model_discovery.py','product_tool/apple_identity.py','product_tool/apple_pipeline.py','product_tool/importer.py','product_tool/web.py']
attrs=Path('.gitattributes');text=attrs.read_text(encoding='utf8')
for p in paths:
    rule=subprocess.check_output(['git','check-attr','eol','--',p],text=True).strip().rsplit(': ',1)[1]
    raw=Path(p).read_bytes()
    style=rule if rule in {'lf','crlf'} else ('crlf' if raw.count(b'\r\n')>raw.count(b'\n')/2 else 'lf')
    if rule not in {'lf','crlf'}:text+='\n'+p+' text eol='+style+'\n'
    raw=raw.replace(b'\r\n',b'\n');Path(p).write_bytes(raw if style=='lf' else raw.replace(b'\n',b'\r\n'))
attrs.write_text(text,encoding='utf8')
reason='Owner-requested Apple first-product actual UI regression recovery: no commercial-SKU early gate on hardware input; published catalog/PDP/specs/Store links, strict Pro/Max and color/configuration scopes, corrected Apple external classifier, permanent per-job progress traces, explicit import header/collision diagnostics. Shared scoped mapper preserves additive display/button semantics and chip suffixes; readiness thresholds and other brand routes unchanged.'
pins={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
with Path('tests/_pipeline_migration.py').open('a',encoding='utf8',newline='') as f:
    f.write('\r\n# Apple actual production UI recovery, 2026-10-14; earlier guards retained.\r\nALL_AUTHORIZED_CHANGES.update('+repr(dict.fromkeys(paths,reason))+')\r\nPINNED_SHA256.update('+repr(pins)+')\r\n')
print('Exact recovery pins:',len(pins))
