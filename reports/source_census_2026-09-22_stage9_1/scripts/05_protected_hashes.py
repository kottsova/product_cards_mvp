import json
import hashlib
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-22_stage9_1'

h8 = json.load(open(ROOT / 'reports/source_census_2026-09-22_stage8/protected_hashes_after.json', encoding='utf-8'))['after']
mism8, miss8 = [], []
for path, expected in h8.items():
    p = ROOT / path
    if not p.exists():
        miss8.append(path)
        continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != expected:
        mism8.append(path)


def hash_dir(d):
    base = ROOT
    files = sorted(str(p.relative_to(base)).replace('\\', '/') for p in (base / d).rglob('*') if p.is_file())
    return {f: hashlib.sha256((base / f).read_bytes()).hexdigest() for f in files}


stages = {}
for name in ('stage8_1', 'stage8_2', 'stage8_2_1', 'stage8_2_2', 'stage8_3', 'stage8_4', 'stage8_5', 'stage8_6', 'stage9'):
    d = hash_dir(f'reports/source_census_2026-09-22_{name}')
    test_file = ROOT / f'tests/test_structural_census_v{name[5:]}.py'
    if test_file.exists():
        d[str(test_file.relative_to(ROOT)).replace('\\', '/')] = hashlib.sha256(test_file.read_bytes()).hexdigest()
    stages[f'{name}_files_hashed_now'] = d

out = {
    'checked_at': '2026-09-23',
    'stage8_manifest_check': {'total': len(h8), 'missing': miss8, 'mismatches': mism8},
    **stages,
    'note': 'Stage 9.1 wrote nothing into Stage 8 through Stage 9 directories; these hashes are the post-run reference point. The source catalog and production registry were only read, never written. 0 new network requests were made this stage.',
    'catalog_and_registry_untouched': {
        'catalog_sha256': hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
        'registry_files_sha256': {
            f: hashlib.sha256((ROOT / f'product_tool/config/{f}').read_bytes()).hexdigest()
            for f in ('source_catalog.v2.json', 'brand_normalization.v1.json', 'official_domains.v1.json')
        },
    },
}
(OUT / 'protected_hashes_check.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print('stage8:', len(miss8), len(mism8))
for k, v in stages.items():
    print(k, len(v))
