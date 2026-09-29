"""Stage 11.5 -- apply the documented, one-time exemption to all 10
tests/test_structural_census_v8_1.py .. v9_1.py files, importing the shared
migration record (tests/_pipeline_migration.py) instead of hardcoding a
local list per file. Uses byte-level I/O throughout (no text-mode newline
translation) to avoid corrupting the existing LF-only line endings.
"""
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
TESTS = ROOT / 'tests'

IMPORT_LINE = b"from _pipeline_migration import is_authorized_change\n"

# --- 1. The Stage-8-baseline check, identical across all 10 files ---------
BASELINE_OLD = (
    b"    def test_stage2_to_8_files_byte_identical(self):\n"
    b"        manifest = read(STAGE8 / 'protected_hashes_after.json')['after']\n"
    b"        self.assertGreaterEqual(len(manifest), 200)\n"
    b"        for path, expected in manifest.items():\n"
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

# --- 2. Cross-stage checks: one variant per file, since the exact loop
#        shape (single key vs a tuple of keys) differs slightly. ------------
CROSS_CHECK_VARIANTS = [
    (
        ROOT / 'tests/test_structural_census_v8_2.py',
        b"        for rel in check['stage8_1_files_hashed_now']:\n"
        b"            full = ROOT / rel\n"
        b"            self.assertTrue(full.exists(), f'Stage 8.1 file missing: {rel}')\n"
        b"            current[rel] = hashlib.sha256(full.read_bytes()).hexdigest()",
        b"        for rel in check['stage8_1_files_hashed_now']:\n"
        b"            if is_authorized_change(rel):\n"
        b"                continue\n"
        b"            full = ROOT / rel\n"
        b"            self.assertTrue(full.exists(), f'Stage 8.1 file missing: {rel}')\n"
        b"            current[rel] = hashlib.sha256(full.read_bytes()).hexdigest()",
    ),
    (
        ROOT / 'tests/test_structural_census_v8_2_1.py',
        b"            for rel, expected in check[key].items():\n"
        b"                full = ROOT / rel\n"
        b"                self.assertTrue(full.exists(), f'missing: {rel}')\n"
        b"                actual = hashlib.sha256(full.read_bytes()).hexdigest()",
        b"            for rel, expected in check[key].items():\n"
        b"                if is_authorized_change(rel):\n"
        b"                    continue\n"
        b"                full = ROOT / rel\n"
        b"                self.assertTrue(full.exists(), f'missing: {rel}')\n"
        b"                actual = hashlib.sha256(full.read_bytes()).hexdigest()",
    ),
]
# v8_2_2, v8_3, v8_4, v8_5, v8_6, v9, v9_1 all share the exact same 4-line
# indented-by-12 loop body as v8_2_1 (verified by direct inspection) -- add
# them to the same replacement pair, applied file by file below.
for name in ('v8_2_2', 'v8_3', 'v8_4', 'v8_5', 'v8_6', 'v9', 'v9_1'):
    CROSS_CHECK_VARIANTS.append((
        ROOT / f'tests/test_structural_census_{name}.py',
        CROSS_CHECK_VARIANTS[1][1],
        CROSS_CHECK_VARIANTS[1][2],
    ))

REPORT = []


def patch_file(path: Path, edits: list[tuple[bytes, bytes]]) -> None:
    data = path.read_bytes()
    original = data
    for old, new in edits:
        if old not in data:
            raise SystemExit(f'PATTERN NOT FOUND in {path}: {old[:60]!r}...')
        data = data.replace(old, new, 1)
    # Add the shared-module import once, right after the stdlib imports
    # (after the last 'import unittest' line), if not already present.
    if IMPORT_LINE not in data:
        marker = b'import unittest\n'
        idx = data.index(marker) + len(marker)
        data = data[:idx] + b'\n' + IMPORT_LINE + data[idx:]
    if data != original:
        path.write_bytes(data)
        REPORT.append(str(path.relative_to(ROOT)))


# File 1: v8_1 -- only the baseline check, no cross-stage check exists yet.
patch_file(TESTS / 'test_structural_census_v8_1.py', [(BASELINE_OLD, BASELINE_NEW)])

# Files 2-10: baseline check + their own cross-stage check variant.
for path, cross_old, cross_new in CROSS_CHECK_VARIANTS:
    patch_file(path, [(BASELINE_OLD, BASELINE_NEW), (cross_old, cross_new)])

print('patched files:')
for p in REPORT:
    print(' -', p)
