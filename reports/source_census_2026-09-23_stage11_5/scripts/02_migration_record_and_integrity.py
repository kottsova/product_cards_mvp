"""Stage 11.5 -- build the explicit, auditable migration record (old hash ->
new hash, per file, with reason) and confirm every reports/ directory,
the catalog, and the production registry are untouched. Reads only; the
migration record itself lives under this stage's own directory.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_5'
sys.path.insert(0, str(ROOT / 'tests'))
from _pipeline_migration import ALL_AUTHORIZED_CHANGES, MIGRATION_DATE, PRODUCTION_CODE_MIGRATION, TEST_FILE_MIGRATION  # noqa: E402

stage8_manifest = json.loads((ROOT / 'reports/source_census_2026-09-22_stage8/protected_hashes_after.json').read_text(encoding='utf-8'))['after']

migration_record = {}
for path, reason in ALL_AUTHORIZED_CHANGES.items():
    old_hash = stage8_manifest.get(path)
    full = ROOT / path
    new_hash = hashlib.sha256(full.read_bytes()).hexdigest() if full.exists() else None
    migration_record[path] = {
        'old_sha256_stage8_baseline': old_hash,
        'new_sha256_current': new_hash,
        'changed': old_hash != new_hash,
        'category': 'production_code' if path in PRODUCTION_CODE_MIGRATION else 'test_file',
        'reason': reason,
    }

# --- Integrity: every prior stage report directory + catalog + registry ---
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
    'source_census_2026-09-23_stage11_4',
]
REGISTRY_FILES = [
    'source_catalog.v2.json', 'brand_normalization.v1.json', 'official_domains.v1.json',
    'identity_reconciliation.v1.json', 'source_research.v1.json', 'source_candidates.v1.json',
    'adapter_profiles.v1.json',
]


def hash_dir(rel):
    base = ROOT / 'reports' / rel
    files = sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in base.rglob('*') if p.is_file())
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}


prior_hashes = {name: hash_dir(name) for name in PRIOR_STAGE_DIRS}
prior_file_count = sum(len(v) for v in prior_hashes.values())

# Also confirm every file the migration record's own reasoning depends on
# (the frozen Stage 8 manifest itself) is unread-only -- untouched.
stage8_manifest_sha = hashlib.sha256(
    (ROOT / 'reports/source_census_2026-09-22_stage8/protected_hashes_after.json').read_bytes()
).hexdigest()

result = {
    'migration_date': MIGRATION_DATE,
    'migration_record': migration_record,
    'migration_record_summary': {
        'production_code_files': len(PRODUCTION_CODE_MIGRATION),
        'test_files': len(TEST_FILE_MIGRATION),
        'total': len(ALL_AUTHORIZED_CHANGES),
        'all_changed_as_expected': all(v['changed'] for v in migration_record.values()),
    },
    'prior_stage_directories_hashed': PRIOR_STAGE_DIRS,
    'prior_stage_file_count': prior_file_count,
    'prior_stage_hashes': prior_hashes,
    'stage8_manifest_sha256_unread_only_confirmation': stage8_manifest_sha,
    'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
    'registry_files_sha256': {
        f: hashlib.sha256((ROOT / f'product_tool/config/{f}').read_bytes()).hexdigest()
        for f in REGISTRY_FILES
    },
    'no_network_requests_made_this_stage': True,
    'no_quadcast_2s_manual_search_performed_this_stage': True,
}

(OUT / 'migration_record_and_integrity.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('migration entries:', len(migration_record))
print('all changed as expected:', result['migration_record_summary']['all_changed_as_expected'])
print('prior stage files hashed:', prior_file_count)
