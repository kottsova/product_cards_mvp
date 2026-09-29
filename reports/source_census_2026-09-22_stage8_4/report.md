# Stage 8.4 — short catalog-first Samsung cycle

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md) through [Stage 8.3](../source_census_2026-09-22_stage8_3/report.md). All 209 Stage 2–8 files, 26 Stage 8.1, 58 Stage 8.2, 31 Stage 8.2.1, 38 Stage 8.2.2 and 22 Stage 8.3 files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json), which also records the source catalog's and registry files' hashes (read-only, unmodified).

**Galaxy S20 FE, Galaxy Z Fold3 and the N5300 TV were not revisited.** No request or catalog lookup this stage mentions any of the three.

## Part 1 — Galaxy Buds3 FE catalog match

**No match found.** Offline-only search of `data/catalog_2026-09-21_filtered.xlsx` (brand, seller article, name and alt-name columns; terms `sm-r420`, `r420nzkacis`, `r420n`, `buds3 fe`/`buds 3 fe`/`buds3fe` and Cyrillic variants) found **zero** rows for Galaxy Buds3 FE. Full detail, including a noted false-positive trap (a naive `r420` substring search also coincidentally matches Xiaomi's `BHR4208GL`) and the three closest existing rows (Samsung **Galaxy Buds2**, `SM-R177N...` — a different, older product, not treated as a substitute): [`buds3fe_catalog_check.json`](buds3fe_catalog_check.json).

**Consequence, per instructions**: Stage 8.3's evidence stands unchanged as a verified **official-source fixture** (exact_variant identity, one confirmed image, confirmed absence of a manual on that page) with **no catalog-linked card**. No new requests were made for this item — there is no catalog variant to reconcile gaps against, and every field this stage would have checked was already answered in Stage 8.3.

## Part 2 — Selecting the next catalog row

**Category chosen: home appliances (Микроволновые печи / microwave ovens).** This sidesteps the harder novelty judgment entirely — the stated rule explicitly permits old appliance models, so **no currency/release-date evidence is claimed or needed** for this candidate. Tablets and other wearable-adjacent categories were deliberately avoided for this pick specifically because they would require the evidence-based novelty judgment the instructions caution against guessing at.

**Discovery was fully offline**: Stage 8.2.1's already-fetched `da-sitemap.xml` link index (`reports/source_census_2026-09-22_stage8_2_1/link_index/samsung_da_sitemap.json`, 300 links) contains a `microwave-ovens` segment (37 links). Cross-referencing those links against the catalog's 58 Samsung "Микроволновые печи" rows by exact model-code match found exactly one clean, unambiguous hit: catalog article **`MS23K3614AK/BW`** against sitemap URL `.../microwave-ovens/solo/ms23k3614akbw/`. Zero new requests were needed to find this candidate. Full reasoning: [`candidate_selection.json`](candidate_selection.json).

## Part 3 — Full cycle: Samsung MS23K3614AK/BW (microwave oven, Solo)

**Discovery → official Product page**: `https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/`, JSON-LD `Product` confirmed (`is_product_page=true`).

**Identity — `exact_variant`**:

| Field | Value | Evidence |
|---|---|---|
| Brand | Samsung | JSON-LD `Product.brand = {"@type":"Brand","name":"Samsung"}` |
| Model name | 23 Л Микроволновая печь Соло БИО-Керамическое покрытие | JSON-LD `Product.name` + HTML `<title>` |
| Manufacturer code | MS23K3614AK/BW | JSON-LD `Product.sku` — **exact match** to the catalog's own `seller_article`, independently corroborated a third way by the manual PDF's own `ModelName=MS23K3614AK` query parameter |
| Color | Черный (Black) | HTML `<title>` tag, not the URL |
| Volume | 23 л | Body text (×2, labeled), `<title>`, JSON-LD name, **and** the catalog row's own alt-name field ("...23 л") — 4 independent confirmations |

Model code and the variant-defining color field are both independently confirmed on-page — this clears the bar for `exact_variant`, not merely `exact_model`. Full field-by-field detail: [`evidence.json`](evidence.json).

**Specifications — partial but real**: input power 1150 Вт, output power 800 Вт, both labeled and found as plain body text (same static-rendering limitation as every other Samsung page checked so far — no structured table/dl/details markup, so the generic structural contract shows `specifications` empty even though real spec facts exist as prose). No exhaustive spec sheet (dimensions, weight, turntable size) was reached — reported honestly as a gap, not claimed complete.

**Images — confirmed**: one official image, the larger of two explicitly advertised `srcset` widths (624×468 and 1164×776 of the same asset), selected per the project's existing "largest advertised candidate" rule.

**Instruction manual — found and confirmed reachable**, the first successful manual find in this whole Samsung investigation (Buds3 FE in Stage 8.3 had none): `CDCttType=UM` (Samsung's own document-type code) and `ModelName=MS23K3614AK` in the download URL's own query parameters — first-party, model-linked evidence, not a guess from the filename alone. Fetching it confirmed real PDF content (`%PDF-1.6` magic bytes, 1.43MB). **Language**: the filename lists `RU-UK-KK-UZ` (Russian first) — this is evidenced from Samsung's own filename/query-parameter convention, **not** from opening and parsing the PDF's internal text (no PDF text-extraction capability exists in the current pipeline, and building one was out of this stage's scope — stated plainly, not glossed over).

**Card export readiness: mostly ready.** Identity (catalog-matched `exact_variant`), one official image, a partial-but-real spec set, and a confirmed-reachable model-linked manual are all evidence-backed. Open, non-blocking gaps: no exhaustive spec sheet, manual's internal-page language not content-verified, the `/BW` suffix's precise meaning not independently decoded.

Machine-readable item table: [`card_summary.json`](card_summary.json). Document detail: [`documents.json`](documents.json).

## Request log

3 new requests, 2 hosts, 0 blocks, well under the planned 6-request/4-per-host/2-host budget (widened from an initial 1-host plan mid-stage to admit the manual's own first-party `samsung.com` subdomain — disclosed in `checkpoint.json`, not silently changed):

| # | URL | Purpose | Result |
|---|---|---|---|
| 1 | `.../microwave-ovens/solo/ms23k3614akbw/` | Product page — full single-pass extraction | 200, all fields captured |
| 2 | manual URL, narrow `allowed_hosts` | Reachability check | Rejected as `regional_redirect` — the real redirect target host wasn't yet allow-listed. Recorded honestly rather than hidden. |
| 3 | same manual URL, `allowed_hosts` widened to the already-observed redirect target | Retry | 200, confirmed genuine PDF content |

Full log with running total/per-host counters: [`checkpoint.json`](checkpoint.json). This stage continues Stage 8.3's fixed counter-persistence logic unchanged — counters are always recomputed from the persisted `run_state.json`, never from an in-process value that could reset across script invocations.

## Artifacts

- [`report.md`](report.md) — this file
- [`buds3fe_catalog_check.json`](buds3fe_catalog_check.json) — Part 1 evidence
- [`candidate_selection.json`](candidate_selection.json) — Part 2 selection reasoning
- [`evidence.json`](evidence.json) — Part 3 field-by-field evidence
- [`card_summary.json`](card_summary.json) — machine-readable item table
- [`documents.json`](documents.json) — manual/document findings
- [`checkpoint.json`](checkpoint.json) — budget plan, request log, counters
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–8.3 + catalog + registry integrity check
- [`fixtures/`](fixtures) — 1 new sanitized structural fixture (product page only; the manual reachability checks produced no structural fixture, as PDFs aren't HTML)
- [`scripts/`](scripts) — fetch scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v8_4.py` — checks the Stage 2–8.3 protection guarantee, that no request mentions Galaxy S20 FE/Z Fold3/N5300, that the Buds3 FE non-match is honestly recorded (not silently dropped), that the microwave's `exact_variant` status is backed by a non-URL color confirmation, that the manual is correctly linked to its model via first-party query-parameter evidence rather than filename guessing alone, and that the PDF-language claim is scoped to filename evidence rather than overclaiming content verification.

## Not started automatically

No further Samsung categories, models, or documents were opened beyond what this report describes.
