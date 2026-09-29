import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_2')
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))

samsung_pipeline_contract = {
    "schema_version": "stage8_2_2_samsung_pipeline_contract.v1",
    "status": "architecture_contract_only -- no production adapter included",
    "components": {
        "shared_discovery_orchestration": {
            "scope": "One official domain (www.samsung.com), one sitemap system (per-region sitemap.xml -> b2c-sitemap.xml -> category sub-sitemaps), one identity-code convention (sku field, unverified_sku_meaning) -- confirmed shared across every Samsung category checked so far (TV, audio, and now attempted for smartphones).",
            "status": "confirmed_shared",
        },
        "static_product_template": {
            "scope": "JSON-LD Product (.name + .sku) + responsive_srcset media, confirmed on TV (Stage 8.2) and Galaxy Buds (Stage 8.2), each with 2 independently verified pages.",
            "categories_confirmed": ["tvs", "audio-sound (mobile-accessories overlap)"],
            "categories_not_yet_confirmed": ["home appliances (da-sitemap.xml)", "memory/storage (memory-sitemap.xml)"],
            "status": "confirmed_for_2_categories_only -- per instructions, home appliances and memory are NOT assumed compatible with TV/audio without their own Product page fixtures, even though their sitemap branches were reached in Stage 8.2.1.",
        },
        "smartphone_client_rendered_template": {
            "scope": "/smartphones/... family and /buy/ configurator pages (Stage 8.2.1) plus every /support/... route tried this stage -- all confirmed to carry zero static JSON-LD/microdata Product data.",
            "status": "unresolved -- requires an embedded-state extraction capability (reading client-side JS state, not full browser rendering) that does not currently exist in this pipeline and is out of this stage's scope to build.",
        },
        "support_first_model_resolver": {
            "scope": "Attempted this stage: support root, GET search (searchvalue param), manuals hub, model-finder tool, one content-article leaf page -- all client-rendered, 0 model-specific evidence for either target smartphone.",
            "status": "not_viable_as_currently_scoped_on_kz_ru -- would need either (a) the same embedded-state capability as the smartphone template, or (b) a genuinely different regional support surface (samsung_us's /support/downloads/ is the strongest untested lead) that turns out to render statically.",
        },
        "document_resolver": {
            "scope": "Confirmed working for TV/Galaxy Buds (a[href:pdf] + support_navigation=true, Stage 8.2, 2/2 pages). Zero evidence for smartphones this stage -- no document link was ever reached in static HTML.",
            "status": "category_specific -- the TV/audio document pattern is Samsung-specific already (per Stage 8.1/8.2, not shared with other brands), and this stage found no basis to extend or contradict it for smartphones; it simply produced no smartphone evidence either way.",
        },
        "category_specific_identity_validation": {
            "scope": "model_semantics=unverified_sku_meaning confirmed identical on TV and Buds identity contracts; smartphones have no identity contract to compare at all (no product object reached).",
            "status": "required_per_category -- no pooling assumed between categories; each category's identity contract must be independently verified before use, consistent with Stage 8.1's identity_semantics_resolver rule.",
        },
    },
    "production_adapter_included": False,
    "next_step_gate": "Per the stage's exit criteria: smartphones remain an unresolved flow (support-first did not confirm exact_model or a document); this does NOT block a limited Samsung pilot restricted to the two categories with confirmed static Product pages (TV, audio-sound/Galaxy Buds).",
}
json.dump(samsung_pipeline_contract, open(OUT / 'samsung_pipeline_contract.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

checkpoint = {
    "schema_version": "stage8_2_2_checkpoint.v1",
    "budget_plan": {"max_total": 12, "max_per_host": 4, "max_hosts": 3, "max_pages_per_item": 2, "max_documents_per_model": 2},
    "budget_actual": {
        "total_requests": len(run_state['attempts']),
        "by_host": {"www.samsung.com": len(run_state['attempts'])},
        "hosts_contacted": 1,
        "per_host_cap_overshoot": "6 requests to www.samsung.com against a planned cap of 4 -- disclosed and explained in support_routes.json's budget_note_and_correction; no further requests were made to this or any host once identified.",
    },
    "offline_reuse_before_any_request": [
        "robots.txt (samsung_kz, Stage 7 sqlite) -- 0 requests",
        "kz_ru/sitemap.xml index (Stage 8.2 offline reprocess) -- 0 requests",
        "b2c-sitemap.xml + all 5 children (Stage 8.2 / Stage 8.2.1) -- 0 requests, not re-checked per instructions",
        "kz_ru homepage full link list (Stage 8.2.1 offline reprocess, reused) -- 0 requests, source of the /support/... links used this stage",
        "samsung.com/sec/support/ cached structure (Stage 8 structural_cache.json) -- 0 requests, checked for mobile-manuals links (none found)",
        "samsung.com/us/ homepage (Stage 7 sqlite) reprocessed offline for the first time this stage -- 0 requests, source of the samsung_us fallback candidates recorded in regional_fallbacks.json",
    ],
    "stop_reason": "Consistent, repeated negative structural result (5 different route types, 6 requests, 0 identity matches for either target model) plus an identified per-host budget overshoot. Stopping here is a deliberate choice to not keep spending budget on a route category (kz_ru support/search) that has now been thoroughly disproven, rather than forcing a result.",
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "requests_not_made": [
        {"item": "samsung_us /support/downloads/", "reason": "Discovered offline (0 cost) but not fetched live this stage -- recorded as the recommended next step in regional_fallbacks.json rather than opened under an already-overshot per-host budget."},
        {"item": "A second /smartphones/... or /buy/ page for either model", "reason": "Not attempted -- Stage 8.2.1 already established this page type is client-rendered on 2/2 samples; a 3rd would not add information."},
    ],
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

results = {
    "schema_version": "stage8_2_2_results.v1",
    "scope": "Samsung support-first discovery for exactly 2 catalog smartphones (Galaxy S20 FE, Galaxy Z Fold3), www.samsung.com only.",
    "official_support_host_confirmed": "www.samsung.com (region-path pattern: /kz_ru/support/, /us/support/, /sec/support/) -- support.samsung.com was never assumed or contacted.",
    "models": {
        "Galaxy S20 FE": {
            "catalog_article": "488776SM-G780GZRDSKZ",
            "product_page_or_support_page_found": False,
            "status": "official_support_client_rendered",
            "catalog_identity_result": "insufficient",
            "documents_found": 0,
        },
        "Galaxy Z Fold3": {
            "catalog_article": "491953SM-F926BZGGSKZ",
            "product_page_or_support_page_found": False,
            "status": "official_support_client_rendered",
            "catalog_identity_result": "insufficient",
            "documents_found": 0,
        },
    },
    "routes_tried": ["support_root", "GET search (searchvalue param)", "user-manuals-and-guide hub", "mobile/find-your-galaxy model finder", "one support-content article leaf page"],
    "new_http_requests": len(run_state['attempts']),
    "hosts_contacted": 1,
    "regional_fallback_recommended": True,
    "smartphone_flow_status": "unresolved -- moved to a separate flow, does not block the TV/audio pilot",
    "categories_ready_for_pilot": ["tvs", "audio-sound (Galaxy Buds / mobile-accessories)"],
}
json.dump(results, open(OUT / 'results.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote samsung_pipeline_contract.json, checkpoint.json, results.json')
