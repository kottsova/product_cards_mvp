# Stage 10.3 — final bounded image check for XXU-00015 (Xbox Series S, Carbon Black, 1TB)

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 10.2](../source_census_2026-09-23_stage10_2/report.md). All 598 prior files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No manual search, no general Xbox census, no other catalog row.**

## 1. Offline: does the page's own image gallery have a Carbon Black slot?

Full detail: [`offline_dom_gallery_analysis.json`](offline_dom_gallery_analysis.json). Re-reading the same live (non-comment) markup Stage 10.1/10.2 already saved, the page's per-option "hero-gallery" carousel — the same mechanism driving the live variant selector and purchase buttons — was traced structurally: it has a complete 4-slide set for **standard** (512GB Robot White, `campsiteName: "page-hero-standard"`) and another complete 4-slide set for **special** (1TB Robot White, `special-slide1..4`). **No `new-slideN` set and no `page-hero-new` campsite exists anywhere in the saved page.** This is a structural finding, not a filename search: Microsoft's own gallery infrastructure simply has no dedicated photography slot configured for the Carbon Black 1TB option in this snapshot.

Every live `<img>` referencing either known Xbox asset CDN (`cms-assets.xboxservices.com`, `assets.xboxservices.com`) was inventoried and classified — never by filename keyword alone:

- **14 elements** confirmed White by the page's *own alt text* ("...Robot White...") or by sharing the single `389964` buy-box bundle id already tied to that same White bundle's retail copy.
- **1 element** (the "Carbon-Aware" image, 3 responsive resolutions) — its own caption text (Stage 10.2) describes an unrelated sustainability feature, not the color.
- **1 element** — a different product listing ("XBOX Series S Refurbished").
- **1 element** — a technical dimensions schematic, not a product photo.
- **2 elements** — screenshots of gameplay on a TV, no console visible.
- **2 elements** remained genuine candidates: console visible, color unstated in alt text, not tied to any option via DOM. Per instructions, a missing "Black"/"White" filename keyword was **not** treated as disqualifying — these two were kept specifically because the DOM/caption evidence was ambiguous, not because their names lacked the word "Black."

## 2. Budget, declared before any request

[`budget_predeclaration.json`](budget_predeclaration.json): both official CDN hosts named explicitly (found on the already-confirmed page, not guessed), 4 requests max, 2 per host, robots.txt checked first (both returned 404 — no crawl restrictions declared, normal for static asset CDNs, not a blocker).

## 3. The two candidates: fetched, verified, and visually inspected

[`phase2_fetch_candidate_images.json`](phase2_fetch_candidate_images.json): both images were fetched with a bounded, Range-aware, byte-preserving mechanism (the same logic as Stage 8.6/10.1's document fetch, adapted for binary images) and **verified complete** — assembled byte count matched the server's declared `Content-Range` total exactly, for both:

| Candidate | Bytes | Visual result |
|---|---:|---|
| "XBOX Series S next to a space ship on a Starfield planet" (Super-Hero, Complete Control) | 575,457 | **White console, white controller.** |
| "Back of the XBOX Series S" (StorageExpansion callout) | 376,996 | **White rear panel.** |

Per this project's no-raw-content rule (established in Stage 8.6 for PDFs), the assembled image bytes were inspected in-session and then discarded — not committed to the repository. Only the evidence (byte counts, completeness, content-type, and this visual description) is kept.

**Both candidates are rejected — confirmed White, not Carbon Black.**

## 4. Final image verdict

**Zero images accepted.** Every image reachable from the confirmed official page was either textually confirmed White, confirmed to depict an unrelated feature, a different product, not a product photo at all, or — for the two remaining ambiguous candidates — visually confirmed White after a bounded, verified fetch. The page's own gallery mechanism has no Carbon Black slot at all. This is stated as a **confirmed gap in the available official content**, never as "no such photo exists anywhere on xbox.com."

## 5. Updated card

Full detail: [`card.json`](card.json).

- **Variant-specific fields** (Carbon Black, 1TB storage) — carried forward unchanged from Stage 10.2, each with URL and evidence.
- **Line-wide fields** (CPU/GPU/memory/video/sound/ports, dimensions, weight with its caveat) — carried forward unchanged.
- **Images** — 0 accepted, 17 individual page elements examined and rejected with stated evidence each (see above); none discarded merely for lacking a color word in its filename.
- **Manual** — left exactly as Stage 10.2 recorded it: neither confirmed present nor confirmed absent (JS-only support articles, both languages). Not re-searched this stage.

Explicit 5-point criterion:

1. Brand/model confirmed — ✅ (unchanged)
2. Catalog row linked to confirmed variant — ✅ (unchanged; never depended on images)
3. Official matched image confirmed — ❌ **now a confirmed absence** (exhaustive small-number visual check performed), not merely "not yet found"
4. Specifications sufficient — ✅ (unchanged)
5. Manual confirmed present or absence noted — ❌ (unchanged, not re-examined)

**Export readiness: `not_ready`, unchanged at 3 of 5 criteria** — but criterion 3's status is now evidence-backed rather than open, and the whole product cycle for this catalog row stops here per instructions, regardless of outcome.

## Request log and budget verification

[`checkpoint.json`](checkpoint.json): **4 requests total**, 2 to `cms-assets.xboxservices.com`, 2 to `assets.xboxservices.com`, 0 rejections, 0 protection stops, both images byte-verified complete.

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_dom_gallery_analysis.json`](offline_dom_gallery_analysis.json) — the structural gallery-slot finding and full image classification
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget, declared before any request
- `phase1_robots_check.json`, `phase2_fetch_candidate_images.json` — the two live phases
- [`card.json`](card.json) — accepted/rejected images with evidence, updated 5-point criterion
- [`checkpoint.json`](checkpoint.json) — request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–10.2 + catalog + registry integrity check
- [`scripts/`](scripts) — all 6 scripts used, for reproducibility (raw image bytes were not retained, per the no-raw-content rule)
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v10_3.py` — checks that no Carbon Black gallery slide slot exists while both White slots do, that exactly 2 candidates were kept for visual review, that both were rejected with an explicit "visually confirmed white" reason (never silently dropped), that no image is mislabeled Carbon Black, that the budget was declared before any request and every request stayed on an allowed CDN host, that both images were verified byte-complete, that no binary image file was committed to the repository, that the manual status is untouched and never claims non-existence, that criterion 3 is now stated as a confirmed absence, that exactly 3 of 5 criteria pass, and that every prior stage (through 10.2) plus the catalog and registry remain byte-identical.

## Not started automatically

No manual search. No general Xbox census. No other catalog row. No further image search beyond this one bounded check, per instructions — this stage stops here regardless of the (negative) outcome.
