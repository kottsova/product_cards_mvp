# HyperX readiness-map update (Stage 14 → Stage 15 correction)

This file, not `reports/source_census_2026-09-23_stage13/readiness_table.md`,
is where HyperX's status update now lives. `readiness_table.md` is Stage
13's own artifact — Stage 14 edited it in place on the reasoning that it was
updating "the same stage's own artifact," but the table was written and
owned by Stage 13, not Stage 14. That was a mistake: past-stage artifacts
are supposed to stay byte-identical once the stage that produced them is
done. Stage 15 restored `readiness_table.md` to its exact Stage 13 bytes
(verified against the `Write` tool call that produced it, before any Stage
14 edit — SHA-256 `fd9ed8ab4b38eeb377ab39775c1da0c43eeff4e100ba12e854ce80e2a22766d6`,
confirmed identical to the restored file on disk) and moves the update here
instead, where it belongs to the stage that actually made the change.

This is the same content Stage 14 wrote into Stage 13's file, refreshed
with what Stage 15 additionally did (real URLs, a real identity-check
correction, real saved-page verification) — not a second draft from
scratch.

## Part 1 row — HyperX (`hyperx`)

| Brand / profile | Catalog scope | Confirmed official host(s) | Discovery route | Real Product page | Adapter in pipeline | Fields actually extracted | Tested on | Docs / media | Blockers | Next concrete step |
|---|---|---|---|---|---|---|---|---|---|---|
| **HyperX** (`hyperx`) | 41 products, 7 categories | hyperx.com confirmed — Shopify platform | Product page, human-confirmed URL per row (no crawl/guess) | **Yes, production** — 2 of 41 rows (9A273AA, A1KY6AA) have a real, human-confirmed URL wired into `KNOWN_URLS` and reach the pipeline via `worker.run_once()` on the real saved Stage 11/11.1 pages | **Yes** — `HyperXAdapter`, wired into `worker.py`'s `run_once()` since Stage 14, real `KNOWN_URLS` entries since Stage 15 | identity (JSON-LD `sku`), specs (DOM table), full gallery, description images, video — each field with url/evidence/role/confirmation | 2 of 41 rows reach `exact_variant` through the real pipeline (QuadCast 2S Black, Pulsefire Fuse); 1 of 41 is a confirmed real negative (Alloy Rise 75 keyboard, `#ABA` page vs catalog `#ACB` → `base_code_confirmed`, never `exact_variant`); 38 of 41 have no confirmed URL at all | Manual: still unresolved for both confirmed rows — a Quick Start Guide mentioned in box-contents text is never turned into a document link | **38 of 41 rows have no URL** — that is the real remaining gap, not code. A Stage 15 identity-check bug (JSON-LD `productID` wrongly treated as a second identity anchor that had to agree with `sku`) was found and fixed using the real saved pages; it would have made every real HyperX page report `mismatch` in production | Supply a human-confirmed URL for more of the other 39 rows; nothing else blocks adding them once a URL exists |

## Group A — corrected

**Bosch Home (bosch_de/home/uk), HyperX, Cudy** — HyperX is no longer "one layer short of a complete structural profile" alongside the other two; it has a real, production-wired adapter with 2 of 41 catalog rows actually reaching `exact_variant` end to end. Bosch and Cudy are untouched — no identity check, no adapter, still structural-only.

- **Reusable**: `product_tool/adapters/structured_page.py` (JSON-LD Product fields, DOM spec-table extraction, `data-media-id`/`data-fancybox` gallery, description images, video) — boundary-tested against synthetic Bosch/Cudy-shaped fixtures (Stage 14): JSON-LD/DOM-table extraction generalizes to both; the gallery extractor correctly finds nothing on their plain-`<img srcset>` pattern, since that attribute pattern is HyperX's Shopify markup, not theirs.
- **Stays separate**: identity. Bosch uses explicit gtin+mpn; HyperX is Shopify `sku`-based (JSON-LD `productID` is Shopify's own internal numeric id, not comparable to a catalog code — a real bug found and fixed this stage, see below); Cudy's identity strategy is still uncharacterized. No Bosch/Cudy identity or adapter exists.
- **Bosch remains the highest-ROI *unstarted* step** in this group: 3 real structural pages and the strongest identity signal in the project, still not promoted to a real adapter.

## Stage 15 — what changed, stated plainly

- **2 of 41 HyperX catalog rows now have a human-confirmed, production `KNOWN_URLS` entry**: 9A273AA (QuadCast 2 S microphone) and A1KY6AA (Pulsefire Fuse mouse) — both verified against real saved Stage 11/11.1 pages (`reports/source_census_2026-09-23_stage11/card.json`, `reports/source_census_2026-09-23_stage11_1/additional_rows_and_adapter_status.json`), not guessed or matched by name similarity.
- **A real identity-check bug was found and fixed**: `check_identity()` treated JSON-LD `sku` and `productID` as two anchors that had to agree. On all 3 real HyperX pages sampled (microphone, mouse, keyboard), Shopify's `productID` is that platform's own internal numeric id, unrelated to the merchant `sku` — the old rule made every real page report `mismatch` even where `sku` matched the catalog exactly. Stage 14's synthetic fixtures never populated a realistic, differing `productID`, so this was invisible until real captured pages were used. Fixed: `sku` is now the sole identity anchor; `productID` is a fallback only when `sku` is absent.
- **The negative case (`7G7A4AA#ACB` keyboard) is now proven against a real saved page**, not a synthetic one: the real Alloy Rise 75 page's own `sku` is `7G7A4AA#ABA` (US layout), confirming a genuine regional-suffix mismatch against the catalog's `#ACB` (RU) row — `base_code_confirmed`, never `exact_variant`. This row is deliberately **not** in production `KNOWN_URLS`, since its only found candidate page is a confirmed mismatch for this exact row.
- **38 of the other 39 HyperX catalog rows remain with no confirmed URL** — `official_url_needed`, never guessed. This stage did not attempt a new brand census or search for more URLs; only the 2 rows a human had already confirmed were wired in.
- **A real network-safety incident happened and was fixed during this stage**: populating `KNOWN_URLS` broke an invariant 3 pre-existing tests in `tests/test_dns_fallback.py` relied on (a bare `HyperXAdapter()`/no `hyperx_adapter_factory` override safely returning "no URL" for 9A273AA). Once 9A273AA became a real production URL, those 3 tests' default (real-session) HyperX adapter could reach the real hyperx.com URL during an ordinary offline test run. This was caught by the test suite itself failing (`status == "done"` where `"needs_review"` was expected), consistent with a live request having actually succeeded — the sandbox this session ran in does have outbound DNS/network resolution. Fixed by explicitly injecting `hyperx_adapter_factory=lambda: HyperXAdapter(urls={})` in all 3 tests. Re-ran the entire suite wrapped in `enforce_policy_aware_fetch_only()` afterward (823/823 pass) to confirm zero real network calls remain possible anywhere in the suite. See `report.md` for the full incident note.
