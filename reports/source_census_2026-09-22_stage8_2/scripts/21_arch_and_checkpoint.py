import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2')
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))

# ---------------------------------------------------------------------------
# architecture_observations.json
# ---------------------------------------------------------------------------
arch = {
    "schema_version": "stage8_2_architecture_observations.v1",
    "baseline_primitives": "reports/source_census_2026-09-22_stage8_1/primitives.v1.json",
    "note": "Compares each newly-verified Product page against Stage 8.1's compatible_primitive candidates (additionalProperty_specification_reader, responsive_srcset_media_picker). No new shared_primitive_candidate is declared from a single family's evidence, per instructions.",
    "families": {
        "samsung": {
            "pages_verified": 2,
            "discovery": {
                "status": "source_specific",
                "route": "robots/known sitemap.xml -> sitemap index (b2c-sitemap.xml) -> category sitemap (vd-sitemap.xml / im-sitemap.xml) -> product URL",
                "note": "A new, reproducible discovery pattern (deep sitemap-index descent) not previously exercised by Stage 8.1's four primary families, which all relied on homepage/category first-party navigation. Distinct sub-sitemap naming (vd=visual display/TV, im=IT&mobile, da=digital appliances) is Samsung-specific."
            },
            "identity": {
                "status": "source_specific",
                "contract": "JSON-LD .name + .sku, model_semantics=unverified_sku_meaning",
                "note": "Same shape as hyperx/dreame/asus/nintendo from Stage 8.1 (sku present, no mpn/gtin/model). Reinforces -- does not change -- the existing rule that identity_semantics_resolver stays custom per family."
            },
            "specifications": {
                "status": "insufficient_evidence",
                "note": "additionalProperty and DOM table/dl/details both absent on 2/2 pages (TV + earbuds). Stage 8.1's additionalProperty_specification_reader does not apply here -- specs are very likely rendered client-side, matching the xiaomi_global/dreame pattern of confirmed-absent (not just unsampled) static specs."
            },
            "media": {
                "status": "reconfirms_compatible_primitive",
                "primitive": "responsive_srcset_media_picker",
                "note": "JSON-LD .image + DOM responsive_srcset confirmed identical on 2/2 pages (TV, earbuds), on Adobe Experience Manager + generic_json_ld_product -- a CMS Stage 8.1 never tested this primitive against. This is a 3rd independent family reconfirming the same primitive with no change to its contract or scope."
            },
            "documents": {
                "status": "candidate_single_family",
                "note": "a[href:pdf] link plus support_navigation=true confirmed on 2/2 pages -- the first multi-page-confirmed document evidence anywhere in this project's review (Stage 8.1's dreame sample was a single page). Recorded as a Samsung-specific candidate only; documents still has no second independently-confirmed family at >=2 pages each, so no shared_primitive_candidate is declared."
            }
        },
        "lg": {
            "pages_verified": 0,
            "pages_reached_but_unverified": 2,
            "discovery": {
                "status": "source_specific",
                "route": "robots/known sitemap.xml -> sitemap index (kz-gpone-index.xml) -> PDP-labeled sitemap (kz-pdp-sitemap-hreflang.xml) -> product URL",
                "note": "LG explicitly names a sitemap file for Product Detail Pages, a stronger discovery signal than Samsung's category-coded sitemap names, but the pages it points to did not verify structurally (see identity)."
            },
            "identity": {
                "status": "insufficient_evidence",
                "contract": "no JSON-LD Product objects, no microdata Product nodes (product_objects=0) on 2/2 fetched PDP-sitemap URLs",
                "note": "Confirms, with fresh evidence, Stage 8's existing javascript_only finding for other LG profiles: LG.com/kz's PDP pages very likely render identity/spec data client-side (next_js + adobe_experience_manager fingerprints both present) and do not embed it in the initial HTTP response. No Chromium was used, per scope, so this cannot be resolved within Stage 8.2."
            },
            "specifications": {"status": "insufficient_evidence", "note": "Not reachable without a confirmed product page."},
            "media": {
                "status": "not_applicable",
                "note": "DOM responsive_srcset markup IS present on both pages, but since is_product_page=false the pages do not qualify as product-page evidence for the responsive_srcset_media_picker primitive -- the images present may be generic site chrome, not product photography. Not counted toward or against the primitive."
            },
            "documents": {"status": "insufficient_evidence", "note": "support_navigation=true detected, but no PDF link found on either page."}
        },
        "playstation": {
            "pages_verified": 2,
            "discovery": {
                "status": "source_specific",
                "route": "Stage 8 cached PS Direct collection page (0 new requests) -> first-party navigation to accessories/controllers-and-remotes and games/catalog category pages -> /buy-accessories/ and /buy-games/ product URLs",
                "note": "PS Direct (direct.playstation.com) is Sony's first-party D2C storefront, separate from www.playstation.com marketing pages and store.playstation.com's digital store. Confirmed reproducible with a first-party-navigation-only route."
            },
            "identity": {
                "status": "new_pattern_not_in_stage8_1",
                "contract": "schema.org Microdata (itemprop=\"sku\"/\"name\"), NOT JSON-LD -- the first confirmed non-JSON-LD identity source across this entire review (Stage 8.1 + this stage).",
                "note": "The json_ld_product_field_extractor primitive does not apply to PS Direct at all (different technology). A hypothetical 'microdata_product_field_extractor' primitive is recorded as a single-family candidate only -- no second family with confirmed microdata-based identity exists yet."
            },
            "identity_tooling_gap": {
                "status": "observation",
                "note": "inspect_structure()'s model_semantics classification (product_tool/census/structural_contracts_v8.py) only inspects the JSON-LD-derived `fields` set, not the microdata `props` set, when deciding explicit_manufacturer_or_model / unverified_sku_meaning / marketing_name_only. PS Direct pages therefore report model_semantics=marketing_name_only even though a real sku microdata property is present and code_fields correctly includes 'sku' (code_fields DOES merge fields+props). This is a real, reproducible gap in Stage 8's own classifier, not a fact about PlayStation's page structure. Not fixed in this stage -- flagged as evidence only, per scope (verification, not adapter/tooling changes)."
            },
            "specifications": {"status": "insufficient_evidence", "note": "additionalProperty and DOM table/dl/details both absent on 2/2 pages."},
            "media": {
                "status": "partial_reconfirmation",
                "primitive": "responsive_srcset_media_picker",
                "note": "DOM responsive_srcset (plus itemprop=image semantic_gallery marker) confirmed on 2/2 verified product pages. The DOM-selection half of the primitive (pick the largest declared srcset candidate) is technology-agnostic and matches here; the JSON-LD .image / ImageObject.contentUrl half of the primitive's fallback rule does not apply (no JSON-LD at all on this site). Recorded as a partial reconfirmation of the DOM half only, not a full primitive match, since the primitive's stated fallback path was never exercised."
            },
            "documents": {"status": "insufficient_evidence", "note": "support_navigation=true detected, no PDF link found on either page."}
        }
    }
}

json.dump(arch, open(OUT / 'architecture_observations.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote architecture_observations.json')

# ---------------------------------------------------------------------------
# checkpoint.json
# ---------------------------------------------------------------------------
from collections import Counter
hosts = Counter(a['url'].split('/')[2] for a in run_state['attempts'])
checkpoint = {
    "schema_version": "stage8_2_checkpoint.v1",
    "reused_snapshots": {
        "offline_reprocessed_from_existing_sqlite_snapshots": 37,
        "note": "37 pre-existing HTTP snapshots (Stage 5.1-7.1 sqlite stores) for samsung_kr/samsung_kz/samsung_kz_02d9e6/samsung_us/lg_kr/lg_kz were reprocessed offline with inspect_structure() -- zero new network requests -- before any new fetch was planned. See scripts/02_offline_reprocess.py and offline_reprocess.json.",
        "key_finding_from_reuse": "internal_http_search turned out to be non-viable via static HTTP for both families that had it queued, discovered entirely from existing snapshots (0 new requests): Samsung's ?search=<term> responses (5 distinct queries, kz_ru and us) are byte-identical to the plain homepage; LG's search/?q=<term> (lg_kz) and search?keyword=<term> (lg_kr) responses vary only by a byte or two across distinct queries (the echoed query string itself), with identical extracted category links every time. Both are client-side-rendered SPA shells that do not return per-query server-rendered results. This eliminated internal_http_search as a viable route for samsung_kz/samsung_kz_02d9e6/samsung_us/lg_kr before any new request was made, and redirected all new-request budget to sitemap_or_catalog_feed instead."
    },
    "new_http_requests": {
        "total": len(run_state['attempts']),
        "by_host": dict(hosts),
        "budget_caps_used": {"max_per_host": 8, "max_total": 30},
    },
    "stop_reasons": {
        "hosts_paused_this_run": run_state['blocked_hosts'],
        "note": "No host reached a confirmed 403/429/challenge_confirmed in this run. www.samsung.com reached its self-imposed 8-request host cap and further Samsung sitemap descent (e.g. a mobile/phones-named sitemap for smartphones) was deferred to next_queue.json rather than exceeding the cap.",
    },
    "requests_not_made_due_to_scope_or_checkpoint": [
        {"family": "apple", "reason": "No queue entry in internal_http_search/sitemap_or_catalog_feed (only regional_official_domain, support_first) -- out of this stage's permitted method scope."},
        {"family": "jbl", "reason": "http_blocked from Stage 8 (jbl.com and support.jbl.com both paused) -- not retried, per host-stop policy."},
        {"family": "razer", "reason": "No queue entry in the two permitted groups (only official_category) -- out of scope."},
        {"family": "hiper", "reason": "No queue entry in the two permitted groups (only official_category) -- out of scope."},
        {"family": "microsoft", "reason": "No queue entry in the two permitted groups (only support_first) -- out of scope."},
        {"family": "samsung_us / samsung_kz / samsung_kz_02d9e6 internal search", "reason": "Confirmed via offline snapshot reprocessing (not a new request) to return content identical (or near-identical, differing only by the echoed query string) to the plain homepage across 5 distinct queries -- not a viable static-HTTP route; not retried live."},
        {"family": "lg_kr internal search (lge.co.kr)", "reason": "Confirmed via offline snapshot reprocessing (not a new request) to return near-identical content across 3 distinct queries, same pattern as Samsung -- not a viable static-HTTP route; not retried live."},
    ],
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote checkpoint.json')
