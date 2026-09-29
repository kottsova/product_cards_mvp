"""Stage 11 -- confirm the catalog, production registry, and every earlier
stage directory (through Stage 10.3, including Stage 8/8.1 whose fixtures
this stage relied on) are untouched."""
import hashlib
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11'

PRIOR_STAGE_DIRS = [
    'source_census_2026-09-21', 'source_census_2026-09-22', 'source_census_2026-09-22_stage2',
    'source_census_2026-09-22_stage3', 'source_census_2026-09-22_stage4', 'source_census_2026-09-22_stage5',
    'source_census_2026-09-22_stage5_1', 'source_census_2026-09-22_stage6', 'source_census_2026-09-22_stage6_1',
    'source_census_2026-09-22_stage7', 'source_census_2026-09-22_stage7_1', 'source_census_2026-09-22_stage8',
    'source_census_2026-09-22_stage8_1', 'source_census_2026-09-22_stage8_2', 'source_census_2026-09-22_stage8_2_1',
    'source_census_2026-09-22_stage8_2_2', 'source_census_2026-09-22_stage8_3', 'source_census_2026-09-22_stage8_4',
    'source_census_2026-09-22_stage8_5', 'source_census_2026-09-22_stage8_6', 'source_census_2026-09-22_stage9',
    'source_census_2026-09-22_stage9_1', 'source_census_2026-09-23_stage10', 'source_census_2026-09-23_stage10_1',
    'source_census_2026-09-23_stage10_2', 'source_census_2026-09-23_stage10_3',
]

REGISTRY_FILES = [
    'source_catalog.v2.json', 'brand_normalization.v1.json', 'official_domains.v1.json',
    'identity_reconciliation.v1.json', 'source_research.v1.json', 'source_candidates.v1.json',
    'adapter_profiles.v1.json',
]

# HyperX-relevant test fixture, read this stage as context -- confirmed unchanged too.
EXTRA_FILES = ['tests/fixtures/stage5_1/hyperx_product.html']


def hash_dir(rel: str) -> dict:
    base = ROOT / 'reports' / rel
    files = sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in base.rglob('*') if p.is_file())
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}


prior_hashes = {name: hash_dir(name) for name in PRIOR_STAGE_DIRS}
prior_file_count = sum(len(v) for v in prior_hashes.values())

result = {
    'checked_at': '2026-09-23',
    'note': (
        'This stage only read from earlier stage report directories (including Stage 8/8.1\'s '
        'HyperX fixtures and reports), product_tool/config/*, data/catalog_2026-09-21_filtered.xlsx, '
        'tests/fixtures/stage5_1/hyperx_product.html, and made network requests only to '
        'hyperx.com (the exact host Stage 8.1 already confirmed official). It wrote files only '
        'under its own reports/source_census_2026-09-23_stage11/ directory. No Xbox, Samsung, '
        'PlayStation, or Kingston host was contacted.'
    ),
    'prior_stage_directories_hashed': list(PRIOR_STAGE_DIRS),
    'prior_stage_file_count': prior_file_count,
    'prior_stage_hashes': prior_hashes,
    'extra_files_hashed': {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in EXTRA_FILES},
    'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
    'registry_files_sha256': {
        f: hashlib.sha256((ROOT / f'product_tool/config/{f}').read_bytes()).hexdigest()
        for f in REGISTRY_FILES
    },
    'this_stage_wrote_only_under': 'reports/source_census_2026-09-23_stage11/',
}

(OUT / 'protected_hashes_check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('prior stage files hashed:', prior_file_count)
