"""Append-only Stage 74 source authorization; earlier stage blocks retain their bytes."""
from pathlib import Path
import subprocess,hashlib
paths=[p for p in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() if p.startswith('product_tool/')]
paths+=['product_tool/adapters/published_page.py','product_tool/adapters/xiaomi.py','product_tool/xiaomi_identity.py','product_tool/xiaomi_page.py','product_tool/xiaomi_pipeline.py','product_tool/xiaomi_presentation.py']
paths=sorted(set(paths));reason='Stage 74: user-authorized Xiaomi baseline audit and small adapter over existing worker/discovery/policy/resolution; explicit model/hardware/region/retail scopes, component extraction and Russian UI/Excel. No model URL seeds or separate configuration framework; existing thresholds preserved.'
p=Path('tests/_pipeline_migration.py');before=p.read_bytes();marker=b'\n# Stage 74: append-only authorization; earlier stage blocks preserved.'
assert marker not in before
block=marker.decode()+'\nSTAGE74_AUTHORIZED_CHANGES = '+repr(dict.fromkeys(paths,reason))+'\nALL_AUTHORIZED_CHANGES.update(STAGE74_AUTHORIZED_CHANGES)\nSTAGE74_PINNED_SHA256 = '+repr({n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in paths})+'\nPINNED_SHA256.update(STAGE74_PINNED_SHA256)\n'
p.write_bytes(before+block.encode('utf8'));assert p.read_bytes().startswith(before);print('Pinned',len(paths),'application paths')
