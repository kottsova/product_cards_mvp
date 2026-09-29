# Stage 8.6 — bounded verification of large official instructions as a reusable pipeline capability

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md) through [Stage 8.5](../source_census_2026-09-22_stage8_5/report.md). All 209 Stage 2–8 files and every Stage 8.1–8.5 file (26+58+31+38+22+24+24 = 223 files) were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json), which also records the unchanged catalog and registry hashes. **No new product search or Samsung census was run.** Control document: the already-known `MS23K3614AK/BW` manual PDF (same URL established in Stage 8.4, first content-checked in Stage 8.5).

## Offline review: what Stage 8.5 actually measured

[`offline_review.json`](offline_review.json). Stage 8.5's `fetch_binary()` already counted **raw bytes** (`len()` of joined response chunks), not decoded-text length — the text-length bug this stage was asked to fix belongs to **Stage 8.4** specifically (which measured a UTF-8-decoded string's length as a stand-in for byte count). Stage 8.5 correctly reported `bytes_read=1,500,000, truncated=True` and stopped. What was still missing was a way to get *past* that single-request cap safely, and an explicit three-way completeness classification instead of a bare boolean. This stage adds both, then runs them against the same control document.

## Bounded capability: design

A new `fetch_document_bounded()` was added, reusing the same `requests.Session`, `ProbePolicy` timeout/user-agent, and the same redirect-host allow-list check as the existing `AccessProbe` — **the ordinary HTML page-load cap (1,500,000 bytes) is untouched** and continues to govern `fetch()` for pages; it is only reused as the *per-chunk* size for Range requests, never silently redefined as "the whole document must be complete."

Every response is classified as exactly one of **`complete`** / **`partial`** / **`unknown_completeness`** — derived from `Content-Range`/`Content-Length` compared against bytes actually read, never assumed. If the server honors `Range` (`206` + parseable `Content-Range`), each additional part's declared total size, `ETag`, and `Last-Modified` are compared against the first part's; **any disagreement aborts assembly** rather than splicing potentially different document versions. If `Range` isn't honored and no reliable `Content-Length` is available, no unbounded fallback download is attempted — the result is `unknown_completeness`.

**Budget, declared before any request**: [`budget_predeclaration.json`](budget_predeclaration.json) — max document size 6,000,000 bytes, 1,500,000-byte chunks, max 8 requests total / 6 per host / 2 hosts, both PDF-serving hosts pre-declared (`org.downloadcenter.samsung.com`, `downloadcenter.samsung.com` — both already observed in Stage 8.4/8.5's own redirect chain, not new/invented).

## Attempt 1 — the safety stop worked

The first probe request (`Range: bytes=0-1499999`) returned `206` with `Content-Range: bytes 0-1499999/10572005` — **the control document is 10,572,005 bytes (≈10.08MB)**, confirmed directly, not guessed. Since this exceeds the pre-declared 6,000,000-byte cap, the capability **stopped immediately**, fetched no further bytes, and returned `unknown_completeness` — exactly the instructed behavior when a full document cannot be safely obtained within budget. Full result: [`assembly_result_attempt1_6mb_cap.json`](assembly_result_attempt1_6mb_cap.json).

## Budget revision — declared before any further request, not a retroactive change

Since this stage's explicit purpose is verifying *large* instructions, stopping permanently at the first conservative cap would validate only the stop-safety mechanism, not the assembly mechanism. A second, explicit, written revision was declared — **before making any further request** — raising the ceiling to 12,000,000 bytes (comfortably above the confirmed 10,572,005-byte total, still a fixed finite number, not "unlimited"), and the request limits to accommodate 8 chunk requests. The original declaration and its outcome are kept unmodified as a separate artifact. Full reasoning: [`budget_revision.json`](budget_revision.json).

## Attempt 2 — complete, verified assembly

8 further Range requests assembled the full file: `10,572,005 / 10,572,005` bytes, size matches the declared total exactly. **All 9 requests total (including the attempt-1 probe) returned the identical `ETag` (`"0863cfa2a41d51:0"`) and `Last-Modified` (`Tue, 23 Jul 2019 07:48:12 GMT`)** — confirmed no version drift across parts, no splicing risk. Full result: [`assembly_result.json`](assembly_result.json).

## Content verification — read from the actual file, not the filename

`pypdf.PdfReader` (already installed in Stage 8.5, local `.venv` only) parsed the assembled file **cleanly, with no recovery warnings** — unlike Stage 8.5's truncated 1.5MB partial, which failed with `Invalid object in /Pages`. **80 pages**, Adobe InDesign 2019 production file. Full detail: [`content_verification.json`](content_verification.json).

- **Is it a user manual?** **Confirmed by content.** Page 1's cover reads, literally: *"Микроволновая печь / Руководство пользователя / MS23K3614A\*"* — "Microwave oven / User Manual / MS23K3614A\*".
- **Does it pertain to MS23K3614AK/BW?** **Confirmed by content, exactly, not just family.** The cover states the wildcard family `MS23K3614A*`, but the document's own embedded production-file footer — `MS23K3614AK_BW_DE68-04547Q-00_RU.indd` (and the `_UK`/`_KK`/`_UZ` equivalents) — names the **exact full catalog code including the color suffix**, appearing 20 times per language section (80 occurrences total). This is independent of, and stronger than, the URL's `ModelName=` parameter, which is used only as linkage evidence throughout this investigation, never as content proof.
- **What languages are actually present?** **Confirmed page-by-page**: Russian (pages 1–19, cover *"Микроволновая печь"*), Ukrainian (20–39, *"Мікрохвильова піч"*), Kazakh (40–59, *"Микротолқынды пеш"*), Uzbek (60–79, *"Mikroto'lqinli pech"*) — matching the filename's `RU-UK-KK-UZ` claim exactly, now independently corroborated by real, readable prose rather than trusted from the name alone. **Russian is confirmed**: pages 1–19 form a complete manual section (safety, installation, operation, cleaning, manufacturer/importer contacts including `www.samsung.com/kz_ru/support` for Kazakhstan).

## Updated card status

[`updated_card.json`](updated_card.json) — a **new, separate artifact**; Stage 8.5's `card.json` is left byte-identical and unmodified (verified in `protected_hashes_check.json`).

| Field | Stage 8.5 status | Stage 8.6 status |
|---|---|---|
| `instruction_manual` | `official_pdf_candidate_content_language_not_confirmed` | **`confirmed_by_content`** — 80 pages, user manual, exact model code, 4 languages content-verified |
| `manual_confirmed_by_content` | `false` | **`true`** |
| `russian_language_confirmed` | `false` | **`true`** |
| `export_readiness` | `partially_ready` | **`ready_with_minor_gaps`** |

The 6 missing physical characteristics identified in Stage 8.5 (weight, dimensions, turntable diameter, control type, auto-program/power-level counts, defrost mode list) are **unchanged** — out of this stage's scope, which was the document-verification capability specifically, not a fresh product-page pass.

## Request log

9 requests total, 1 host, 0 rejections, 0 blocks:

| # | Range | Status | Content-Range | Bytes | ETag match |
|---|---|---:|---|---:|---|
| 1 (attempt 1, superseded budget) | 0–1,499,999 | 206 | `0-1499999/10572005` | 1,500,000 | ✓ |
| 2 (attempt 2, chunk 1) | 0–1,499,999 | 206 | `0-1499999/10572005` | 1,500,000 | ✓ |
| 3 | 1,500,000–2,999,999 | 206 | `.../10572005` | 1,500,000 | ✓ |
| 4 | 3,000,000–4,499,999 | 206 | `.../10572005` | 1,500,000 | ✓ |
| 5 | 4,500,000–5,999,999 | 206 | `.../10572005` | 1,500,000 | ✓ |
| 6 | 6,000,000–7,499,999 | 206 | `.../10572005` | 1,500,000 | ✓ |
| 7 | 7,500,000–8,999,999 | 206 | `.../10572005` | 1,500,000 | ✓ |
| 8 | 9,000,000–10,499,999 | 206 | `.../10572005` | 1,500,000 | ✓ |
| 9 | 10,500,000–10,572,004 | 206 | `.../10572005` | 72,005 | ✓ |

Full log with running per-host counters, the (empty) rejected-attempts list kept separate from executed requests, and both budget declarations: [`checkpoint.json`](checkpoint.json).

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_review.json`](offline_review.json) — what Stage 8.5 established and what was still missing
- [`budget_predeclaration.json`](budget_predeclaration.json) — original budget, declared before any request
- [`budget_revision.json`](budget_revision.json) — revised budget, declared before further requests
- [`assembly_result_attempt1_6mb_cap.json`](assembly_result_attempt1_6mb_cap.json) — the safe stop at the original cap
- [`assembly_result.json`](assembly_result.json) — the successful complete assembly
- [`content_verification.json`](content_verification.json) — manual/model/language confirmation from real extracted text
- [`updated_card.json`](updated_card.json) — new, separate card artifact with the updated manual status
- [`checkpoint.json`](checkpoint.json) — budgets, request log, version-consistency result
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–8.5 + catalog + registry integrity check
- [`scripts/`](scripts) — fetch/assembly/extraction scripts used, for reproducibility (the reusable `fetch_document_bounded()` capability lives in `scripts/lib.py`)
- [`tests.txt`](tests.txt) — full test suite output

The assembled PDF bytes themselves were never written into the repository — kept only in the session's scratch directory and discarded after analysis, consistent with the project's no-raw-content rule.

## Tests

New regression tests: `tests/test_structural_census_v8_6.py` — unit-tests the completeness classification (complete / partial / unknown_completeness) against synthetic truncated, partial, and version-inconsistent responses (no network required), checks that the size-check counts raw bytes only, that ETag/Last-Modified mismatches abort assembly rather than splicing, that the pre-declared budgets are honored, and that the Stage 8.5 `card.json` remains byte-identical while `updated_card.json` correctly reflects the new manual status. Full suite (Stage 2–8.6): [`tests.txt`](tests.txt).

## Not started automatically

No further Samsung iterations, products, or categories were opened. This stage ends here regardless of the PDF outcome, per instructions — the successful content verification is a result, not a license to continue.
