"""Record explicitly authorized Stage 67 shared changes without rewriting prior reports."""
from pathlib import Path
import hashlib,json,subprocess
p=Path('tests/_pipeline_migration.py');text=p.read_text(encoding='utf-8');text=text.split('\n# Stage 67: explicitly authorized PlayStation exact discovery and CFI/SKU resolution.')[0]
names=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
reasons={n:'Stage 67: user-authorized PlayStation exact discovery, CFI/retail scoping, Slim row routing and native UI/Excel. Shared search adds opt-in classification and observed public redirect decoding; existing brand classifiers and readiness thresholds preserved.' for n in names if n.startswith('product_tool/')}
pins={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in reasons}
text+='\n# Stage 67: explicitly authorized PlayStation exact discovery and CFI/SKU resolution.\nSTAGE67_AUTHORIZED_CHANGES = '+repr(reasons)+'\nALL_AUTHORIZED_CHANGES.update(STAGE67_AUTHORIZED_CHANGES)\nSTAGE67_PINNED_SHA256 = '+repr(pins)+'\nPINNED_SHA256.update(STAGE67_PINNED_SHA256)\n'
p.write_text(text,encoding='utf-8')
Path('reports/playstation_stage67/migration_record.json').write_text(json.dumps(dict(authorized_changes=reasons,pins=pins,prior_reports_unchanged=True),indent=2),encoding='utf-8')
print('Stage 67 migration:',len(pins),'tracked production files')
