"""Stage 13 -- product_tool/config/source_catalog.v2.json is being
deliberately, authorizedly changed this stage (Mechta removed). Every
per-stage regression test that hash-checks 'product_tool/config/*' files
against a frozen snapshot needs the same authorized-change exemption the
project already uses elsewhere (tests/_pipeline_migration.py). This patches
the identical 3-line registry_files_sha256 loop found in 11 test files,
adding a local _pipeline_migration import where the file doesn't already
have a top-level one. Byte-level I/O throughout; idempotent re-run safe."""
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
TESTS = ROOT / 'tests'

OLD = (
    b"        for name, expected in check['registry_files_sha256'].items():\n"
    b"            actual = hashlib.sha256((ROOT / 'product_tool/config' / name).read_bytes()).hexdigest()\n"
    b"            self.assertEqual(actual, expected)"
)
NEW_WITH_LOCAL_IMPORT = (
    b"        from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file\n"
    b"        for name, expected in check['registry_files_sha256'].items():\n"
    b"            path = f'product_tool/config/{name}'\n"
    b"            actual = hashlib.sha256((ROOT / 'product_tool/config' / name).read_bytes()).hexdigest()\n"
    b"            if path in ALL_AUTHORIZED_CHANGES:\n"
    b"                ok, msg = check_migrated_file(path, actual)\n"
    b"                self.assertTrue(ok, msg)\n"
    b"                continue\n"
    b"            self.assertEqual(actual, expected)"
)
NEW_TOP_LEVEL_IMPORT_ALREADY_PRESENT = (
    b"        for name, expected in check['registry_files_sha256'].items():\n"
    b"            path = f'product_tool/config/{name}'\n"
    b"            actual = hashlib.sha256((ROOT / 'product_tool/config' / name).read_bytes()).hexdigest()\n"
    b"            if path in ALL_AUTHORIZED_CHANGES:\n"
    b"                ok, msg = check_migrated_file(path, actual)\n"
    b"                self.assertTrue(ok, msg)\n"
    b"                continue\n"
    b"            self.assertEqual(actual, expected)"
)

FILES_WITH_TOP_LEVEL_IMPORT = [
    'test_structural_census_v8_3.py', 'test_structural_census_v8_4.py', 'test_structural_census_v8_6.py',
    'test_structural_census_v9.py', 'test_structural_census_v9_1.py',
]
FILES_NEEDING_LOCAL_IMPORT = [
    'test_structural_census_v10.py', 'test_structural_census_v10_1.py', 'test_structural_census_v10_2.py',
    'test_structural_census_v10_3.py', 'test_structural_census_v11.py', 'test_structural_census_v11_1.py',
]

REPORT = []


def patch(name: str, new: bytes) -> None:
    path = TESTS / name
    data = path.read_bytes()
    if new in data:
        REPORT.append(f'{name} (already up to date)')
        return
    if OLD not in data:
        raise SystemExit(f'PATTERN NOT FOUND in {name}')
    data = data.replace(OLD, new, 1)
    path.write_bytes(data)
    REPORT.append(name)


for name in FILES_WITH_TOP_LEVEL_IMPORT:
    patch(name, NEW_TOP_LEVEL_IMPORT_ALREADY_PRESENT)
for name in FILES_NEEDING_LOCAL_IMPORT:
    patch(name, NEW_WITH_LOCAL_IMPORT)

print('patched:')
for p in REPORT:
    print(' -', p)
