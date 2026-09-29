"""Stage 19 step 3 -- OFFLINE. Decide which of the seven variant URLs may enter hyperx.KNOWN_URLS.

A row is accepted only if ALL hold, each read from a saved file:
  1. step 1: the URL is printed in the page's own data and its variant id equals the embedded product JSON id
     (confirmed by two in-page sources), colour and model tokens agree with the catalog title;
  2. step 2: the URL was fetched (HTTP 200) and the adapter, run on THAT page, returns exact_variant for the catalog code;
  3. the extraction from the variant page equals the extraction from the default page (variant attributes identical,
     same number of variant photos) -- i.e. the rule does not depend on which page was fetched;
  4. no request was made outside the declared budget (<= 7, hyperx.com only).

Note recorded here because it changed the design: on every fetched `?variant=` page the JSON-LD top-level sku is STILL the
page's default variant (server-side JSON-LD does not follow the query). So the identity of these rows can only come from
the in-page variant record, never from "the page selected this variant".

Output: raw/accepted_variant_urls.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
RAW = STAGE / "raw"


def main() -> None:
    linkage = {r["seller_sku"]: r for r in json.loads((RAW / "variant_linkage.json").read_text(encoding="utf-8"))["rows"]}
    live = json.loads((RAW / "live_variant_result.json").read_text(encoding="utf-8"))
    budget = json.loads((RAW / "budget_predeclaration.json").read_text(encoding="utf-8"))
    assert live["requests_made"] <= budget["max_requests_total"] and budget["declared_at"] < live["fetch_log"][0]["checked_at"]
    log = {e["seller_sku"]: e for e in live["fetch_log"]}
    accepted, rejected = [], []
    for result in live["results"]:
        sku = result["seller_sku"]
        row = linkage[sku]
        checks = {
            "url_observed_in_page_data_two_sources": row["url_observed_in_page_data"],
            "title_model_tokens_and_colour_agree": row["title_model_tokens_on_page"] and row["title_colour_agrees"],
            "fetched_200": result["outcome"] == "fetched" and log[sku]["http_status"] == 200,
            "adapter_exact_variant_on_the_variant_page": result.get("match_level") == "exact_variant",
            "variant_attributes_equal_default_page_extraction": [list(x) for x in result.get("variant_attributes", [])] == [list(x) for x in result.get("offline_variant_attributes", [])],
            "variant_photo_count_equal_default_page_extraction": result.get("variant_photos") == result.get("offline_variant_photos"),
            "same_host_as_page": log[sku]["final_url"].startswith("https://hyperx.com/products/"),
        }
        if all(checks.values()):
            accepted.append({
                "seller_sku": sku, "url": result["url"], "variant_id": row["variant"]["variant_id"], "variant_sku": row["variant"]["sku"],
                "variant_name": row["variant"]["name"], "colour": row["colour_option"], "page_selected_sku_on_that_page": row["page_selected_sku"],
                "identity_route": "in_page_variant_record", "saved_as": log[sku]["saved_as"], "content_sha256": log[sku]["sha256"], "fetched_at": log[sku]["checked_at"],
                "observed_in": row["page_url"], "checks": checks,
            })
        else:
            rejected.append({"seller_sku": sku, "checks": checks})
    out = {"rule": "see the module docstring", "requests_made": live["requests_made"], "accepted": sorted(accepted, key=lambda a: a["seller_sku"]), "rejected": rejected}
    (RAW / "accepted_variant_urls.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("accepted", len(accepted), "rejected", len(rejected))
    for a in out["accepted"]:
        print(" ", a["seller_sku"], a["url"])


if __name__ == "__main__":
    main()
