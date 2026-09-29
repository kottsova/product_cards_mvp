"""Read-only integrity audit for the LG UI change."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tests._pipeline_migration import STAGE37_PINNED_SHA256, check_migrated_file  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
BEFORE = json.loads((ROOT / "reports/source_census_2026-09-26_stage36/before_hashes.json").read_text(encoding="utf-8"))


def sha(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def main():
    immutable = ("data/catalog_2026-09-21_filtered.xlsx",
                 "product_tool/config/source_catalog.v2.json", "data/batches.sqlite3")
    protected = {path: check_migrated_file(path, sha(path))[0] for path in STAGE37_PINNED_SHA256}
    results = {
        "catalog_unchanged": sha(immutable[0]) == BEFORE[immutable[0]],
        "production_registry_unchanged": sha(immutable[1]) == BEFORE[immutable[1]],
        "production_database_unchanged": sha(immutable[2]) == BEFORE[immutable[2]],
        "stage37_pins_ok": all(protected.values()),
        "stage37_pin_results": protected,
        "dns_adapter_sha256": sha("product_tool/adapters/dns.py"),
        "lg_adapter_sha256": sha("product_tool/adapters/lg.py"),
        "stage23_report_sha256": sha("reports/source_census_2026-09-25_stage23/report.md"),
    }
    (OUT / "integrity.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if isinstance(v, bool)}, indent=2))
    if not all(v for v in results.values() if isinstance(v, bool)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
