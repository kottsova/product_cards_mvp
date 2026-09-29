"""Stage 18 step 4 -- OFFLINE. For every catalog row whose candidate page was fetched but whose page-level sku
is a different variant, look inside the SAME saved page for the catalog code. No request is made.

Finding the code inside the page's own variant data proves the page is the right model line and that the catalog
variant exists on it; it does NOT give an observed URL for that variant (the page's JSON-LD offer url points at the
default variant only). Such rows are therefore not added to the working map: they go to the grouped user request
with the page URL and the variant evidence.

Output: raw/variant_listing.json
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
RAW = STAGE / "raw"
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402


def page_text(entry: dict) -> str:
    with gzip.open(STAGE / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


def variants_on(html: str) -> list[dict]:
    """Every {"id":..., "sku":"..."} pair the page's embedded product JSON exposes."""
    found = []
    for match in re.finditer(r'\{[^{}]*?"id":(\d{8,}),[^{}]*?"sku":"([^"]+)"[^{}]*?\}', html):
        found.append({"variant_id": match.group(1), "sku": match.group(2)})
    return found


def main() -> None:
    live = json.loads((RAW / "live_discovery_result.json").read_text(encoding="utf-8"))
    saved = {entry["url"]: entry for entry in live["fetch_log"] if entry.get("saved_as")}
    out = []
    for item in live["results"]:
        if item.get("outcome") != "rejected" or item.get("match_level") not in {"mismatch", "base_code_confirmed"}:
            continue
        entry = saved.get(item["url"]) or next((e for u, e in saved.items() if u.split("?", 1)[0] == item["url"]), None)
        if entry is None:
            continue
        html = page_text(entry)
        pairs = variants_on(html)
        listed = sorted({p["sku"] for p in pairs})
        out.append({
            "seller_sku": item["seller_sku"], "page_url": item["url"], "page_default_sku": item["page_sku"], "page_name": item["page_name"],
            "catalog_code_in_page_html": item["seller_sku"] in html,
            "variant_skus_listed_on_page": listed,
            "catalog_variant_listed": item["seller_sku"] in listed,
            "reading": ("page lists this catalog code as a variant; no observed URL for that variant -> ask the user for the exact link"
                        if item["seller_sku"] in listed else
                        ("code appears in page html but not as a variant record" if item["seller_sku"] in html else
                         "code is not on the page: a different product, region or generation")),
        })
    listed_count = sum(1 for row in out if row["catalog_variant_listed"])
    (RAW / "variant_listing.json").write_text(json.dumps({"step": "offline, zero requests", "rows": out, "rows_listed_as_variant": listed_count}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rows={len(out)} listed_as_variant_on_page={listed_count}")
    for row in out:
        print(f"  {row['seller_sku']:<12} default={row['page_default_sku']:<12} listed={row['catalog_variant_listed']!s:<5} in_html={row['catalog_code_in_page_html']!s:<5} {row['page_url'].rsplit('/',1)[-1]}")


if __name__ == "__main__":
    with offline_only():
        main()
