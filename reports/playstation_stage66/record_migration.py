"""Append the explicit Stage 66 authorization to the existing hash registry."""
from pathlib import Path
import hashlib,json,subprocess
p=Path('tests/_pipeline_migration.py');text=p.read_text(encoding='utf-8');assert 'STAGE66_AUTHORIZED_CHANGES' not in text
reasons={
 'product_tool/worker.py':'PlayStation/SIE dispatch reuses common run_once and injectable adapters.',
 'product_tool/resolution.py':'Separate official model, exact CFI hardware and retail configuration scopes; sensitive family fields withheld.',
 'product_tool/readiness.py':'Route PlayStation to evidence gate; User Guide advisory; configuration and exact photos required.',
 'product_tool/web.py':'Render PlayStation model/configuration, candidates and manual status; exact gallery identity.',
 'product_tool/templates/product.html':'PlayStation evidence, raw candidates, bundle fields and document roles in existing product UI.',
 'product_tool/exporter.py':'Native Excel audit sheets for PlayStation identity/configuration, candidates and document roles.',
 'product_tool/display.py':'Russian PlayStation scope status labels; other source labels unchanged.',
 'product_tool/attribute_projection.py':'PlayStation-only Russian dimension labels and metric unit presentation.',
 'product_tool/photo_metadata.py':'Allow measured image bytes on official PlayStation hosts for the PlayStation source keys.',
}
pins={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in reasons}
text+='\n# Stage 66: user-authorized PlayStation baseline and shared-pipeline adapter.\nSTAGE66_AUTHORIZED_CHANGES = '+repr(reasons)+'\nALL_AUTHORIZED_CHANGES.update(STAGE66_AUTHORIZED_CHANGES)\nSTAGE66_PINNED_SHA256 = '+repr(pins)+'\nPINNED_SHA256.update(STAGE66_PINNED_SHA256)\n'
p.write_text(text,encoding='utf-8')
Path('reports/playstation_stage66/migration_record.json').write_text(json.dumps(dict(reason='Explicit Stage 66 implementation request; no archived report rewritten',authorized_changes=reasons,pins=pins),indent=2),encoding='utf-8')
print('Stage 66 migration recorded:',len(pins),'files')
