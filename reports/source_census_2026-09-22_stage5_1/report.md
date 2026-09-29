# Stage 5.1 — internal-search result quality hardening

Generated: 2026-09-22T14:44:18.250896+00:00

Stage 5 remains an immutable historical baseline. No new discovery strategy or production orchestrator was implemented. Work is limited to result quality, semantic checkpoint compatibility, snapshot reprocessing and two explicitly authorized product rechecks.

## Causes and fixes

- The old card-marker regex matched search-results/search-result-container and inherited that marker across the entire results region. Ordinary navigation therefore received structured_product_result_card:+20. The parser now records the nearest local Product container and respects navigation/layout boundaries. Generic wrappers have no card weight.
- The old shared product-path signal accepted product- substrings, including product-support. Stage 5.1 uses complete product/products/p/mkt-product segments; service paths are excluded unless exact model evidence justifies an explicit exception.
- First-party host, brand-in-host and category hints are not admission criteria. A link must have model evidence, a real product path, a local product card, a Product ItemList element or a declared source path prefix.
- ItemList entries are no longer all classified as Product. A Product node or unambiguous product URL is required. Generic navigation retains generic_first_party_anchor provenance and gets no structured bonus.
- Evidence now distinguishes html_product_card, json_ld_itemlist_product, exact_model_in_result_title, exact_model_in_result_url, configured_product_pattern and generic_first_party_anchor. These are ranking evidence only.
- Two HyperX links were query echoes leading back to search. Search routes are now excluded even when their query contains the target model. This refinement bumped result parser and ranking versions to 3; final validation reprocessed stored responses without new HTTP.

## Checkpoint compatibility

| Component | Version |
| --- | --- |
| checkpoint_schema_version | 2 |
| strategy_version | 5.1 |
| route_detector_version | 2 |
| result_parser_version | 3 |
| ranking_version | 3 |

These versions are included in compatibility_key together with the identity/source key, category hints and declarative product path configuration. An unversioned Stage 5 checkpoint returns checkpoint_incompatible, never checkpoint_complete. Matching-version complete checkpoints alone establish zero-request resume. Missing content cannot silently trigger network access.

## Snapshot inventory and processing

The two pre-existing SQLite databases had no source_snapshots table, and Stage 5 checkpoints had no snapshot references. Initial reprocessing therefore returned snapshot_missing for both products. One explicit bounded refresh was authorized and performed for each product: LG 27ART10AKPL and HyperX 4P5D4AA. No other sources were requested.

Four successful response snapshots now use the existing FetchAttempt/SourceSnapshot schema in the isolated source_snapshots.sqlite3 database. Snapshot content is a sanitized HTML discovery/identity projection; scripts, private URL parameters and secret-bearing form/meta values are excluded. Checkpoints store IDs/store references and verified content hashes, never HTML. Final snapshots use sanitizer version 2. All subsequent parser/ranking reprocessing, including the final parser version, was offline.

A local product-row uniqueness error initially prevented HyperX setup before its first HTTP request; it was corrected and that same refresh proceeded. LG was replayed from its saved snapshot, not requested again.

Per-refresh bounds: 3 queries, 20 candidates, 3 product probes, 10 HTTP requests including redirects; minimum interval 1 second; deadline 50 seconds. Final replay request counts are separate from historical refresh counts.

## Before / after

| Product | Stage 5 candidates | Final candidates | Removed baseline URLs | Navigation/service exclusions in current response | Refresh HTTP | Final reprocessing HTTP | Final outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| lg_kz 27ART10AKPL | 8 | 0 | 8 | 21 | 2 | 0 | search_no_results |
| hyperx 4P5D4AA | 19 | 1 | 18 | 41 | 3 | 0 | exact_model_found |

Exclusion counts are unique normalized service/navigation URLs per processed search response; they differ from removed baseline candidate counts because most links never appeared in the old top-candidate list. Search-route echoes and other rejection categories are recorded separately in result_audits. Final HyperX processing excludes two search-route echoes.

Total actual refresh HTTP requests: **5**. Final snapshot reprocessing and compatible resume issue **0** HTTP requests. No 403/429/challenge was observed in this recheck.

### lg_kz — evidence

- Route: `GET https://www.lg.com/kz/search`; query key `q`; source `configured_endpoint`; rejection `none`.
- Query `27ART10AKPL`: exact_seller_manufacturer_model_code; outcome `search_no_results`.
- No admitted product candidates; no exact match is claimed or required.
- Old checkpoint: `checkpoint_incompatible`. Compatible resume: `checkpoint_complete`, new requests 0. Independent snapshot rebuild: `search_no_results`; candidates/ranks/identity equal: True.

Removed Stage 5 candidate URLs:

- https://www.lg.com/kz/my-lg
- https://www.lg.com/kz/support/contact-us
- https://www.lg.com/kz/support/contact-us/web-survey
- https://www.lg.com/kz/support/product-support/appliances-cleaning
- https://www.lg.com/kz/support/product-support/manuals-software
- https://www.lg.com/kz/support/product-support/product-registration
- https://www.lg.com/kz/support/product-support/repair-request
- https://www.lg.com/kz/support/product-support/troubleshoot

### hyperx — evidence

- Route: `GET https://hyperx.com/search`; query key `q`; source `html_search_form`; rejection `none`.
- Route: `GET https://hyperx.com/search`; query key `q`; source `html_search_form`; rejection `none`.
- Query `4P5D4AA`: exact_seller_manufacturer_model_code; outcome `search_results_found`.
- Candidate: https://hyperx.com/products/hyperx-cloud-alpha-wireless; score 60; reasons: canonical_first_party_host:+15, product_like_path:+25, html_product_card:+20.
- Target-page identity: `exact_model`.
- Structured model evidence: `4P5D4AA`, state `match`, extraction `json_ld_product`. This value came from the target-page snapshot, not search title/URL/card evidence.
- Old checkpoint: `checkpoint_incompatible`. Compatible resume: `checkpoint_complete`, new requests 0. Independent snapshot rebuild: `exact_model_found`; candidates/ranks/identity equal: True.

Removed Stage 5 candidate URLs:

- https://hyperx.com/
- https://hyperx.com/blogs/hyperx-blog
- https://hyperx.com/blogs/press
- https://hyperx.com/pages/about-hyperx
- https://hyperx.com/pages/data-sharing-opt-out
- https://hyperx.com/pages/delivery-information
- https://hyperx.com/pages/hp-hyperx-visual-content-terms-of-use
- https://hyperx.com/pages/hx3d
- https://hyperx.com/pages/limited-warranty-statement
- https://hyperx.com/pages/ngenuity
- https://hyperx.com/pages/omen-gaming-pcs-laptops-overview
- https://hyperx.com/pages/price-guarantee
- https://hyperx.com/pages/promo-tcs
- https://hyperx.com/pages/returns-policy
- https://hyperx.com/pages/reviews
- https://hyperx.com/pages/social-impact
- https://hyperx.com/pages/support
- https://supportcenter.hyperx.com/

## Regression and preservation

Full regression suite: **164 tests passed**, exit code 0. Unit tests use local fixtures; live network is not part of regression discovery.

Tests cover generic wrappers, nearest-card attribution, service paths, ItemList navigation, model-only ranking, HyperX structured identity, every semantic version mismatch, compatible zero-request resume, missing/tampered snapshots, offline rebuilding, privacy filtering, production_ready=false, multi-product snapshot storage and unchanged protected files.

Protected hashes identical: **True**. Full SHA-256 manifests: protected_hashes_before.json and protected_hashes_after.json. They cover production configurations, Stage 2–5 reports, LG/Sulpak adapter files, source policy and pre-existing SQLite files. Registry examples:

| File | Before SHA-256 | After SHA-256 |
| --- | --- | --- |
| product_tool\config\brand_normalization.v1.json | 492140a0acff4a4c023d2e5f227f37015f76d5d20fd8ed992904f01815ef61ee | 492140a0acff4a4c023d2e5f227f37015f76d5d20fd8ed992904f01815ef61ee |
| product_tool\config\source_candidates.v1.json | ff69f1d583bea396f9e0214cf65a4fdcef255b3e1c80112eac6c27731842338e | ff69f1d583bea396f9e0214cf65a4fdcef255b3e1c80112eac6c27731842338e |
| product_tool\config\source_catalog.v2.json | c4bb7076b6febdd47026a766e89f95eaa4ffb0b74dc9c83c129063b043c487f3 | c4bb7076b6febdd47026a766e89f95eaa4ffb0b74dc9c83c129063b043c487f3 |
| product_tool\config\source_research.v1.json | acfa38933946a6d429cc55eb554a319bb8e1974a18099c54ddc11d90ca863d11 | acfa38933946a6d429cc55eb554a319bb8e1974a18099c54ddc11d90ca863d11 |

The 186 unresolved labels, Accesstyle negative result, next census batch, LG/Sulpak restrictions and Mechta exclusion remain unchanged. No pre-existing snapshots or uncommitted user changes were removed. Every readiness result remains production_ready=false; this is not completion of the all-brand census.

## One next strategy recommendation

Evaluate bounded browser-assisted first-party internal search for sources such as LG where the static search response does not expose a valid product result. Retain the same budgets, host allowlists, target-page identity gate and immediate protection stop. This strategy is recommended only and was not implemented in Stage 5.1.
