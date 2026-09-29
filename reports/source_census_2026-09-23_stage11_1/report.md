# Stage 11.1 — is HyperX a repeatable adapter, or just one card?

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 11](../source_census_2026-09-23_stage11/report.md). All 636 prior files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No Kingston, HIPER, or other brand network activity this stage.**

## 1. Offline re-audit of card `9A273AA`

Full detail: [`offline_card_reaudit.json`](offline_card_reaudit.json). Stage 11's own artifacts are unmodified; this is a new file.

**Correction — sku/offers.sku were not independent evidence.** Stage 11 checked both `Product.sku` and `Product.offers.sku` and implied this strengthened the identity claim. Both values come from **one** JSON-LD block, on **one** fetch, of **one** URL (`phase1_robots_and_product_fetch.json`, request #2) — `offers.sku` is schema.org's own required mirror of the parent SKU onto the Offer sub-object, not a second, independently-sourced signal. Corrected statement: the catalog's `9A273AA` matches **one** extracted value from **one** official source — still a genuine, exact-code-level match (the strongest single-page identity signal used in this project), but one source, not two. This does **not** change the identity verdict, only the epistemic weight claimed.

**Manual status — unchanged.** A Quick Start Guide is confirmed physically included (official spec table, "What's In The Box"); no online document or its language is confirmed. Not re-examined further this stage.

**Image evidence — upgraded from filename-only to integrity+visual.** Stage 11 accepted 9 images solely because the SKU string appeared in each CDN filename. This stage fetched **2 of those 9** (a small number, not all) with a byte-preserving, Range-assembled mechanism and visually inspected the result:

| URL | Bytes | SHA-256 | Visual result |
|---|---:|---|---|
| `.../hyperx_quadcast_2_s_9a273aa_main_1.jpg` | 530,088 | `000a36af...b10f33` | Black cylinder, RGB honeycomb grille, "HX" logo, shock mount, gain/mute knob — matches the described product |
| `.../hyperx_quadcast_2_s_9a273aa_angle_2.jpg` | 578,352 | `17602045...9fe50bcf` | Same unit from the side, USB-C port visible |

Both byte counts match their declared `Content-Range` totals exactly (host: `hyperx.com`, same as the confirmed page — not a separate CDN subdomain). Per the no-raw-content rule, the bytes were inspected in-session and discarded, not committed. The remaining 7 images stay filename-matched only, honestly flagged as such.

## 2. Two additional HYPERX catalog rows, offline-selected

Full detail: [`additional_rows_and_adapter_status.json`](additional_rows_and_adapter_status.json). Selected via already-known category-page links from the microphone fixture (`gaming-keyboards`, `gaming-mice`), not guessed: a **mouse** and a **keyboard** — different peripheral types, as requested.

Budget declared before any request: [`budget_predeclaration.json`](budget_predeclaration.json) — host `hyperx.com` only, 12 requests max, robots.txt fetched fresh first (34 `Disallow` rules, none covering `/cdn/shop/files/` or `/products/` or `/collections/`). **7 requests total**: robots.txt (1), 2 image integrity fetches, 2 category pages, 2 candidate product pages.

- **Mouse** — `A1KY6AA`, "Беспроводная мышь Pulsefire Fuse". Found at `hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse` (via the confirmed `gaming-mice` category page). Official `Product.sku = A1KY6AA` — **exact match**, `confirmed_by_exact_code_match`.
- **Keyboard** — `7G7A4AA#ACB`, "Проводная клавиатура для ПК Alloy Rise 75 (Red switch) (RU)". Found at `hyperx.com/products/hyperx-alloy-rise-75-mechanical-gaming-keyboard`. Official `Product.sku = 7G7A4AA#ABA` — **base code matches, exact suffix does not**: the fetched page's own `additionalProperty` states `Keyboard Layout: US Layout`, while the catalog row is explicitly the **(RU)** market variant. **No RU-specific page was found, and none was substituted to paper over the gap** — this row's exact regional variant is `model_line_confirmed_exact_regional_variant_not_confirmed`, not a pass.

## 3. Which extraction component actually works, on which page

This is the central question of this stage. Full table: [`additional_rows_and_adapter_status.json`](additional_rows_and_adapter_status.json) → `component_matrix`. Three live product pages now checked project-wide (microphone, keyboard, mouse), covering 3 peripheral types:

| Component | Shape present, 3/3 pages | Actual value yield |
|---|---|---|
| JSON-LD `.sku`/`.productID`/`.gtin12` | ✅ | Exact catalog match on 2/3 rows checked (mic, mouse); keyboard has a real, identified regional-suffix mismatch |
| JSON-LD `.additionalProperty` | ✅ | **Varies wildly**: 0/5 populated on the microphone, 1/5 on the mouse, 6/10 on the keyboard — the field existing proves nothing about whether it's populated |
| DOM specs table (`specs-label`/`specs-value`) | ✅ | **Reliable** — real values obtained on all 3 pages; this, not the JSON-LD property array, is the dependable specification source |
| JSON-LD `.image` (url/width/height) | ✅ | Reliable real values on all 3 pages (4000×4000, 4000×4000, 1500×1500 respectively — the mouse's smaller size was reported as-is, never upscaled) |
| DOM `responsive_srcset` marker | ✅ (attribute exists) | **Not a genuine per-product signal on any of the 3 pages** — every real multi-width srcset list found belongs to the shared site logo asset; every product photo uses a single URL. This corrects Stage 8.1's characterization of `responsive_srcset` as a confirmed shared media primitive. |
| PDF/document link | — | **0 of 5** HyperX product pages examined project-wide (3 live + 2 earlier sanitized-fixture-only) show any PDF link |

## 4. Adapter verdict — scoped, not blanket

> HyperX supports a repeatable **extraction shape** (JSON-LD `Product` + a DOM specs table) confirmed across 3 independent peripheral categories — a genuine, evidenced `compatible_primitive` at the structural level. It does **not** support a fully repeatable **identity-to-catalog-row guarantee**: 2 of 3 checked rows matched exactly by SKU; one did not, for a real, identified reason (a regional/layout variant gap), not a data problem. A generic adapter can extract HyperX product data reliably; each catalog row's exact variant match must still be verified individually.

## 5. Card `9A273AA` — what's exportable, what's open

Full detail: [`card.json`](card.json). Exportable fields are unchanged from Stage 11 (brand, model, color, GTIN-12, full acoustic/physical spec set, box contents, warranty) — now backed by integrity+visually-verified images for 2 of 9. Export readiness is unchanged: `not_ready_pending_manual_confirmation`.

**Gaps, stated plainly:**
- 7 of 9 known images remain filename-matched only.
- Manual: physically included, no online copy or language confirmed.
- Keyboard row `7G7A4AA#ACB`: no exact-match official page found (US-layout sibling only).
- Documents: unconfirmed across the whole family sampled so far.

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_card_reaudit.json`](offline_card_reaudit.json) — the sku/offers.sku correction + manual status carried forward
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget, declared before any request
- `phase1_robots_and_images.json`, `phase2_category_discovery.json`, `phase3_candidate_product_pages_fetch.json` — the three live phases
- [`additional_rows_and_adapter_status.json`](additional_rows_and_adapter_status.json) — the 2 additional rows + full component matrix
- [`card.json`](card.json) — updated 9A273AA export status + scoped adapter verdict + gaps
- [`checkpoint.json`](checkpoint.json) — full request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–11 + catalog + registry integrity check
- [`raw/`](raw) — fetched HTML pages saved offline (images hashed and discarded, per the no-raw-content rule)
- [`scripts/`](scripts) — all 8 scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v11_1.py` — checks that the sku/offers.sku correction is recorded without changing the identity verdict, that the manual stays an open (not absent) item, that both fetched images are byte-complete/hashed/host-confirmed and not committed as binary files, that the budget was declared before any request and every request stayed on `hyperx.com` (never Kingston/HIPER/other brands), that the mouse's exact SKU match and the keyboard's regional mismatch are both recorded honestly, that `additionalProperty` value population is shown to vary by page, that the `responsive_srcset` correction is recorded, that the adapter verdict distinguishes extraction shape from identity guarantee, and that every prior stage (through 11) plus the catalog and registry remain byte-identical.

## Not started automatically

No Kingston, HIPER, or other-brand work. No wider HyperX census beyond the 2 additional rows. No renewed manual/document search for `9A273AA`. No RU-specific keyboard page was guessed to resolve the regional mismatch.
