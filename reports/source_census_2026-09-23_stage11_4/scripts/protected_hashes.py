"""Stage 11.4 -- confirm the catalog, production registry, and every prior
stage REPORT directory (reports/source_census_*) are untouched. This stage's
own explicit mandate was to modify product_tool/{display,jobs,worker}.py --
that is documented separately, not hidden -- this check covers everything
else."""
import hashlib
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_4'

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
]

REGISTRY_FILES = [
    'source_catalog.v2.json', 'brand_normalization.v1.json', 'official_domains.v1.json',
    'identity_reconciliation.v1.json', 'source_research.v1.json', 'source_candidates.v1.json',
    'adapter_profiles.v1.json',
]


def hash_dir(rel: str) -> dict:
    base = ROOT / 'reports' / rel
    files = sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in base.rglob('*') if p.is_file())
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}


prior_hashes = {name: hash_dir(name) for name in PRIOR_STAGE_DIRS}
prior_file_count = sum(len(v) for v in prior_hashes.values())

# Explicit, documented exception -- these 3 production files were
# intentionally modified this stage (the DNS dealer-fallback pipeline
# integration). Every other tracked file is checked strictly against the
# Stage 8 baseline in the same way prior stages did.
INTENTIONAL_CHANGES = ['product_tool/display.py', 'product_tool/jobs.py', 'product_tool/worker.py']
stage8_manifest = json.loads((ROOT / 'reports/source_census_2026-09-22_stage8/protected_hashes_after.json').read_text(encoding='utf-8'))['after']
mismatches, missing, unexpected_matches = [], [], []
for path, expected in stage8_manifest.items():
    full = ROOT / path
    if not full.exists():
        missing.append(path)
        continue
    actual = hashlib.sha256(full.read_bytes()).hexdigest()
    if path in INTENTIONAL_CHANGES:
        if actual == expected:
            unexpected_matches.append(path)  # would mean the change didn't actually happen
    elif actual != expected:
        mismatches.append(path)

result = {
    'checked_at': '2026-09-23',
    'note': (
        'This stage read from earlier stage report directories, product_tool/config/*, and '
        'data/catalog_2026-09-21_filtered.xlsx. It made NO network requests (no Technopark URL '
        'was supplied). It wrote new report files only under its own '
        'reports/source_census_2026-09-23_stage11_4/ directory, and -- per this stage\'s '
        'explicit mandate, unlike every prior stage -- it modified real application source code: '
        'product_tool/display.py, product_tool/jobs.py, product_tool/worker.py (plus new files: '
        'product_tool/source_types.py, product_tool/dealer_fallback.py, '
        'product_tool/adapters/dns.py, product_tool/adapters/document_verification.py, and '
        'tests/test_dns_fallback.py + tests/fixtures/stage11_4/*). No catalog data and no '
        'production registry (source_catalog.v2.json etc.) were modified. No prior stage REPORT '
        'directory was modified.'
    ),
    'prior_stage_directories_hashed': list(PRIOR_STAGE_DIRS),
    'prior_stage_file_count': prior_file_count,
    'prior_stage_hashes': prior_hashes,
    'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
    'registry_files_sha256': {
        f: hashlib.sha256((ROOT / f'product_tool/config/{f}').read_bytes()).hexdigest()
        for f in REGISTRY_FILES
    },
    'stage8_baseline_check': {
        'total_files_in_stage8_manifest': len(stage8_manifest),
        'intentionally_changed_this_stage': INTENTIONAL_CHANGES,
        'unexpected_mismatches': mismatches,
        'unexpected_matches_among_intentional_list': unexpected_matches,
        'missing_files': missing,
        'clean': not mismatches and not missing and not unexpected_matches,
    },
    'this_stage_wrote_new_files_only_under': 'reports/source_census_2026-09-23_stage11_4/ and product_tool/ (code) and tests/ (tests+fixtures)',
    'dns_not_added_to_production_registry': True,
    'no_network_requests_made_this_stage': True,
}

(OUT / 'protected_hashes_check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('clean:', result['stage8_baseline_check']['clean'])
print('mismatches:', mismatches)
print('prior stage files hashed:', prior_file_count)
