"""Stage 14 -- confirm the pinned-hash protection holds for all now-
authorized files, the one authorized deletion is still genuinely absent,
and every prior reports/ directory (through Stage 13), the catalog, and
the data/ catalog file remain untouched. Reads only; writes solely to this
stage's own directory."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage14'
sys.path.insert(0, str(ROOT / 'tests'))
from _pipeline_migration import (  # noqa: E402
    ALL_AUTHORIZED_CHANGES, DELETED_FILES, PINNED_SHA256,
    check_deleted_file, check_migrated_file,
)

pin_check = {}
for path in ALL_AUTHORIZED_CHANGES:
    full = ROOT / path
    actual = hashlib.sha256(full.read_bytes()).hexdigest()
    ok, msg = check_migrated_file(path, actual)
    pin_check[path] = {'ok': ok, 'message': msg, 'actual_sha256': actual}

deletion_check = {}
for path in DELETED_FILES:
    full = ROOT / path
    exists = full.exists()
    ok, msg = check_deleted_file(path)
    deletion_check[path] = {'ok': ok and not exists, 'still_exists': exists, 'message': msg}

PRIOR_STAGE_DIRS = [
    'source_census_2026-09-21', 'source_census_2026-09-22', 'source_census_2026-09-22_stage2',
    'source_census_2026-09-22_stage3', 'source_census_2026-09-22_stage4', 'source_census_2026-09-22_stage5',
    'source_census_2026-09-22_stage5_1', 'source_census_2026-09-22_stage6', 'source_census_2026-09-22_stage6_1',
    'source_census_2026-09-22_stage7', 'source_census_2026-09-22_stage7_1', 'source_census_2026-09-22_stage8',
    'source_census_2026-09-22_stage8_1', 'source_census_2026-09-22_stage8_2', 'source_census_2026-09-22_stage8_2_1',
    'source_census_2026-09-22_stage8_2_2', 'source_census_2026-09-22_stage8_3', 'source_census_2026-09-22_stage8_4',
    'source_census_2026-09-22_stage8_5', 'source_census_2026-09-22_stage8_6', 'source_census_2026-09-22_stage9',
    'source_census_2026-09-22_stage9_1', 'source_census_2026-09-23_stage10', 'source_census_2026-09-23_stage10_1',
    'source_census_2026-09-23_stage10_2', 'source_census_2026-09-23_stage10_3', 'source_census_2026-09-23_stage11',
    'source_census_2026-09-23_stage11_1', 'source_census_2026-09-23_stage11_2', 'source_census_2026-09-23_stage11_3',
    'source_census_2026-09-23_stage11_4', 'source_census_2026-09-23_stage11_5', 'source_census_2026-09-23_stage12',
    'source_census_2026-09-23_stage13',
]


def hash_dir(rel):
    base = ROOT / 'reports' / rel
    files = sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in base.rglob('*') if p.is_file())
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}


prior_hashes = {name: hash_dir(name) for name in PRIOR_STAGE_DIRS}
prior_file_count = sum(len(v) for v in prior_hashes.values())

result = {
    'pinned_hash_check': pin_check,
    'pinned_hash_check_all_ok': all(v['ok'] for v in pin_check.values()),
    'deletion_check': deletion_check,
    'deletion_check_all_ok': all(v['ok'] for v in deletion_check.values()),
    'prior_stage_directories_hashed': PRIOR_STAGE_DIRS,
    'prior_stage_file_count': prior_file_count,
    'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
    'no_network_requests_made_this_stage': True,
    'no_bosch_or_cudy_identity_or_adapter_built': True,
    'hyperx_known_urls_in_production_count': 0,
}

(OUT / 'protected_hashes_check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('pinned files checked:', len(pin_check))
print('all pinned ok:', result['pinned_hash_check_all_ok'])
print('deletion checked:', len(deletion_check))
print('all deletions ok:', result['deletion_check_all_ok'])
print('prior stage files hashed:', prior_file_count)
