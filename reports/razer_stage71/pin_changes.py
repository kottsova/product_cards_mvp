"""Append Stage 71 authorization; preserve every prior stage block verbatim."""
from pathlib import Path
import subprocess,hashlib
paths=[p for p in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() if p.startswith('product_tool/')]
paths+=['product_tool/census/public_browser.py','product_tool/razer_store.py']
reason='Stage 71: explicitly authorized Razer live session recovery, proved attended temporary-stop resolution, shared rowspan/colspan extraction and scoped SSR retail/gallery evidence. Earlier brand defaults, model identity and numeric readiness thresholds preserved.'
p=Path('tests/_pipeline_migration.py');before=p.read_bytes();assert b'STAGE71_AUTHORIZED_CHANGES' not in before
block='\n# Stage 71: append-only authorization; earlier blocks preserved.\nSTAGE71_AUTHORIZED_CHANGES = '+repr(dict.fromkeys(paths,reason))+'\nALL_AUTHORIZED_CHANGES.update(STAGE71_AUTHORIZED_CHANGES)\nSTAGE71_PINNED_SHA256 = '+repr({n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in paths})+'\nPINNED_SHA256.update(STAGE71_PINNED_SHA256)\n'
p.write_bytes(before+block.encode('utf8'));assert p.read_bytes().startswith(before)
print(paths)
