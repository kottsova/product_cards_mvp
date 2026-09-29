"""Stage 13 -- product_tool/adapters/mechta.py was part of the Stage 8
baseline manifest and is now deleted, not edited. Every one of the 10
test_structural_census_v8_1..v9_1.py files independently re-checks that
full Stage 8 manifest (test_stage2_to_8_files_byte_identical), so all ten
need the same DELETED_FILES exemption: skip the existence check for an
authorized deletion, but only after confirming the file is ACTUALLY gone
(never a silent pass). Byte-level I/O; idempotent re-run safe."""
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
TESTS = ROOT / 'tests'

IMPORT_OLD = b"from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file\n"
IMPORT_NEW = b"from _pipeline_migration import ALL_AUTHORIZED_CHANGES, DELETED_FILES, check_migrated_file\n"

LOOP_OLD = (
    b"        for path, expected in manifest.items():\n"
    b"            full = ROOT / path\n"
    b"            self.assertTrue(full.exists(), f'protected file missing: {path}')\n"
    b"            actual = hashlib.sha256(full.read_bytes()).hexdigest()\n"
    b"            if path in ALL_AUTHORIZED_CHANGES:\n"
    b"                ok, msg = check_migrated_file(path, actual)\n"
    b"                self.assertTrue(ok, msg)\n"
    b"                continue\n"
    b"            self.assertEqual(actual, expected, f'protected file changed: {path}')"
)
LOOP_NEW = (
    b"        for path, expected in manifest.items():\n"
    b"            full = ROOT / path\n"
    b"            if path in DELETED_FILES:\n"
    b"                self.assertFalse(full.exists(), f'authorized-deleted file still present: {path}')\n"
    b"                continue\n"
    b"            self.assertTrue(full.exists(), f'protected file missing: {path}')\n"
    b"            actual = hashlib.sha256(full.read_bytes()).hexdigest()\n"
    b"            if path in ALL_AUTHORIZED_CHANGES:\n"
    b"                ok, msg = check_migrated_file(path, actual)\n"
    b"                self.assertTrue(ok, msg)\n"
    b"                continue\n"
    b"            self.assertEqual(actual, expected, f'protected file changed: {path}')"
)

FILES = [
    'test_structural_census_v8_1.py', 'test_structural_census_v8_2.py', 'test_structural_census_v8_2_1.py',
    'test_structural_census_v8_2_2.py', 'test_structural_census_v8_3.py', 'test_structural_census_v8_4.py',
    'test_structural_census_v8_5.py', 'test_structural_census_v8_6.py', 'test_structural_census_v9.py',
    'test_structural_census_v9_1.py',
]
REPORT = []

for name in FILES:
    path = TESTS / name
    data = path.read_bytes()
    original = data
    if LOOP_NEW not in data:
        if LOOP_OLD not in data:
            raise SystemExit(f'LOOP PATTERN NOT FOUND in {name}')
        data = data.replace(LOOP_OLD, LOOP_NEW, 1)
    if IMPORT_OLD in data:
        data = data.replace(IMPORT_OLD, IMPORT_NEW, 1)
    if data != original:
        path.write_bytes(data)
        REPORT.append(name)
    else:
        REPORT.append(name + ' (already up to date)')

print('patched:')
for p in REPORT:
    print(' -', p)
