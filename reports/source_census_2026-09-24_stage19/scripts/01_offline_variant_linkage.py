"""Stage 19 step 1 -- OFFLINE, zero requests. Group A of hyperx_user_request.md: seven catalog rows whose code is
a variant listed on an already found HyperX page. For every row, tie the catalog code to a variant id and a URL
using ONLY what the saved page itself contains, and say which sources agree:

  * the embedded product JSON (<script data-product-json>): variant id + sku + option + barcode;
  * the JSON-LD Product offers: sku + name + gtin12 + the offer's own `?variant=<id>` url;
  * the raw page text: how often that variant id is printed elsewhere (analytics / selectors), as a third witness.

A URL is called observed only if it is printed in the page's own data and its variant id equals the embedded id.
No address is constructed here. Then the adapter's variant extraction is run on the saved default page for each
row and checked for leakage of the default variant's values.

Output: raw/variant_linkage.json
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE18 = ROOT / "reports/source_census_2026-09-24_stage18"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(STAGE18 / "scripts"))

import hx_matching  # noqa: E402  (Stage 18 helper, read-only use)
from product_tool.adapters.hyperx import ALLOWED_HOSTS, HyperXAdapter  # noqa: E402
from product_tool.adapters.structured_page import extract_shopify_product  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

GROUP_A = ["727A8AA", "727A9AA", "A59YZAA", "A59Z0AA", "AJ0T1AA", "B5VC5AA", "BS7C1AA"]
COLOURS = {"black": "Black", "white": "White", "red": "Red", "blue": "Blue", "pink": "Pink", "lavender": "Lavender"}


def load_page(entry: dict) -> str:
    with gzip.open(STAGE18 / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


def main() -> None:
    findings = json.loads((STAGE18 / "raw/url_findings.json").read_text(encoding="utf-8"))["findings"]
    live = json.loads((STAGE18 / "raw/live_discovery_result.json").read_text(encoding="utf-8"))
    saved = {e["url"].split("?", 1)[0]: e for e in live["fetch_log"] if e.get("saved_as")}
    units = {u["seller_sku"].upper(): u for u in (json.loads(l) for l in (STAGE18 / "queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if l)
             if u["family"] == "hyperx"}
    adapter = HyperXAdapter(session=object(), fetch_log_path=STAGE / "raw/unused_fetch_log.json")
    rows = []
    for sku in GROUP_A:
        finding = findings[sku]
        assert finding["outcome"] == "catalog_variant_listed_on_page_url_not_observed", (sku, finding["outcome"])
        page_url = finding["page_url"]
        html = load_page(saved[page_url])
        product = extract_shopify_product(html, page_url)
        variant = product.variant_by_sku(sku) if product else None
        checks = {}
        if variant is not None:
            match = re.search(r"[?&]variant=(\d+)", variant.url or "")
            parts = urlsplit(variant.url or "")
            checks = {
                "embedded_product_json_has_sku": True,
                "json_ld_offer_has_sku": "json_ld_offer" in variant.sources,
                "offer_url_variant_id_equals_embedded_id": bool(match) and match.group(1) == variant.variant_id,
                "offer_url_host_allowed": parts.hostname in ALLOWED_HOSTS,
                "offer_url_path_is_this_product_page": parts.path.rstrip("/") == f"/products/{product.handle}",
                "offer_url_has_only_the_variant_query": parts.query == f"variant={variant.variant_id}",
                "variant_id_printed_in_page_text": len(re.findall(r'"?%s"?' % variant.variant_id, html)),
                "gtin_in_offer_equals_embedded_barcode": bool(variant.barcode) and f'"gtin12": "{variant.barcode}"' in html.replace('"gtin12":"', '"gtin12": "'),
                "confirmed_by_adapter_rule": variant.confirmed,
            }
        title_tokens = hx_matching.model_tokens(units[sku]["title"])[0]
        page_tokens = set(hx_matching._words(product.handle.replace("-", " ") + " " + (variant.name if variant else "")))
        title_colours = sorted({label for word, label in COLOURS.items() if word in units[sku]["title"].casefold()})
        colour_option = next((v for n, v in (variant.options if variant else ()) if n.casefold() == "color"), "")
        document = adapter.parse_page(html, page_url, catalog_code=sku).document
        candidates = document.photo_candidates
        default_sku = product.selected_sku
        default_variant = product.variant_by_sku(default_sku)
        leak = {
            "default_variant_sku_in_variant_attributes": any(a.value == default_sku for a in document.attributes if a.scope == "variant"),
            "default_variant_gtin_in_variant_attributes": bool(default_variant) and any(a.value == default_variant.barcode for a in document.attributes if a.scope == "variant"),
            "default_variant_name_in_variant_attributes": bool(default_variant) and any(a.value == default_variant.name for a in document.attributes if a.scope == "variant"),
            "found_model_is_catalog_code": document.found_model.upper() == sku,
        }
        chosen_tags = sorted({m.tag for m in product.media if m.src in {c.url for c in candidates if not c.excluded_reason}} or {"(none)"})
        rows.append({
            "seller_sku": sku, "catalog_title": units[sku]["title"], "page_url": page_url, "page_selected_sku": default_sku,
            "variant": None if variant is None else {
                "variant_id": variant.variant_id, "sku": variant.sku, "title": variant.title, "name": variant.name, "options": dict(variant.options),
                "barcode": variant.barcode, "url": variant.url, "sources": list(variant.sources), "featured_media_id": variant.featured_media_id,
            },
            "checks": checks, "url_observed_in_page_data": bool(variant and variant.confirmed and all(v for k, v in checks.items() if k != "variant_id_printed_in_page_text")),
            "title_model_tokens_on_page": all(t in page_tokens for t in title_tokens), "title_colours": title_colours, "colour_option": colour_option,
            "title_colour_agrees": (not title_colours) or any(c.casefold() in colour_option.casefold() for c in title_colours),
            "adapter_result_on_saved_default_page": {
                "match_level": document.match_level, "variant_photos": len([c for c in candidates if not c.excluded_reason and c.kind == "product_gallery"]),
                "excluded_other_variant_images": len([c for c in candidates if c.excluded_reason]), "photo_tags_used": chosen_tags,
                "variant_attributes": [(a.name, a.value) for a in document.attributes if a.scope == "variant"],
                "model_attributes": len([a for a in document.attributes if a.scope == "model"]), "leak_checks": leak,
            },
        })
    ok = [r for r in rows if r["url_observed_in_page_data"] and r["title_model_tokens_on_page"] and r["title_colour_agrees"]
          and r["adapter_result_on_saved_default_page"]["match_level"] == "exact_variant" and not any(r["adapter_result_on_saved_default_page"]["leak_checks"][k] for k in
                                                                                                    ("default_variant_sku_in_variant_attributes", "default_variant_gtin_in_variant_attributes", "default_variant_name_in_variant_attributes"))]
    result = {"step": "offline, zero requests", "rows": rows, "rows_examined": len(rows), "variants_linked_and_url_observed": len([r for r in rows if r["url_observed_in_page_data"]]),
              "variants_passing_every_offline_check": len(ok), "sku_of_rows_passing": [r["seller_sku"] for r in ok]}
    (STAGE / "raw" / "variant_linkage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("linked+observed:", result["variants_linked_and_url_observed"], " passing all offline checks:", result["variants_passing_every_offline_check"])
    for r in rows:
        a = r["adapter_result_on_saved_default_page"]
        print(f"  {r['seller_sku']} id={r['variant']['variant_id']} colour={r['colour_option']!r} title_colours={r['title_colour_agrees']} url_observed={r['url_observed_in_page_data']} "
              f"level={a['match_level']} photos={a['variant_photos']} excluded={a['excluded_other_variant_images']} tags={a['photo_tags_used']}")


if __name__ == "__main__":
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    with offline_only():
        main()
