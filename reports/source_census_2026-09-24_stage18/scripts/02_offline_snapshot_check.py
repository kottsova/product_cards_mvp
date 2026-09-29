"""Stage 18 step 2 -- OFFLINE. Replays every hyperx.com product snapshot already saved in a repository
snapshot database through HyperXAdapter.parse_page() against the 38 adapter_url_missing rows.
No request is made. A snapshot counts only if the page's own JSON-LD sku equals the catalog code
(match_level == "exact_variant") -- the same rule the working adapter applies at run time.

Output: raw/offline_snapshot_check.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.adapters.hyperx import HyperXAdapter  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

SNAPSHOT_DBS = sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "reports").glob("*/*.sqlite3"))


def missing_rows() -> dict[str, dict]:
    rows = [json.loads(line) for line in (STAGE / "queue_a_evidence_scope" / "coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    return {r["seller_sku"].upper(): r for r in rows if r["status"] == "adapter_url_missing" and r["family"] == "hyperx"}


def main() -> None:
    rows = missing_rows()
    adapter = HyperXAdapter(session=object(), fetch_log_path=STAGE / "raw" / "unused_fetch_log.json")  # parse_page never touches the session
    found, examined = [], []
    for rel in SNAPSHOT_DBS:
        connection = sqlite3.connect(f"file:{ROOT / rel}?mode=ro", uri=True)
        try:
            for snapshot_id, url, content, sha in connection.execute(
                "SELECT id, source_url, content, content_sha256 FROM source_snapshots WHERE source_url LIKE 'https://hyperx.com/products/%'"
            ):
                page_url = url.split("?", 1)[0]
                record = {"database": rel, "snapshot_id": snapshot_id, "url": url, "content_sha256": sha, "matches": []}
                for code, row in rows.items():
                    result = adapter.parse_page(content, page_url, catalog_code=code)
                    if result.document.match_level != "unknown" and result.document.found_model.strip().upper().split("#")[0] == code.split("#")[0]:
                        record["matches"].append({"seller_sku": code, "match_level": result.document.match_level, "page_sku": result.document.found_model, "evidence": result.document.evidence})
                examined.append(record)
                if any(m["match_level"] == "exact_variant" for m in record["matches"]):
                    found.append(record)
        finally:
            connection.close()
    out = {
        "step": "offline, zero requests", "databases_scanned": SNAPSHOT_DBS, "hyperx_product_snapshots_examined": len(examined),
        "exact_variant_matches": [{"seller_sku": m["seller_sku"], "url": r["url"].split("?", 1)[0], "database": r["database"], "snapshot_id": r["snapshot_id"],
                                   "content_sha256": r["content_sha256"], "page_sku": m["page_sku"], "match_level": m["match_level"]}
                                  for r in found for m in r["matches"] if m["match_level"] == "exact_variant"],
        "examined": examined,
    }
    (STAGE / "raw" / "offline_snapshot_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"examined={len(examined)} exact_variant={len(out['exact_variant_matches'])}")
    for item in out["exact_variant_matches"]:
        print(" ", item["seller_sku"], item["url"], item["page_sku"], item["match_level"])


if __name__ == "__main__":
    with offline_only():
        main()
