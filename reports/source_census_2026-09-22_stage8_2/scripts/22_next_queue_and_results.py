import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2')

next_queue = {
    "schema_version": "stage8_2_next_queue.v1",
    "note": "Per-brand next safe method. This file is a plan only; nothing here was executed automatically.",
    "entries": [
        {
            "source_family": "samsung", "profile_id": "samsung_kz_02d9e6",
            "status": "partially_closed_2_pages_verified_smartphone_still_open",
            "next_method": "sitemap_or_catalog_feed",
            "detail": "TV and audio/mobile-accessories categories now have a verified Product page each. Smartphones (Galaxy S-series) were not located inside the b2c/im/vd/assorted sitemap slice actually served (300-loc cap per file). Next: check samsung.com/kz_ru/robots.txt directly for any additional declared sitemap not yet seen, and/or try samsung_kr's consumer_sitemap.xml (South Korea site) as a cross-check for the phones sitemap naming convention, still without inventing a URL."
        },
        {
            "source_family": "lg", "profile_id": "lg_kz",
            "status": "pages_reached_not_verified",
            "next_method": "manual_review",
            "detail": "A correctly-named PDP sitemap exists and resolves to real model URLs, but the static HTML carries zero JSON-LD/microdata Product objects (client-side rendering, next_js). No further sitemap/search request will fix this; the blocking constraint is architectural (no Chromium in the automatic pipeline), matching Stage 8's existing javascript_only classification elsewhere in LG. Recommend manual_review_only status for LG.com/kz PDP pages until an embedded-state extraction method is separately researched and approved -- not a network retry."
        },
        {
            "source_family": "playstation", "profile_id": "playstation_global_candidate",
            "status": "controllers_closed_game_discs_open",
            "next_method": "regional_official_domain",
            "detail": "DualSense controller category is closed (verified page, exact_model catalog match). The catalog's 'Диски с играми' (game discs) category does not map well onto PS Direct's /buy-games/ collector's-edition-style listings. Next: consider the official PlayStation Store as a separate first-party official domain (store.playstation.com is already within the playstation.com allowed-host scope) for physical/digital game titles specifically, in a future stage."
        },
        {
            "source_family": "apple", "profile_id": "apple_kz",
            "status": "not_attempted_out_of_group_scope",
            "next_method": "regional_official_domain",
            "detail": "Carried over unchanged from Stage 8.1's queue: apple_kz sits in regional_official_domain, and apple_kz_support sits in support_first. Neither is in the two groups this stage was permitted to run."
        },
        {
            "source_family": "jbl", "profile_id": "jbl_global_candidate",
            "status": "blocked_not_retried",
            "next_method": "blocked_manual_review",
            "detail": "Both jbl.com and support.jbl.com are http_blocked from Stage 8 (http_host_paused). Per the host-stop policy, this is not retried automatically in any future pass; it needs a deliberate, separately-approved retry (new day / different route) or manual_review."
        },
        {
            "source_family": "razer", "profile_id": "razer_global_candidate",
            "status": "not_attempted_out_of_group_scope",
            "next_method": "official_category",
            "detail": "Carried over unchanged from Stage 8.1's queue: razer.com sits in official_category, not in the two groups this stage was permitted to run."
        },
        {
            "source_family": "hiper", "profile_id": "hiper",
            "status": "not_attempted_out_of_group_scope",
            "next_method": "official_category",
            "detail": "Carried over unchanged from Stage 8.1's queue: hiper-power.com sits in official_category, not in the two groups this stage was permitted to run."
        },
        {
            "source_family": "microsoft", "profile_id": "microsoft",
            "status": "not_attempted_out_of_group_scope",
            "next_method": "support_first",
            "detail": "Carried over unchanged from Stage 8.1's queue: only support.microsoft.com is registered, in support_first, not in the two groups this stage was permitted to run. Catalog rows for this brand (gamepads, consoles) were confirmed to be genuinely Xbox products by name ('XBOX Series Carbon Black', 'Xbox One S...'), but no dedicated Xbox-specific official domain is currently verified in the source registry -- registry research (not a network search) would be needed before a next network pass, since inventing an xbox.com profile is out of this stage's scope."
        },
    ],
}
json.dump(next_queue, open(OUT / 'next_queue.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote next_queue.json with', len(next_queue['entries']), 'entries')
