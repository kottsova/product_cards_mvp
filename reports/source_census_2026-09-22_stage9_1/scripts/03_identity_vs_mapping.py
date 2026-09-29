"""Stage 9.1 -- fully offline. Build the core artifact separating question (1)
official product/variant confirmation from question (2) catalog-row mapping.
No network access in this script."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-22_stage9_1'

PAGE_URL = "https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile"

doc = {
    "schema_version": "stage9_1_identity_variant_vs_catalog_mapping.v1",
    "question_1_is_the_product_variant_confirmed_by_official_features": {
        "status": "confirmed",
        "confirmed_variant": "DualSense\u00ae Wireless Controller \u2014 Cosmic Red",
        "evidence": [
            {"feature": "brand", "value": "Sony / PlayStation", "status": "confirmed", "source": "Stage 9 evidence.json"},
            {"feature": "model_name", "value": "DualSense\u00ae Wireless Controller", "status": "confirmed", "source": "microdata itemprop=name, corroborated by <title>"},
            {"feature": "color", "value": "Cosmic Red", "status": "confirmed_structured", "source": "structured 'Color:' label+value pair on the official page body"},
        ],
        "what_this_confirms": "That an official, first-party PlayStation product with exactly this name and color exists and was verified (direct.playstation.com, Stage 8.2 discovery + Stage 9 field extraction).",
        "what_this_does_not_confirm": "Which manufacturer/regional factory code (if any is even meaningfully distinct) applies -- the page exposes only its own internal webstore sku (1000050734), never a CFI-ZCT1x style code.",
    },
    "question_2_can_this_confirmed_variant_be_linked_to_catalog_rows": {
        "status": "linked_to_both_rows_by_consistency_not_by_code_confirmation",
        "reasoning": (
            "Both catalog rows' own descriptive names ('\u0413\u0435\u0439\u043c\u043f\u0430\u0434 DualSense \u0434\u043b\u044f PS5 Cosmic Red' and "
            "'\u0411\u0435\u0441\u043f\u0440\u043e\u0432\u043e\u0434\u043d\u043e\u0439 \u0433\u0435\u0439\u043c\u043f\u0430\u0434 DualSense Cosmic Red') name the identical product line and color as the "
            "confirmed official variant, and neither row's descriptive text conflicts with it (no different color, no "
            "different edition/bundle mentioned in either). No catalog field distinguishes them as different physical "
            "products (see offline_row_analysis.json) -- the only differing field capable of denoting a real "
            "manufacturer/regional split is the seller-assigned article string, which per instruction cannot alone "
            "establish that difference, and no known official route (see known_routes_review.json) could confirm or "
            "refute it either way this stage."
        ),
        "per_row_mapping": [
            {
                "seller_article": "CFI-ZCT1J 02",
                "catalog_name": "\u0413\u0435\u0439\u043c\u043f\u0430\u0434 DualSense \u0434\u043b\u044f PS5 Cosmic Red",
                "mapped_official_page": PAGE_URL,
                "mapping_basis": "Row name is textually consistent with the confirmed variant; no evidence of conflict.",
                "manufacturer_code_confirmed_for_this_row": False,
                "row_status": "linked_by_descriptive_consistency; manufacturer_code_unconfirmed",
            },
            {
                "seller_article": "CFI-ZCT1W_cosmic_red",
                "catalog_name": "\u0411\u0435\u0441\u043f\u0440\u043e\u0432\u043e\u0434\u043d\u043e\u0439 \u0433\u0435\u0439\u043c\u043f\u0430\u0434 DualSense Cosmic Red",
                "mapped_official_page": PAGE_URL,
                "mapping_basis": "Row name is textually consistent with the confirmed variant; no evidence of conflict.",
                "manufacturer_code_confirmed_for_this_row": False,
                "row_status": "linked_by_descriptive_consistency; manufacturer_code_unconfirmed",
            },
        ],
        "rows_merged_or_deleted": False,
        "explicit_caveat": (
            "'Linked by descriptive consistency' is not the same claim as 'proven to be the identical factory SKU'. "
            "Absence of evidence that the two seller articles denote different products is not proof that they denote "
            "the same one -- it is the strongest conclusion the available official evidence supports, stated as such "
            "rather than overstated as a hard identity match. If a future official source (e.g. a packaging photo, an "
            "order confirmation, or a PlayStation page that does expose a CFI-ZCT1x code) contradicts this, this "
            "mapping should be revisited -- it is not treated as permanently settled."
        ),
    },
    "correction_to_stage_9_framing": (
        "Stage 9's card.json described the manufacturer-code absence on the official page as evidence the rows "
        "'cannot be told apart' and treated this as a blocking export gap. Per this stage's instruction, absence of "
        "the CFI- pattern on the page is NOT by itself disproof of either row's linkage -- it only means the code is "
        "not displayed there. Stage 9's artifacts are left byte-identical (see protected_hashes_check.json); this "
        "file supersedes that framing in NEW reporting only."
    ),
}

(OUT / 'identity_variant_vs_catalog_mapping.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote identity_variant_vs_catalog_mapping.json')
