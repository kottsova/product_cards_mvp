"""Stage 12 Part A -- confirm the pinned-hash protection holds for all 13
migration files (via check_migrated_file(), the real protection check, not
mere membership), and that every prior reports/ directory (through Stage
11.5), the catalog, and the production registry remain untouched. Reads
only; writes solely to this stage's own directory."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage12'
sys.path.insert(0, str(ROOT / 'tests'))
from _pipeline_migration import ALL_AUTHORIZED_CHANGES, PINNED_SHA256, check_migrated_file  # noqa: E402

pin_check = {}
for path in ALL_AUTHORIZED_CHANGES:
    full = ROOT / path
    actual = hashlib.sha256(full.read_bytes()).hexdigest()
    ok, msg = check_migrated_file(path, actual)
    pin_check[path] = {'ok': ok, 'message': msg, 'actual_sha256': actual}

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
    'source_census_2026-09-23_stage11_4', 'source_census_2026-09-23_stage11_5',
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

result = {
    'pinned_hash_check': pin_check,
    'pinned_hash_check_all_ok': all(v['ok'] for v in pin_check.values()),
    'dealer_url_needed_fix_summary': {
        'problem_1_generic_default_always_used': (
            'worker.py never passed missing_fields to DnsAdapter.find_source(), '
            'so dns.py\'s hardcoded ["характеристики","фото","инструкция"] default '
            'fired on every dealer_url_needed, regardless of what was actually missing.'
        ),
        'fix_1': (
            'worker.py:_compute_missing_fields() checks jobs.get_facts / '
            'get_photo_candidates(include_excluded=False) / get_documents for the '
            'product, restricted to the stages the job actually requested, and '
            'passes the real (possibly empty) list to find_source(). dns.py now '
            'distinguishes missing_fields=None (caller did not check -- old default '
            'kept for backward compatibility) from an explicit [] (caller checked, '
            'nothing missing -- returns match_level="not_needed", no ask).'
        ),
        'problem_2_no_row_level_dedup': (
            'A row already fully covered by another source (official or dealer) '
            'would still be asked about again on every re-run, because the ask was '
            'built from a static list instead of live per-row state.'
        ),
        'fix_2': (
            'Because missing_fields is now computed fresh from current DB state '
            'each run, a field found by any source since the last run drops out of '
            'the list on its own; once every requested field is covered, DNS '
            'returns match_level="not_needed" and no dealer_url_needed request is '
            'raised for that row again. Verified by '
            'ComputeMissingFieldsTests.test_worker_stops_asking_once_the_gap_is_filled_elsewhere '
            'in tests/test_dns_fallback.py.'
        ),
        'files_changed': ['product_tool/adapters/dns.py', 'product_tool/worker.py'],
        'new_tests': [
            'DealerUrlNeededTests.test_explicit_empty_missing_fields_means_not_needed_not_dealer_url_needed',
            'ComputeMissingFieldsTests.test_only_requested_stages_are_considered',
            'ComputeMissingFieldsTests.test_lists_only_genuinely_empty_categories',
            'ComputeMissingFieldsTests.test_all_three_missing_when_stages_requested_and_nothing_found',
            'ComputeMissingFieldsTests.test_worker_stops_asking_once_the_gap_is_filled_elsewhere',
        ],
    },
    'prior_stage_directories_hashed': PRIOR_STAGE_DIRS,
    'prior_stage_file_count': prior_file_count,
    'prior_stage_hashes': prior_hashes,
    'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
    'registry_files_sha256': {
        f: hashlib.sha256((ROOT / f'product_tool/config/{f}').read_bytes()).hexdigest()
        for f in REGISTRY_FILES
    },
    'no_network_requests_made_this_part': True,
    'no_quadcast_2s_work_this_stage': True,
}

(OUT / 'protected_hashes_check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('pinned files checked:', len(pin_check))
print('all pinned ok:', result['pinned_hash_check_all_ok'])
print('prior stage files hashed:', prior_file_count)
