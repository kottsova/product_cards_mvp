import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_2')

IDENTITY_FIELDS_TEMPLATE = {
    'manufacturer_confirmed': 'Samsung (generic brand text present on every page fetched)',
    'family_name_confirmed': False,
    'consumer_model_name_confirmed': False,
    'manufacturer_model_code_confirmed': False,
    'regional_suffix_confirmed': False,
    'storage_confirmed': False,
    'color_confirmed': False,
    'connectivity_confirmed': False,
    'other_variant_fields_confirmed': False,
    'link_to_source_catalog_row': 'none -- no page reached exposes any field to compare against the catalog row',
}

identity_evidence = {
    "schema_version": "stage8_2_2_identity_evidence.v1",
    "rule": "The mere presence of the words 'S20 FE' or 'Z Fold3' in arbitrary text, a URL, or a result listing is explicitly NOT treated as sufficient identity confirmation, per instructions.",
    "models": {
        "Galaxy S20 FE (catalog article 488776SM-G780GZRDSKZ, 128GB)": {
            "pages_checked": [
                "https://www.samsung.com/kz_ru/search/?searchvalue=Galaxy%20S20%20FE",
                "https://www.samsung.com/kz_ru/support/user-manuals-and-guide/",
                "https://www.samsung.com/kz_ru/mobile/find-your-galaxy/",
            ],
            "identity_fields": dict(IDENTITY_FIELDS_TEMPLATE),
            "catalog_identity_result": "insufficient",
            "reasoning": "None of the 3 pages checked for this model contain the string 'Galaxy S20 FE' or 'S20 FE' anywhere in the rendered static text (identity_term_matches all false), let alone a model code, storage, color, or connectivity field. Every candidate route returned the same generic client-rendered navigation shell. No page can be linked to this catalog row at any confidence level above insufficient.",
        },
        "Galaxy Z Fold3 5G (catalog article 491953SM-F926BZGGSKZ, 512GB)": {
            "pages_checked": [
                "https://www.samsung.com/kz_ru/search/?searchvalue=Galaxy%20Z%20Fold3",
                "https://www.samsung.com/kz_ru/support/user-manuals-and-guide/",
                "https://www.samsung.com/kz_ru/mobile/find-your-galaxy/",
            ],
            "identity_fields": dict(IDENTITY_FIELDS_TEMPLATE),
            "catalog_identity_result": "insufficient",
            "reasoning": "Same outcome as Galaxy S20 FE: 'Galaxy Z Fold3' / 'Fold3' never appears in the static text of any checked page. No identity field beyond the generic brand word 'Samsung' was confirmed anywhere.",
        },
    },
    "note_on_the_near_miss": (
        "One support-content article WAS reached with a mobile-related slug (check-out-the-new-camera-functions-of-galaxy-s20-plus-s20-ultra), "
        "but it names Galaxy S20 Plus / S20 Ultra, a DIFFERENT variant from the catalog-targeted Galaxy S20 FE, and per instructions "
        "'family name' matching (S20-series) alone is not treated as evidence for a different specific model -- it was not counted toward "
        "either catalog row's identity evidence."
    ),
}
json.dump(identity_evidence, open(OUT / 'identity_evidence.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

documents = {
    "schema_version": "stage8_2_2_documents.v1",
    "documents_found": [],
    "note": (
        "Zero official documents (manuals, guides, downloads) were reached for either model. Every candidate route that could plausibly "
        "list documents (support/user-manuals-and-guide/, mobile/find-your-galaxy/, search/?searchvalue=<model>) rendered as a client-side "
        "shell in the static HTTP response, with no document links present in the HTML actually served. No PDF or manual URL was ever "
        "observed for Galaxy S20 FE or Galaxy Z Fold3 within this stage's budget. This is an honest empty result, not a broad support crawl "
        "failure -- each route was checked exactly once, per the 'max two documents per model' and 'no unbounded support crawl' constraints."
    ),
    "language_priority_applied": "n/a -- no documents were found to prioritize by language (Russian first, then English, then any other).",
}
json.dump(documents, open(OUT / 'documents.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

regional_fallbacks = {
    "schema_version": "stage8_2_2_regional_fallbacks.v1",
    "kz_ru_status": "exhausted within this stage's budget -- support root, search, manuals hub, model finder, and one content-article leaf page all confirmed client-rendered with zero model-specific evidence.",
    "candidate_fallback_regions": [
        {
            "region": "samsung_us (https://www.samsung.com/us/)",
            "ownership_evidence": "Already a registered, official Stage 8 profile (samsung_us, support_hosts=['www.samsung.com']).",
            "offline_findings_this_stage": [
                "/us/support/downloads/ -- a real first-party link, a page TYPE not yet tried on kz_ru (kz_ru only exposed /support/user-manuals-and-guide/, already tested and found client-rendered)",
                "/us/mobile/find-your-galaxy/ -- same tool as kz_ru, already proven client-rendered there; low expectation of a different result",
                "/us/support/troubleshoot/TSG10001565/ -- an ID-based troubleshoot guide URL pattern, suggesting some support content may be indexed by stable IDs -- not yet explored",
            ],
            "not_fetched_this_stage": "Discovered entirely offline (0 cost) but not fetched live -- this stage's budget was intentionally stopped after the kz_ru host-budget overshoot (see support_routes.json) rather than opening a second host under time pressure.",
            "recommended_as_next_step": True,
        },
        {
            "region": "samsung_kr (https://www.samsung.com/sec/)",
            "ownership_evidence": "Already a registered, official Stage 8 profile with a cached support root fetch (samsung.com/sec/support/, 92 links).",
            "offline_findings_this_stage": "Only a laptop-specific (Galaxy Books) download center link was found in its cached link list; no mobile-phone-specific manuals/downloads link is evidenced for this region.",
            "recommended_as_next_step": False,
            "reason_deprioritized": "Weaker offline evidence for a mobile-specific route than samsung_us; would likely require fresh discovery requests rather than reusing an already-known link, unlike samsung_us's /support/downloads/.",
        },
    ],
    "recommendation": "regional_support_fallback_required -- try samsung_us's /us/support/downloads/ (and, if that also proves client-rendered, treat the entire support-first route as architecturally blocked for smartphones and move to manual_review_required) before attempting any further region.",
}
json.dump(regional_fallbacks, open(OUT / 'regional_fallbacks.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

print('wrote identity_evidence.json, documents.json, regional_fallbacks.json')
