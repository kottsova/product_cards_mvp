"""Stage 19 step 7 -- OFFLINE. The seven group-A rows now have a URL of record (hyperx.KNOWN_URLS), so they leave the
"examined, no URL" list. The remaining 20 findings are Stage 18's, unchanged, and are written both to
raw/url_findings.json (this stage's own record; Stage 18's file is not touched) and to coverage_planner.v1.json
(`url_findings.hyperx`, stage 19). Idempotent: rewrites only that key."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE18 = ROOT / "reports/source_census_2026-09-24_stage18"
CONFIG = ROOT / "product_tool/config/coverage_planner.v1.json"


def main() -> None:
    old = json.loads((STAGE18 / "raw/url_findings.json").read_text(encoding="utf-8"))["findings"]
    accepted = {a["seller_sku"] for a in json.loads((STAGE / "raw/accepted_variant_urls.json").read_text(encoding="utf-8"))["accepted"]}
    assert accepted <= set(old) and all(old[s]["outcome"] == "catalog_variant_listed_on_page_url_not_observed" for s in accepted)
    remaining = {sku: item for sku, item in sorted(old.items()) if sku not in accepted}
    (STAGE / "raw/url_findings.json").write_text(json.dumps({
        "rows_in_scope": 38, "accepted_stage18": 11, "accepted_stage19": len(accepted), "not_accepted": len(remaining), "findings": remaining}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["url_findings"] = {"hyperx": {
        "stage": "19",
        "evidence": [
            "reports/source_census_2026-09-24_stage18/raw/url_findings.json",
            "reports/source_census_2026-09-24_stage18/raw/live_discovery_result.json",
            "reports/source_census_2026-09-24_stage19/raw/url_findings.json",
            "reports/source_census_2026-09-24_stage19/raw/accepted_variant_urls.json",
        ],
        "rule": "Rows listed here were examined and did not get a URL of record. Rows that did are in adapters/hyperx.py KNOWN_URLS.",
        "rows": {sku: {key: value for key, value in item.items() if key in {"outcome", "page_url", "page_default_sku", "detail"}} for sku, item in remaining.items()},
    }}
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("remaining findings:", len(remaining))


if __name__ == "__main__":
    main()
