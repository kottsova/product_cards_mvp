# Stage 5 — bounded internal-search discovery v1

Generated: 2026-09-22T14:12:03.065101+00:00

Reuses DiscoveryBudget, BudgetUsage, CandidatePage, StrategyResult, URL normalization, host allowlists, AccessProbe and structured IdentityVerifier. StrategyResult now carries strategy and strategy_evidence. SearchRoute records action, method, query key, constants, origin, allowed host, confidence, rejection and timestamp. Historical census serialization remains compatible.

Automatic routes are declared GET only. POST, account/cart/login, password/file fields, CSRF/session keys, JavaScript handlers, unconfigured APIs and foreign hosts are rejected as manual_or_future_strategy. Scripts are never executed or used to invent routes. Hidden parameters outside a small static search/locale allowlist require review.

Per source hard caps: 3 queries, 20 retained candidates, 3 product probes, 10 actual HTTP requests including redirects; 1 second minimum interval; 50 second deadline; bounded response/parser sizes. Each redirect is checked before issuing the next GET. 403/429/confirmed challenges stop the family immediately. Cookies, authorization and token values are not persisted.

Search titles, URLs, snippets and ItemList/card evidence rank candidates only. Only target-page structured Product identity can establish exact_model or exact_variant. Explicit expected variant fields are all checked, including service index and revision. No production adapter, production orchestrator, extraction of product attributes/media/manuals, dealer fallback, browser automation or registry promotion was added.

## Live dry-run

| Source | Catalog code | Requests | Queries executed | Candidates | Product probes | Outcome |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| lg_kz | 27ART10AKPL | 8 | 1 | 8 | 3 | results_identity_insufficient |
| bosch_home | SBV45FX01R | 1 | 0 | 0 | 0 | search_route_not_found |
| apple_kz | MGEX4FE/A | 1 | 0 | 0 | 0 | search_route_not_found |
| karcher_global | 1.055-701.0 | 1 | 0 | 0 | 0 | unsafe_search_route |
| dreame | HHR12A | 1 | 0 | 0 | 0 | unsafe_search_route |
| hyperx | 4P5D4AA | 5 | 1 | 19 | 3 | exact_model_found |

### lg_kz

- Route: `GET https://www.lg.com/kz/search`; query key `q`; constants `[]`; origin `configured_endpoint` from https://www.lg.com/kz; rejection `none`.
- Query `27ART10AKPL`: exact_seller_manufacturer_model_code; outcome `search_results_found`; final URL `https://www.lg.com/kz/search?q=27ART10AKPL`.
- Candidate https://www.lg.com/kz/support/product-support/appliances-cleaning: score 60; reasons canonical_first_party_host:+15, product_like_path:+25, structured_product_result_card:+20; identity `insufficient`; rejection `results_identity_insufficient`.
- Candidate https://www.lg.com/kz/support/product-support/manuals-software: score 60; reasons canonical_first_party_host:+15, product_like_path:+25, structured_product_result_card:+20; identity `insufficient`; rejection `results_identity_insufficient`.
- Candidate https://www.lg.com/kz/support/product-support/product-registration: score 60; reasons canonical_first_party_host:+15, product_like_path:+25, structured_product_result_card:+20; identity `insufficient`; rejection `results_identity_insufficient`.
- Candidate https://www.lg.com/kz/support/product-support/repair-request: score 60; reasons canonical_first_party_host:+15, product_like_path:+25, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://www.lg.com/kz/support/product-support/troubleshoot: score 60; reasons canonical_first_party_host:+15, product_like_path:+25, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://www.lg.com/kz/my-lg: score 35; reasons canonical_first_party_host:+15, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://www.lg.com/kz/support/contact-us: score 35; reasons canonical_first_party_host:+15, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://www.lg.com/kz/support/contact-us/web-survey: score 35; reasons canonical_first_party_host:+15, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Resume: `{"checkpoint_unchanged": true, "new_http_requests": 0, "stop_reason": "checkpoint_complete"}`.

### bosch_home

- No declared search route found.
- Query `SBV45FX01R`: exact_seller_manufacturer_model_code; outcome `not_executed`; final URL ``.
- Resume: `{"checkpoint_unchanged": true, "new_http_requests": 0, "stop_reason": "checkpoint_complete"}`.

### apple_kz

- No declared search route found.
- Query `MGEX4FE/A`: exact_seller_manufacturer_model_code; outcome `not_executed`; final URL ``.
- Resume: `{"checkpoint_unchanged": true, "new_http_requests": 0, "stop_reason": "checkpoint_complete"}`.

### karcher_global

- Route: `GET https://www.kaercher.com/gb/en/dealer-search-main`; query key ``; constants `[]`; origin `first_party_search_link` from https://www.kaercher.com/gb/en; rejection `query_parameter_not_declared`.
- Query `1.055-701.0`: exact_seller_manufacturer_model_code; outcome `not_executed`; final URL ``.
- Query `1.055701.0`: remove_spaces_and_hyphens_preserve_revision_and_index; outcome `not_executed`; final URL ``.
- Resume: `{"checkpoint_unchanged": true, "new_http_requests": 0, "stop_reason": "checkpoint_complete"}`.

### dreame

- Route: `GET https://global.dreametech.com/search`; query key ``; constants `[]`; origin `first_party_search_link` from https://global.dreametech.com/collections/all; rejection `query_parameter_not_declared`.
- Query `HHR12A`: exact_seller_manufacturer_model_code; outcome `not_executed`; final URL ``.
- Resume: `{"checkpoint_unchanged": true, "new_http_requests": 0, "stop_reason": "checkpoint_complete"}`.

### hyperx

- Route: `GET https://hyperx.com/search`; query key `q`; constants `[["options[prefix]", "last"], ["type", "product"]]`; origin `html_search_form` from https://hyperx.com/pages/support; rejection `none`.
- Route: `GET https://hyperx.com/search`; query key `q`; constants `[["options[prefix]", "last"]]`; origin `html_search_form` from https://hyperx.com/pages/support; rejection `none`.
- Query `4P5D4AA`: exact_seller_manufacturer_model_code; outcome `search_results_found`; final URL `https://hyperx.com/search?options%5Bprefix%5D=last&q=4P5D4AA&type=product`.
- Candidate https://hyperx.com/products/hyperx-cloud-alpha-wireless: score 60; reasons canonical_first_party_host:+15, product_like_path:+25, source_family_in_url:+8, structured_product_result_card:+20; identity `exact_model`; rejection `none`.
- Candidate https://hyperx.com/: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `insufficient`; rejection `results_identity_insufficient`.
- Candidate https://hyperx.com/blogs/hyperx-blog: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `insufficient`; rejection `results_identity_insufficient`.
- Candidate https://hyperx.com/blogs/press: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, content_page:-35, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/about-hyperx: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/data-sharing-opt-out: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/delivery-information: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/hp-hyperx-visual-content-terms-of-use: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/hx3d: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/limited-warranty-statement: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/ngenuity: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/omen-gaming-pcs-laptops-overview: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/price-guarantee: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/promo-tcs: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/returns-policy: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/reviews: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/social-impact: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://hyperx.com/pages/support: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Candidate https://supportcenter.hyperx.com/: score 35; reasons canonical_first_party_host:+15, source_family_in_url:+8, structured_product_result_card:+20; identity `not_probed`; rejection `none`.
- Resume: `{"checkpoint_unchanged": true, "new_http_requests": 0, "stop_reason": "checkpoint_complete"}`.

Live protection summary: no 403, 429 or confirmed challenge occurred. No explicit JavaScript-required response was classified. Missing/undeclared routes do not prove that a site requires JavaScript. Unsafe route evidence is recorded for K?rcher and Dreame; no POST, token, browser or external search was attempted.

## Sitemap versus internal search

| Source | Stage 4 sitemap outcome / requests / candidates | Stage 5 internal search outcome / requests / candidates |
| --- | --- | --- |
| lg_kz | not sampled / 0 / 0 | results_identity_insufficient / 8 / 8 |
| bosch_home | sitemap_document_budget_exhausted / 9 / 20 | search_route_not_found / 1 / 0 |
| apple_kz | insufficient / 2 / 0 | search_route_not_found / 1 / 0 |
| karcher_global | insufficient / 6 / 0 | unsafe_search_route / 1 / 0 |
| dreame | url_budget_exhausted / 8 / 20 | unsafe_search_route / 1 / 0 |
| hyperx | url_budget_exhausted / 7 / 20 | exact_model_found / 5 / 19 |

Stage 4 values are historical, not new network probes. Samples use the same catalog selection rule; LG was not sampled in Stage 4.

## Regression and preservation

Protected registry/configuration, LG/Sulpak adapters and Stage 2–4 report hashes unchanged: **True**. Full before/after SHA-256 evidence is in dry_run.json. No census labels or queues are rewritten: 186 unresolved_requires_human_review labels, Accesstyle official_source_not_found, next census batch, LG/Sulpak restrictions and Mechta exclusion remain preserved. This is not completion of the all-brand census.

Offline regression: **140 tests passed, exit code 0** (97 pre-existing and 43 Stage 5 tests); actual output is in tests.txt. Final-code replay of all six saved checkpoints was also verified with a probe that raises on any attempted network call; see final_verification.json. Fixtures cover unsafe forms, query normalization, dedup/tracking, ranking-only evidence, structured identities, significant variant fields, protection stops, redirect budgets, checkpoints and unchanged registry hashes. Live network is not part of unittest discovery.

## One next strategy recommendation

Evaluate bounded browser-assisted first-party internal-search discovery for sites whose declared HTML routes are absent or require JavaScript. Retain the same allowlists, query/probe caps, identity gate and immediate protection stop; this recommendation does not authorize bypassing a challenge. Do not implement it in Stage 5.
