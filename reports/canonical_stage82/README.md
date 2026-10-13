# Stage 82 — canonical mapping cleanup and classification

Baseline commit: `6a6a20e4950334028e696873544debd48e461477`.
Frozen population: **1643 Stage 81 unsupported rows**, **206 literal label groups**. The original records are immutable; SHA256 `f3347d3517f27e479e235defa1a029877f70e38f32d4918128b2fc71f7ab9e98`.

| Class | Action | Rows |
|---|---|---:|
| A — technical | mapped | 836 |
| B — feature | feature | 415 |
| C — conditional/scoped | candidate | 105 |
| D — marketing | excluded_marketing | 70 |
| E — help/service | excluded_support | 39 |
| F — internal/headings | excluded_internal | 49 |
| G — parser artifact | parser_fixed | 7 |
| H — ambiguity/evidence gap | ambiguous | 122 |

Every row has exactly one class/action, reason, original provenance, corrected source when recovered, component/identity scope, and native targets for mapped outcomes. An extractor test passing does not make an unqualified historical row confirmed: two legacy compound SSR rows remain candidates.

## Mapping progress

**43 new canonical keys / 104 added product occurrences**. Raw rows assigned A/B include restored lineage to already-existing facts; they are not counted as newly invented attributes. Three former keys are renamed: native display resolution is unified, and headset sensitivity replaces a mouse/sensor label. No other prior canonical key is lost.

Native canonical/UI/Excel: **3610 rows / 103 products / 38 categories**. Duplicate keys: **0**. Technical sheet `Исходные поля и mapping` contains all **1643** original raw rows, including exclusions and ambiguity. It is not a source of product facts. All **1984 confirmed gallery assets** and their URL/SHA evidence are unchanged; no gallery completion was requested.

## Systemic repairs

1. Explicit parser-authored raw→translated/derived targets for scalar dimensions, modes, booleans and feature presence; normalization equality retains source/component isolation.
2. Audit provenance recovery: default/empty Stage 81 source attribution is corrected only when a qualified parser bank supplies an exact origin relation. Original attribution is preserved.
3. Apple common section mapper reused after order/Tech Specs identity qualification; Unicode heading aliases and missing language, accessibility, safety, environment, controls and compatibility sections handled without SKU hardcode.
4. Apple resolution/ppi extraction and case-size-scoped area/fit recovered. RF region, case materials, optional display/GPU configurations and tested acoustic configuration remain candidates.
5. Razer component SSR cells split at explicit labels; continuation fields and negative features retained. Headphone/microphone sensitivity and frequency columns remain separate, including frequency qualifiers.
6. PlayStation optical table continuation and laser subsections recovered; scope ends at the next known section. Exact CFI relation remains mandatory. Own feature headings retained when explanatory prose uses synonyms.
7. `Supported`/`Not supported` boolean semantics and Russian canonical labels/groups. Branded names remain intact. Technical raw evidence is exported separately from product facts.

These are shared semantic/extractor/audit classes, not per-input URL/value patches. No discovery, photo pipeline, document search or numerical readiness threshold is changed.

## Live and offline are separate

Actual live: **18 observations / 16 distinct frozen inputs / 11 brands**, all received fresh official data through existing workers. Initial representative jobs, extra exact-CFI/controller jobs and final affected reruns have separate phases. No historical response replay substitutes for those results.

All-103 parser qualification uses Stage 81 observations offline. It preserves already-proven same-order Apple enrichment overrides because that production step is separate from a standalone parser call. Only absent exact-CFI keys from the actual hardware verification are added to that qualification copy. Neither process is an additional live success.

Jobs request stages `[1,3]`, so a fresh representative DB has no requested gallery and reports full-card readiness accordingly. It is not evidence that a previously qualified adapter regressed. Existing photo/document proof stays in the full qualification copy. PlayStation's unchanged hardware-source flow fetches exact-CFI spec/identity PDFs; no manual search stage is requested and downloaded document inventory rows are zero.

## Remaining limits

**122 ambiguous rows** remain. Per-brand counts: {'Apple': 4, 'PlayStation': 25, 'Xbox': 14, 'Razer': 74, 'Xiaomi': 3, 'Dreame': 1, 'Electrolux': 1}. Most are historical raw representations whose product/variant owner path is not reproduced in the qualified saved source inventory. A known technical-sounding label alone does not justify transferring a current/default configuration. Other cases lack component parent, stable prose structure or a declared unit (for example, a die size printed with mm rather than an area unit). These raw values and exact reasons remain available; they are not hidden in marketing exclusions.

`classification.json`, `classification_groups.json`, `semantic_label_groups.json` and `remaining_ambiguous.json` expose all decisions. `category_inventory_38.json`, `native_output_checks.json`, `new_canonical_fields.json` and `live_verification.json` expose schema, output reconciliation, new keys and independent fresh observations. `Canonical_Stage82.xlsx` is the native local deliverable (Git-ignored).

## Validation and release

Final targeted semantic checks: **114 tests OK**, preserving the previous Apple/Razer/PlayStation and Stage 81 guards. Two complete pre-release runs passed **1906 tests** with immutable source manifests; final component-label/scope assertions add one test. Mandatory full release regression on final bytes is recorded separately before commit/push.

Native interaction checks cover all 11 brands. Read-only artifact-tool QA generated 89 sheet previews; its runtime exits 1 after reporting all files written, without a diagnostic exception. Native workbook row/formula checks are successful; the renderer tooling exit is not represented as pipeline failure or concealed as exit 0. Final label/group changes receive a fresh preview check.

## Final verdict

**Stage 82 PASS.** Post-PASS complete release regression on final bytes: **1907 tests OK**, 846.594 seconds, immutable source manifest. Final workbook SHA matches native content and four final read-only previews; all 11 interactive UI representatives pass. `git diff --check` passes. Remaining 122 ambiguity/evidence-gap rows are retained without unsupported confirmation.
