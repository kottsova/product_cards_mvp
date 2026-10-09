from pathlib import Path
import subprocess,hashlib
paths=[x for x in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() if x.startswith('product_tool/')]
reason='Stage 70: user-authorized small Razer adapter, separate model/configuration identity, bounded opt-in public browser capture with challenge/cooldown guards, and scoped Russian UI/Excel. Earlier brand defaults and numeric readiness thresholds preserved.'
target=Path('tests/_pipeline_migration.py');assert 'STAGE70_AUTHORIZED_CHANGES' not in target.read_text(encoding='utf8')
with target.open('a',encoding='utf8',newline='\n') as f:f.write('\n# Stage 70: append-only authorization; prior stage pins preserved.\nSTAGE70_AUTHORIZED_CHANGES = '+repr(dict.fromkeys(paths,reason))+'\nALL_AUTHORIZED_CHANGES.update(STAGE70_AUTHORIZED_CHANGES)\nSTAGE70_PINNED_SHA256 = '+repr({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths})+'\nPINNED_SHA256.update(STAGE70_PINNED_SHA256)\n')
print(paths)
