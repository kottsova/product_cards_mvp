# Stage 10.2 — completing the bounded cycle for XXU-00015 (Xbox Series S, Carbon Black, 1TB)

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 10.1](../source_census_2026-09-23_stage10_1/report.md). All 578 prior files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No general Xbox census, no other catalog row, no other product.**

## 1. Offline re-audit of Stage 10.1's product page — an error found and corrected

Full detail: [`offline_reverification.json`](offline_reverification.json). Every field Stage 10.1 accepted was re-read from the already-saved page (`raw/series_s_landing_en_us.html.txt`, no new request) and classified as **variant-specific** (Carbon Black 1TB only) or **line-wide** (all Series S SKUs), with a check for whether the source text is live, rendered HTML or dead markup inside an `<!--...-->` comment.

- **Variant selector markup**: two near-identical copies exist. The first (an old in-page-navigation menu) is wrapped in an HTML comment — dead, unrendered. The second, live and uncommented, has a functional `aria-label` ("...This also changes the images in the gallery...") and matching uncommented purchase buttons. Stage 10.1's evidence traces to the **live** copy.
- **JS hash-routing** (`case '#black1tb': ... theOption = 's-new';`) independently confirms the Carbon Black 1TB option is a real, addressable SKU, not placeholder text.
- **Storage** ("XBOX Series S Carbon Black: 1TB Custom NVME SSD") — confirmed live, uncommented, and correctly **variant-specific**: it is the only spec restated once per color+capacity combination.
- **Dimensions (6.5×15.1×27.5cm) and weight (4.25 lbs)** — confirmed live, uncommented, but appear **exactly once**, never per option. Reclassified explicitly as **line-wide**, carried with a caveat: not demonstrated identical across SKUs by the page itself, applied to the Carbon Black unit only by physical-design inference.
- **The three "Carbon-Aware" images — Stage 10.1's claim is WRONG and is retracted.** Reading the actual panel text behind that tab: *"XBOX Series S is our first XBOX console ever to contain Post-Consumer Recycled (PCR) plastics, while energy-saving power modes fine-tune your console when it's on or off."* This is Xbox's **environmental/sustainability** messaging (a "Purchase Restrictions" tab titled "Carbon aware," sibling to a "Safer gaming" parental-controls tab) — nothing to do with the **Carbon Black** color. The image alt text ("XBOX Series S surrounded by leaves and plants") is a nature-themed illustration of this feature, line-wide, not a photo of any specific SKU. **No image or video asset on the page has "Black," "White," or "Robot" (the real color names) anywhere in its filename.** No genuine color-specific image was found.
- **Seller article** `XXU-00015` remains the catalog identifier only; rechecked and confirmed absent from the page text — its absence is not evidence of anything, per instructions.

## 2. One bounded document/support route, Russian first

Budget declared before any request: [`budget_predeclaration.json`](budget_predeclaration.json) — host `support.xbox.com` only, 6 requests max, Russian checked before English, only already-declared sitemap URLs used (no locale-substitution guessing).

1. Fetched `support.xbox.com/ru-RU/sitemap.xml` — the exact URL already listed in Stage 10.1's own saved sitemap index, not guessed. 200 OK, 2,967 URLs. It lists the **same slugs** as the English sitemap, just under `/ru-RU/`: `.../console/unbox-xbox-series-xs-console` and `.../getting-started-set-up/set-up-new-series-x-s` — confirmed present, not assumed by pattern substitution.
2. Fetched both Russian article URLs. **Identical result to the English versions already found in Stage 10.1**: HTTP 200, ~2,897-byte bare React SPA shell (`<noscript>You need to enable JavaScript to run this app.</noscript>`), no readable content in either language.
3. **PDF search**: zero `.pdf` references anywhere across the already-fetched `www.xbox.com` sitemap/CMS chunk/landing page, or either `support.xbox.com` sitemap (en-US or ru-RU, offline re-check + this stage's fetch). No document-CDN host was ever discovered, so no document-fetch budget (Stage 8.6-style) was needed this stage.

Per the pre-declared stop condition, once the identical JS-only architecture was confirmed in **both** languages, further requests to structurally identical pages (e.g. the warranty-service article also listed in the sitemap) were not made — they would not produce new information. **3 requests total, all to `support.xbox.com`, 0 rejections.**

## 3. Variant-specific vs. line-wide fields, each with URL and evidence

Full detail: [`card.json`](card.json).

| Field | Value | Classification | Evidence |
|---|---|---|---|
| Цвет/вариант | Carbon Black | **variant-specific** | live purchase-option label + JS hash-route |
| Объём накопителя | 1TB Custom NVMe SSD | **variant-specific** | live, explicit per-color spec line |
| Модельный ряд, CPU, GPU, память, расширение памяти, видео, звук, порты | — | line-wide | same TECH SPECS block, never restated per option |
| Габариты | 6.5×15.1×27.5cm | line-wide *(caveated)* | stated once, not confirmed identical across SKUs |
| Вес | 4.25 lbs | line-wide *(caveated)* | same caveat |

## 4. Manual search result

**Neither confirmed present nor confirmed absent.** Two real, live, on-topic candidate articles exist in **both** Russian and English (HTTP 200, correct URLs from the site's own sitemaps), but neither's content is reachable without executing JavaScript, which stays out of scope for this stage. No PDF or static instruction was found anywhere in the routes checked. **Language confirmed: none** — no content was actually read, so no language claim is made, and a generic Xbox article is never labeled a "Series S manual" without content-confirmed applicability, which was not obtained.

## 5. What can be exported vs. what blocks a full card

Explicit 5-point criterion, [`card.json`](card.json):

1. Brand/model confirmed by an official source — ✅
2. Catalog row linked to confirmed variant — ✅ (by model+capacity+color descriptive consistency; unaffected by the image retraction, which was never load-bearing for this criterion)
3. Official matched image confirmed — ❌ **corrected from Stage 10.1's false ✅** — no genuine color-specific image exists
4. Specifications sufficient — ✅
5. Manual confirmed present or absence explicitly noted — ❌ still open, now confirmed exhausted in both languages

**Already exportable with evidence:** brand, exact model, Carbon Black color, 1TB storage (both variant-specific), and a full line-wide spec set (with an explicit caveat on dimensions/weight) — each with its URL and evidence basis.

**Full card readiness: `not_ready`** — 3 of 5 criteria pass (down from Stage 10.1's incorrectly-claimed 4, corrected here), blocked by the image gap (now genuinely absent, not just unfound) and the manual gap (a structural JS-access blocker, exhaustively checked in Russian and English, not a data gap and not a confirmed absence).

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_reverification.json`](offline_reverification.json) — full field-by-field re-audit, including the image-claim correction
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget, declared before any request
- `phase1_ru_sitemap_fetch.json`, `phase2_ru_article_fetch.json` — the two live phases
- [`card.json`](card.json) — variant-specific/line-wide fields, manual search result, corrected 5-point criterion
- [`checkpoint.json`](checkpoint.json) — request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–10.1 + catalog + registry integrity check
- [`raw/`](raw) — the two Russian article shells and the ru-RU sitemap, saved offline
- [`scripts/`](scripts) — all 6 scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v10_2.py` — checks that the "Carbon-Aware" image claim is explicitly retracted with a stated reason, that no filename contains a real color word, that storage is confirmed live and variant-specific while dimensions/weight are confirmed live but line-wide with a caveat, that the dead/live selector-copy distinction is recorded, that the budget was declared before any request and prioritizes Russian, that every request stayed on `support.xbox.com`, that the manual-search status is exactly "not confirmed present and not confirmed absent" (never "no manual exists"), that criterion 3 is now correctly failing with the correction stated, that exactly 3 of 5 criteria pass, and that every prior stage (through 10.1) plus the catalog and registry remain byte-identical.

## Not started automatically

No general Xbox census. No other catalog row. No Chromium session to render the confirmed JS-only support articles — that stays a separate, explicit decision for the user.
