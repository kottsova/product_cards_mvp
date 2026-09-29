import json
import hashlib
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5')

h8 = json.load(open('reports/source_census_2026-09-22_stage8/protected_hashes_after.json', encoding='utf-8'))['after']
mism8, miss8 = [], []
for path, expected in h8.items():
    p = Path(path)
    if not p.exists():
        miss8.append(path)
        continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != expected:
        mism8.append(path)


def hash_dir(d):
    files = sorted(str(p.relative_to('.')).replace('\\', '/') for p in Path(d).rglob('*') if p.is_file())
    return {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}


s81 = hash_dir('reports/source_census_2026-09-22_stage8_1')
s81['tests/test_structural_census_v8_1.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_1.py').read_bytes()).hexdigest()

s82 = hash_dir('reports/source_census_2026-09-22_stage8_2')
s82['tests/test_structural_census_v8_2.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_2.py').read_bytes()).hexdigest()

s821 = hash_dir('reports/source_census_2026-09-22_stage8_2_1')
s821['tests/test_structural_census_v8_2_1.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_2_1.py').read_bytes()).hexdigest()

s822 = hash_dir('reports/source_census_2026-09-22_stage8_2_2')
s822['tests/test_structural_census_v8_2_2.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_2_2.py').read_bytes()).hexdigest()

s83 = hash_dir('reports/source_census_2026-09-22_stage8_3')
s83['tests/test_structural_census_v8_3.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_3.py').read_bytes()).hexdigest()

s84 = hash_dir('reports/source_census_2026-09-22_stage8_4')
s84['tests/test_structural_census_v8_4.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_4.py').read_bytes()).hexdigest()

out = {
    'checked_at': '2026-09-22',
    'stage8_manifest_check': {'total': len(h8), 'missing': miss8, 'mismatches': mism8},
    'stage8_1_files_hashed_now': s81,
    'stage8_2_files_hashed_now': s82,
    'stage8_2_1_files_hashed_now': s821,
    'stage8_2_2_files_hashed_now': s822,
    'stage8_3_files_hashed_now': s83,
    'stage8_4_files_hashed_now': s84,
    'note': 'Stage 8.5 wrote nothing into Stage 8, 8.1, 8.2, 8.2.1, 8.2.2, 8.3 or 8.4 directories; these hashes are the post-run reference point. The source catalog and production registry were only read, never written.',
    'catalog_and_registry_untouched': {
        'catalog_sha256': hashlib.sha256(Path('data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest(),
        'registry_files_sha256': {
            f: hashlib.sha256(Path(f'product_tool/config/{f}').read_bytes()).hexdigest()
            for f in ('source_catalog.v2.json', 'brand_normalization.v1.json', 'official_domains.v1.json')
        },
    },
}
Path(OUT / 'protected_hashes_check.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print('stage8:', len(miss8), len(mism8), 'stage8.1:', len(s81), 'stage8.2:', len(s82), 'stage8.2.1:', len(s821), 'stage8.2.2:', len(s822), 'stage8.3:', len(s83), 'stage8.4:', len(s84))
