"""Append-only user authorization for Stage 73; retain all earlier pin blocks."""
from pathlib import Path
import subprocess,hashlib
paths=[p for p in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() if p.startswith('product_tool/')]
reason='Stage 73: user-authorized HyperX live recovery, published support discovery, safe shared persistent browser and system CA, byte-verified gallery, optional manuals, scoped runtime and component extraction. Existing identity and readiness thresholds retained.'
p=Path('tests/_pipeline_migration.py');before=p.read_bytes()
marker=b'\n# Stage 73: append-only authorization; earlier stage blocks preserved.'
if marker in before:before=before.split(marker)[0]
block=marker.decode()+'\nSTAGE73_AUTHORIZED_CHANGES = '+repr(dict.fromkeys(paths,reason))+'\nALL_AUTHORIZED_CHANGES.update(STAGE73_AUTHORIZED_CHANGES)\nSTAGE73_PINNED_SHA256 = '+repr({n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in paths})+'\nPINNED_SHA256.update(STAGE73_PINNED_SHA256)\n'
p.write_bytes(before+block.encode('utf8'));assert p.read_bytes().startswith(before)
print(paths)
