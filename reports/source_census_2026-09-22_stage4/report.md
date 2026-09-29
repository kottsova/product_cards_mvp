# Source census — Stage 4 bounded sitemap/catalog-feed discovery core v1

The stage implements a CMS-neutral bounded discovery strategy only. Samsung, AEM, Shopify, generic JSON-LD production adapters, attribute/media/manual extraction, dealer fallback, browser automation, and protection bypass remain out of scope.

## Contracts and safety

- DiscoveryBudget caps HTTP requests, sitemap documents/depth, URLs read, candidates, product probes, request interval, response size, gzip expansion, and total deadline.
- CandidatePage separates URL ranking evidence from structured identity evidence.
- StrategyResult records budget usage, sitemap/feed documents, redirects, errors, truncation, stop reason, timestamps, and a resumable checkpoint.
- 403, 429, and confirmed challenges stop the host. No CAPTCHA solving, UA rotation, proxies, or unbounded retries are implemented.
- Strategy code cannot return production readiness. Stage 4 readiness always keeps production_ready=false.
- Live budget per source: 10 requests, 5 sitemap documents, depth 2, 400 URLs, 20 retained candidates, 3 product probes, 1.0s minimum interval, 50.0s deadline.

## Dry-run

| Source family | Product | Requests | Candidates | Stop reason | Product found | Exact model | Exact variant | Next route |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| bosch_home | SBV45FX01R | 9 | 20 | sitemap_document_budget_exhausted | True | False | False | other_strategy |
| apple_kz | MGEX4FE/A | 2 | 0 | insufficient | False | False | False | other_strategy |
| karcher_global | 1.055-701.0 | 6 | 0 | insufficient | False | False | False | other_strategy |
| dreame | HHR12A | 8 | 20 | url_budget_exhausted | True | False | False | other_strategy |
| hyperx | 4P5D4AA | 7 | 20 | url_budget_exhausted | True | False | False | other_strategy |

### Top candidates for `bosch_home:SBV45FX01R`

- https://www.bosch-home.com/ar/es/mkt-product/cafeteras/cafeteras-totalmente-integrables/CTL636ES6 — score 48.0; canonical_first_party_host:+15, product_like_path:+25, source_family_in_url:+8; identity=conflict; rejection=structured_identity_conflict.
- https://www.bosch-home.com/ar/es/mkt-product/cafeteras/cafeteras-totalmente-integrables/CTL7181B0 — score 48.0; canonical_first_party_host:+15, product_like_path:+25, source_family_in_url:+8; identity=conflict; rejection=structured_identity_conflict.
- https://www.bosch-home.com/ar/es/mkt-product/cocina/accesorios/DWZ0DX0U0 — score 48.0; canonical_first_party_host:+15, product_like_path:+25, source_family_in_url:+8; identity=conflict; rejection=structured_identity_conflict.

### Top candidates for `dreame:HHR12A`

- https://global.dreametech.com/es/products/a2 — score 68.0; canonical_first_party_host:+15, product_like_path:+25, product_catalog_sitemap:+20, source_family_in_url:+8; identity=insufficient; rejection=structured_identity_insufficient.
- https://global.dreametech.com/es/products/aero-straight-pro — score 68.0; canonical_first_party_host:+15, product_like_path:+25, product_catalog_sitemap:+20, source_family_in_url:+8; identity=insufficient; rejection=structured_identity_insufficient.
- https://global.dreametech.com/es/products/air-auto — score 68.0; canonical_first_party_host:+15, product_like_path:+25, product_catalog_sitemap:+20, source_family_in_url:+8; identity=insufficient; rejection=structured_identity_insufficient.

### Top candidates for `hyperx:4P5D4AA`

- https://hyperx.com/products/hx3d-headset-accessory-bear-ears — score 68.0; canonical_first_party_host:+15, product_like_path:+25, product_catalog_sitemap:+20, source_family_in_url:+8; identity=conflict; rejection=structured_identity_conflict.
- https://hyperx.com/products/hx3d-headset-accessory-dragon-wings — score 68.0; canonical_first_party_host:+15, product_like_path:+25, product_catalog_sitemap:+20, source_family_in_url:+8; identity=conflict; rejection=structured_identity_conflict.
- https://hyperx.com/products/hx3d-headset-accessory-horns — score 68.0; canonical_first_party_host:+15, product_like_path:+25, product_catalog_sitemap:+20, source_family_in_url:+8; identity=conflict; rejection=structured_identity_conflict.

## Totals and decisions

- HTTP requests: 32; candidates retained: 60.
- Stop reasons: {"insufficient": 2, "sitemap_document_budget_exhausted": 1, "url_budget_exhausted": 2}.
- Candidate access outcomes: {"direct_access": 9, "not_checked": 51}.
- Sitemap/feed errors recorded: 4; blocked/rate-limited dry-runs: 0.
- Strategy not applicable: 1; unavailable product candidates: 0.
- Production registries unchanged: True.
- Legacy identity sources retained for audit: 15; readiness impact: false.
- Remaining unresolved_requires_human_review labels preserved: 186.
- Unit/regression tests passed: 97.

A sitemap URL or a high URL ranking never proves product identity. Exact identity is derived only from structured fields through IdentityVerifier. A successful single-product dry-run does not establish source-family repeatability and never enables a source.

## Required follow-up routes

- Internal search: Bosch Home, Apple, Kärcher, Dreame, HyperX. Sitemap traversal did not locate an exact target identity inside the bounded sample.
- Embedded state: none promoted yet. Evaluate only after internal search reaches the correct first-party product page and JSON-LD remains insufficient.
- Browser/manual review: none from this pass; no CAPTCHA, 403, 429, or browser-only stop was observed.

## Next strategy recommendation

Implement bounded internal-search discovery next. It directly addresses families where official sitemaps are absent, HTML-only, blocked, or too broad while preserving exact model queries, the same host allowlists, budgets, checkpoints, and structured identity gate. Do not implement that strategy in Stage 4.
