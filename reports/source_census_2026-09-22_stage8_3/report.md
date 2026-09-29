# Stage 8.3 — first limited Samsung full cycle (Product page → card readiness)

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md) through [Stage 8.2.2](../source_census_2026-09-22_stage8_2_2/report.md). All 209 Stage 2–8 files, 26 Stage 8.1 files, 58 Stage 8.2 files, 31 Stage 8.2.1 files and 38 Stage 8.2.2 files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). The source catalog (`data/catalog_2026-09-21_filtered.xlsx`) and production registry files were read-only checked, hashes recorded in the same file.

**Galaxy S20 FE and Galaxy Z Fold3 were not revisited.** Stage 8.2.2's result stands as the historical conclusion for both — no request was made this stage that mentions either model.

## Selection: which of the two Stage 8.2 items enter the pilot

Stage 8.2 confirmed exactly two Product pages for Samsung: a TV (`UE43N5300AUXCE`) and Galaxy Buds3 FE. Per the selection rule (novelties only for smartphones/tablets/wearables; old models permitted only within home appliances), the TV was checked **before** being included.

**No project-wide "novelty" criterion exists** — searched across `product_tool/config/*.json`, `docs/`, and all prior reports for any recency/release-date policy; none found. Per instructions, this stage does not invent one. The TV was instead evaluated against objective, already-known evidence:

- Its URL category (`/tvs/full-hd-tv/`) sits in Samsung's own legacy/entry resolution tier, distinct from the premium tiers (Crystal UHD, OLED, NanoCell, lifestyle TVs) visible in the same `vd-sitemap.xml` (Stage 8.2.1).
- Its model prefix (`N5300`) matches Samsung's own public TV model-year lettering convention for the 2018 generation.
- It is **not** a home appliance by Samsung's own site taxonomy — `da-sitemap.xml` (digital appliances) is a separate branch from `vd-sitemap.xml` (TVs), confirmed in Stage 8.2.1 — so it does not qualify for the rule's "old models OK in appliances" exemption either.

**Decision: exclude the TV from this pilot.** Full reasoning: [`tv_selection_check.json`](tv_selection_check.json). Per the task's fallback instruction, existing fixtures were checked for a substitute new-model Samsung product — none exists (only the TV and Buds3 FE have ever reached `verified`; Stage 8.2.1's smartphone pages are `candidate` only, and Stage 8.2.2 found no product pages at all). **The pilot proceeds with Galaxy Buds3 FE only**, a deliberate scope reduction, not a search failure.

## Bug fix carried over from Stage 8.2.2

Stage 8.2.2's per-host request counter reset at the start of every separate script invocation instead of reading back from the persisted `run_state.json`, so its stated 4-per-host cap was silently overshot (6 requests against a cap of 4). This stage's `scripts/lib.py` now recomputes total and per-host counts directly from the persisted attempt log on every single call — there is no separate in-process counter that can drift. Verified two ways: empirically (this stage's own 2 requests were made in 2 *separate* Python process invocations against the same `run_state.json`, and `budget_status()` correctly read 1 then 2 — see [`checkpoint.json`](checkpoint.json)), and with a dedicated regression test (`tests/test_structural_census_v8_3.py::BudgetPersistenceTests`) that seeds a fake prior-attempts log and confirms a fresh module import correctly rejects the next call once the cap is reached.

## Galaxy Buds3 FE — full cycle

**Discovery**: already-known, already-verified product page from Stage 8.2 — `https://www.samsung.com/kz_ru/audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/`. No new discovery step was needed; the two new requests this stage re-fetched this same URL specifically because Stage 8.2's structural-census fixture records field *names* (`.name`, `.sku`) but never field *values*, so no actual card content existed anywhere offline.

**Identity — `exact_variant`**, confirmed via three independent on-page fields, none from URL text alone:

| Field | Value | Evidence |
|---|---|---|
| Brand | Samsung | JSON-LD `Product.brand`/`manufacturer` (`@id` references to `samsung.com`) |
| Model name | Galaxy Buds3 FE | JSON-LD `Product.name` **and** HTML `<title>` tag (2 independent sources) |
| Manufacturer code | SM-R420NZKACIS | JSON-LD `Product.sku` |
| Color | Черный (Black) | HTML `<title>` tag + repeated in visible body text (not the URL slug) |

Canonical URL matches the fetched URL exactly. Full field-by-field detail with exact evidence strings: [`evidence.json`](evidence.json).

**Specifications — partial**: Bluetooth v5.4, IP54 water/dust resistance, and active noise cancellation (qualitative) were found as plain body text. No comprehensive specifications table was reached — Stage 8.2's structural contract already showed `specifications.dom_semantics` empty (no table/dl/details markup), and this stage's direct full-text search confirms the individual facts exist as loose prose, not a structured list; the full "characteristics" tab is very likely client-rendered, consistent with every other Samsung category checked so far.

**Images — confirmed**: one official image, `images.samsung.com/.../kz-ru-galaxy-buds3-fe-sm-r420nzkacis-548910327?$1164_776_PNG$` — the larger of two explicitly advertised `srcset` widths (624×468 and 1164×776), selected per the project's existing "largest advertised candidate" rule. JSON-LD separately references a different, smaller "thumb" asset (id `548910328`), noted but not used as the primary image.

**Instruction manual — not found**: the only PDF link on the page is `Delivery-Service-TnC.pdf` — first-party (`images.samsung.com`) but a delivery-terms document, not a product manual, and not model-specific. Explicitly excluded from being reported as an instruction: [`documents.json`](documents.json). A further support-route search for a Buds3 FE-specific manual was considered and deliberately not attempted — Stage 8.2.2 already exhaustively proved (5 route types, 6 requests) that Samsung's entire `kz_ru` support surface renders client-side regardless of the model searched; repeating that proof for a new model was judged low-value against the remaining budget.

**Card export readiness: partially ready.** Identity, one official image, and a partial spec set are export-ready with full evidence. Full specifications and an instruction manual remain open gaps.

## Item table

| Item | Catalog identity | Official URL | Model/variant status | Specs | Images | Manual | Language | Gaps | Export readiness |
|---|---|---|---|---|---|---|---|---|---|
| Galaxy Buds3 FE | No matching row in the working catalog (reached via Samsung's own sitemap, not a catalog search) | `.../audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/` | `exact_variant` | Partial (Bluetooth v5.4, IP54, ANC) | 1 confirmed (1164×776 PNG) | Not found (only a non-model-specific delivery-terms PDF) | n/a (no document) | No full spec table; no manual; no catalog row link; "KACIS" suffix meaning not independently verified | Partially ready |
| Samsung TV (N5300) | n/a — excluded before identity work | `.../tvs/full-hd-tv/n5300-43-inch-full-hd-smart-tv-ue43n5300auxce/` | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Excluded from pilot — see `tv_selection_check.json` | Excluded |

Machine-readable version of this table: [`card_summary.json`](card_summary.json).

## Request log

2 new requests total, both to `www.samsung.com`, both HTTP 200, 0 blocks, 0 pauses — well under the planned 8-request/4-per-host/2-host budget:

| # | URL | Purpose | Total after | Host count after |
|---|---|---|---:|---:|
| 1 | `.../galaxy-buds3-fe-black-sm-r420nzkacis/` | Extract JSON-LD (name/sku/image) + PDF link | 1 | 1 |
| 2 | same URL, second pass | Extract `<title>`, canonical, color/spec body text, embedded-state check | 2 | 2 |

Full log with reasons: [`checkpoint.json`](checkpoint.json). Offline reuse before any request: Stage 8.2's fixture URLs, Stage 8.2.1's sitemap link indexes (for the TV taxonomy check), Stage 8.2.2's support-route findings (to justify not re-attempting a manual search) — all zero-cost.

## Artifacts

- [`report.md`](report.md) — this file
- [`tv_selection_check.json`](tv_selection_check.json) — TV novelty check and exclusion reasoning
- [`evidence.json`](evidence.json) — field-by-field identity/spec/image/document evidence for Buds3 FE
- [`card_summary.json`](card_summary.json) — machine-readable version of the item table
- [`documents.json`](documents.json) — document findings, including the excluded non-manual PDF
- [`checkpoint.json`](checkpoint.json) — budget plan, actual usage, request log, bug-fix verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–8.2.2 + catalog + registry integrity check
- [`fixtures/`](fixtures) — 2 new sanitized structural fixtures (no raw HTML, no product values)
- [`scripts/`](scripts) — fetch scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v8_3.py`, including `BudgetPersistenceTests` (proves the Stage 8.2.2 counter bug is fixed by reloading the fetch helper fresh against a seeded prior-attempts log), checks that no request mentions Galaxy S20 FE/Z Fold3, that the TV's exclusion evidence is objective rather than an invented threshold, that `exact_model` was not silently promoted to `exact_variant` without on-page (non-URL) variant evidence, and the full Stage 2–8.2.2 protection guarantee.

## Not started automatically

No further Samsung categories, models, or support routes were opened beyond what this report describes. Home appliances and memory/storage remain unconfirmed by their own Product page fixtures and are not treated as pilot-ready.
