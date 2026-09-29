# Stage 9 — first catalog-first full cycle: PlayStation DualSense Cosmic Red

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md) through [Stage 8.6](../source_census_2026-09-22_stage8_6/report.md). All 209 Stage 2–8 files and every Stage 8.1–8.6 file (26+58+31+38+22+24+24+21 = 244 files) were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json), which also records the unchanged catalog and registry hashes. **Samsung was not investigated this stage.**

## Part 1 — Exact catalog row

Offline search of `data/catalog_2026-09-21_filtered.xlsx` for the already-verified Stage 8.2 page (`Геймпады` category, name containing both "DualSense" and "Cosmic Red") found **two** candidate rows, not one: [`catalog_match.json`](catalog_match.json).

| Seller article | Catalog name |
|---|---|
| `CFI-ZCT1J 02` | Геймпад DualSense для PS5 Cosmic Red |
| `CFI-ZCT1W_cosmic_red` | Беспроводной геймпад DualSense Cosmic Red |

Both name the identical color ("Cosmic Red") but carry **different manufacturer/regional codes** (`CFI-ZCT1J` vs `CFI-ZCT1W`) — a genuine ambiguity, not a naming quirk to collapse. Per instructions, neither was assumed to be "the" match; both are carried forward and the official page was checked for evidence that could disambiguate them.

**Result: the ambiguity is not resolved by official evidence.** The live product page's own `sku` microdata value is `1000050734` — PS Direct's internal US-webstore product ID, unrelated to Sony's `CFI-ZCTxx` regional numbering. A direct search (microdata scan + regex for the `CFI-` pattern across the entire fetched page) found **zero** occurrences of either candidate code, or any `CFI-` string at all. Full detail: [`identity_ambiguity.json`](identity_ambiguity.json). This report treats `CFI-ZCT1J 02` as the primary reporting target only for continuity with Stage 8.2's original search — **not** as a confirmed match.

## Part 2 — Model/variant confirmation level

Since an exact catalog row exists (even if ambiguous between two), the full cycle proceeded — 1 request, `direct.playstation.com`, HTTP 200, re-fetching the already-verified URL specifically to extract real microdata **values** (Stage 8.2's sanitized structural census recorded only field *names*, never values, by design).

- **Brand**: confirmed (Sony logo `alt` text, "PlayStation® (US)" in `<title>`).
- **Model name**: confirmed — microdata `name` = "DualSense® Wireless Controller - Cosmic Red - For PS5, PC, MAC & Mobile", corroborated by `<title>`.
- **Color**: confirmed via a **structured** `Color:` label+value pair in the page body — stronger evidence than Stage 8.2's plain-text-only mention.
- **Manufacturer/regional code**: **confirmed absent** from this page (searched, not merely unchecked).

**Per instructions, `exact_variant` is not assigned.** Even with color now confirmed at a structured level, the specific catalog **row** cannot be identified — two real SKUs share that color name, and the page's own identifier system doesn't overlap with either. **Identity result: `exact_model`** — the product itself (DualSense, Cosmic Red) is confirmed; which catalog SKU it corresponds to is not. Full reasoning: [`evidence.json`](evidence.json), [`card.json`](card.json).

## Characteristics

Confirmed, with textual evidence: haptic feedback, adaptive triggers, built-in battery with USB-C charging, Bluetooth wireless connectivity, firmware-updatable. All qualitative — **no numeric specifications** (battery capacity, weight, dimensions, battery life, Bluetooth version) were found anywhere on the page; the structural contract confirms `specifications` is empty (no table/dl/details, no JSON-LD `additionalProperty`).

## Images

One official image confirmed: `media.direct.playstation.com/.../2025-dualsense-ps5-controller-cosmic-red-accessory-front?$Background_Large$` — alt text matches model+color (not URL-only), first-party PlayStation media CDN, the largest of the site's own named size tokens (`$Thumbnail_Large$`/`$Background_Small$`/`$Background_Large$`) selected per the project's existing "largest advertised candidate" principle, adapted to this site's naming convention (no pixel-dimension `srcset` was offered here, unlike Samsung's pages). A second product-angle image was also found and is available as a secondary candidate.

## Instruction and language

**Not found in checked sources.** No `.pdf` link exists anywhere on the verified product page; its only `/support/` links are generic e-commerce policy pages (financing, FAQs, shipping, returns, subscriptions) — none is a manual or quick-start guide. Per instructions, **this is recorded as "not found," not as evidence the manual does not exist.** `www.playstation.com` and `support.playstation.com` were pre-declared as available hosts in case a first-party link pointed there; none did, so neither was contacted — no broad brand search was performed. Stage 8.6's bounded document-assembly capability (`fetch_document_bounded()`) was carried over unchanged and remained available, but was never invoked since no document link existed to apply it to.

## Gaps and export readiness

An explicit 5-point export-readiness criterion is stated in [`card.json`](card.json) before judging against it — gaps are evaluated against it, not called "minor" by default:

1. Brand/model confirmed by an official source. ✅
2. The *specific* catalog row confirmed unambiguously. ❌ — **two real, different seller SKUs cannot be told apart from the confirmed evidence.** This is named as the blocking gap, not glossed over.
3. At least one official, matched image confirmed. ✅
4. Specifications sufficient to describe this variant for a customer listing. ❌ — only qualitative marketing text, no numeric specs.
5. Manual confirmed present (with language) or its absence explicitly noted. ✅ (explicitly noted as not found).

**Export readiness: not ready** — specifically because of criteria 2 and 4, both named plainly rather than minimized. What would close each gap is stated in `card.json` (e.g., a source mapping the page's internal SKU to a `CFI-ZCTxx` code; a specifications page not opened this stage since no link led there).

## Request log

1 new request, 1 host, 0 rejections, 0 blocks — within the pre-declared budget (max 6 total, max 4/host, max 2 hosts, hosts pre-declared **before** the first request: `direct.playstation.com`, `www.playstation.com`, `support.playstation.com`):

| # | Host | URL | Purpose | Result |
|---|---|---|---|---|
| 1 | direct.playstation.com | verified product page (re-fetch) | Extract real microdata values, specs text, image candidates, manual links | 200, all fields extracted in one pass |

Full log with running counters: [`checkpoint.json`](checkpoint.json). `www.playstation.com` and `support.playstation.com` were pre-declared but never contacted (no first-party link led there — see above).

## Artifacts

- [`report.md`](report.md) — this file
- [`catalog_match.json`](catalog_match.json) — offline catalog search, both candidate rows
- [`identity_ambiguity.json`](identity_ambiguity.json) — the SKU-scheme mismatch and unresolved-row finding
- [`evidence.json`](evidence.json) — field-by-field evidence with URLs
- [`card.json`](card.json) — final card, explicit export-readiness criterion and gap analysis
- [`checkpoint.json`](checkpoint.json) — budget, request log, counters
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–8.6 + catalog + registry integrity check
- [`fixtures/`](fixtures) — 1 new sanitized structural fixture
- [`scripts/`](scripts) — fetch/extraction scripts used, for reproducibility (`scripts/lib.py` extends Stage 8.6's `fetch_document_bounded()` unchanged, adding an ordinary `fetch()` under the same budget gate)
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v9.py` — checks the Stage 2–8.6 protection guarantee, that both candidate catalog rows are preserved rather than one being silently dropped, that the manufacturer code's *confirmed absence* (not just "unchecked") is correctly distinguished, that `exact_variant` was not assigned, that gaps are tied to the stated 5-point criterion rather than labeled "minor," and that `support.playstation.com`/`www.playstation.com` were never contacted despite being pre-declared.

## Not started automatically

No further PlayStation items, Samsung work, or broader brand search was opened beyond this one card.
