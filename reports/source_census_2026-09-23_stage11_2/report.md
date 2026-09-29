# Stage 11.2 — the real 14-image gallery, the confirmed video, and one open field

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 11.1](../source_census_2026-09-23_stage11_1/report.md). All 662 prior files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No Kingston, HIPER, Sulpak, Mechta, or other brand/dealer host was contacted.**

## 1. Root cause of Stage 11's "9 images" — found offline, from the already-saved HTML

Full detail: [`offline_gallery_root_cause.json`](offline_gallery_root_cause.json). Stage 11 counted gallery images with a regex requiring the literal SKU string `9a273aa` in the filename — that matched the main photo and 8 angle photos (9 total), and silently excluded **5 real gallery images** whose filenames don't contain the SKU at all: `annotated_1_future_en`, `annotated_2_dynamic_en`, `annotated_3_tap_en`, `annotated_4_versatile_en`, `annotated_5_redesigned_en` — feature-callout images, still part of the same official gallery.

The page's own gallery is grouped by `data-media-id` (14 distinct numeric IDs) paired with `data-fancybox="images"` — Shopify's own lightbox-grouping mechanism, independent of filename. Re-reading the saved HTML with this method finds all **14**.

## 2. Fresh fetch vs. saved snapshot — extraction fixed and re-verified live

Budget declared before any request: [`budget_predeclaration.json`](budget_predeclaration.json) — hosts `hyperx.com` (already confirmed) and `cdn.shopify.com` (new, justified below). The product page was re-fetched fresh and compared to Stage 11's saved copy: the two HTML documents are not byte-identical (minor dynamic content, e.g. cache-busting tokens), but **the 14-item gallery set is identical** between the fresh fetch and the saved snapshot. The corrected, DOM-based extraction method now includes an explicit completeness assertion (`expected=14`) instead of a filename heuristic — both the fresh page and the re-read saved snapshot pass it.

## 3. The 14 gallery items

Full list: [`card.json`](card.json) → `gallery_14_items`.

| # | Kind | Filename |
|---:|---|---|
| 1 | main product photo | `hyperx_quadcast_2_s_9a273aa_main_1.jpg` |
| 2–6 | annotated feature callouts | `annotated_1_future_en`, `annotated_2_dynamic_en`, `annotated_3_tap_en`, `annotated_4_versatile_en`, `annotated_5_redesigned_en` |
| 7–14 | angle photos | `9a273aa_angle_2` through `9a273aa_angle_9` |

## 4. The user-provided video — confirmed by DOM containment, not shared hosting

`https://cdn.shopify.com/videos/c/o/v/b05b09498da44727be948864df7222ac.mp4` was found **verbatim, offline, in the already-saved HTML** (3 occurrences) — inside `<video><source src="...">` tags nested in a `<deferred-media data-media-id="template--20613538611357__video_block_tTVMRn">`, under `<section id="shopify-section-template--20613538611357__video_block_tTVMRn">`. This section's template-id prefix (`template--20613538611357`) is the **same one** shared by all 14 image-gallery containers on this exact page. That DOM containment — not the shared `cdn.shopify.com` hostname — is what ties the video to this product; per instructions, the shared CDN alone was never treated as evidence.

A small bounded Range check (first 64KB only, per budget — the ~545MB file was never downloaded) confirmed: HTTP 206, `Content-Type: video/mp4`, a valid MP4 container signature (`ftyp` box), and a server-declared total size of 571,852,430 bytes.

**Cover image, tracked separately from the video itself:** `https://hyperx.com/cdn/shop/files/HX-QUADCAST-2-S-YouTube-tn-1080p_1920x.jpg` — fetched complete (163,180 bytes, byte count matches the declared total), hashed, and visually inspected: it explicitly reads **"HYPERX QUADCAST 2 S"** / **"GLOW UP."** over the same RGB-lit microphone on a desk setup with the HyperX logo — unambiguous, product-specific artwork.

## 5. Text sections

Full list: [`text_sections.json`](text_sections.json), read offline from the page's own `data-description` attribute — a heading+paragraph pair for each feature: *Dynamic Lighting Display*, *Tap-to-Mute Sensor*, *Versatile Multifunction Knob*, *Redesigned Detachable Shock Mount*, *Four Selectable Polar Patterns*, *Mic Status LED Indicators*, *HyperX NGENUITY Software*, plus the intro "Glow up." paragraph — richer, readable prose behind the terse JSON-LD description and directly corresponding to the 5 annotated gallery images.

## 6. Specification table — unchanged

The spec table already extracted in Stage 11 (acoustic element, polar patterns, frequency response, sensitivity, self-noise, SNR, connection type, weight breakdown, box contents, warranty) is carried forward unmodified — this stage found no discrepancy against the fresh fetch.

## 7. Open gaps and the one field needing user or dealer input

Full detail: [`card.json`](card.json) → `field_needing_user_or_dealer_input`. After this bounded check of the confirmed official pages (the product page in full, and `hyperx.com/pages/support` from Stage 11), the search is **stopped rather than continued indefinitely**, per instructions:

- **Exact product**: HyperX QuadCast 2 S – USB Microphone, Black, catalog seller article `9A273AA`.
- **Missing field**: an online/downloadable Quick Start Guide and its confirmed language. The spec table confirms one ships physically in the box; no PDF or web version is linked anywhere on the pages checked.
- **What's specifically needed**: either a direct URL to an official or dealer-hosted copy (with its language), or explicit confirmation to leave this open rather than search further, or — if a dealer source is wanted — the exact dealer domain plus confirmation it's allowed for this brand/category. **The current allowlist (Sulpak) is scoped only to a fixed LG home-appliance category set and does not cover HyperX or microphones** — no dealer fallback was invoked this stage, and none is available without a new, explicit domain decision.

This question was put to the user; independent parts of this stage's work (the gallery fix, video/cover evidence, and text-section extraction above) were completed regardless of the answer. **User decision (2026-09-23): leave the field open, do not search further for this product.** The manual status stands as recorded above — physically confirmed included, online document/language not confirmed, never claimed absent.

## Request log and budget verification

[`checkpoint.json`](checkpoint.json): **4 requests total** — 2 to `hyperx.com` (product page re-fetch, cover image), 2 to `cdn.shopify.com` (robots.txt, video type check) — 0 rejections, 0 protection stops. The video file was never fully downloaded.

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_gallery_root_cause.json`](offline_gallery_root_cause.json) — root cause of the 9-vs-14 discrepancy + video DOM-linkage evidence
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget, declared before any request
- `phase1_fresh_product_page_and_gallery_fix.json`, `phase2_video_and_cover_check.json` — the two live phases
- [`text_sections.json`](text_sections.json) — the 8 marketing text sections, offline extraction
- [`card.json`](card.json) — full 14-item gallery, video+cover evidence, gaps, and the user-input request
- [`checkpoint.json`](checkpoint.json) — request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–11.1 + catalog + registry integrity check
- [`raw/`](raw) — fetched HTML pages saved offline (video/cover image bytes hashed and discarded, per the no-raw-content rule)
- [`scripts/`](scripts) — all 7 scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v11_2.py` — checks that the corrected extraction finds all 14 gallery items via DOM grouping (not a filename/SKU substring), that the 5 previously-missed annotated images are identified, that the fresh fetch and saved snapshot agree exactly, that the video is confirmed MP4/reachable via a small bounded check without a full download, that its DOM containment (not shared CDN hosting) is the stated evidence, that the cover image is byte-verified and hashed, that no binary content is committed to the repo, that the budget was declared before any request and every request stayed on the two allowed hosts, that no dealer/other-brand host was contacted, that the manual gap is phrased as "unresolved" rather than absent, and that every prior stage (through 11.1) plus the catalog and registry remain byte-identical.

## Not started automatically

No dealer fallback (no applicable domain determined). No further manual/document search beyond what's reported here. No other HyperX row, brand, or general census.
