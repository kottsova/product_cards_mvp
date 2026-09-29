# Stage 8.2 — targeted Product page discovery for zero-fixture priority brands

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md), [Stage 8.1](../source_census_2026-09-22_stage8_1/report.md) — its [`stage8_2_queue.json`](../source_census_2026-09-22_stage8_1/stage8_2_queue.json), [`compatibility_matrix.json`](../source_census_2026-09-22_stage8_1/compatibility_matrix.json) and [`primitives.v1.json`](../source_census_2026-09-22_stage8_1/primitives.v1.json). All 209 Stage 2–8 protected files and all 26 Stage 8.1 files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json).

Scope, exactly as instructed: only `stage8_2_queue.json` entries in the **`internal_http_search`** and **`sitemap_or_catalog_feed`** groups were executed, for 8 target families with zero confirmed Product page fixtures (Samsung, Apple, LG, JBL, PlayStation, Razer, HIPER, Microsoft/Xbox). `official_category`, `support_first` and `regional_official_domain` entries were not run. HyperX was used only as an existing reference (its Stage 8.1 fixtures), never re-fetched.

## Which brands actually had a permitted route

Checking `stage8_2_queue.json` first (0 network requests) showed that only **3 of the 8** target brands have any entry in the two permitted groups at all:

| Brand | Groups present | In scope this stage? |
|---|---|---|
| Samsung | `sitemap_or_catalog_feed` (samsung_kr) + `internal_http_search` (samsung_kz, samsung_kz_02d9e6, samsung_us) | Yes |
| LG | `sitemap_or_catalog_feed` (lg_kz) + `internal_http_search` (lg_kr) | Yes |
| PlayStation | `sitemap_or_catalog_feed` (playstation_global_candidate) | Yes |
| Apple | `regional_official_domain` + `support_first` only | No |
| JBL | none — `http_blocked` from Stage 8 (jbl.com and support.jbl.com both paused) | No, and not retried per host-stop policy |
| Razer | `official_category` only | No |
| HIPER | `official_category` only | No |
| Microsoft | `support_first` only | No |

This is itself a real finding, not an oversight: five of the eight brands simply have no reproducible internal-search or sitemap route recorded yet, and this stage correctly performed **zero requests** against them, moving each to [`next_queue.json`](next_queue.json) with its already-known next method instead of improvising one.

## Catalog samples

For every one of the 8 brands, the two most massive categories were read from the catalog's own `Бренд_Категория` sheet and one representative product picked from each (16 rows total): [`catalog_samples.json`](catalog_samples.json). Microsoft's two sampled rows were checked by name and are genuinely Xbox products (`"Беспроводной геймпад XBOX Series Carbon Black"`, `"Игровая консоль Xbox One S 1ТБ + ..."`) — no generic Microsoft product was mistaken for Xbox. Only Samsung/LG/PlayStation's samples were actually searched for, per the scope above; the other 10 rows are recorded with an explicit `out_of_scope_reason` and were not searched.

## Budget and reuse

Before any new request, existing evidence was reused:

- **37 pre-existing HTTP snapshots** (Stage 5.1–7.1 sqlite stores, for all 6 in-scope Samsung/LG profiles) were reprocessed **offline** with the same `inspect_structure()` Stage 8 uses — zero network calls. This is what first revealed that Samsung's and LG's `internal_http_search` routes are non-viable (see below), *before* a single new request was made.
- Stage 8's own `structural_cache.json` was read for the already-fetched PS Direct collection page, giving PlayStation's category-page links for free (0 new requests).

New live requests: **16 total**, all HTTP 200, **0 confirmed blocks** (no 403/429/`challenge_confirmed` on any host):

| Host | Requests |
|---|---:|
| www.samsung.com | 8 |
| direct.playstation.com | 5 |
| www.lg.com | 3 |

Full attempt log: [`raw/run_state.json`](raw/run_state.json); reasons every skipped request wasn't made: [`checkpoint.json`](checkpoint.json). `www.samsung.com` reached its self-imposed 8-request cap for this pass; further Samsung sitemap descent (to reach the exact smartphone SKU) is deferred to `next_queue.json` rather than raising the cap mid-run.

**Key reuse finding — internal_http_search is not viable for Samsung or LG via static HTTP.** Offline reprocessing showed Samsung's `?search=<term>` responses (5 distinct queries, `kz_ru` and `us`) are byte-identical to the plain homepage, and LG's `search/?q=<term>` (`kz`) / `search?keyword=<term>` (`kr`) responses vary only by the length of the echoed query string itself, with identical extracted navigation links every time. Both are client-side-rendered SPA shells with no server-rendered per-query results. This was established entirely from existing snapshots — it eliminated `internal_http_search` as a route for 4 of the 6 in-scope profiles before any new request, and redirected all new-request budget to `sitemap_or_catalog_feed` instead.

## Per-brand results

### Samsung — **2 verified Product pages**, catalog SKU not reached

Route: `robots`-declared `sitemap.xml` → sitemap index `b2c-sitemap.xml` → category sub-sitemap (`vd-sitemap.xml` = visual display/TV, `im-sitemap.xml` = IT & mobile) → product URL. All sub-sitemaps were within their host's official domain, discovered only through `<loc>` entries already present in a fetched sitemap — no URL was invented.

- **TV**: `https://www.samsung.com/kz_ru/tvs/full-hd-tv/n5300-43-inch-full-hd-smart-tv-ue43n5300auxce/` — `product_page_fixture_result: verified` (JSON-LD Product confirmed, single object). `catalog_identity_result: insufficient` — the targeted catalog article (`QE100QN80FUX`, a 100″ set) was not present in the ~52-URL TV slice actually served by `vd-sitemap.xml`; a different, real Samsung TV was reached instead.
- **Galaxy Buds3 FE**: `https://www.samsung.com/kz_ru/audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/` — `verified`. `catalog_identity_result: insufficient` — `im-sitemap.xml`'s 300 `<loc>` entries covered only `audio-sound` and `mobile-accessories` paths; no `/smartphones/` path segment appeared, so the targeted Galaxy S20 FE catalog row was not reached.
- Both pages: identity = `.name` + `.sku` (`unverified_sku_meaning`, no mpn/gtin) — same shape as HyperX/Dreame/ASUS/Nintendo from Stage 8.1. Specifications = confirmed empty in static HTML on both pages. Media = `.image` + `responsive_srcset`, **reconfirming Stage 8.1's `responsive_srcset_media_picker` primitive on a 3rd independent family** (Adobe Experience Manager, a CMS Stage 8.1 never tested it against). Documents = a real PDF link found on **both** pages — the first multi-page-confirmed document evidence anywhere in this project, recorded as a Samsung-only `candidate` (not a shared primitive — no second family has ≥2 confirmed document pages yet).

### LG — 2 pages reached, **0 verified** (candidate only)

Route: `robots`-declared `sitemap.xml` → sitemap index `kz-gpone-index.xml` → a sitemap LG itself names for Product Detail Pages, `kz-pdp-sitemap-hreflang.xml` → product URL.

- TV `.../tvs-soundbars/4k-uhd-tvs/43um7100plb/` and washing machine `.../laundry/washing-machines/f2v5hs2s/` — both `product_page_fixture_result: candidate`: real model slugs from a sitemap LG explicitly labels "PDP", but the static HTML carried **zero JSON-LD Product objects and zero microdata Product nodes** on both pages. This reconfirms, with fresh two-category evidence, Stage 8's existing `javascript_only` finding for other LG profiles — LG.com/kz's product pages render identity/spec data client-side (Next.js) and do not embed it in the initial HTTP response. `catalog_identity_result: insufficient` for both (no structured data to compare, and neither model exactly matched the targeted catalog SKUs either). No Chromium was used, per scope, so this cannot be resolved here.

### PlayStation — **2 verified Product pages**, one exact catalog match

Route: Stage 8's already-cached PS Direct collection page (`direct.playstation.com/en-us/collections/wolverine`, 0 new requests) → first-party navigation to `accessories/controllers-and-remotes` and `games/catalog` category pages → `/buy-accessories/` and `/buy-games/` product URLs.

- **DualSense controller, Cosmic Red**: `https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile` — `verified`. `catalog_identity_result: exact_model`. The page text contains "DualSense", "Cosmic Red" and "PS5", matching the catalog row (`Геймпад DualSense для PS5 Cosmic Red`, article `CFI-ZCT1J 02`) on brand, product line and stated color variant. The manufacturer regional part number `CFI-ZCT1J` was **not** found in the page text, and the sanitized structural pipeline deliberately never extracts/compares raw field values — so this is classified `exact_model`, not `exact_variant`: model and color are corroborated, the manufacturer code itself is not.
- **Ghost of Yotei Collector's Edition**: `https://direct.playstation.com/en-us/buy-games/ghost-of-yotei-collectors-edition-ps5` — `verified`, confirms PS Direct's `/buy-games/` convention, but is a different title from the catalog-targeted "007 First Light PS5" (not found as its own `/buy-games/` listing within the pages reached; it only appears bundled into a DualSense controller limited edition). `catalog_identity_result: family_only`.
- **New architecture finding**: identity on both pages is exposed via **schema.org Microdata** (`itemprop="sku"`/`"name"`), **not JSON-LD** — the first confirmed non-JSON-LD identity source anywhere in this whole review (Stage 8.1 included). This also surfaced a real gap in Stage 8's own classifier: `model_semantics` in `inspect_structure()` only looks at JSON-LD `fields`, never microdata `props`, so both pages report `marketing_name_only` even though a real `sku` microdata property is present (`code_fields` correctly includes `sku` because *that* computation does merge both sources). Recorded as an observation, not fixed here (out of this stage's scope). Media: DOM `responsive_srcset` + `itemprop=image` gallery marker confirmed on both pages — a **4th independent family reconfirming the DOM half** of `responsive_srcset_media_picker`; the primitive's JSON-LD/`ImageObject.contentUrl` fallback half does not apply here (no JSON-LD on this site at all).

Full per-product detail, structural contracts and reasoning: [`product_page_fixtures.json`](product_page_fixtures.json). Cross-family comparison against the two Stage 8.1 primitives: [`architecture_observations.json`](architecture_observations.json). New fixtures: [`fixtures/`](fixtures) (13 files).

## What repeats

- **`responsive_srcset_media_picker`** (Stage 8.1's primitive) now has independent confirmation on **4 families** total (bosch_home, hyperx, samsung, and the DOM half on playstation), across three different CMS platforms and one microdata-only site — strong evidence this primitive generalizes, while its JSON-LD/`ImageObject` fallback clause remains JSON-LD-specific by construction.
- **`additionalProperty_specification_reader`** does **not** apply to any of the three brands checked here — Samsung, LG (unverifiable) and PlayStation all show confirmed-empty or unreachable specifications in static HTML. No change to that primitive's scope.
- **Identity stays fully custom, and gets more varied, not less**: Bosch's explicit manufacturer code, HyperX/Dreame/ASUS/Nintendo/Samsung's unverified sku, Xiaomi/De'Longhi's marketing-name-only, and now PlayStation's microdata-based sku add a fourth genuinely distinct pattern. No pooling is justified anywhere.
- **A Samsung-only documents candidate** (PDF link + support nav, confirmed 2/2 pages) is new evidence, not yet a shared primitive (needs a second family at ≥2 confirmed document pages).

## What is still missing

- Samsung's smartphone category (Galaxy S-series) was not reached within the bounded sitemap sample.
- LG has zero verified pages — both reached pages need client-side rendering to confirm, which is out of scope (no Chromium).
- PlayStation's game-disc category doesn't map cleanly onto PS Direct's hardware/collector's-edition storefront; the official PlayStation Store may be a better-suited domain for that category specifically.
- Apple, JBL, Razer, HIPER, Microsoft/Xbox: no route was attempted at all in this stage, by design (see table above).

Full next-step plan per brand: [`next_queue.json`](next_queue.json). Nothing in it was executed.

## Tests

New regression tests: [`tests/test_structural_census_v8_2.py`](../../tests/test_structural_census_v8_2.py) (33 tests) — checks the byte-identical protection guarantee for Stage 2–8 and Stage 8.1, that only the three permitted hosts were ever contacted, that no request continued after a block, that `jbl`/`sulpak`/`mechta` were never touched, that the `official_exact_product_not_found` status was never assigned, and that every catalog sample carries a two-category, brand+article+name search query. Full suite (Stage 2–8.2, 326 tests): [`tests.txt`](tests.txt).

## Answers

1. **Confirmed Product pages found for**: Samsung (2, TV + Galaxy Buds) and PlayStation (2, DualSense controller + a game). LG reached 2 plausible pages but neither structurally verified (client-side rendering). Apple, JBL, Razer, HIPER, Microsoft: none attempted (no permitted-group route, or blocked).
2. **Exact catalog products found for**: none at `exact_variant`. PlayStation's DualSense Cosmic Red controller reached `exact_model` (brand/model/color text-corroborated, manufacturer code unconfirmed). Everything else that reached a verified page is `insufficient` or `family_only` — real Samsung/PlayStation products were verified, but not the specific catalog rows targeted.
3. **Brands without a Product page, and why**: LG (pages reached, structurally unverifiable without JS rendering — architectural gap, not a missing route). Apple/Razer/HIPER/Microsoft (no queue entry in the two permitted method groups this stage). JBL (`http_blocked` from Stage 8, correctly not retried).
4. **Structures that repeat**: the `responsive_srcset_media_picker` primitive, now confirmed on 4 independent families. Nothing else pools — specifications and identity remain source-specific everywhere checked.
5. **Brands ready for a full card-production cycle**: none yet. Samsung is closest (2 verified pages, stable identity/media contract, one genuine gap — smartphones) but still needs the exact catalog SKU reached and its documents-candidate evaluated on a second family before any shared piece is safe to build. PlayStation has one genuinely strong `exact_model` match but only 2 categories tested and a microdata-only identity contract nothing else in this project has handled yet.

## Recommendation

Close Samsung's smartphone gap next: probe `samsung.com/kz_ru/robots.txt` directly for any sitemap declaration not yet seen (bounded, zero guessed URLs), specifically for a mobile/phones-named file to pair with the already-confirmed `vd`/`im`/`da`/`memory`/`assorted` set — this is the single most reproducible, already-budgeted step left, and would give Samsung a complete 2-category verified pair with one bounded, low-risk request. This is a recommendation only; it was not run automatically.
