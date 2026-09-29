"""Stage 18 step 5 -- OFFLINE. Turn the saved evidence of the URL-discovery wave into (a) the rows that may enter the working
URL map and (b) one finding per row that did not, so the planner and the user request can state the exact reason.

A row enters the map only if BOTH hold:
  1. the page's own JSON-LD sku equals the catalog code (HyperXAdapter.parse_page -> exact_variant), and
  2. every distinctive model token of the catalog title is in the page's product name.
A saved page is re-parsed here (not trusted from the live run's summary).

Inputs : raw/offline_snapshot_check.json, raw/live_discovery_result.json, raw/variant_listing.json, raw/pages/*.gz,
         the saved Stage 5.1 snapshot database, queue_a_evidence_scope/coverage_units.jsonl
Outputs: raw/accepted_urls.json, raw/url_findings.json
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
RAW = STAGE / "raw"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import hx_matching  # noqa: E402
from product_tool.adapters.hyperx import HyperXAdapter  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402


def product_name(html: str) -> str:
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            kind = item.get("@type")
            if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                return str(item.get("name", ""))
    return ""


def main() -> None:
    rows = {r["seller_sku"].upper(): r for r in (json.loads(line) for line in (STAGE / "queue_a_evidence_scope" / "coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line)
            if r["status"] == "adapter_url_missing" and r["family"] == "hyperx"}
    adapter = HyperXAdapter(session=object(), fetch_log_path=RAW / "unused_fetch_log.json")
    live = json.loads((RAW / "live_discovery_result.json").read_text(encoding="utf-8"))
    snapshot = json.loads((RAW / "offline_snapshot_check.json").read_text(encoding="utf-8"))
    listing = {r["seller_sku"]: r for r in json.loads((RAW / "variant_listing.json").read_text(encoding="utf-8"))["rows"]}
    saved = {e["url"].split("?", 1)[0]: e for e in live["fetch_log"] if e.get("saved_as")}

    accepted, findings = [], {}

    def check(sku: str, page_url: str, html: str, source: dict):
        document = adapter.parse_page(html, page_url, catalog_code=sku).document
        name = product_name(html)
        page_tokens = set(hx_matching._words(name))
        tokens = hx_matching.model_tokens(rows[sku]["title"])[0]
        return document, name, all(token in page_tokens for token in tokens)

    # 1. offline snapshot rows
    for item in snapshot["exact_variant_matches"]:
        sku = item["seller_sku"]
        connection = sqlite3.connect(f"file:{ROOT / item['database']}?mode=ro", uri=True)
        try:
            html = connection.execute("SELECT content FROM source_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()[0]
        finally:
            connection.close()
        document, name, title_ok = check(sku, item["url"], html, item)
        if document.match_level == "exact_variant" and title_ok:
            accepted.append({"seller_sku": sku, "url": item["url"], "page_sku": document.found_model, "page_name": name, "match_level": document.match_level,
                             "basis": "saved_official_snapshot", "database": item["database"], "snapshot_id": item["snapshot_id"], "content_sha256": item["content_sha256"],
                             "how_the_url_was_observed": "Stage 5.1 saved the site's own search-result page for this code (snapshot 3 of the same database); its only product link is this page"})
    # 2. live pages, re-parsed from the saved copy
    for result in live["results"]:
        sku = result["seller_sku"]
        if result["outcome"] == "not_fetched" or "url" not in result:
            continue
        entry = saved.get(result["url"])
        if entry is None:
            continue
        with gzip.open(STAGE / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
            html = handle.read()
        document, name, title_ok = check(sku, result["url"], html, result)
        if document.match_level == "exact_variant" and title_ok:
            accepted.append({"seller_sku": sku, "url": result["url"], "page_sku": document.found_model, "page_name": name, "match_level": document.match_level,
                             "basis": "live_page_wave_stage18", "saved_as": entry["saved_as"], "content_sha256": entry["sha256"], "fetched_at": entry["checked_at"],
                             "how_the_url_was_observed": "link saved on an official hyperx.com page (Stage 11/11.1)" if result["url"] in {"https://hyperx.com" + c["path"] for i in json.loads((RAW / "offline_candidates.json").read_text(encoding="utf-8"))["items"] for c in i["candidates"]} else "<loc> of the product sitemap declared in robots.txt"})
        else:
            base = "different_variant_on_page" if document.match_level in {"mismatch", "base_code_confirmed"} else document.match_level
            row = listing.get(sku, {})
            findings[sku] = {
                "outcome": "catalog_variant_listed_on_page_url_not_observed" if row.get("catalog_variant_listed") else ("page_sku_differs_from_catalog" if document.match_level == "mismatch" else base),
                "page_url": result["url"], "page_default_sku": document.found_model, "page_name": name, "match_level": document.match_level,
                "detail": row.get("reading", ""),
            }
    accepted_skus = {a["seller_sku"] for a in accepted}
    for sku, row in rows.items():
        if sku in accepted_skus or sku in findings:
            continue
        if "title_names_other_manufacturer" in row["flags"]:
            findings[sku] = {"outcome": "title_names_other_manufacturer", "detail": "Kingston memory module under the HYPERX brand: hyperx.com is not its manufacturer's storefront."}
        else:
            findings[sku] = {"outcome": "no_observed_page_for_title", "detail": "no saved official link and no product slug in the official sitemap carries every model token of the title"}
    (RAW / "accepted_urls.json").write_text(json.dumps({"rule": "sku equals catalog code on the page (exact_variant) and every model token of the catalog title is in the product name",
                                                        "accepted": sorted(accepted, key=lambda a: a["seller_sku"])}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RAW / "url_findings.json").write_text(json.dumps({"rows_in_scope": len(rows), "accepted": len(accepted), "not_accepted": len(findings), "findings": dict(sorted(findings.items()))}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    print("in scope", len(rows), "accepted", len(accepted), "findings", dict(Counter(f["outcome"] for f in findings.values())))
    for a in sorted(accepted, key=lambda a: a["seller_sku"]):
        print(" ", a["seller_sku"], a["url"], "|", a["page_name"], "|", a["basis"])


if __name__ == "__main__":
    with offline_only():
        main()
