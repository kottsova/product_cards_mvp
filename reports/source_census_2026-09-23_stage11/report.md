# Stage 11 — Xbox count addendum + a catalog-first cycle for HyperX QuadCast 2S Black

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 10.3](../source_census_2026-09-23_stage10_3/report.md). All 615 prior files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No Xbox, Samsung, PlayStation, or Kingston network requests were made this stage.**

## Part A — offline correction addendum to Stage 10.3 (no artifact there was modified)

Full detail: [`xbox_stage10_3_addendum.json`](xbox_stage10_3_addendum.json). Stage 10.3's `card.json` states `"images_rejected_count": 17`, built from its own 6 classification categories, which together total **21** elements:

| Category | Count | In the "17"? |
|---|---:|---|
| Confirmed White by alt text / shared bundle id | 14 | ✅ |
| Carbon-Aware environmental illustration | 1 | ✅ |
| Visually-checked candidates (both rejected) | 2 | ✅ |
| **Subtotal — rejected-with-evidence** | **17** | |
| Different product (Refurbished listing) | 1 | ❌ (excluded, never treated as color evidence) |
| Technical dimensions schematic | 1 | ❌ |
| TV-screenshot, no console visible | 2 | ❌ |
| **Subtotal — excluded, not evidence either way** | **4** | |
| **Total classified** | **21** | |

No overlap between the two buckets; 17 + 4 = 21 exactly. Stage 10.3's report.md already used "17" correctly for the rejected-with-evidence figure and separately listed the 4 excluded elements — this addendum simply makes the arithmetic explicit.

For the two visually-checked candidates, exact URLs, byte-exact SHA-256 hashes (computed from the same bytes Stage 10.3 fetched, kept in this session's scratch copy — no new HTTP request), and rejection reasons are now recorded in a new, separate file:

| URL | SHA-256 | Bytes | Reason |
|---|---|---:|---|
| `.../Xbox-Series-S_Super-Hero-1400_Complete-Control_1920x1400_01.jpg` | `92deb97a...bf8e644` | 575,457 | visually confirmed white |
| `.../XBX_L-StorageExpansion-D.jpg` | `ecb049bd...bec3b91e7` | 376,996 | visually confirmed white |

Both byte counts match the `Content-Range` totals declared at fetch time exactly. **Stage 10.3's Xbox conclusion is unchanged** — this is a bookkeeping clarification, not new evidence.

## Part B — HyperX QuadCast 2S Black, catalog row 6985 (seller article `9A273AA`)

### Offline catalog search and brand separation

Full detail: [`offline_catalog_and_fixture_match.json`](offline_catalog_and_fixture_match.json). The catalog has **53** rows mentioning "HyperX", under **two different `Бренд` values**: `HYPERX` (41 rows — gaming peripherals: keyboards, mice, headsets, microphones, mousepads, webcam) and `Kingston` (12 rows — memory modules that merely use "HyperX" as a Kingston product-line name, e.g. "Kingston HyperX Fury"). These are kept fully separate — Kingston's official domain (kingston.com) has no confirmed Stage 8.1 fixture and was not touched. `HIPER` (a distinct, unrelated brand named elsewhere in this project's priority-brand lists) does not appear in this search at all.

### Match against Stage 8.1's confirmed fixtures

Stage 8.1 live-fetched and confirmed two hyperx.com product pages: the QuadCast 2S USB microphone and the Cloud Alpha Air headset. **No catalog row corresponds to "Cloud Alpha Air"** — the catalog's headset rows list only Cloud Alpha Wireless, Cloud Alpha S, Cloud Stinger (2 Core), Cloud II Core, Cloud III (and variants), Cloud Flight 2, Cloud Jet — so that page isn't usable this stage. The QuadCast microphone family, however, has an exact match: row 6985, **"Микрофон для пк игровой QuadCast 2S Black"**, seller article `9A273AA` — matching the URL slug `quadcast-2-s` and model name exactly, with an explicit color the confirmed page also carries. Three other, more generic QuadCast/SoloCast rows were considered and rejected as different model generations (see the JSON for each).

### Snapshot replay, then one bounded fresh fetch — and why both were needed

Stage 8.1's fixture for this URL is a **sanitized structural contract** (JSON-LD paths + signatures, no field values, per this project's no-raw-content rule) — it proves the field *shape* is stable but stores no actual text. Budget declared before any request: [`budget_predeclaration.json`](budget_predeclaration.json) — host `hyperx.com` only, 6 requests max, robots.txt first.

1. `robots.txt` — 200, ordinary.
2. `https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone` (the exact Stage 8.1 URL) — 200, 612,518 bytes, not truncated.

### Two separate checks: general contract vs. actual identity

This distinction is made explicit and kept genuinely separate, per instructions:

- **General extractor check**: re-running `inspect_structure()` (the same function that produced Stage 8.1's fixture) on the fresh fetch produced **byte-identical signatures** to Stage 8.1's fixture for all 5 contract layers (discovery/identity/specifications/media/documents). This proves the page's field *shape* is still stable — nothing more.
- **Actual identity verification** (separate step): the catalog's seller article `9A273AA` was compared directly, by string equality, against the fresh page's own extracted `Product.sku` **and** `Product.offers.sku` values — both `9A273AA`, an exact match. The offer name itself reads *"HyperX QuadCast 2 S – USB Microphone - Black"*, confirming the color too. This is **confirmed by exact code match** — a stronger identity tier than the descriptive-consistency-only matches used for other brands in this project (Xbox, PlayStation), where no manufacturer code was ever exposed on the official page. Per instructions, the seller SKU appearing here is incidental corroboration, not a requirement.

### Specifications: the generic reader found nothing — the actual page had real values in a different place

JSON-LD's `additionalProperty` array exists exactly per Stage 8.1's contract (`Compatibility`, `Connectivity`, `Polar Pattern`, `RGB`, `Software`) but every `.value` was an **empty string** on this page. The real specification content lives in a DOM specs table (`<td class="specs-label">`/`<td class="specs-value">`) that isn't the same shape as Stage 8.1's abstracted `dl:dt+dd` fallback label, but serves the same role — read directly from this page, not through a generic reusable reader. Real values obtained: acoustic element (three 14mm capsules), 4 polar patterns, 20Hz–20kHz frequency response, sensitivity, self-noise, SNR, USB-C/3.5mm connections, a full physical weight breakdown, box contents, and a 2-year warranty.

### Images

The main product image (`.../hyperx_quadcast_2_s_9a273aa_main_1.jpg`, confirmed 4000×4000 via both JSON-LD `offers.image` and the `og:image` meta tag — the largest explicitly advertised size) plus 8 angle photos, **every filename embedding the exact SKU `9a273aa`** — image-to-SKU linkage as direct as this project has seen.

### Manual — checked, not found as a document, not claimed absent

`https://hyperx.com/pages/support` (an already-known navigation link from the product page itself) was fetched — 200 OK, an internal product-search form present, **zero PDF links**, and zero mentions of this exact model. The product's own official spec table lists a **"Quick Start Guide"** as a physically included box item — so a manual demonstrably exists — but no downloadable/online copy was located within this stage's bounded route. Per instructions, this is stated as an open item, never as "no manual exists." Stage 8.6's PDF-verification mechanism was not invoked because no PDF URL was ever found to feed it.

### Card status — explicit 5-point criterion

Full detail: [`card.json`](card.json).

1. Brand/model confirmed by an official source — ✅
2. Catalog row linked to confirmed variant — ✅ **(exact SKU code match — the strongest identity tier in this project to date)**
3. Official matched image confirmed — ✅ (SKU embedded directly in every image filename)
4. Specifications sufficient — ✅
5. Manual confirmed present (with language) or absence explicitly noted — ❌ open (physically confirmed included, not confirmed as a fetchable document)

**Export readiness: `not_ready_pending_manual_confirmation`** — 4 of 5 criteria pass, a materially stronger result than every prior brand cycle in this project (Xbox stalled at criterion 1; PlayStation/Samsung reached 3–4 of 5 with weaker, descriptive-only identity evidence). The single open item is narrowly scoped: the manual's URL and language.

## Request log and budget verification

[`checkpoint.json`](checkpoint.json): **3 requests total**, all to `hyperx.com`, 0 rejections. One response (`hyperx.com/pages/support`) carried a `challenge_suspected` signal, per Stage 8.1's own precedent this does not stop the host (only `challenge_confirmed`/403/429 would) — resolved as an ordinary 200 page. No PDF document route was invoked (nothing was found to fetch with it).

## Artifacts

- [`report.md`](report.md) — this file
- [`xbox_stage10_3_addendum.json`](xbox_stage10_3_addendum.json) — Part A: count reconciliation + byte hashes for the two visually-checked Xbox images
- [`offline_catalog_and_fixture_match.json`](offline_catalog_and_fixture_match.json) — Part B: catalog scan, brand separation, row selection and reasoning
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget, declared before any request
- `phase1_robots_and_product_fetch.json`, `phase2_support_page_fetch.json` — the two live phases
- [`card.json`](card.json) — general-contract-check vs. identity-verification, exportable fields, manual status, 5-point criterion
- [`checkpoint.json`](checkpoint.json) — request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–10.3 (incl. Stage 8/8.1) + catalog + registry integrity check
- [`raw/`](raw) — the fetched product and support pages, saved offline
- [`scripts/`](scripts) — all 6 scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v11.py` — checks the Xbox reconciliation arithmetic (17 + 4 = 21) and that Stage 10.3's own card is unchanged, that HyperX and Kingston stay separated, that the selected row and Stage 8.1 fixture URLs match, that the budget was declared before any request and every request stayed on `hyperx.com` (never Xbox/Samsung/PlayStation/Kingston hosts), that the general contract-signature check and the actual SKU-value identity check are recorded as two distinct steps, that the SKU match is exact, that real (non-empty) specification values are present, that images reference the exact SKU, that the manual is never declared absent, that exactly 4 of 5 readiness criteria pass, and that every prior stage (through 10.3) plus the catalog and registry remain byte-identical.

## Not started automatically

No Xbox/Samsung/PlayStation/Kingston work. No wider HyperX census beyond this one catalog row. No internal-site search query was run beyond the two confirmed navigation links, to keep this stage's document search bounded.
