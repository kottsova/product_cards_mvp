"""Stage 19 step 2 -- the ONE bounded live check, for one concrete gap.

Gap: offline, the seven group-A variants are tied to `?variant=<id>` URLs printed in their page's own data, but no
page has been fetched AT those URLs. Before they become URLs of record, each must be fetched once and its own JSON-LD
sku must equal the catalog code (the rule every other URL in the map met), and the adapter's variant extraction
from the default page (step 1) must agree with what the variant page itself says.

Budget (written to raw/budget_predeclaration.json BEFORE the first request):
  host hyperx.com only; at most 7 requests, one per URL listed in raw/variant_linkage.json and observed there;
  no other URL, no search, no sitemap, no retries; every request through PolicyAwareFetcher (allowlist, redirect
  checks, min interval, persisted fetch log data/hyperx_fetch_log.json, which now also records the protection
  status); the first 401/403/429 or CONFIRMED challenge (any HTTP status) halts the run and stops the host.

Output: raw/live_variant_result.json, raw/pages/*.gz
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
RAW = STAGE / "raw"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.hyperx import ALLOWED_HOSTS, DEFAULT_FETCH_LOG_PATH, HyperXAdapter  # noqa: E402
from product_tool.adapters.policy_fetch import CONFIRMED_CHALLENGE, PolicyAwareFetcher  # noqa: E402
from product_tool.census.endpoint_probe import AccessStatus, ProbePolicy  # noqa: E402
from product_tool.census.models import EndpointCapability  # noqa: E402

MAX_REQUESTS = 7


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    linkage = json.loads((RAW / "variant_linkage.json").read_text(encoding="utf-8"))
    targets = [(r["seller_sku"], r["variant"]["url"], r) for r in linkage["rows"] if r["url_observed_in_page_data"]]
    assert len(targets) <= MAX_REQUESTS
    budget = {
        "declared_at": now(), "host": "hyperx.com", "max_requests_total": MAX_REQUESTS, "urls": [{"seller_sku": s, "url": u} for s, u, _ in targets],
        "url_source": "raw/variant_linkage.json: each URL is printed in the saved page's JSON-LD offer and its variant id equals the embedded product JSON id",
        "forbidden": ["any URL not listed above", "site search", "sitemaps", "retries", "any other host"],
        "stop_rule": "first 401/403/429 or confirmed challenge (any HTTP status) halts the run; the host stays stopped via data/hyperx_fetch_log.json",
        "script": "reports/source_census_2026-09-24_stage19/scripts/02_live_variant_pages.py",
    }
    (RAW / "budget_predeclaration.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fetcher = PolicyAwareFetcher(DEFAULT_FETCH_LOG_PATH, policy=ProbePolicy(max_bytes=3_000_000, min_interval_seconds=2.0))
    adapter = HyperXAdapter(session=object(), fetch_log_path=RAW / "unused_fetch_log.json")
    (RAW / "pages").mkdir(parents=True, exist_ok=True)
    results, log, halted = [], [], ""
    for sku, url, row in targets:
        if halted:
            results.append({"seller_sku": sku, "url": url, "outcome": "not_fetched", "detail": halted})
            continue
        if urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise ValueError(url)
        result = fetcher.get(url, allowed_hosts=tuple(ALLOWED_HOSTS), capability=EndpointCapability.PRODUCT_PAGE)
        body = result.diagnostic_text or ""
        entry = {"seller_sku": sku, "url": url, "http_status": result.http_status, "final_url": result.final_url, "access_status": result.access_status.value,
                 "protection_status": result.protection_status.value, "bytes": len(body.encode("utf-8")), "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest() if body else "",
                 "checked_at": result.checked_at, "error": result.error}
        log.append(entry)
        if result.access_status in (AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED) or result.protection_status.value in CONFIRMED_CHALLENGE:
            halted = f"{result.http_status} / {result.access_status.value} / {result.protection_status.value} on {url}"
        if result.http_status != 200 or not body:
            results.append({"seller_sku": sku, "url": url, "outcome": "not_ok", "detail": result.error or f"HTTP {result.http_status}"})
            continue
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", f"variant_{sku}") + ".gz"
        with gzip.open(RAW / "pages" / name, "wt", encoding="utf-8", newline="") as handle:
            handle.write(body)
        entry["saved_as"] = f"raw/pages/{name}"
        document = adapter.parse_page(body, (result.final_url or url), catalog_code=sku).document
        offline = row["adapter_result_on_saved_default_page"]
        results.append({
            "seller_sku": sku, "url": url, "final_url": result.final_url, "outcome": "fetched",
            "match_level": document.match_level, "page_selected_sku": document.found_model, "evidence": document.evidence[:400],
            "variant_attributes": [(a.name, a.value) for a in document.attributes if a.scope == "variant"],
            "variant_photos": len([c for c in document.photo_candidates if not c.excluded_reason and c.kind == "product_gallery"]),
            "excluded_photos": len([c for c in document.photo_candidates if c.excluded_reason]),
            "offline_variant_attributes": offline["variant_attributes"], "offline_variant_photos": offline["variant_photos"],
        })
    fetched = [r for r in results if r["outcome"] == "fetched"]
    out = {"finished_at": now(), "requests_made": len(log), "halted": halted, "fetched": len(fetched),
           "exact_variant_on_the_variant_page": len([r for r in fetched if r["match_level"] == "exact_variant"]), "results": results, "fetch_log": log}
    (RAW / "live_variant_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"requests={len(log)} halted={halted!r} exact_variant={out['exact_variant_on_the_variant_page']}/{len(targets)}")
    for r in results:
        print(" ", r["seller_sku"], r["outcome"], r.get("match_level", ""), r.get("page_selected_sku", ""), "photos", r.get("variant_photos"), "vs offline", r.get("offline_variant_photos"))


if __name__ == "__main__":
    main()
