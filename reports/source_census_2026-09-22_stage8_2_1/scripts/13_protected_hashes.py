import json
import hashlib
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_1')

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

s81_hashes = hash_dir('reports/source_census_2026-09-22_stage8_1')
s81_hashes['tests/test_structural_census_v8_1.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_1.py').read_bytes()).hexdigest()

s82_hashes = hash_dir('reports/source_census_2026-09-22_stage8_2')
s82_hashes['tests/test_structural_census_v8_2.py'] = hashlib.sha256(Path('tests/test_structural_census_v8_2.py').read_bytes()).hexdigest()

out = {
    'checked_at': '2026-09-22',
    'stage8_manifest_check': {'total': len(h8), 'missing': miss8, 'mismatches': mism8},
    'stage8_1_files_hashed_now': s81_hashes,
    'stage8_2_files_hashed_now': s82_hashes,
    'note': 'Stage 8.2.1 wrote nothing into Stage 8, Stage 8.1 or Stage 8.2 directories; these hashes are the post-run reference point.',
}
Path(OUT / 'protected_hashes_check.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print('stage8:', len(miss8), len(mism8), 'stage8.1 files:', len(s81_hashes), 'stage8.2 files:', len(s82_hashes))
