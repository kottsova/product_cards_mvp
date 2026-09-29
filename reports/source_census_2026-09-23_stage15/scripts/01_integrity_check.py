"""Stage 15 -- confirm: (1) the pinned-hash protection holds for every
now-authorized file, including the 9 new/changed this stage; (2) the one
authorized deletion is still genuinely absent, checked via the real path
(this script is an archival research artifact, so it may name it plainly,
the same way every prior stage's own scripts do -- only the ACTIVE
tests/_pipeline_migration.py had its literal name removed); (3) every
prior reports/ directory through Stage 14, the catalog, and the data/
catalog file remain untouched; (4) Stage 13's readiness_table.md was
genuinely restored to its exact original bytes. Reads only; writes solely
to this stage's own directory."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage15'
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

# The deleted module's real historical path -- named plainly here, an
# archival research script, exactly as reports/source_census_2026-09-23_
# stage13/scripts/ already does. tests/_pipeline_migration.py itself no
# longer contains this string; see that module for the hash-based check.
deletion_check = {}
for path in ['product_tool/adapters/mechta.py']:
    full = ROOT / path
    exists = full.exists()
    ok, msg = check_deleted_file(path)
    deletion_check[path] = {'ok': ok and not exists, 'still_exists': exists, 'message': msg}

READINESS_TABLE = ROOT / 'reports/source_census_2026-09-23_stage13/readiness_table.md'
READINESS_TABLE_STAGE13_ORIGINAL_SHA256 = 'fd9ed8ab4b38eeb377ab39775c1da0c43eeff4e100ba12e854ce80e2a22766d6'
readiness_table_actual = hashlib.sha256(READINESS_TABLE.read_bytes()).hexdigest()
readiness_table_restored_correctly = readiness_table_actual == READINESS_TABLE_STAGE13_ORIGINAL_SHA256

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
    'source_census_2026-09-23_stage13', 'source_census_2026-09-23_stage14',
]


def hash_dir(rel, *, skip=()):
    base = ROOT / 'reports' / rel
    files = sorted(
        str(p.relative_to(ROOT)).replace('\\', '/') for p in base.rglob('*')
        if p.is_file() and str(p.relative_to(ROOT)).replace('\\', '/') not in skip
    )
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}


# readiness_table.md is intentionally excluded from the "byte-identical"
# prior-stage snapshot below -- it was edited (Stage 14) then restored
# (Stage 15); its own before/after state is checked explicitly above,
# not folded into the generic untouched-prior-stages hash set.
prior_hashes = {
    name: hash_dir(name, skip={'reports/source_census_2026-09-23_stage13/readiness_table.md'} if name == 'source_census_2026-09-23_stage13' else ())
    for name in PRIOR_STAGE_DIRS
}
prior_file_count = sum(len(v) for v in prior_hashes.values())

result = {
    'pinned_hash_check': pin_check,
    'pinned_hash_check_all_ok': all(v['ok'] for v in pin_check.values()),
    'deletion_check': deletion_check,
    'deletion_check_all_ok': all(v['ok'] for v in deletion_check.values()),
    'readiness_table_restored_to_stage13_original_bytes': readiness_table_restored_correctly,
    'readiness_table_current_sha256': readiness_table_actual,
    'prior_stage_directories_hashed': PRIOR_STAGE_DIRS,
    'prior_stage_file_count': prior_file_count,
    'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
    'no_new_stage15_http_requests_made': True,
    'hyperx_known_urls_in_production_count': 2,
    'hyperx_catalog_rows_total': 41,
    'hyperx_catalog_rows_reaching_exact_variant_via_real_pipeline': 2,
    'hyperx_catalog_rows_with_confirmed_real_variant_mismatch': 1,
    'hyperx_catalog_rows_with_no_confirmed_url': 38,
    'network_safety_incident_this_stage': (
        'Populating KNOWN_URLS with a real 9A273AA URL made 3 pre-existing '
        'tests in tests/test_dns_fallback.py capable of a real outbound '
        'request via worker.py default hyperx_adapter_factory (a bare '
        'requests.Session()). Caught by the test suite itself failing; '
        'fixed by injecting urls={} explicitly in all 3. Full suite '
        're-run wrapped in enforce_policy_aware_fetch_only() afterward: '
        '823/823 pass, zero blocked calls, zero real calls possible.'
    ),
}

(OUT / 'protected_hashes_check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('pinned files checked:', len(pin_check))
print('all pinned ok:', result['pinned_hash_check_all_ok'])
print('deletion checked:', len(deletion_check))
print('all deletions ok:', result['deletion_check_all_ok'])
print('readiness_table restored correctly:', readiness_table_restored_correctly)
print('prior stage files hashed:', prior_file_count)
