"""Stage 19 step 5 -- a second, one-request live check for one concrete gap.

Gap: the card for 4P5D4AA (Cloud Alpha Wireless) was built from a SANITISED Stage 5.1 snapshot: no embedded product JSON,
no gallery nodes, so no variant data and no photos. The URL of record is already in the map (observed in Stage 5.1).

Budget (raw/budget_predeclaration_2.json, written BEFORE the request): host hyperx.com, exactly 1 request, only
https://hyperx.com/products/hyperx-cloud-alpha-wireless; PolicyAwareFetcher; no retry; halt on 401/403/429 or a confirmed challenge.

Output: raw/live_snapshot_gap_result.json, raw/pages/products_hyperx-cloud-alpha-wireless.gz
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
RAW = STAGE / "raw"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.hyperx import ALLOWED_HOSTS, DEFAULT_FETCH_LOG_PATH, HyperXAdapter, KNOWN_URLS  # noqa: E402
from product_tool.adapters.policy_fetch import CONFIRMED_CHALLENGE, PolicyAwareFetcher  # noqa: E402
from product_tool.census.endpoint_probe import ProbePolicy  # noqa: E402
from product_tool.census.models import EndpointCapability  # noqa: E402

SKU = "4P5D4AA"
URL = "https://hyperx.com/products/hyperx-cloud-alpha-wireless"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    assert KNOWN_URLS[SKU] == URL
    budget = {"declared_at": now(), "host": "hyperx.com", "max_requests_total": 1, "url": URL, "seller_sku": SKU,
              "reason": "the saved snapshot is sanitised (no product JSON, no gallery)", "stop_rule": "401/403/429 or confirmed challenge halts; no retry",
              "script": "reports/source_census_2026-09-24_stage19/scripts/05_live_snapshot_gap.py"}
    (RAW / "budget_predeclaration_2.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fetcher = PolicyAwareFetcher(DEFAULT_FETCH_LOG_PATH, policy=ProbePolicy(max_bytes=3_000_000, min_interval_seconds=2.0))
    result = fetcher.get(URL, allowed_hosts=tuple(ALLOWED_HOSTS), capability=EndpointCapability.PRODUCT_PAGE)
    body = result.diagnostic_text or ""
    entry = {"url": URL, "http_status": result.http_status, "final_url": result.final_url, "access_status": result.access_status.value,
             "protection_status": result.protection_status.value, "bytes": len(body.encode("utf-8")),
             "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest() if body else "", "checked_at": result.checked_at, "error": result.error}
    out = {"request": entry, "halted": result.protection_status.value in CONFIRMED_CHALLENGE or result.http_status in (401, 403, 429)}
    if result.http_status == 200 and body:
        name = "products_hyperx-cloud-alpha-wireless.gz"
        with gzip.open(RAW / "pages" / name, "wt", encoding="utf-8", newline="") as handle:
            handle.write(body)
        entry["saved_as"] = f"raw/pages/{name}"
        adapter = HyperXAdapter(session=object(), fetch_log_path=RAW / "unused_fetch_log.json")
        document = adapter.parse_page(body, result.final_url or URL, catalog_code=SKU).document
        out["parse"] = {"match_level": document.match_level, "found_model": document.found_model, "evidence": document.evidence[:500],
                        "photos": len(document.photos), "excluded_photos": len([c for c in document.photo_candidates if c.excluded_reason]),
                        "variant_attributes": [(a.name, a.value) for a in document.attributes if a.scope == "variant"],
                        "model_attributes": len([a for a in document.attributes if a.scope == "model"])}
    (RAW / "live_snapshot_gap_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"http": entry["http_status"], "protection": entry["protection_status"], **out.get("parse", {})}, ensure_ascii=False)[:700])


if __name__ == "__main__":
    main()
