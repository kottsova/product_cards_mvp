"""Stage 18 step 6 -- OFFLINE. Copy the per-row outcome of the URL-discovery wave into coverage_planner.v1.json
(`url_findings`), so the planner can say WHY a HyperX row still has no URL and the grouped request can name it.
Idempotent: rewrites only the `url_findings` key.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONFIG = ROOT / "product_tool" / "config" / "coverage_planner.v1.json"
FINDINGS = HERE.parent / "raw" / "url_findings.json"


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    findings = json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"]
    config["url_findings"] = {
        "hyperx": {
            "stage": "18",
            "evidence": [
                "reports/source_census_2026-09-24_stage18/raw/url_findings.json",
                "reports/source_census_2026-09-24_stage18/raw/live_discovery_result.json",
                "reports/source_census_2026-09-24_stage18/raw/variant_listing.json",
            ],
            "rule": "Rows listed here were examined by the Stage 18 wave and did not get a URL of record. Rows that did are in adapters/hyperx.py KNOWN_URLS.",
            "rows": {sku: {key: value for key, value in item.items() if key in {"outcome", "page_url", "page_default_sku", "detail"}} for sku, item in sorted(findings.items())},
        }
    }
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("url_findings rows:", len(config["url_findings"]["hyperx"]["rows"]))


if __name__ == "__main__":
    main()
