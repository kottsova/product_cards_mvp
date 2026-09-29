"""Stage 12 -- upgrade the Stage 11.5 "is this path authorized" exemption to
a real "does this path's CURRENT content match its pinned post-migration
hash" check, in all 10 protection test files. Byte-level I/O throughout to
avoid corrupting LF-only line endings (lesson learned in Stage 11.4)."""
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')

IMPORT_OLD = b"from _pipeline_migration import is_authorized_change\n"
IMPORT_NEW = b"from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file\n"

# --- 1. Baseline check: same across all 10 files ---------------------------
BASELINE_OLD = (
    b"    def test_stage2_to_8_files_byte_identical(self):\n"
    b"        # Stage 11.4 authorized product_tool/{display,jobs,worker}.py to\n"
    b"        # change (a real pipeline integration, not research); see\n"
    b"        # tests/_pipeline_migration.py for the full, documented record.\n"
    b"        # Every other file here is still checked with zero exceptions.\n"
    b"        manifest = read(STAGE8 / 'protected_hashes_after.json')['after']\n"
    b"        self.assertGreaterEqual(len(manifest), 200)\n"
    b"        for path, expected in manifest.items():\n"
    b"            if is_authorized_change(path):\n"
    b"                continue\n"
    b"            full = ROOT / path\n"
    b"            self.assertTrue(full.exists(), f'protected file missing: {path}')\n"
    b"            actual = hashlib.sha256(full.read_bytes()).hexdigest()\n"
    b"            self.assertEqual(actual, expected, f'protected file changed: {path}')"
)
BASELINE_NEW = (
    b"    def test_stage2_to_8_files_byte_identical(self):\n"
    b"        # Stage 11.4 authorized product_tool/{display,jobs,worker}.py to\n"
    b"        # change (a real pipeline integration, not research); see\n"
    b"        # tests/_pipeline_migration.py for the full, documented record.\n"
    b"        # Stage 12: an authorized path must ALSO match its pinned exact\n"
    b"        # post-migration hash -- any further, undocumented edit fails this\n"
    b"        # test again, the same as it would for any other protected file.\n"
    b"        manifest = read(STAGE8 / 'protected_hashes_after.json')['after']\n"
    b"        self.assertGreaterEqual(len(manifest), 200)\n"
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

# --- 2. Cross-stage checks -------------------------------------------------
CROSS_V82_OLD = (
    b"    def test_stage8_1_untouched(self):\n"
    b"        check = read(STAGE82 / 'protected_hashes_check.json')\n"
    b"        expected = {rel: h for rel, h in check['stage8_1_files_hashed_now'].items() if not is_authorized_change(rel)}\n"
    b"        current = {}\n"
    b"        for rel in expected:\n"
    b"            full = ROOT / rel\n"
    b"            self.assertTrue(full.exists(), f'Stage 8.1 file missing: {rel}')\n"
    b"            current[rel] = hashlib.sha256(full.read_bytes()).hexdigest()\n"
    b"        self.assertEqual(current, expected)"
)
CROSS_V82_NEW = (
    b"    def test_stage8_1_untouched(self):\n"
    b"        check = read(STAGE82 / 'protected_hashes_check.json')\n"
    b"        full_map = check['stage8_1_files_hashed_now']\n"
    b"        expected, current = {}, {}\n"
    b"        for rel, recorded in full_map.items():\n"
    b"            full = ROOT / rel\n"
    b"            self.assertTrue(full.exists(), f'Stage 8.1 file missing: {rel}')\n"
    b"            actual = hashlib.sha256(full.read_bytes()).hexdigest()\n"
    b"            if rel in ALL_AUTHORIZED_CHANGES:\n"
    b"                ok, msg = check_migrated_file(rel, actual)\n"
    b"                self.assertTrue(ok, msg)\n"
    b"                continue\n"
    b"            expected[rel] = recorded\n"
    b"            current[rel] = actual\n"
    b"        self.assertEqual(current, expected)"
)

CROSS_GENERIC_OLD = (
    b"            for rel, expected in check[key].items():\n"
    b"                if is_authorized_change(rel):\n"
    b"                    continue\n"
    b"                full = ROOT / rel\n"
    b"                self.assertTrue(full.exists(), f'missing: {rel}')\n"
    b"                actual = hashlib.sha256(full.read_bytes()).hexdigest()"
)
CROSS_GENERIC_NEW = (
    b"            for rel, expected in check[key].items():\n"
    b"                full = ROOT / rel\n"
    b"                self.assertTrue(full.exists(), f'missing: {rel}')\n"
    b"                actual = hashlib.sha256(full.read_bytes()).hexdigest()\n"
    b"                if rel in ALL_AUTHORIZED_CHANGES:\n"
    b"                    ok, msg = check_migrated_file(rel, actual)\n"
    b"                    self.assertTrue(ok, msg)\n"
    b"                    continue"
)

CROSS_FILES_GENERIC = [
    'test_structural_census_v8_2_1.py', 'test_structural_census_v8_2_2.py',
    'test_structural_census_v8_3.py', 'test_structural_census_v8_4.py',
    'test_structural_census_v8_5.py', 'test_structural_census_v8_6.py',
    'test_structural_census_v9.py', 'test_structural_census_v9_1.py',
]

REPORT = []


def patch(path: Path, edits: list[tuple[bytes, bytes]]) -> None:
    data = path.read_bytes()
    original = data
    for old, new in edits:
        if new in data:
            continue  # already applied (idempotent re-run)
        if old not in data:
            raise SystemExit(f'PATTERN NOT FOUND in {path}: {old[:80]!r}...')
        data = data.replace(old, new, 1)
    if IMPORT_OLD in data:
        data = data.replace(IMPORT_OLD, IMPORT_NEW, 1)
    if data != original:
        path.write_bytes(data)
        REPORT.append(str(path.relative_to(ROOT)))
    else:
        REPORT.append(str(path.relative_to(ROOT)) + ' (already up to date)')


TESTS = ROOT / 'tests'
patch(TESTS / 'test_structural_census_v8_1.py', [(BASELINE_OLD, BASELINE_NEW)])
patch(TESTS / 'test_structural_census_v8_2.py', [(BASELINE_OLD, BASELINE_NEW), (CROSS_V82_OLD, CROSS_V82_NEW)])
for name in CROSS_FILES_GENERIC:
    patch(TESTS / name, [(BASELINE_OLD, BASELINE_NEW), (CROSS_GENERIC_OLD, CROSS_GENERIC_NEW)])

print('patched:')
for p in REPORT:
    print(' -', p)
