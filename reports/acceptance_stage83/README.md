# Stage 83 — production acceptance recovery

Date: 2026-10-15. Base HEAD: `a866276d8a3ac349b79594307533ba0dee851b6d` (Stage 82).

Actual UI: `http://127.0.0.1:8765/`. Final qualification uses the ordinary embedded worker, default adapter factories and stages `[1,2,3,4,6]`. No PDP/capture fixtures or adapter/provider injection supplied live results. Historical observations remain separate from new results. Full regression status is recorded in `final_regression.json`; publication requires exit code 0. The earlier `full_regression.json` is an intentionally interrupted run, stopped when visual QA identified the remaining display-order issue.

## LG root cause and known-good comparison

Original user product **101**, batch `12ba4aacda4b41a98ed111c28e584d55`, `тест.xlsx`, row 3:

- `search_code = Паровой шкаф LG Styler S3WER`;
- `alternate_code = S3WER.ALWPCOM`;
- `name = Паровой шкаф LG Styler S3WER`, brand LG;
- confirmed mapping: brand=3, search_code=2, fallback_code=1, name=2.

The model was retained in the Excel row. The runtime treated the descriptive primary cell as an article and normalized it to `ПАРОВОЙШКАФLGSTYLERS3WER`. It then searched this key in LG discovery. The structured alternate article was not selected. Worker and LG adapter did execute; this was not an absence of official sources or a readiness gate before discovery. The failed job `ce1b055b89a04e22b0ba7193ee069c2c` ran 13:08:45–13:09:25 UTC. Its official miss triggered sitemap/other-region/external fallback with the wrong identity query. The external browser also reported runtime unavailability, a secondary failure that did not establish product absence.

The last qualified Stage 81 S3WER input (frozen ID 39) used `S3WER.ALWPCOM` directly, as did earlier user product 65. LG used the default factories in that harness. The divergence begins at effective input selection, before sitemap matching, not at an LG URL filter. Both old and repaired successful routes admit the KZ PDP by its explicit `data-pim-sku=S3WER.ALWPCOM.EEAK.KZ.C`; RU is only `base_model` and remains so.

The common `product_input.resolve_product_input` now uses an explicit structured fallback only when the primary is clearly descriptive. This is a query choice, not an official identity claim. Valid primary articles, numeric hardware identifiers and explicit multi-component kits remain intact. The SQL cells, original row and frozen Stage 81 dataset are not rewritten. `jobs.get_product` and `storage.get_batch` share this resolution, so worker, UI, export and readiness see the same effective query.

Sanitized original evidence: [original_lg_failure.json](original_lg_failure.json). The full local DB backup and unrelated supplier rows are excluded from Git.

### Actual repaired route, fresh UI product 118

The same raw user input was imported through the working upload/confirmation UI, then selected in its batch form. Full events, sources, raw facts and trace: [cross_brand_final/118.json](cross_brand_final/118.json).

| Stage | UTC timestamp | Input / result / skip reason |
|---|---|---|
| Import confirmation | 14:13:43 | Same raw cells, no guessed SKU; explicit field mapping saved |
| Queue | 14:13:58 | Actual POST `/batches/24a7ccfa0a7040ef869fac71c7c783fd/search`, HTTP 303 |
| Dispatch / resolution | 14:13:59 | Descriptive primary → structured fallback `S3WER.ALWPCOM`; identity_claim=false |
| LG adapter | 14:14:00.014 | `LGAdapter`, `LGRUDocumentAdapter`; injected_factory=false |
| Official KZ sitemap | 14:14:00.925 | 3988 published product URLs |
| Candidate generation | 14:14:00.996 / 14:14:01.088 | Full article has no slug; base `S3WER` yields published KZ PDP |
| KZ identity / extraction | 14:14:03.687 / .759 | Explicit PIM full SKU; 10 raw specs, 20 gallery candidates |
| RU sitemap / PDP | 14:14:08.891–14:14:12.719 | 11383 URLs; published RU model PDP, base_model; 45 raw specs, 39 candidates |
| Other-region / external fallback gate | 14:14:12.728 | Skipped because a fresh exact official KZ PDP is already verified; 32.25 s remained |
| Persistence / resolution | 14:14:17.299 | 56 facts, 50 resolved keys, zero real conflicts; 54 final canonical rows |
| Documents, photos, readiness | Finish 14:14:50 | Existing exact-article verified manual remains available; 20 identity-confirmed photos; export_ready |

Original user product **101** was also reprocessed through the actual UI form, not merely replaced by the new test row: [lg_recovery/101.json](lg_recovery/101.json), 13:56:33–13:57:39 UTC, 54 final attributes, 20 confirmed photos, `export_ready`. Original S40T product 109 also recovered, 35 attributes / 59 photos / `export_ready`. Evidence retention is preserved: a weaker or empty refresh does not replace a saved full-SKU source.

## Runtime and production parity

Initial listener: PID 1484, parent 20340, started the prior day; command snapshot in `initial_runtime.json`. Its precise imported Python bytes cannot be reconstructed retrospectively. Current HEAD alone cannot prove which source bytes a long-lived process loaded. The repaired server was restarted deliberately. Each new job records PID, executable, argv, observed process start, HEAD, dirty state and a SHA256 manifest of production source files. `/diagnostics/runtime` exposes the same startup identity.

The first compared UI and direct live runs share source fingerprint `954dfda4bc912f8133cdac8c57cc2051758ff97b48137906ea7782b96bf07f58`. `production_dispatch`, effective input resolution, per-provider discovery, sitemap candidate/open/identity decisions, extraction/persistence, fallback skip reasons, resolution and final readiness are permanently recorded with timestamps. Apple additionally distinguishes discovery-not-started, started, official miss, identity rejection, extraction empty and readiness failure.

The new all-brand batch form delegates to `jobs.enqueue`, exactly like a single-card action; the same `worker.run_once` dispatches every brand. Existing LG-specific controls remain available. The deterministic regression traverses the real FastAPI batch POST and direct enqueue/run_once with the same fake transport, comparing providers, persisted facts, identity and readiness. This test is offline; live qualification below is independent.

The old Stage 81 report used `manuals_required=False` for one headline readiness result, while it separately stored `readiness_with_documents` matching UI policy. Some brands, including Dreame, also received explicit browser factories. The new acceptance harness uses no injected factory and evaluates standard UI readiness. Dreame succeeds through its default HTTP adapter; no transport change was needed.

### Six actual live inputs

Inputs: current user S3WER, S40T and iPhone; Samsung/Xiaomi/Dreame unchanged known-good Stage 81 inputs. `cross_inputs.json` records provenance; the frozen dataset is untouched. Import screenshots and actual batch mapping are retained. Photos below count identity-confirmed entries, not a claim that every gallery candidate was byte-verified in this stage.

| Model | Final UI ID | Canonical specs | Confirmed photos | UI | Direct, same prior evidence |
|---|---:|---:|---:|---|---|
| LG S3WER.ALWPCOM | 118 | 54 | 20 | export_ready | export_ready |
| LG S40T | 119 | 35 | 59 | export_ready | export_ready |
| Apple iPhone 18 Pro, input A3714/256GB/Silver | 120 | 82 | 1 | export_ready | export_ready |
| Samsung QE55QN90FAUXCE | 121 | 109 | 8 | export_ready | export_ready |
| Xiaomi 15 | 122 | 23 | 142 | export_ready | export_ready |
| Dreame Z30 | 123 | 8 | 69 | export_ready | export_ready |

Both UI runs (initial/final) reached 6/6 actual official data and export_ready. The final fresh UI run took 51/21/14/47/28/36 seconds by job timestamps. Direct same-history jobs took 55.67/23.13/14.09/48.30/25.57/33.95 seconds.

[production_parity.json](production_parity.json): all 6/6 pass all seven comparisons: dispatch, discovery provider set, exact official source/model/match relation, normalized source facts, canonical values/status/conflict, raw semantic evidence, complete readiness result. Direct jobs use separate DB/log state, actual fresh discovery and the original user's prior verified evidence.

An additional completely empty-DB live run is preserved under `direct_production/`. It found all six models and the same product data; LG S3WER was `export_ready_with_gaps` because no prior verified manual existed in that DB. User UI correctly reuses an earlier verified manual for the identical article. Repeating direct production with the same original history eliminates that difference. This is an evidence-state difference, not a provider or readiness-policy mismatch, and it is not hidden by a manual-policy override. DB files/history are local-only and are not published.

### Release confirmation after the final display fix

Visual QA found an English `paired` left after a longer accessory replacement consumed `with`. The generic relation is now localized before accessory phrases. Both the source raw value and normalized facts remain unchanged. The added deterministic condition check passes in `localization_final.json` (7 tests OK).

All six models were then run live again through the UI and through direct default production with the same original history. `cross_brand_release/` and `direct_release_shared_history/` both give 6/6 export_ready with unchanged source/spec/photo counts. [production_parity_release.json](production_parity_release.json) again passes all seven comparisons for all six models. Both processes share final source fingerprint **`7d9921bff812caaa48aacc419e24f7660ac5acef9c35ca1c00bd9845223e42cc`**. The original current Apple product was also rerun (`current_apple_release/`); export assertions, all ten read-only renders and UI screenshots were refreshed afterward. The complete final regression starts after this production source freeze.

## Semantic fields, localization and raw evidence

The shared normalizer applies closed structural grammars without a brand argument. A block is decomposed only if every clause is recognized and no ambiguous duplicate/configuration alternative remains. Unknown residual clauses or multiple possible charging transports retain the complete original fact. Every child keeps the full raw label/value/section; card evidence separately records the exact rule, source URL and children. Existing confidence thresholds and source identity rules are unchanged.

For the current iPhone's live model Tech Specs, 7 source blocks become 38 child facts (37 distinct semantic keys; spatial audio appears in two source blocks and is displayed once):

| Before: one source block | After |
|---|---|
| MagSafe and wireless charging | Separate MagSafe and Qi2 maximum power, magnet array, alignment magnet, NFC accessory identification, magnetometer |
| Two fast-charge scenarios | USB-C and MagSafe each have support, target %, time, minimum adapter power and conditions |
| Audio Calling | Eight separate calling/audio features |
| Audio Playback | Supported formats, spatial playback and volume limit |
| Video Playback | Supported formats, HDR formats, AirPlay output |
| USB-C support list | Charging, DisplayPort, data standard, maximum data rate |
| Four brightness modes | Typical maximum, HDR peak, outdoor peak, minimum brightness |

The previous successful pre-decomposition Apple production capture contained 52 stored/resolved rows, with 50 confirmed. Current model extraction still supplies the same 50 raw model fields plus configuration overlay; after decomposition/deduplication the current card has **83 stored facts, 82 resolved/canonical attributes and 80 confirmed model specs**. The other two rows are the supported configuration overlay, not an exact commercial SKU claim. This is expanded semantics from real sources, not a relaxed threshold or substituted fixture.

Examples in both actual UI and Excel: `Мощность беспроводной зарядки MagSafe, Вт = До 25 Вт`; `Мощность беспроводной зарядки Qi2, Вт = До 25 Вт`; `Идентификация аксессуаров NFC = Да`; `Магнитометр = Да`; USB-C time `Около 15 мин`, MagSafe time `30 мин`; minimum adapter powers remain `Не менее 60 Вт` and `Не менее 35 Вт`. Declared bounds and accessory conditions are retained. Brightness values are 1000/1600/3000/1 нит in distinct fields.

Ordinary terms use conservative Russian presentation: Video playback → Воспроизведение видео; Fast-charge capable → Поддержка быстрой зарядки; FaceTime audio → Аудиозвонки FaceTime; boolean capabilities → Да/Нет. Proper technologies and formats remain named (MagSafe, Qi2, USB-C, Dolby Atmos, HEVC, H.264). Raw English text is not rewritten. Long camera descriptions with unqualified interdependent clauses remain whole; unknown prose is not guessed into smaller facts. `5G` is preserved as cellular technology, not converted to grams.

System Requirements is grouped under **Совместимость и системные требования** in UI and the Excel attributes/schema tabs. Explicit help-only prose is omitted from ordinary projection, while raw DB evidence remains. Configuration input stays separate from official facts. A supported model/color relation is not promoted to an exact supplier commercial SKU or regional radio identity.

### Current user's Apple UI and Excel

The original current user iPhone **92**, batch `6cb1a747ecd84b1ab9f079a14eeac52d`, was rerun through the working UI on final code, 14:17:16–14:17:30 UTC, `export_ready`. It obtained the published PDP and Tech Specs and a decoded exact-model/color official image, not an old capture.

[ui_qa.json](ui_qa.json) asserts exact separate visible values, compatibility group, actual image load and original LG product 101 readiness. Screenshots are under `qa/`.

`verify_export.py` downloaded the actual user batch's `/export.xlsx`, not a separately authored result workbook. [export_qa.json](export_qa.json): **87 total product columns (5 identifiers + 82 attributes), duplicate columns=0, formula errors=0; 38 children retain full raw values from 7 blocks**. Raw evidence is visible in `Семантика и исходные значения`. The other seven user rows have not been run by this acceptance task and remain honestly unverified; this report does not claim their readiness.

Artifact Tool imported the workbook read-only, inspected it and rendered all 10 sheets; PNGs were visually checked. Its native renderer exits 1 after writing all requested outputs and printing completion (also observed while creating the input sheet). Valid ZIP/XML, openpyxl read-only assertions, all 10 PNGs and UI checks independently verify the actual artifacts. Production export code, not Artifact Tool, produced the tested user workbook. Large ambiguous source paragraphs still require Excel's formula bar/detail sheet to inspect their complete text.

## Regression and publication

- Targeted production/UI/Apple/LG/canonical regression: **92 tests OK**, source tree unchanged. After the final display correction: **7 focused semantic/parity tests OK**; the complete final suite includes these checks.
- New deterministic tests cover independent semantics, charging bounds/conditions, ambiguous preservation, raw evidence export, compatibility grouping, 5G preservation, safe input resolution, actual batch-route/direct-worker parity.
- Stage 37's existing test still asserts five stage controls in its LG form and now separately asserts five in the new general form; no old assertions were dropped.
- Exact authorized hash pins were updated for changed source files. Historical guards and frozen reports/datasets were retained.
- Full regression: see `final_regression.json`; PASS and publication require exit_code=0 and production_tree_unchanged=true.
- `git diff --check` passes before publication. Commit/push and clean-tree verification follow only after full regression passes. The published commit is reported in the final response; no self-referential hash is embedded here.

Qualification verdict: **Stage 83 PASS**. Live acceptance, release UI/direct parity, UI/Excel raw preservation/localization and the complete final regression pass. See `qualification_final.json` and `final_regression.json` for machine-readable evidence.

Final complete regression: Ran 1923 tests in 978.013s; OK. Production source tree unchanged during the suite: true.
