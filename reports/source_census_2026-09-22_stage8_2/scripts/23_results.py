import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2')

results = {
    "schema_version": "stage8_2_results.v1",
    "scope": "internal_http_search and sitemap_or_catalog_feed Stage 8.2 queue groups only, for 8 priority brands with zero confirmed Product page fixtures in Stage 8.1.",
    "brands": {
        "samsung": {
            "queue_groups_present": ["sitemap_or_catalog_feed (samsung_kr)", "internal_http_search (samsung_kz, samsung_kz_02d9e6, samsung_us)"],
            "method_used": "sitemap_or_catalog_feed (samsung_kz_02d9e6): sitemap.xml index -> b2c-sitemap.xml -> vd-sitemap.xml / im-sitemap.xml -> product URL",
            "internal_http_search_outcome": "non_viable: confirmed client-side-rendered, identical output regardless of query, via offline reprocessing of 5 existing snapshots -- 0 new requests spent proving this",
            "product_pages_verified": 2,
            "categories_covered": ["Телевизоры (TV)", "audio-sound (Galaxy Buds; smartphones not reached)"],
            "catalog_exact_match": False,
            "catalog_identity_result_summary": "insufficient for both (route reached real Samsung products, not the targeted catalog articles)",
            "primitives_applicability": {"specifications_additionalProperty_reader": "does not apply (confirmed empty)", "responsive_srcset_media_picker": "reconfirmed (3rd independent family)"},
            "new_candidate_evidence": ["pdf_document_link_reader (Samsung-only, 2/2 pages, not yet a shared primitive)"]
        },
        "lg": {
            "queue_groups_present": ["sitemap_or_catalog_feed (lg_kz)", "internal_http_search (lg_kr)"],
            "method_used": "sitemap_or_catalog_feed (lg_kz): sitemap.xml index -> kz-gpone-index.xml -> kz-pdp-sitemap-hreflang.xml -> product URL",
            "internal_http_search_outcome": "non_viable: confirmed client-side-rendered via offline reprocessing of lg_kz and lg_kr existing snapshots -- 0 new requests spent proving this",
            "product_pages_verified": 0,
            "product_pages_reached_as_candidate": 2,
            "categories_covered": ["Телевизоры (TV, candidate only)", "Стиральные машины (washing machine, candidate only)"],
            "catalog_exact_match": False,
            "catalog_identity_result_summary": "insufficient for both (no structured product data in static HTML to compare against)",
            "primitives_applicability": {"specifications_additionalProperty_reader": "not applicable (no product page confirmed)", "responsive_srcset_media_picker": "not applicable (no product page confirmed)"},
            "blocker": "client-side rendering (next_js); needs embedded-state extraction research out of this stage's scope"
        },
        "playstation": {
            "queue_groups_present": ["sitemap_or_catalog_feed (playstation_global_candidate)"],
            "method_used": "sitemap_or_catalog_feed: reused Stage 8 cached PS Direct collection page (0 new requests) -> first-party navigation to category pages -> product URLs",
            "product_pages_verified": 2,
            "categories_covered": ["Геймпады (DualSense controller)", "Диски с играми (collector's edition game, different title from catalog target)"],
            "catalog_exact_match": "partial (controller: brand+model+color text match, manufacturer part number unconfirmed)",
            "catalog_identity_result_summary": "exact_model (controller, Cosmic Red), family_only (game, different title)",
            "primitives_applicability": {"specifications_additionalProperty_reader": "does not apply (confirmed empty)", "responsive_srcset_media_picker": "DOM half reconfirmed (4th independent family); JSON-LD fallback half not applicable (microdata site, no JSON-LD)"},
            "new_finding": "Identity is schema.org Microdata-based, not JSON-LD -- first such case in this whole review. Also surfaced a real gap in Stage 8's own model_semantics classifier (does not consider microdata fields)."
        },
        "apple": {"queue_groups_present": ["regional_official_domain (apple_kz)", "support_first (apple_kz_support)"], "in_scope_this_stage": False, "reason": "No entry in internal_http_search or sitemap_or_catalog_feed."},
        "jbl": {"queue_groups_present": [], "in_scope_this_stage": False, "reason": "http_blocked from Stage 8 (jbl.com and support.jbl.com both paused); not retried per host-stop policy."},
        "razer": {"queue_groups_present": ["official_category (razer_global_candidate)"], "in_scope_this_stage": False, "reason": "No entry in internal_http_search or sitemap_or_catalog_feed."},
        "hiper": {"queue_groups_present": ["official_category (hiper)"], "in_scope_this_stage": False, "reason": "No entry in internal_http_search or sitemap_or_catalog_feed."},
        "microsoft": {"queue_groups_present": ["support_first (microsoft)"], "in_scope_this_stage": False, "reason": "No entry in internal_http_search or sitemap_or_catalog_feed.",
                       "xbox_check": "Catalog rows sampled for Microsoft (Gamepads, Game consoles) are confirmed by product name to be genuine Xbox products ('XBOX Series Carbon Black', 'Xbox One S 1TB + ...'), not generic Microsoft hardware. No product page search was performed since no permitted-group queue entry exists."}
    },
    "totals": {
        "brands_with_verified_product_pages": 2,
        "brands_with_candidate_pages_only": 1,
        "brands_out_of_scope_this_stage": 5,
        "total_new_http_requests": 16,
        "total_offline_reprocessed_snapshots": 37,
    }
}
json.dump(results, open(OUT / 'results.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote results.json')
