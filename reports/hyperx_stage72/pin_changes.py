"""Append-only Stage 72 authorization; previous pins and reports remain unchanged."""
from pathlib import Path
import subprocess,hashlib
paths=[p for p in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() if p.startswith('product_tool/')]
paths+=['product_tool/adapters/hyperx_discovery.py','product_tool/adapters/hyperx_support.py','product_tool/hyperx_page.py','product_tool/hyperx_audit.py','product_tool/hyperx_presentation.py']
reason='Stage 72: user-authorized HyperX baseline audit and reuse of common discovery, Shopify extraction, scoped model/variant facts, safe access lifecycle and Russian UI/Excel. No separate configuration framework; earlier brands and readiness thresholds retained.'
p=Path('tests/_pipeline_migration.py');before=p.read_bytes()
if b'STAGE72_AUTHORIZED_CHANGES' in before:
    before=before.split(b'\n# Stage 72: append-only authorization; earlier stage blocks preserved.')[0]
block='\n# Stage 72: append-only authorization; earlier stage blocks preserved.\nSTAGE72_AUTHORIZED_CHANGES = '+repr(dict.fromkeys(paths,reason))+'\nALL_AUTHORIZED_CHANGES.update(STAGE72_AUTHORIZED_CHANGES)\nSTAGE72_PINNED_SHA256 = '+repr({n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in paths})+'\nPINNED_SHA256.update(STAGE72_PINNED_SHA256)\n'
p.write_bytes(before+block.encode('utf8'));assert p.read_bytes().startswith(before)
print(paths)
