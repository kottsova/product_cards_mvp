# Stage 8.5 — point verification and completion of the Samsung MS23K3614AK/BW catalog card

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md) through [Stage 8.4](../source_census_2026-09-22_stage8_4/report.md). All 209 Stage 2–8 files, 26 Stage 8.1, 58 Stage 8.2, 31 Stage 8.2.1, 38 Stage 8.2.2, 22 Stage 8.3 and 24 Stage 8.4 files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json), which also records the source catalog's and registry's unchanged hashes. **No new Samsung census was run and no other item was selected** — this stage worked exclusively on `MS23K3614AK/BW`.

## Separating independent evidence (offline)

Before any request, Stage 8.4's own evidence was reviewed and split into genuinely independent strands: [`evidence_separation.json`](evidence_separation.json).

| Strand | Value | Independence |
|---|---|---|
| Catalog article | `MS23K3614AK/BW` | From the seller's own catalog file |
| Official page `sku` (JSON-LD) | `MS23K3614AK/BW` | From Samsung's structured product data |
| Official page color (`<title>`) | Черный (Black) | A separate on-page element from the JSON-LD block |
| PDF link `ModelName=` parameter | `MS23K3614AK` | **Linkage evidence only** — confirms which model Samsung's download system associated with the link, **not** what the file actually contains |

Stage 8.4's manual claims ("User Manual", "language RU-UK-KK-UZ") were both based on this last strand plus the filename — metadata about the link, never opened content. This stage treats that gap as material and closes it directly.

## PDF verified as a document, not just a reachable file

**Method**: `AccessProbe.probe()` decodes every response as text (`bytes.decode(..., errors='replace')`) before returning it — a lossy, unrecoverable transform for binary PDF content. A scoped `fetch_binary()` extension was added to the fetch helper, reusing the same session, the same `ProbePolicy` timeout/size-cap/user-agent, and the same redirect-host safety and 403/429 handling — just without the text-decode step. `pypdf` was installed into the local, gitignored `.venv` (no tracked project file changed) to parse the result.

**Fetch**: 1 request, HTTP 200, `application/pdf`, magic bytes `%PDF-1.6` confirmed. **1,500,000 bytes read — truncated at the existing size cap** (not raised).

**Important correction to Stage 8.4**: its `content_len=1,431,426` (measured via the lossy text-decode path) was read as evidence the full file had been captured. That inference was invalid — it was the length of a UTF-8-decoded *string*, not a byte count; a truncated binary response can produce a shorter string than its true byte length once invalid sequences collapse to replacement characters. This stage's binary-safe fetch shows what actually happened: the file exceeds 1.5MB and was cut off.

**Parse attempt** (`pypdf.PdfReader(path, strict=False)`): the constructor recovered a partial trailer (`/Root`, `/Info`, `/Size`) and the root object's key list, but **failed** on `reader.pages` (`Invalid object in /Pages`, object 8629 undefined) and on the `/Info` dictionary (object 8644 undefined) — both objects live beyond the truncation point. A raw-byte search for `MS23K3614AK`, `Title`, `/Lang` found nothing (expected: PDF content streams are normally compressed, unreadable as plain bytes without a working page tree). Full diagnosis: [`pdf_content_verification.json`](pdf_content_verification.json).

**Conclusion — per the instructed fallback, used exactly as intended**: **`official PDF candidate; content/language not confirmed`**. The document is demonstrably real, first-party, and model-linked (by URL parameter), but no text was extracted and no language was read from content. **The RU-UK-KK-UZ filename suffix is not used as a substitute finding.**

## Specifications completeness (offline, from already-saved evidence)

A second, broader text scan of the already-confirmed product page (same URL, re-fetched once to widen the keyword search — the specific unclosed field being "what characteristics remain unknown") found **label text** for 8 additional characteristics — weight, product dimensions, turntable dimensions, control type, auto-programs, power-level count, defrost modes, sound toggle — but **no adjacent value** for any of them in the static HTML. This matches the pattern already established for every other Samsung page in this investigation: the specifications panel shell is present statically, its values are injected client-side. Full detail: [`specs_completeness.json`](specs_completeness.json).

**Confirmed with values**: volume (23 л), power consumption (1150 Вт), output power (800 Вт), color, oven type (Solo). **Explicitly unknown**: physical weight, dimensions, turntable diameter, control type, auto-program/power-level counts, defrost mode list — listed, not guessed.

## Image verified as belonging to this model and fit for the card

The image already selected in Stage 8.4 (`.../kz-ru-ms23k3614akbw-ms23k3614ak-bw-frontblack-190178091?$1164_776_PNG$`) was fetched live this stage: HTTP 200, `Content-Type: image/png`, valid PNG magic bytes, 491,012 bytes, **not** truncated. It was advertised via the product page's own `srcset` (not guessed), and its own filename encodes both the exact model code and the confirmed color. **Confirmed fit for card use.** Detail: [`image_verification.json`](image_verification.json).

## Final card: Samsung MS23K3614AK/BW

| Field | Value | Status | Evidence / URL |
|---|---|---|---|
| Brand | Samsung | confirmed | JSON-LD `Product.brand.name` |
| Model name | 23 Л Микроволновая печь Соло БИО-Керамическое покрытие | confirmed | JSON-LD `Product.name` + `<title>` |
| Manufacturer code | MS23K3614AK/BW | confirmed | JSON-LD `sku`, exact catalog match, manual `ModelName` (3 independent sources) |
| Color | Черный (Black) | confirmed | `<title>` tag (not URL) |
| Volume | 23 л | confirmed | Body text label+value, 4-way corroborated |
| Power consumption | 1150 Вт | confirmed | Body text label+value |
| Output power | 800 Вт | confirmed | Body text label+value |
| Official image | 1164×776 PNG | confirmed | Product page `srcset`; live-verified genuine PNG this stage |
| Instruction manual | reachable PDF | **official PDF candidate; content/language not confirmed** | First-party, model-linked by URL parameter; content unreadable due to size-cap truncation |

Full machine-readable card: [`card.json`](card.json).

**Identity result: `exact_variant`** — model code confirmed via 3 independent sources, color confirmed on-page (not URL).
**Manual confirmed by content? No.** Reachability and linkage are confirmed; content is not.
**Russian language confirmed? No.** Only first-party filename/site-parameter metadata suggests it; no text was read from the file itself.
**Missing characteristics**: physical weight, dimensions, turntable diameter, control type, auto-program/power-level counts, defrost mode list.
**Export readiness: partially ready.** The 8 confirmed fields above (brand, model name, code, color, volume, both power figures, image) are export-ready with full evidence. The manual and the 6 missing characteristics are explicitly flagged as open gaps — the card is not blocked, but should not be presented as fully complete either.

## Request log

3 new requests, 3 hosts, 0 rejections, 0 blocks — within the pre-declared budget (max 5 total, max 3/host, max 3 hosts, hosts pre-declared **before** the first request: `www.samsung.com`, `org.downloadcenter.samsung.com`, `downloadcenter.samsung.com`, `images.samsung.com`):

| # | Host | URL | Purpose | Result |
|---|---|---|---|---|
| 1 | org.downloadcenter.samsung.com | manual PDF | Binary content fetch | 200, truncated at 1.5MB cap |
| 2 | www.samsung.com | product page (re-fetch) | Broader spec-label scan | 200, 8 new labels found, no values |
| 3 | images.samsung.com | product image | Reachability/content-type check | 200, valid PNG confirmed |

Full log with running counters and the (empty) rejected-attempts list, kept separate from executed requests per instructions: [`checkpoint.json`](checkpoint.json). Counter persistence continues Stage 8.3/8.4's fix unchanged.

## Artifacts

- [`report.md`](report.md) — this file
- [`evidence_separation.json`](evidence_separation.json) — independent-evidence review
- [`pdf_content_verification.json`](pdf_content_verification.json) — PDF fetch/parse diagnosis
- [`specs_completeness.json`](specs_completeness.json) — confirmed vs. unknown characteristics
- [`image_verification.json`](image_verification.json) — image reachability/content check
- [`card.json`](card.json) — final consolidated card
- [`checkpoint.json`](checkpoint.json) — budget, request log, counters
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–8.4 + catalog + registry integrity check
- [`fixtures/`](fixtures) — 1 new sanitized structural fixture (product-page re-fetch)
- [`scripts/`](scripts) — fetch/extraction scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v8_5.py` — checks the Stage 2–8.4 protection guarantee, that the `ModelName` link parameter is never treated as content confirmation, that the manual's status is exactly `official PDF candidate; content/language not confirmed` (not silently upgraded), that Russian is not claimed confirmed, that unknown characteristics are listed rather than invented, and that the pre-declared host allow-list (including the PDF-serving domain) was fixed before the first request.

## Not started automatically

No further Samsung items, categories, or documents were opened beyond this one card.
