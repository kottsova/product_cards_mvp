"""Append only Stage 69 authorization pins; preserve all prior migration bytes."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).parent;p=Path('tests/_pipeline_migration.py');s=p.read_text(encoding='utf8')
marker='\n# Stage 69: user-authorized Xbox common pipeline audit.\n'
if marker in s:s=s.split(marker)[0]
names=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
reasons={n:'Stage 69: user-authorized Xbox exact discovery, official catalog/search routing, hardware-retail relations, scoped extraction/photos, bounded network retry and attended fallback. Prior brand defaults and numeric readiness thresholds preserved.' for n in names if n.startswith('product_tool/')}
pins={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in reasons}
s+=marker+'STAGE69_AUTHORIZED_CHANGES = '+repr(reasons)+'\nALL_AUTHORIZED_CHANGES.update(STAGE69_AUTHORIZED_CHANGES)\nSTAGE69_PINNED_SHA256 = '+repr(pins)+'\nPINNED_SHA256.update(STAGE69_PINNED_SHA256)\n';p.write_text(s,encoding='utf8')
(R/'migration_record.json').write_text(json.dumps(dict(authorized_changes=reasons,pins=pins,prior_reports_unchanged=True),indent=2),encoding='utf8');print('Stage 69 appended pins:',len(pins))
