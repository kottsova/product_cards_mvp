"""Stage 9.1 -- fully offline. Recompute export readiness against an explicit
criterion, with the identity-mapping question and the specs/manual gaps kept
as separate, distinctly-stated items (not merged into one "ambiguity" gap).
No network access in this script."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-22_stage9_1'
PAGE_URL = "https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile"

card = {
    "schema_version": "stage9_1_card.v1",
    "item": "PlayStation DualSense Wireless Controller, Cosmic Red",
    "supersedes_reporting_in": "reports/source_census_2026-09-22_stage9/card.json (left byte-identical; this is new reporting, not a rewrite of that file)",
    "official_variant": {
        "status": "confirmed",
        "value": "DualSense\u00ae Wireless Controller \u2014 Cosmic Red",
        "url": PAGE_URL,
    },
    "catalog_rows": {
        "status": "both_retained_distinct_both_linked_by_consistency",
        "rows": [
            {"seller_article": "CFI-ZCT1J 02", "catalog_name": "\u0413\u0435\u0439\u043c\u043f\u0430\u0434 DualSense \u0434\u043b\u044f PS5 Cosmic Red", "linkage": "linked_by_descriptive_consistency; manufacturer_code_unconfirmed"},
            {"seller_article": "CFI-ZCT1W_cosmic_red", "catalog_name": "\u0411\u0435\u0441\u043f\u0440\u043e\u0432\u043e\u0434\u043d\u043e\u0439 \u0433\u0435\u0439\u043c\u043f\u0430\u0434 DualSense Cosmic Red", "linkage": "linked_by_descriptive_consistency; manufacturer_code_unconfirmed"},
        ],
        "detail": "identity_variant_vs_catalog_mapping.json",
    },
    "identity_result": "exact_model",
    "identity_result_reasoning": (
        "Unchanged from Stage 9: model and color are confirmed at a structured level, but no official source "
        "exposes a manufacturer/regional code, so exact_variant is still not assigned to either catalog row "
        "specifically. What changes in Stage 9.1 is not the identity_result value itself, but the interpretation "
        "of what the code's absence means (see identity_variant_vs_catalog_mapping.json) and the resulting export "
        "readiness reasoning below."
    ),
    "export_readiness_criterion": {
        "stated_explicitly": True,
        "criteria": [
            "(1) Brand and model name confirmed by an official source.",
            "(2) Every catalog row intended for export is linked to the confirmed official variant by explicit, stated evidence (descriptive consistency counts; a code-level match is not required if no official source exposes a comparable code) -- and any unresolved conflict between rows is stated, not assumed away.",
            "(3) At least one official, model-and-variant-matched image is confirmed.",
            "(4) Specifications are sufficient to distinguish and describe this variant for a customer-facing listing (not merely marketing prose).",
            "(5) An instruction manual is either confirmed present with verified language, or its absence is explicitly noted as 'not found in checked sources' -- never concluded to not exist.",
        ],
    },
    "criterion_check": {
        "1_brand_model_confirmed": True,
        "2_rows_linked_by_stated_evidence": True,
        "2_detail": "Both rows linked by descriptive consistency (see identity_variant_vs_catalog_mapping.json); this is weaker than a code-confirmed match and is stated as such, not overstated.",
        "3_official_image_confirmed": True,
        "4_specifications_sufficient_for_listing": False,
        "4_reason": "Only qualitative marketing features confirmed (haptic feedback, adaptive triggers, USB-C/battery, Bluetooth); no numeric specs (battery capacity, weight, dimensions, battery life) were found. This is a standalone gap, separate from the manual gap and from the catalog-linkage question.",
        "5_manual_status_explicit": True,
        "5_detail": "Explicitly recorded as not_found_in_checked_sources, not concluded non-existent. This is a standalone gap, separate from the specifications gap.",
    },
    "gaps": [
        {
            "gap": "No numeric specifications (battery capacity, weight, dimensions, battery life, Bluetooth version)",
            "severity": "blocks criterion 4",
            "note": "Stated as its own gap, not merged with the manual gap or the catalog-linkage question.",
        },
        {
            "gap": "No instruction manual found on the verified page or its own first-party links",
            "severity": "explicitly noted as a gap on its own; per criterion 5's own wording this does not by itself block export, but no manual is available to attach to the card",
            "note": "Stated as its own gap, not merged with the specifications gap.",
        },
        {
            "gap": "Manufacturer/regional code (CFI-ZCT1x) not confirmed for either catalog row",
            "severity": "does not block criterion 2 under this stage's revised wording (descriptive-consistency linkage is sufficient), but remains an open item -- if a future official source contradicts the current linkage, this card should be revisited",
            "note": "This is the item that WAS the sole blocking reason in Stage 9; it is now a stated, non-blocking residual gap, not a resolved certainty and not a blocking ambiguity.",
        },
    ],
    "export_readiness": {
        "status": "not_ready",
        "reasoning": (
            "Fails criterion 4 (sufficient specifications) of the explicitly stated 5-point criterion above. "
            "Criterion 2, which blocked export in Stage 9, now passes under this stage's more precise reading: "
            "absence of a manufacturer code on the official page is not disproof of either row's linkage, and "
            "both rows are linked to the confirmed variant by stated, explicit (if not code-level) evidence. "
            "The remaining specifications gap is not described as 'minor' -- a customer-facing listing without "
            "any numeric specification is a genuine completeness gap, stated plainly."
        ),
        "what_changed_from_stage_9": "Criterion 2 (catalog row linkage) moved from failing/blocking to passing/non-blocking. Criterion 4 (specifications) remains failing, unchanged from Stage 9. The manual gap (criterion 5) remains explicitly noted but non-blocking, unchanged from Stage 9.",
        "what_would_close_it": [
            "A numeric specifications source (e.g. a support.playstation.com or www.playstation.com specs page, not opened this or the prior stage since no first-party link on the verified page pointed there) would close criterion 4.",
        ],
    },
}

(OUT / 'card.json').write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding='utf-8')

checkpoint = {
    "schema_version": "stage9_1_checkpoint.v1",
    "budget_declared_before_first_request": json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8')),
    "budget_actual": {
        "total_requests": 0,
        "by_host": {},
        "hosts_contacted": [],
        "within_plan": True,
    },
    "rejected_attempts": [],
    "request_log": [],
    "offline_reuse_before_any_decision": [
        "data/catalog_2026-09-21_filtered.xlsx (read-only) -- full 8-column schema inspection, both candidate rows re-read field-by-field.",
        "reports/source_census_2026-09-22_stage8_2/link_index/ps_controllers_cat.json -- confirms exactly 1 DualSense Cosmic Red link exists in the entire controllers category (90 links total).",
        "reports/source_census_2026-09-22_stage9/evidence.json and raw/product_fetch.json -- reused for the already-checked support links and the already-performed CFI- pattern search; no re-fetch needed.",
    ],
    "stop_reason": "Offline analysis (offline_row_analysis.json) plus a review of every already-known official route (known_routes_review.json) found no substantial difference between the two catalog rows and no unchecked route capable of confirming one, so the conditional trigger for a bounded network check was never met. 0 new HTTP requests were made this stage.",
    "no_other_products_searched_this_stage": True,
    "samsung_investigated_this_stage": False,
}
(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote card.json, checkpoint.json')
