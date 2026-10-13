# Stage 81 — cross-brand exhaustive attributes + photos audit

Frozen dataset: **103 inputs / 11 brands / 38 supported categories**. Selection was frozen before any run; no inputs were replaced.
`SHA256: 58e20783d601ba953f04edaab49471e398ebf05bc5ce38cabcdab03e6ca04894`

Actual live: **103/103 official-data observations**, followed by **17 fresh affected reruns**. The qualified DB consolidates original live observations; consolidation and parser/UI QA are not additional live successes. Baseline, final live, delta live and image continuation evidence are kept separately. Same-run publisher/catalog cache is not historical capture replay.

No manual search stages were requested. `stages = [1,2,3,4]`; downloaded document inventory rows = 0. Apple procurement SKU PDF and PlayStation CFI documents were used only where model/hardware identity required them. Existing document evidence is retained under its original identity.

Canonical output: **3509 rows**; native UI and Excel long attribute sheet: **3509 rows**. LG dimension aliases merge by the same scoped axis through the existing resolver; all source parents and real conflicts remain visible. Accepted source facts with unexplained projection loss: **0**. This does not assert that every raw paragraph has a safe canonical mapping.

Official gallery: **1984 unique valid confirmed assets / 1984 byte-verified**. Selected subset: **709**. All confirmed assets appear in UI and `Фотографии`; unconfirmed assets remain candidates. Broken/blank/tiny/non-image media and unresolved URL templates are recorded as excluded, not silently dropped.

Official color confirmed for **45/103** inputs. Other colors remain explicitly unconfirmed; input configuration is not official evidence.

| Brand | Inputs | Unique raw rows | Canonical | Confirmed gallery | Byte verified | Selected | Ready |
|---|---:|---:|---:|---:|---:|---:|---:|
| JBL | 6 | 209 | 182 | 66 | 66 | 65 | 5 |
| Samsung | 21 | 1032 | 1052 | 182 | 182 | 182 | 18 |
| LG | 12 | 1066 | 921 | 707 | 707 | 303 | 6 |
| Apple | 9 | 2533 | 326 | 27 | 27 | 22 | 9 |
| PlayStation | 7 | 1067 | 79 | 13 | 13 | 13 | 3 |
| Xbox | 7 | 180 | 104 | 11 | 11 | 11 | 6 |
| Razer | 8 | 302 | 154 | 17 | 17 | 17 | 5 |
| HyperX | 7 | 131 | 122 | 42 | 42 | 42 | 6 |
| Xiaomi | 10 | 202 | 198 | 543 | 543 | 23 | 10 |
| Dreame | 6 | 88 | 83 | 264 | 264 | 12 | 6 |
| Electrolux | 10 | 374 | 288 | 112 | 112 | 19 | 7 |

## Artifacts

- `dataset.json`, `category_coverage_frozen.json`: frozen selection and category coverage.
- `qualified_live/observation_manifest.json`: original actual observation/job and phase per ID.
- `qualified_live_audit/loss_report.json`: every raw classification, candidate/rejection reason and stored fact → output lineage.
- `qualified_live_audit/category_inventory.json`: observed category → group → attribute union, roles, canonical keys, brands and model IDs.
- `qualified_live_audit/gallery_report.json`: every saved/alias/excluded gallery row, role, relation, URL, dimensions, MIME, SHA and completion state.
- `qualified_live_audit/color_resolution.json`: input color, official result, exact proof and ambiguity.
- `CrossBrand_Stage81.xlsx`: native application export; local XLSX is intentionally Git-ignored.
- `qualified_live_audit/native_ui_excel_qa.json`, `qa/final_ui/interaction_checks.json`: native output and browser interaction checks.

## Fixed common failures

1. Selected-only photo export and small gallery subsets; all valid owned assets now remain independently available.
2. Rendition dedupe depended on equal SHA: resized bytes differ. Both published asset identity and equal bytes are now independent duplicate proofs; confidence/color/layout scopes remain isolated.
3. Full photo metadata was tied to volatile SQL IDs. Stable source/asset/URL proof survives refresh.
4. GIF was decoded as text despite format support; animated blank first frames were treated as placeholders. Binary preservation and sampled animation content are tested.
5. Video and `{width}` / `*img*` templates entered image inventory. They are excluded with explicit reasons, without guessed URLs.
6. Component/package dimension keys collided or lost published axis order; component scopes and explicit unit/order are preserved.
7. Negative feature flags disappeared with empty-looking values, while missing physical quantities became false. Features survive; absent quantities remain unknown.
8. Xiaomi mixed memory, conditional dimensions and eSIM sections dropped model-stable fields. Shared technologies/axes/connectivity recover independently of candidate capacities/colors/regions.
9. Apple minimum/maximum brightness became a conflict; distinct modes now remain separate. Optional nano texture/TB5/configuration claims stay candidates.
10. Branded Dreame and Electrolux capabilities were treated as prose; exact-owned capability presence is retained without admitting promotional percentages.
11. Manuals ran during attributes/photos-only Apple refresh and prior document proof could be overwritten. No-search gates and identity-scoped historical proof retention are covered.
12. English generic labels and missing parent groups; common vocabulary now supplies Russian labels and scoped groups while branded names remain intact.
13. Long SHA metadata expanded CSS grid tracks, causing overlapping images/click interception. Bounded tracks, wrapping and normal clicks are verified on all 11 brands.

## Completeness limits

Attribute inventory is complete for the observed frozen output, not a claim that the entire category universe or every free-text source paragraph is canonically understood. Raw unsupported/conditional lines remain in the loss report with reasons; source conflicts are not suppressed.
Photo completeness covers published assets admitted by existing model/configuration policy. Unproved color/layout/bundle/hardware relations stay candidates. PlayStation hardware inputs without a matching appearance source and the synthetic Electrolux revision are not forced ready.
A 8540-second wall interval occurred in LG gallery completion while the ordinary worker job itself completed in six seconds. The overlapping offline regression also accumulated a long wall interval. Missing in-flight trace prevents attributing that interval to a particular HTTP/browser cause. Later gallery starts/ends/errors are durable in `gallery_timing.jsonl`; no speculative root cause is selected.

## Final qualification and release validation

**Stage 81 audit PASS.** All 11 adapters retain controlled-use qualification; this audit does not make unresolved cards ready. 81 inputs are ready and 22 keep explicit evidence gaps.

Post-PASS full offline regression: **1896 tests OK**, 759.078 seconds; source manifest unchanged. Separate cross-brand representatives: **231 tests OK**; final dimension/lineage checks: **19 tests OK**. Native UI/Excel counts agree for all 103 inputs, with no duplicate canonical keys or formula errors. Interactive UI checks pass for all 11 brands. `git diff --check` passes.

Excel visual QA generated 88 sheet previews and reviewed representative layouts. Artifact renderer exited with code 1 after reporting all renders saved, without an explanatory exception; this tooling exit is recorded separately from successful native workbook validation. Previews precede the final cosmetic Russian dimension-label suffix cleanup; final native export SHA and row counts are checked in `native_ui_excel_qa.json`.

**Attribute completeness:** full normalized observed schema inventory for all 38 categories; no unexplained loss of accepted source facts between canonical output, UI and Excel. Unsupported raw mappings and conditional/ambiguous source statements remain in the loss report, so exhaustive understanding of all source prose is not asserted.

**Photo completeness:** qualified observed gallery is complete for all 11 brands (1984/1984 valid confirmed unique assets). Missing exact appearance/configuration relations, particularly PlayStation hardware, Razer layouts and HyperX RU, remain candidate/evidence gaps rather than confirmed galleries for those variants.
