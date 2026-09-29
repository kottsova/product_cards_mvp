import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_1')
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))

checkpoint = {
    "schema_version": "stage8_2_1_checkpoint.v1",
    "budget": {"max_total": 6, "max_per_host": 6, "used": len(run_state['attempts']), "remaining_unused": 6 - len(run_state['attempts'])},
    "requests": [{'url': a['url'], 'kind': a['kind'], 'http_status': a['http_status'], 'protection_status': a['protection_status'], 'reason': a['reason']} for a in run_state['attempts']],
    "offline_reuse_before_any_request": [
        "robots.txt (samsung_kz snapshot, Stage 7 sqlite) -- confirmed no mobile-specific Sitemap: declaration",
        "kz_ru/sitemap.xml index (Stage 8.2 offline reprocess) -- confirmed 5 branches, only b2c-sitemap.xml is consumer-catalog-shaped",
        "vd-sitemap.xml / im-sitemap.xml / assorted-sitemap.xml (Stage 8.2 fixtures + link_index) -- already fully checked, 0 smartphone URLs, reused without re-fetching",
        "kz_ru homepage (Stage 7 sqlite snapshot, samsung_kz) reprocessed offline for the FIRST time with a full (non-truncated) link list -- this is what found the /smartphones/ site section, at zero network cost",
    ],
    "stop_reason": "Route exhausted, not budget-forced: the only proven consumer-catalog sitemap branch set (b2c-sitemap.xml's 5 children) was fully checked (0 phones), and the alternate first-party /smartphones/ route was checked as far as instructed (2 product-shaped pages), both returning candidate-only (unverifiable) results. 1 of 6 budgeted requests was left unused deliberately rather than trying a third smartphone URL for a likely-identical result.",
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "requests_not_made": [
        {"url": "https://www.samsung.com/kz_ru/top_sitemap.xml", "reason": "No naming evidence connecting it to smartphones; not opened, per instructions to only follow proven branches."},
        {"url": "https://www.samsung.com/kz_ru/business/top-sitemap.xml", "reason": "B2B/business by name."},
        {"url": "https://www.samsung.com/kz_ru/business/b2b-sitemap.xml", "reason": "B2B by name."},
        {"url": "https://www.samsung.com/kz_ru/support/sitemap.xml", "reason": "Support/documents by name, not product catalog."},
        {"url": "a 3rd /smartphones/ product-shaped page (e.g. galaxy-z-fold8/buy/)", "reason": "Not fetched: the first 2 already gave a consistent, repeatable negative structural result; spending the remaining budget on a near-certain repeat was judged not worthwhile. Left in the budget reserve instead."},
    ],
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

next_queue = {
    "schema_version": "stage8_2_1_next_queue.v1",
    "note": "This file is a plan only; nothing here was executed.",
    "entries": [
        {
            "source_family": "samsung",
            "profile_id": "samsung_kz_02d9e6",
            "category": "smartphones",
            "route_result_status": "mobile_sitemap_no_product_urls",
            "next_method": "support_first",
            "detail": (
                "The b2c-sitemap.xml consumer catalog (the only proven sitemap branch) contains zero smartphone URLs across all 5 of its "
                "children. A real /smartphones/ site section exists via first-party navigation but requires client-side rendering to verify "
                "any specific product -- the same architectural gap already found for LG in Stage 8.2. Per instructions, this is NOT "
                "recorded as official_exact_product_not_found for any catalog product. "
                "Recommended next method: support_first -- Samsung's support.samsung.com portal (already a known support_hosts entry in the "
                "samsung_kz_02d9e6 profile) frequently exposes model-code-indexed device pages for warranty/manual lookup that are more "
                "likely to expose static identity data than the marketing/configurator smartphones/ section; this was not attempted here "
                "(out of this stage's strict same-domain-path scope: only www.samsung.com/kz_ru/ was permitted)."
            ),
        },
    ],
}
json.dump(next_queue, open(OUT / 'next_queue.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

results = {
    "schema_version": "stage8_2_1_results.v1",
    "scope": "Samsung smartphones only, www.samsung.com/kz_ru/ only, sitemap + proven first-party navigation only.",
    "official_sitemap_for_smartphones_found": False,
    "sitemap_route_status": "mobile_sitemap_no_product_urls",
    "alternate_first_party_route_found": True,
    "alternate_route_detail": "/kz_ru/smartphones/ site section, discovered entirely offline from the already-known homepage snapshot (0 new requests).",
    "product_pages_verified": 0,
    "product_pages_candidate": 2,
    "catalog_exact_match": False,
    "catalog_identity_result_summary": "insufficient for both attempted smartphone pages (no structured data to compare, and the pages reached are current-generation models, not the catalog-targeted 2020-2022 models anyway)",
    "template_vs_tv_and_audio": "different -- TV/audio-sound pages expose JSON-LD Product (.name/.sku); smartphone pages expose no structured product data at all (same platform, Adobe Experience Manager, but a different frontend template)",
    "responsive_srcset_media_picker": "not_applicable to smartphone pages (srcset markup present but not attributable to a confirmed product)",
    "new_http_requests": len(json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))['attempts']),
    "offline_reprocessed_evidence_items": 4,
    "budget_used_of": "5 of 6",
}
json.dump(results, open(OUT / 'results.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote checkpoint.json, next_queue.json, results.json')
