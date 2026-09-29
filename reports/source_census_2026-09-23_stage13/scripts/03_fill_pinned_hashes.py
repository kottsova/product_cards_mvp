"""Stage 13 -- compute the final post-migration hash for each of the 19
now-authorized files (now in their final Stage 13 state) and write them
into tests/_pipeline_migration.py's PINNED_SHA256 dict, replacing the
placeholder tokens. Byte-level I/O to preserve line endings."""
import hashlib
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')

PLACEHOLDER_TO_PATH = {
    "__PINNED_display_py__": "product_tool/display.py",
    "__PINNED_jobs_py__": "product_tool/jobs.py",
    "__PINNED_worker_py__": "product_tool/worker.py",
    "__PINNED_endpoint_probe_py__": "product_tool/census/endpoint_probe.py",
    "__PINNED_source_catalog_v2_json__": "product_tool/config/source_catalog.v2.json",
    "__PINNED_resolution_py__": "product_tool/resolution.py",
    "__PINNED_exporter_py__": "product_tool/exporter.py",
    "__PINNED_multi_domain_md__": "docs/MULTI_DOMAIN_OFFICIAL_FALLBACK_V7.md",
    "__PINNED_source_census_md__": "docs/SOURCE_CENSUS.md",
    "__PINNED_v8_1__": "tests/test_structural_census_v8_1.py",
    "__PINNED_v8_2__": "tests/test_structural_census_v8_2.py",
    "__PINNED_v8_2_1__": "tests/test_structural_census_v8_2_1.py",
    "__PINNED_v8_2_2__": "tests/test_structural_census_v8_2_2.py",
    "__PINNED_v8_3__": "tests/test_structural_census_v8_3.py",
    "__PINNED_v8_4__": "tests/test_structural_census_v8_4.py",
    "__PINNED_v8_5__": "tests/test_structural_census_v8_5.py",
    "__PINNED_v8_6__": "tests/test_structural_census_v8_6.py",
    "__PINNED_v9__": "tests/test_structural_census_v9.py",
    "__PINNED_v9_1__": "tests/test_structural_census_v9_1.py",
}

migration_path = ROOT / 'tests/_pipeline_migration.py'
data = migration_path.read_bytes()
for placeholder, relpath in PLACEHOLDER_TO_PATH.items():
    actual_hash = hashlib.sha256((ROOT / relpath).read_bytes()).hexdigest()
    token = placeholder.encode()
    if token not in data:
        raise SystemExit(f'placeholder {placeholder} not found (already filled?)')
    data = data.replace(token, actual_hash.encode())
    print(relpath, '->', actual_hash)
migration_path.write_bytes(data)
print('done')
