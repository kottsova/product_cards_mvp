# Stage 8.2.1 — Samsung smartphones: closing the sitemap gap

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md), [Stage 8.1](../source_census_2026-09-22_stage8_1/report.md), [Stage 8.2](../source_census_2026-09-22_stage8_2/report.md), which already confirmed Samsung Product pages for a TV and Galaxy Buds but left smartphones open. All 209 Stage 2–8 files, all 26 Stage 8.1 files and all 57 Stage 8.2 files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json).

Scope, exactly as instructed: `https://www.samsung.com/kz_ru/` only, sitemap + proven first-party navigation only, small deliberate budget (6 requests planned, 5 used, 1 left unspent).

## Offline first

Before any new request, four pieces of existing evidence were reused at zero network cost:

1. **robots.txt** (Stage 7 snapshot, `samsung_kz`) — declares one `Sitemap:` line per region (`https://www.samsung.com/kz_ru/sitemap.xml` among ~90 others). No mobile/phone-specific sitemap is declared there.
2. **`kz_ru/sitemap.xml` index** (Stage 8.2 offline reprocessing) — 5 branches: `b2c-sitemap.xml`, `top_sitemap.xml`, `business/top-sitemap.xml`, `business/b2b-sitemap.xml`, `support/sitemap.xml`. Only `b2c-sitemap.xml` is shaped like a consumer catalog by name; the rest were not opened (no smartphone-related naming evidence, and opening them would mean guessing at an unproven branch).
3. **`vd-sitemap.xml` / `im-sitemap.xml` / `assorted-sitemap.xml`** — already fully fetched and indexed in Stage 8.2. Re-checking their already-saved link lists confirmed: `vd` (TVs/audio/monitors/projectors, 300 links) has 0 smartphones; `im` ("IT & Mobile", 300 links) has 0 smartphones — it turns out to contain only `mobile-accessories` (281) and `audio-sound` (19), i.e. phone *accessories*, not phones; `assorted` (300 links) is marketing/promo pages, 0 smartphones.
4. **The `kz_ru` homepage snapshot** (Stage 7 sqlite) was reprocessed offline **for the first time with its full, non-truncated link list** (Stage 8.2 had only kept an 8-link sample). This is what found the answer: the homepage links directly to a `/kz_ru/smartphones/...` path tree that none of the `b2c-sitemap.xml` branches ever referenced — a real site section, reached without spending any network budget.

## New requests (5 of a 6-request budget)

| # | URL | Reason | Result |
|---|---|---|---|
| 1 | `.../kz_ru/da-sitemap.xml` | Last unchecked `b2c-sitemap.xml` branch | Home appliances only (air-conditioners, cooking, dishwashers, microwaves, refrigerators). 0 phones. |
| 2 | `.../kz_ru/memory-sitemap.xml` | Last unchecked `b2c-sitemap.xml` branch | Memory/storage only (90 links). 0 phones. |
| 3 | `.../kz_ru/smartphones/all-smartphones/` | First-party link found offline on the homepage | Real `/smartphones/` section confirmed (family pages `galaxy-s/`, `galaxy-z/`, `galaxy-a/`, plus `/buy/` configurator links) — but this listing page itself returned only navigation-shaped links, not a flat product grid with SKU-bearing URLs (unlike tablets/watches links seen on the *same* page, which *do* embed color+memory+model code, e.g. `.../galaxy-tab-s11-ultra-gray-256gb-sm-x936bzaaskz/buy/`). |
| 4 | `.../kz_ru/smartphones/galaxy-s25-ultra/` | First-party link from the category page | HTTP 200, but **zero JSON-LD Product objects, zero microdata Product nodes**. Page text does confirm "Galaxy S25 Ultra" and "Samsung". |
| 5 | `.../kz_ru/smartphones/galaxy-s26-ultra/buy/` | First-party `/buy/` link from the same page | Same: HTTP 200, zero structured product data. |

All 5 requests returned HTTP 200, `ordinary_page`, no protection signal at all — 0 blocks, 0 pauses. The 6th budgeted request was deliberately left unused: two independent smartphone-shaped pages already gave the same negative structural result, and a third attempt was judged unlikely to add information worth the request. Full log: [`checkpoint.json`](checkpoint.json). Branches explicitly not opened, with reasons: `top_sitemap.xml`, `business/top-sitemap.xml`, `business/b2b-sitemap.xml`, `support/sitemap.xml` (all named as marketing/B2B/support, not product catalog).

## Catalog samples

Two Samsung smartphones from the catalog's "Смартфоны" category (the only category checked, per scope): [`catalog_samples.json`](catalog_samples.json).

- **Galaxy S20 FE 128GB** (article `488776SM-G780GZRDSKZ`) — base model, memory (128GB) and the SKU's embedded color code (`ZRD`) recorded as three separate fields, not merged.
- **Galaxy Z Fold3 5G 512GB** (article `491953SM-F926BZGGSKZ`) — same treatment, color code `ZGG`.

Neither catalog article's model generation (2020–2022) matches what `/smartphones/` currently lists (2025–2026 flagships), so even a fully-verified page from this route would not have matched these specific rows — recorded honestly, not glossed over.

## Product page verdict

Both smartphone pages reached: [`product_page_fixtures.json`](product_page_fixtures.json).

- `product_page_fixture_result`: **`candidate`** for both — real pages, reached through a legitimate route, but no JSON-LD Product object and no microdata Product node in the static HTML, so a single specific product cannot be confirmed. Matches the same bar already applied to LG's pages in Stage 8.2.
- `catalog_identity_result`: **`insufficient`** for both — no code_fields (sku/mpn/gtin), no color, no memory variant exposed statically to compare against the catalog rows, and the model generation doesn't match anyway. Per instructions, Galaxy-family or marketing-name text matches alone (both pages *do* textually contain "Galaxy S25 Ultra"/"Samsung") are explicitly **not** treated as `exact_model`.
- Route-level status: **`mobile_sitemap_no_product_urls`** — all 5 branches of the only proven consumer-catalog sitemap contain zero smartphone URLs; a real alternate first-party route exists but its pages are not statically verifiable. Full route evidence: [`sitemap_evidence.json`](sitemap_evidence.json). No catalog product was marked `official_exact_product_not_found` from this single, limited route.

## Architecture comparison: TV/audio vs. smartphone

Full detail: [`samsung_template_comparison.json`](samsung_template_comparison.json).

| Layer | TV & Galaxy Buds (Stage 8.2) | Smartphones (this stage) | Same? |
|---|---|---|---|
| Identity storage | JSON-LD Product (`.name` + `.sku`) | None (0 JSON-LD, 0 microdata) | **No** |
| Specifications | Empty in static HTML | Empty (nothing to compare) | Inconclusive |
| Media | JSON-LD `.image` + DOM `responsive_srcset` | DOM `responsive_srcset` present, but not attributable to a confirmed product (no JSON-LD `.image`, no confirmed product at all) | **No** |
| CMS / embedded state | `generic_json_ld_product` confirmed, Adobe Experience Manager | `generic_json_ld_product` **not** confirmed; still Adobe Experience Manager | **No** |
| Support/documents route | PDF link + `support_navigation=true` confirmed on both pages | No PDF link found | **No** |

Same underlying platform (Adobe Experience Manager) across every Samsung page checked so far — but, consistent with the project's rule that CMS identity is never treated as adapter-grouping evidence, the *actual data contract* differs sharply between sections. **`responsive_srcset_media_picker` re-check: not applicable to the smartphone pages** — the DOM marker is present, but since no product is confirmed, the primitive is recorded as neither reconfirmed nor contradicted here (same treatment already given to LG's unverified pages in Stage 8.2). No other shared primitive was expanded from this evidence.

## Samsung adapter shape

**Verdict: one shared family orchestration, with separate category-level extraction templates — not one uniform template, and not fully separate brands.**

Samsung stays one `source_family` with one official domain, one sitemap system, and one identity-code convention (sku-only, `unverified_sku_meaning`, confirmed identical on TV and Buds). But two structurally distinct page templates now coexist under that single platform: a JSON-LD-bearing template that covers everything reachable through `b2c-sitemap.xml` (TVs, audio-sound, mobile-accessories, appliances, memory/storage), and a client-side-rendered template with no static structured data at all for the `/smartphones/` family/configurator pages. A single common page-parser would either miss smartphones entirely or wrongly assume JSON-LD is universal; discovery/orchestration can stay shared, but extraction needs a category-aware branch.

## Tests

New regression tests: [`tests/test_structural_census_v8_2_1.py`](../../tests/test_structural_census_v8_2_1.py) — checks the byte-identical protection guarantee for Stage 2–8.2, that only `www.samsung.com` was contacted and only under `/kz_ru/`, that no request continued after a block, that neither catalog sample conflates base model with color/memory, that no `official_exact_product_not_found` status was assigned anywhere, and that the `responsive_srcset_media_picker` re-check is recorded as not-applicable rather than silently reconfirmed. Full suite (Stage 2–8.2.1): [`tests.txt`](tests.txt).

## Answers

1. **Is there an official sitemap for Samsung smartphones?** No — all 5 branches of `b2c-sitemap.xml`, the only proven consumer-catalog sitemap, were checked and none contain smartphone URLs. A real `/smartphones/` site section exists but is reached through ordinary site navigation, not the sitemap system.
2. **Which Product pages are confirmed?** None newly verified this stage — both smartphone pages reached are `candidate` only (no structured product data). Samsung's confirmed pages remain the TV and Galaxy Buds from Stage 8.2.
3. **Were exact catalog models or variants found?** No. Neither reached page exposes identity data to compare, and both are current-generation models (S25/S26 Ultra) rather than the catalog-targeted 2020–2022 phones (Galaxy S20 FE, Galaxy Z Fold3).
4. **Is the structure the same across TV, audio and smartphone pages?** No — TV and Galaxy Buds share an identical JSON-LD-based template; smartphones use a different, client-side-rendered template with no static structured data, on the same backend platform.
5. **How should the Samsung adapter be shaped?** One shared orchestration/discovery layer (domain, sitemap system, identity-code convention), with separate category-aware extraction templates — a JSON-LD extractor for the sitemap-reachable categories, and a distinct (currently out-of-scope) approach for smartphones. Not one uniform template, not fully separate adapters.
6. **Is there enough evidence for a limited full Samsung cycle?** Not yet, even for a limited pilot. The JSON-LD template (TV/audio/appliances/memory) has two independently confirmed categories with a stable contract and could support a narrow pilot restricted to those categories — but smartphones, one of Samsung's largest catalog categories, still has zero verified pages and a confirmed architectural blocker (client-side rendering), so a Samsung-wide pilot is premature.
7. **One recommended next step:** try Samsung's `support_first` route (`support.samsung.com`, already a known `support_hosts` entry for this profile) for smartphones specifically — support/manual portals often index devices by model code for warranty lookup and may expose static identity data the marketing/configurator section does not. This was not attempted here (out of this stage's strict `www.samsung.com/kz_ru/`-only scope). Not started automatically.
