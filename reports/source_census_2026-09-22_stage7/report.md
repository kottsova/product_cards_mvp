# Stage 7: multi-domain official-source fallback - 2026-09-22

Stage 7 is implemented as a bounded research coordinator using ordinary HTTP and snapshots. Browser-assisted discovery is permanently excluded from automatic orchestration. Chromium is a separate manual diagnostic tool only after a new explicit user request. No browser run or browser-strategy change was made in Stage 7.

## Pilot result

Eleven real catalog products: LG 2, Bosch Home 2, Samsung 3, Karcher 2, Dreame 2. Total new HTTP requests: **107** (105 initial + 2 supplementary). Chromium launches: **0**. The initial pilot asserts that no browser, Playwright or Selenium module was loaded. Regression browser tests use fakes; the real Chromium fixture was not run.

Exact official identities: **0**. Outcomes: {'official_exact_product_not_found': 6, 'official_search_incomplete': 5}. There are 45 distinct candidate URLs across 35 product/domain checks; structured target validations, including reuse of already captured pages for another expected identity: 18. Per-candidate identity states: {'conflict': 8, 'insufficient': 10, 'not_validated': 72}. Candidate text/URLs do not establish identity. Any displayed best candidate with insufficient identity is only the best review candidate, not an approved source for a card.

| Family | Catalog SKU | Final official outcome | Permitted dealer |
|---|---|---|---|
| lg | F2J3HS0W | `official_exact_product_not_found` | sulpak |
| lg | A9K-PRO1 | `official_exact_product_not_found` | sulpak |
| bosch_home | SBV45FX01R | `official_search_incomplete` | none |
| bosch_home | CMG633BB1 | `official_search_incomplete` | none |
| samsung | MNA114MS1CCX | `official_exact_product_not_found` | none |
| samsung | Jet_70_turbo/(VS15T7031R4/EV) | `official_search_incomplete` | none |
| karcher | 1.055-701.0 | `official_exact_product_not_found` | none |
| karcher | 1.633-426.0 | `official_exact_product_not_found` | none |
| dreame | HHR12A | `official_search_incomplete` | none |
| dreame | RLD35GD | `official_search_incomplete` | none |
| samsung | WD10T654CBH/LD | `official_exact_product_not_found` | none |

Products were selected from the catalog's highest-coverage eligible categories using a deterministic sample rule, not from manually found product pages. LG samples cover washing machines/vacuums; Bosch dishwashers/ovens; Samsung TVs/vacuums/washing machines; Karcher vacuums/window cleaners; Dreame vacuums/robot vacuums. Whether a product is absent from a primary market is reported only as absence of validated exact evidence within the budget, not a global inventory claim.

The composite Samsung seller code `Jet_70_turbo/(VS15T7031R4/EV)` exposed a partial query (`Jet_70_turbo/`) in the existing model normalization. Final policy 7.0.1 conservatively returns `official_search_incomplete` for an incomplete canonical query. Existing identity/normalization code was not changed. A third Samsung sample, `WD10T654CBH/LD`, supplies a clean full-code check in another mass category. Initial observations remain in `dry_run.json`; final policy results are in `final_results.json`. The first ten decisions were rebuilt offline from their domain observations; their earlier checkpoints are incompatible under the final version. The additional Samsung sample reused prior HTTP snapshots and made only two new requests.

## Domain registry and routing

`product_tool/config/official_domains.v1.json` defines 17 official domain/market records: LG KZ/global/US/Korea, Bosch Home global/Germany/UK, Bosch Professional separately, Samsung KZ/US/Korea, Karcher KZ/global/Germany, Dreame global/US/Germany. Different market paths on a shared hostname are separate source records but not independent network hosts. All are disabled for production; explicit research opt-in is required for pilot records. The Bosch Tools branch is not selected for Home appliances.

Each record has family/brand, market/locale, global/regional scope, division/categories, ownership evidence, page/support/document allowlists, sitemap/search/catalog capabilities, priority, enabled/research status and status/timestamp fields. `official_domain_registry.json` adds the actual endpoint-scoped observations and per-product discovery results without mutating the configuration.

Primary ownership evidence: [LG country selector](https://www.lg.com/common/index), [Bosch international selector](https://www.bosch-home.com/), [Samsung location selector](https://www.samsung.com/sec/function/ipredirection/ipredirectionLocalList/), [Karcher corporate page](https://www.kaercher.com/int/inside-kaercher/company/about-kaercher.html), [Dreame regional/store links](https://www.dreametech.com/pages/where-to-buy). These are ownership/market evidence, not product identity. Web research was restricted to domain ownership and dealer authorization; product candidates came from reproducible HTTP page/sitemap/search parsing. Web-tool research calls are separate from the application's 107-request pilot accounting.

Domain iteration: primary, other verified markets/global domains, then category/division-specific records. Selection: exact_variant anywhere, exact_model anywhere, matched structured-evidence completeness, global only as a tie-breaker, then regional/priority. Unknown/conflicting identity never gains exactness from market preference. Tests demonstrate regional exact beating global family-only and regional richer evidence beating an equally exact global result.

## Access scope and protection

The Stage 6.1 LG challenge is retained only as a `browser` observation for `https://www.lg.com/kz/search?q=27ART10AKPL`. It does not pause HTTP. In this pilot LG KZ safely answered ordinary GET searches for F2J3HS0W and A9K-PRO1 and participated in sitemap discovery. No universal LG-domain block was inferred.

Every observation stores exact host, endpoint, access method, discovery method, HTTP/protection status and timestamp. A newly observed HTTP 403/429/challenge pauses that exact hostname for HTTP during this run. Other hostnames/access methods do not inherit it. Shared-host regional paths obey the same temporary HTTP host stop. Cached snapshots can be read without new traffic. The supplemental run restored the earlier host pauses instead of retrying protected hosts.

Dreame US produced an HTTP protection stop; other Dreame hosts continued. Sulpak also produced a protection stop during the first allowed LG fallback. The second eligible LG fallback consumed cached evidence and made zero new requests to Sulpak. No bypass, proxies, stealth, browser fallback or manually injected product URLs were used.

## Budget and completeness

Per product: at most four eligible official records and 40 actual HTTP requests. Per record: at most ten requests including redirects, three sitemap documents, 800 sitemap URLs, two generated declared GET queries, three target validations and 40 seconds. Responses are bounded to 1 MB, requests to eight seconds and at least a one-second interval. Dealer research, only after the gate, has a separate six-request cap. Shared-response cache hits do not consume new network budget and are explicitly identified in receipts.

Only declared safe GET forms/configured endpoints, robots-declared or configured sitemaps, explicit catalog/support indexes, typed Product/ItemList public endpoints, and candidate links from those responses can be used. No arbitrary embedded application state is traversed. This pilot had no configured structured endpoints; those paths are a contract for already confirmed endpoints, not a claim that APIs were tested.

`official_exact_product_not_found` means every eligible confirmed record in the selected registry was considered within the recorded limits, with discovery evidence and no pending candidate validation. It is not exhaustive global absence. Skipped domains, unvalidated candidates or a partial canonical query produce `official_search_incomplete`; no accessible discovery evidence produces `official_search_unavailable`. The latter two outcomes do not permit dealers. Sitemaps/indexes can remain truncated under the declared bounded scope; details are retained per domain.

## Dealer policy and review queue

Only LG/Sulpak's existing exact appliance allowlist was executable: washing machines, dryers, refrigerators, vacuums and microwave ovens. LG split systems remain review_pending; TV, monitors, audio and computing are excluded. Mechta remains excluded even where an external manufacturer page lists it. Existing source registry/allowlist files are byte-for-byte unchanged.

Two LG cases pass the gate only after four official records each. Both Sulpak research results are protection-limited; no dealer identity or card data was accepted. See `allowed_dealer_fallbacks.json`.

`dealer_review_queue.json` is entirely disabled with `approval_status=review_pending`. Samsung/Sulpak has [manufacturer authorization evidence](https://www.samsung.com/kz_ru/buyoriginal/); Karcher's shop is linked by the [manufacturer's sales page](https://www.kaercher.com/kz/servis/podderzhka/tochki-prodazh.html), with legal ownership/source role still requiring review; Dreame's manufacturer-linked Amazon storefront needs exact seller/storefront scoping. Bosch has only a branded-store locator lead; a particular third-party web dealer remains unverified. Missing evidence is explicitly marked, not fabricated. Entries for incomplete official searches are conditional review leads, not current fallback authorizations. Proposed field coverage is unmeasured and no new dealer was used for a card.

## Field provenance and production boundary

The future card merge contract requires source, URL, fetched date, identity level, extraction method and confidence. Different variant keys are rejected. Existing ResolutionPolicy preserves confirmed manufacturer/support values; an approved dealer can fill an absent field, and a disagreement is logged for review while the official value is retained. No attributes/media/manual extraction or production card writes were performed.

The Stage 7 coordinator and registry are research components. Existing production routing/worker files and user modifications were not rewritten or deployed. This preserves the active registry while making the new policy concrete and testable; production adoption is a separate step.

## Artifacts and verification

- `domain_checks.md` / `.json`: every product/domain, method, new request count, candidates, identity, access/protection and rejection outcomes.
- `final_results.json`: final official result, best review candidate and dealer gate per product.
- `official_exact_product_not_found.json`: only cases passing the complete bounded official-search gate.
- `official_domain_registry.json`: research records plus scoped observed statuses.
- `http_cache.json`, `supplemental_cache.json`, `source_snapshots.sqlite3`, `snapshot_hashes.json`: captured responses and hash-verified immutable SourceSnapshot contents. Protection/error responses are metadata only; successful responses have sanitized content snapshots.
- `checkpoint.json`, initial/final result artifacts: no-network compatible resume and explicit version invalidation. Final policy replay used captured domain results; it is not represented as a new render or new HTTP check.
- `dealer_review_queue.json`, `allowed_dealer_fallbacks.json`: proposed disabled sources versus existing approved scope.

Full regression: **233 tests passed** (`tests.txt`). All **164 protected files** retain their SHA-256 values, including Stage 2-6.1 reports/snapshots, existing registries, catalog, browser strategy, and pre-existing user changes. Therefore the 186 unresolved labels, Accesstyle negative result, Sulpak restrictions, Mechta exclusion and HyperX evidence are preserved. 89 new successful-response snapshots were hash-verified. The complete before/after manifests are included.

## Next stage recommendation

Next: offline canonical model-code/variant reconciliation for composite seller SKUs, plus human review of the disabled dealer queue and already recorded catalog coverage gaps. Use the captured candidates/snapshots to prioritize declared HTTP catalog endpoints; establish exact identity before field extraction or production adoption. Do not resume browser hardening and do not enable any new dealer automatically. This next stage was not implemented.
