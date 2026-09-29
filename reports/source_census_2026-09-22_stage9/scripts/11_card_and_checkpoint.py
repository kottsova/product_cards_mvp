import json
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage9')
URL = "https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile"

card = {
    "schema_version": "stage9_card.v1",
    "item": "PlayStation DualSense Wireless Controller, Cosmic Red",
    "catalog_row": {
        "status": "ambiguous_between_2_candidates",
        "candidates": [
            {"seller_article": "CFI-ZCT1J 02", "name": "Геймпад DualSense для PS5 Cosmic Red"},
            {"seller_article": "CFI-ZCT1W_cosmic_red", "name": "Беспроводной геймпад DualSense Cosmic Red"},
        ],
        "resolution": "Not resolved by official evidence -- see identity_ambiguity.json. This report treats CFI-ZCT1J 02 as the primary reporting target (continuity with Stage 8.2) without claiming it is confirmed over the alternate.",
    },
    "export_readiness_criterion": {
        "stated_explicitly": True,
        "criteria": [
            "(1) Brand and model name confirmed by an official source.",
            "(2) The SPECIFIC catalog row (not just a family/color) is confirmed unambiguously, or the ambiguity is explicitly resolved.",
            "(3) At least one official, model-and-variant-matched image is confirmed.",
            "(4) Specifications are sufficient to distinguish and describe this variant for a customer-facing listing (not merely marketing prose).",
            "(5) An instruction manual is either confirmed present with verified language, or its absence is explicitly noted as 'not found in checked sources' -- never concluded to not exist.",
        ],
    },
    "fields": {
        "brand": {"value": "Sony / PlayStation", "status": "confirmed", "url": URL},
        "model_name": {"value": "DualSense® Wireless Controller", "status": "confirmed", "url": URL},
        "color": {"value": "Cosmic Red", "status": "confirmed_structured", "url": URL},
        "manufacturer_regional_code": {"value": None, "status": "not_found", "url": URL},
        "official_image": {"value": "https://media.direct.playstation.com/is/image/sierialto/2025-dualsense-ps5-controller-cosmic-red-accessory-front?$Background_Large$", "status": "confirmed", "url": URL},
        "specifications": {"status": "partial_qualitative_only", "url": URL},
        "instruction_manual": {"value": None, "status": "not_found_in_checked_sources", "url": URL},
    },
    "identity_result": "exact_model",
    "identity_result_reasoning": (
        "Per instructions, exact_variant is not assigned. Model name is confirmed, and color is now confirmed via a structured field "
        "(stronger than Stage 8.2's plain-text-only evidence) -- but the catalog's manufacturer/regional code (CFI-ZCT1J or CFI-ZCT1W) "
        "is confirmed ABSENT from the page (searched and not found, not merely unchecked), and two catalog rows share the same color "
        "name with different codes. Even with color confirmed, the SPECIFIC catalog row cannot be identified with certainty -- this is "
        "exactly the situation instructions warn against resolving by assumption. exact_model reflects: the product itself (DualSense, "
        "Cosmic Red) is confirmed; which catalog SKU it corresponds to is not."
    ),
    "criterion_check": {
        "1_brand_model_confirmed": True,
        "2_specific_catalog_row_unambiguous": False,
        "2_reason": "Two candidate rows remain genuinely indistinguishable from available official evidence -- this is the field that fails the stated criterion, not a cosmetic or minor gap.",
        "3_official_image_confirmed": True,
        "4_specifications_sufficient_for_listing": False,
        "4_reason": "Only qualitative marketing features confirmed (haptic feedback, adaptive triggers, USB-C/battery, Bluetooth); no numeric specs (battery capacity, weight, dimensions, battery life) were found.",
        "5_manual_status_explicit": True,
        "5_detail": "Explicitly recorded as not_found_in_checked_sources, not concluded non-existent.",
    },
    "gaps": [
        {"gap": "Catalog row ambiguity (2 candidate SKUs, unresolved)", "severity": "blocks criterion 2", "note": "This is the gap that prevents export readiness -- not a minor formatting or completeness issue."},
        {"gap": "No numeric specifications (battery capacity, weight, dimensions, battery life, Bluetooth version)", "severity": "blocks criterion 4"},
        {"gap": "No instruction manual found on the verified page or its own first-party links", "severity": "explicitly noted, does not by itself block export per criterion 5's own wording, but no manual is available to attach to the card"},
    ],
    "export_readiness": {
        "status": "not_ready",
        "reasoning": "Fails criterion 2 (unambiguous catalog row) and criterion 4 (sufficient specifications) of the explicitly stated 5-point criterion above. This is not described as 'minor' -- criterion 2 specifically is a genuine identity gap: two real, different seller SKUs cannot be told apart from the confirmed evidence, which is precisely the kind of gap this stage was instructed not to paper over.",
        "what_would_close_it": [
            "A source that maps the page's internal SKU (1000050734) to Sony's CFI-ZCT1x manufacturer code (e.g. an order confirmation, a packaging photo, or a differently-structured official page) would resolve the catalog-row ambiguity.",
            "A support.playstation.com or www.playstation.com specifications page (not opened this stage, since no first-party link on the verified page pointed there) might carry numeric specifications -- a candidate for a future, separately-scoped stage, not opened automatically here.",
        ],
    },
}
json.dump(card, open(OUT / 'card.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# checkpoint.json
# ---------------------------------------------------------------------------
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))
log = []
running_host = Counter()
for i, a in enumerate(run_state['attempts']):
    host = urlsplit(a['url']).hostname
    running_host[host] += 1
    log.append({
        'seq': i + 1, 'url': a['url'], 'kind': a.get('kind'), 'http_status': a.get('http_status'),
        'protection_status': a.get('protection_status'), 'final_url': a.get('final_url'),
        'total_after': i + 1, 'host_after': dict(running_host),
    })

checkpoint = {
    "schema_version": "stage9_checkpoint.v1",
    "budget_declared_before_first_request": json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8')),
    "budget_actual": {
        "total_requests": len(run_state['attempts']),
        "by_host": dict(Counter(urlsplit(a['url']).hostname for a in run_state['attempts'])),
        "hosts_contacted": sorted({urlsplit(a['url']).hostname for a in run_state['attempts']}),
        "within_plan": True,
    },
    "rejected_attempts": run_state.get('rejected_attempts', []),
    "request_log": log,
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "pre_declared_but_unused_hosts": {
        "hosts": ["www.playstation.com", "support.playstation.com"],
        "reason": "Pre-declared as available in case a manual/support link on the verified page pointed there. No such link was found (all /support/ links on the page are generic e-commerce policy pages), so neither host was ever contacted -- no invented navigation, no broad brand search.",
    },
    "document_capability_reused": "Stage 8.6's fetch_document_bounded() was carried over unchanged and was available for use, but was never invoked -- no PDF/document link was found on the verified product page to apply it to.",
    "counter_persistence": "Continues Stage 8.3-8.6's fix unchanged: total and per-host counts are always recomputed from this stage's own run_state.json.",
    "offline_reuse_before_any_request": [
        "data/catalog_2026-09-21_filtered.xlsx (read-only) -- source of the 2 candidate catalog rows, 0 requests.",
        "reports/source_census_2026-09-22_stage8_2/product_page_fixtures.json -- source of the already-verified product page URL, 0 requests.",
        "Checked for existing sqlite snapshots and Stage 8 structural_cache.json entries for this URL -- none found (the page was originally fetched fresh in Stage 8.2 and never snapshotted), confirming a new request was genuinely necessary to extract real field values.",
    ],
    "stop_reason": "All identifiable gaps for this item (identity, specs, image, manual) were checked within 1 request. No further requests were made once the catalog-row ambiguity was established as unresolvable from this page's own evidence -- per instructions, this was not treated as license to search further afield.",
    "samsung_investigated_this_stage": False,
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote card.json, checkpoint.json')
