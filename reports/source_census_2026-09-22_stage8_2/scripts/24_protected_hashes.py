import json
import hashlib
from pathlib import Path

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

s81_files = sorted(str(p.relative_to('.')).replace('\\', '/') for p in Path('reports/source_census_2026-09-22_stage8_1').rglob('*') if p.is_file())
s81_files.append('tests/test_structural_census_v8_1.py')
s81_hashes_now = {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in s81_files}

out = {
    'checked_at': '2026-09-22',
    'stage8_manifest_check': {'total': len(h8), 'missing': miss8, 'mismatches': mism8},
    'stage8_1_files_hashed_now': s81_hashes_now,
    'stage8_1_file_count': len(s81_files),
    'note': 'Stage 8.1 had no pre-existing hash manifest of its own; this records its current hashes as the reference point going forward. Stage 8.2 wrote nothing into either directory.',
}
Path('reports/source_census_2026-09-22_stage8_2/protected_hashes_check.json').write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print('stage8 missing/mismatch:', len(miss8), len(mism8))
print('stage8.1 files hashed:', len(s81_files))
