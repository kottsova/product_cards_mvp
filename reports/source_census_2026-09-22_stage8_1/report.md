# Stage 8.1 — structural adapter architecture review (deepened, not widened)

Baseline (immutable, read-only): [`reports/source_census_2026-09-22_stage8/`](../source_census_2026-09-22_stage8/report.md) — 127 profiles, 0 complete adapter profiles, 0 confirmed shared adapters, 92 `product_page_not_found`, 10 `structure_partial`. Every Stage 2–8 file remains byte-identical after this stage: [`protected_hashes_check.json`](protected_hashes_check.json) recomputed sha256 for all 209 files listed in Stage 8's own `protected_hashes_after.json` — 209 unchanged, 0 missing, 0 mismatched.

This stage does not run a new census pass, does not search the priority catalog, does not implement a production adapter, and does not touch any dealer/registry file. It deepens analysis on the sources Stage 8 already reached: **xiaomi_global, bosch_home, dreame, hyperx** (primary), with **asus, delonghi, nintendo** used only as fixed single-page reference points, exactly as scoped. No other brand was added.

## Method and bounded supplemental fetches

Stage 8's own fixtures store sanitized structural *contracts* (JSON-LD paths, DOM-semantic markers, CMS fingerprint) but never raw HTML or link lists — by design, per the project's "no raw HTML persisted" rule. That means the existing fixtures could be *compared* but not *mined* for additional pages: getting a second or third product page per family required new, bounded HTTP requests, not deeper reads of old fixtures.

All new requests reused Stage 8's own safety primitives unchanged — `AccessProbe` / `ProbePolicy` (`product_tool/census/endpoint_probe.py`, 6s timeout, 700KB cap, 1.5s min interval) and `inspect_structure()` (`product_tool/census/structural_contracts_v8.py`). No new scraping code, no Chromium, no search engine, no invented catalog-model URLs — every new URL came from first-party navigation links discovered on an already-verified official page (homepage, a known category page, or a known support page), the same discovery method Stage 8 itself used.

- **13 new HTTP requests total**, across 4 hosts: `www.mi.com` (3), `hyperx.com` (5), `www.bosch-home.com` (3), `de.dreametech.com` (2).
- All 13 returned HTTP 200. **0 requests were paused or stopped** — no 403/429/confirmed-challenge was hit on any host. Several `hyperx.com`/`de.dreametech.com` responses carried a `challenge_suspected` protection signal (some Cloudflare-style marker) but resolved as ordinary 200 pages with parseable content; per the same threshold Stage 8 itself uses, only `challenge_confirmed`/`captcha_detected`/403/429 stop a host — `challenge_suspected` does not. This is logged in [`supplemental_fetch_attempts.json`](supplemental_fetch_attempts.json) as an observation, not treated as a block.
- 9 new sanitized fixtures were written to [`fixtures/`](fixtures) in the same schema Stage 8 uses (`fixture_version: 2`, no raw HTML, no links). Full attempt log: [`supplemental_fetch_attempts.json`](supplemental_fetch_attempts.json); full parsed results: [`supplemental_fetch_results.json`](supplemental_fetch_results.json). Scripts used, for reproducibility: [`scripts/`](scripts).
- Dreame's `dreame_us` profile stayed `http_blocked` from Stage 8 and was not retried (no re-contact of a paused host).

This gave each primary family 2–3 verified product pages, deliberately spanning different product lines, instead of Stage 8's single sample:

| Family | Verified pages | Categories | Source |
|---|---:|---|---|
| xiaomi_global | 3 | phone (Leica co-brand), phone (flagship), watch | 1 Stage 8 + 2 new |
| bosch_home | 3 | kettle (DE), kitchen machine (DE), air fryer (UK) | 2 Stage 8 (1 snapshot) + 1 new |
| dreame | 4 (2 usable pairs) | robot vacuum ×2 (DE storefront) + 2 pages on the global storefront that failed the product-page test | 2 Stage 8 (1 snapshot) + 1 new + 2 Stage 8 (global storefront) |
| hyperx | 3 | keyboard+mouse bundle, USB microphone, gaming headset | 1 Stage 8 + 2 new |
| asus (reference) | 1 | laptop | Stage 8 only, not extended |
| delonghi (reference) | 1 | espresso machine | Stage 8 only, not extended |
| nintendo (reference) | 1 | game bundle | Stage 8 only, not extended |

## Per-family findings

**xiaomi_global** — Discovery: homepage-driven, single entry point, not independently re-verified (only 1 homepage sample). Identity: **confirmed absent** across all 3 pages — JSON-LD `Product` objects carry only `.name`, no `sku`/`mpn`/`gtin*` field on any sampled page (`model_semantics: marketing_name_only`). This is a stable finding, not a sampling gap: mi.com genuinely does not expose a manufacturer code through static JSON-LD. Specifications: **confirmed absent** the same way, 3/3 pages — no `additionalProperty`, no table/dl/details markup. Media: stable JSON-LD `.image` + DOM `responsive_srcset` + `itemprop=image` gallery marker on all 3 pages. Documents: never observed.

**bosch_home** — Discovery: Next.js/AEM-style path-prefix locale routing (`/de/de/...`), source-specific. Identity: **strong and stable** — `.gtin` + `.mpn` + `.name` (`model_semantics: explicit_manufacturer_or_model`) confirmed identical across 2 independent DE product categories (kettle, kitchen machine) and matching the UK page's identity signature exactly. This is the only family in this review with an unambiguous manufacturer-code identity contract. Specifications: `.additionalProperty[].name/.value/.unitText` (schema.org `PropertyValue`) confirmed identical on both new/old DE pages; the UK page's specs layer stayed unconfirmed, but only because that sample is a Stage 7 *sanitized* snapshot that structurally omits body content — not evidence the UK page lacks specs. Media: `.image` + `responsive_srcset`, stable on both DE pages. Documents: never observed on any Bosch sample.

**dreame** — This family shows a real **intra-brand inconsistency** worth flagging on its own: the DE storefront (`de.dreametech.com`) reliably exposes a single clean JSON-LD `Product` object per page (identity `.gtin13`/`.name`/`.sku`, confirmed on 2 independent pages, 1 snapshot + 1 fresh live fetch), while the global storefront (`global.dreametech.com`) did **not** — both freshly-fetched product pages there failed the single-clean-`Product`-object test (`is_product_page: false`), most likely because that theme also emits `Product`-typed JSON-LD for related/recommended items on the same page. Specifications: **confirmed absent** on the live-verified DE page (no `additionalProperty`, no DOM fallback) — this closes a real evidence gap, since all 3 previous DE samples were sanitized snapshots that couldn't rule out "just not captured." Media: JSON-LD `.image` present, but **no `responsive_srcset`** on the live page — Dreame does not currently match the srcset pattern seen on bosch_home/hyperx/xiaomi_global. Documents: exactly one sample (the `a2` snapshot) shows a PDF link, but the extractor itself already flags model-linkage and document language as unverified, and it is a single sample — not enough for even a source-specific contract.

**hyperx** — Discovery: Shopify collections + a working bounded internal HTML search form (`GET:q:html_search_form`) detected on the support page. Identity: `.gtin12`/`.productID`/`.sku` (`unverified_sku_meaning`) confirmed byte-for-byte stable across all 3 product categories — a solid intra-family contract, though sku meaning is explicitly unverified against a manufacturer part number. Specifications: `.additionalProperty[].name/.value` (no `unitText`) plus a DOM `accordion`/`dl` fallback, confirmed stable on all 3 pages — the field shape matches bosch_home's minus `unitText`. Media: `.image[...]` + `responsive_srcset`, stable on all 3 pages. Documents: support page reachable, but no PDF link found on any of the 3 sampled product pages.

**Reference families (asus, delonghi, nintendo)** — kept to their single Stage 8 fixture each, as scoped. All three show the same *shape* of pattern seen in the primary families (asus/nintendo: sku-only identity, matching hyperx/dreame's `unverified_sku_meaning`; delonghi: name-only identity, matching xiaomi_global's `marketing_name_only`; all three: JSON-LD `.image` + `responsive_srcset` media) but a single page cannot confirm stability, so every cell for these three stays `insufficient_evidence` in the matrix below — they corroborate a pattern without qualifying it. One incidental finding: Nintendo's product-page fixture shows `.name`/`.sku` extracted from a JSON-LD `Product` object, yet its own `cms_fingerprint` list only reports `next_js`, not `generic_json_ld_product` — a CMS-fingerprint under-detection, not a fact about Nintendo's page structure. Worth fixing in the fingerprinter eventually, not urgent.

## Compatibility matrix

Full machine-readable version: [`compatibility_matrix.json`](compatibility_matrix.json). Status vocabulary: `compatible_primitive` (a low-level reader confirmed on ≥2 independent families, ≥2 verified pages each, matching field-level contract) / `source_specific` (real, stable, but confirmed on only one family or with family-specific meaning) / `insufficient_evidence` (not enough samples, or confirmed-empty) / `blocked_manual_review`.

| Family | Discovery | Identity | Specifications | Media | Documents |
|---|---|---|---|---|---|
| xiaomi_global | source_specific | insufficient_evidence (confirmed absent) | insufficient_evidence (confirmed absent) | **compatible_primitive** | insufficient_evidence |
| bosch_home | source_specific | source_specific (strong) | **compatible_primitive** | **compatible_primitive** | insufficient_evidence |
| dreame | source_specific (unstable across storefronts) | source_specific (DE only) | insufficient_evidence (confirmed absent) | source_specific (no srcset) | insufficient_evidence |
| hyperx | source_specific | source_specific | **compatible_primitive** | **compatible_primitive** | insufficient_evidence |
| asus (ref.) | insufficient_evidence | insufficient_evidence | insufficient_evidence | insufficient_evidence | insufficient_evidence |
| delonghi (ref.) | insufficient_evidence | insufficient_evidence | insufficient_evidence | insufficient_evidence | insufficient_evidence |
| nintendo (ref.) | insufficient_evidence | insufficient_evidence | insufficient_evidence | insufficient_evidence | insufficient_evidence |

CMS fingerprint was **not** used to decide any cell above (bosch_home is Next.js/AEM-style, hyperx is Shopify — completely different platforms — yet they share the specifications and media contract shape; xiaomi_global and dreame both surface `generic_json_ld_product` yet share almost nothing at the data-contract level). This matches the existing project rule (`cluster_profiles(): CMS_used_for_grouping: False`) and is independently re-confirmed by this stage's own evidence, not assumed.

## Primitives

Full detail with evidence and constraints: [`primitives.v1.json`](primitives.v1.json).

**shared_primitive_candidate** (low-level readers only — never identity/variant meaning):
1. `json_ld_product_field_extractor` — already implemented (`discovery.py:json_ld_products()`), already used everywhere; re-confirmed here as brand-agnostic raw parsing, explicitly *not* a semantics decision.
2. `additionalProperty_specification_reader` — new candidate. Confirmed on bosch_home (2 pages) and hyperx (3 pages): `.additionalProperty[].name/.value`, `.unitText` optional. Confirmed *not* to fire on xiaomi_global or dreame (both genuinely empty) — the reader must report "no specs found" there, not guess.
3. `responsive_srcset_media_picker` — new candidate. Confirmed on bosch_home (2 pages) and hyperx (3 pages). xiaomi_global (3/3 pages) corroborates but wasn't needed to clear the 2-family bar. Confirmed *not* to fire on dreame's live-verified page (no srcset present).
4. `sitemap_loc_parser` — already implemented (`discovery.py:parse_sitemap()`), protocol-level, brand-agnostic; still valid, not itself sufficient to reach a verified product page.

**custom_adapter_candidate** (stays per-family, explicitly not poolable):
- `identity_semantics_resolver` — model_semantics genuinely differs per family (bosch_home: explicit manufacturer code; hyperx/dreame/asus/nintendo: unverified sku; xiaomi_global/delonghi: marketing name only). Re-confirmed with fresh multi-page evidence, not just Stage 8's single samples.
- `discovery_navigation_router` — underlying markup/routing genuinely differs (Next.js/AEM path-prefix vs two different Shopify storefronts vs a custom xiaomi homepage); the shared category/navigation *labels* in the contract schema are the classifier's own fixed vocabulary, not evidence of shared code.
- `dom_accordion_dl_specification_fallback` — confirmed only on hyperx (3/3 pages); bosch_home's sampled pages never used this DOM pattern. One family is not enough to pool.

**insufficient_evidence**: xiaomi_global identity & specifications (confirmed-absent, not unsampled); dreame specifications (confirmed-absent on live evidence) and identity on the global storefront specifically; **documents across all 7 families** — only one sample anywhere (dreame's `a2` snapshot) shows any document evidence, and even that is flagged unverified by the extractor itself; asus/delonghi/nintendo's un-extended layers, per scope.

**blocked_manual_review**: `dreame_us` (`http_blocked`, carried over from Stage 8, not retried).

## Stage 8.2 queue (formed, not executed)

Grouping of the 92 Stage 8 `product_page_not_found` profiles by the most reproducible next method, built from Stage 8's own baseline data (discovery routes already detected, CMS fingerprint, source role, regional profile count). Full detail: [`stage8_2_queue.json`](stage8_2_queue.json). **No network request was made against any of these 92 profiles in Stage 8.1.**

| Method group | Profiles | Families | Basis |
|---|---:|---:|---|
| official_category | 30 | 30 | Homepage reachable (all 92 are `direct_access`), but no category/product link resolved in Stage 8's bounded sample. Needs a dedicated category-first crawl. |
| internal_http_search | 20 | 17 | A bounded HTML search form/link was already detected on the sampled page (e.g. `samsung_kz`, `lg_kr`, `karcher_global`) — Stage 5.1's bounded internal search can query it directly. |
| support_first | 17 | 16 | Source role/domain is support-oriented (e.g. `microsoft`, several `*_support_*` profiles), or a support-page sample already yielded structure/document evidence — extend from the confirmed support endpoint. |
| sitemap_or_catalog_feed | 15 | 14 | A structured commerce platform was fingerprinted (Shopify/WooCommerce/Magento/Salesforce Commerce Cloud/AEM) — these expose standard sitemap/catalog-feed routes not yet walked to a product URL. Includes `dreame`/`dreame_global` themselves, consistent with this stage's own finding that the global storefront's JSON-LD is unreliable and a sitemap-first approach may be more robust there than homepage navigation. |
| regional_official_domain | 10 | 8 | Family already has more than one known official/regional profile (e.g. `apple`, `lg`, `karcher`) — an untried market mirror may succeed where this one did not. |

Every group's `reason` field in the JSON is per-profile, not just per-group, so a future stage can act on it directly without re-deriving the rationale.

## Answers to the stage's five questions

1. **Which small components actually work across multiple independent sites?** Two, both at the specification/media reading layer, not at identity or discovery: an `additionalProperty` (schema.org PropertyValue) specification reader, confirmed on bosch_home + hyperx; a responsive-srcset media picker, confirmed on the same two families. Both already-implemented protocol-level primitives (JSON-LD raw parsing, sitemap `<loc>` parsing) remain valid and brand-agnostic, as before.
2. **Which sources need their own adapter?** All four primary families need a fully custom identity resolver — the meaning of the available code field is genuinely different per family (manufacturer code vs unverified sku vs no code at all), confirmed with fresh multi-page evidence, not assumed from Stage 8's single samples. Discovery/navigation also stays fully custom per family. Dreame additionally needs *per-storefront* handling (DE vs global), not one Dreame adapter.
3. **What still can't be concluded from evidence?** The documents layer, everywhere — only one sample across all 7 reviewed families shows any PDF/document evidence at all, and it's explicitly flagged unverified. Xiaomi's and Dreame's specifications are now confirmed-absent (not just unsampled), which is itself a conclusion, but means no specification adapter is possible there without a different capture method (e.g. embedded client-side state, out of this stage's scope). Asus/delonghi/nintendo stay single-sample reference points by design and can't support any stability claim yet.
4. **How should the 92 `product_page_not_found` profiles be closed?** Not by one uniform method — see the Stage 8.2 queue above: 20 already show a usable internal search form, 17 are support-oriented and should start from the support endpoint, 15 sit on a structured commerce platform with an unwalked sitemap/catalog feed, 10 have an untried regional mirror, and the remaining 30 need a plain category-first crawl beyond the homepage.
5. **Is the architecture ready for a full priority-brand cycle?** Not yet, and not uniformly. Identity resolution has zero shortcuts — every family needs its own verified contract, exactly as the existing architecture already assumes. Specifications and media now have two genuinely evidenced shared low-level readers usable as shared utility functions (not adapters) for any future bosch_home/hyperx-style JSON-LD family. Documents remain essentially unevidenced across the board. Before any extraction work starts, several of the highest-coverage priority brands (samsung, apple, lg, jbl, playstation, razer, hiper, microsoft) still have **no confirmed Product page fixture at all** — that gap should close before adapter work, not in parallel with it.

## Recommendation

Run Stage 8.2 next, scoped narrowly to the `internal_http_search` and `sitemap_or_catalog_feed` queue groups for the priority brands that currently have zero confirmed Product page fixtures (samsung, apple, lg, jbl, playstation, razer, hiper, microsoft) — these two methods are the most reproducible and least speculative of the five groups, and closing this specific gap is what blocks any of those priority brands from reaching even a `structure_partial` profile, let alone adapter work. This is a recommendation only; Stage 8.2 is not started here.

## Tests

New regression tests: [`tests/test_structural_census_v8_1.py`](../../tests/test_structural_census_v8_1.py). Run: `.venv/Scripts/python.exe -m pytest tests/test_structural_census_v8_1.py -v` (or `unittest`). Results: [`tests.txt`](tests.txt).
