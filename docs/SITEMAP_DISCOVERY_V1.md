# Sitemap/catalog-feed discovery core v1

Stage 4 implements a bounded discovery strategy, not a product adapter.

## Public contracts

- `DiscoveryBudget` defines per-source request, sitemap document/depth, URL, candidate, product-page, interval, response-size, gzip-expansion, and deadline limits.
- `CandidatePage` stores explainable ranking separately from structured identity verification.
- `StrategyResult` stores budget usage, documents, redirects, errors, truncation, stop reason, timestamps, and a resumable checkpoint.
- `discovery_readiness` evaluates independent readiness flags and always returns `production_ready=false`.

## Traversal

The strategy checks first-party `robots.txt` declarations, then configured or conventional sitemap locations. Sitemap-index children are ranked deterministically: product/catalog/shop/store and category hints first; image/news/blog/tag/article maps last. URL sets and first-party RSS/Atom catalog feeds are bounded before candidate ranking.

Requests reuse `AccessProbe`, including redirect allowlists and host-level stop after 403, 429, or a confirmed challenge. Requests-style streaming decompression remains bounded by `max_response_bytes`; `safe_gzip_decompress` provides an explicit output cap for raw gzip fixtures/future transports.

## Ranking and identity

URL model/manufacturer tokens, product-like paths, category hints, product sitemap provenance, source-family hints, and canonical hosts increase ranking. Content/support flows, assets, PDFs, account/cart/search paths, foreign hosts, and category-only URLs are rejected or demoted.

URL/title/breadcrumb/body matches are ranking evidence only. Exact identity comes from structured fields passed to `IdentityVerifier`. At most three candidate pages are validated per catalog product.

## Non-goals

No runtime registry mutation, production readiness, Samsung/AEM/Shopify/generic JSON-LD adapter, attribute/media/manual extraction, dealer fallback, browser automation, CAPTCHA solving, proxy rotation, or unbounded retry is present.
