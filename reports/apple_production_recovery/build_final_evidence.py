"""Publish proof from the last actual worker run, not from parser fixtures."""
import json,hashlib,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import photo_inventory
out=Path(__file__).parent;root=out.resolve().parents[1]
r=json.loads((out/'actual_production.json').read_text(encoding='utf8'))
gallery=photo_inventory.enriched_photos(root/'data/batches.sqlite3',84)
(out/'final_gallery.json').write_text(json.dumps(gallery,ensure_ascii=False,indent=2),encoding='utf8')
assert all(p['identity_confirmed'] and p['byte_verified'] and p['official_color']=='silver' for p in gallery)
assert len(gallery)==1 and r['readiness']['verdict']=='export_ready'
assert not any(f['conflict'] or f['full_sku_confirmed'] for f in r['resolved'])
events=r['trace'];phases=[]
for e in events:
    phases.append({k:e[k] for k in ('timestamp','event','stage','url','query','accepted','reason') if k in e})
summary=dict(product_id=84,job_id=r['job']['id'],evidence_mode=r['evidence_mode'],job=r['job'],readiness=r['readiness'],
    chain=phases,photos=gallery,raw_fields=len(r['evidence']['model_evidence']['raw_specs']),
    admitted_fields=len(r['evidence']['model_evidence']['admitted']),retail_candidates=r['evidence']['retail_candidates'],
    source_ambiguity_handling='Supplier part number unproven; Store candidates not promoted to supplier identity')
if (out/'regression.json').exists():summary['regression']=json.loads((out/'regression.json').read_text(encoding='utf8'))
if (out/'environment_recheck.json').exists():summary['environment_recheck']=json.loads((out/'environment_recheck.json').read_text(encoding='utf8'))
(out/'qualification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(job=r['job']['id'],ready=r['readiness']['verdict'],confirmed_specs=r['readiness']['confirmed_specs'],photos=len(gallery),byte_verified=True),ensure_ascii=False))
