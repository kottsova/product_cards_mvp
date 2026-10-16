# Stage 84 — ordinary supplier row interpretation

Date: 2026-10-16. Base: `79f2af9117bf8e865fe9415cffb4c2bbe90a0fe1` (`Stage 83`).

Qualification is scoped to input interpretation and ordinary production dispatch. It does **not** claim that every live card is ready. [qualification.json](qualification.json) contains assertions and the final full-regression result; publication requires `PASS`. Frozen earlier stages are unchanged.

Final result: **Stage 84 PASS**. 29 evidence assertions, 5/5 actual official-data rows, 5/5 export_ready, 1938 full-regression tests OK and 73 focused tests OK. No source bytes changed during the final full regression.

## Input rules and persistence

The input remains `Наименование + Артикул + Бренд`. An explicit brand column is authoritative, even if the title omits the brand; conflicting title text produces a warning. Category is inferred from category words, then recognized model families. Specific categories (robot vacuum, wet/dry vacuum, styler) precede general vacuum/cabinet terms.

The shared `input_interpretation` parser uses closed model-family grammars and structured model tokens. It keeps commercial qualifiers such as Pro, Ultra, Plus, 5G and generation/year where meaningful; it separates explicit color, RAM/storage, screen/case size, layout, switch, region, bundle/station, edition and connectivity hints. LG sales suffix stays with the supplier article, not the base model. A recognized explicit Model column remains optional and can override the extracted model. Apple hardware code `A3714` is not treated as an iPhone marketing model.

Resolution/dimension strings (for example `1920x1080`), memory standards and technical quantities are excluded from generic model-code candidates. Supplier articles containing path separators use hashed document-cache filenames and cannot become filesystem paths.

Every extracted field records value, raw text, source and confidence. Contradictory model/color tokens remain candidates; no first candidate becomes the chosen input model. Discovery may investigate reasonable candidates, but ambiguous input blocks overall readiness and confirmed-photo identity. Unknown names retain article/original-name fallback; this parser is not a claim to recognize every future product name.

Query plan: extracted model candidates → structured article → normalized model variants → original name fallback, deduplicated. Existing adapters receive a clean model and separate input configuration through their compatibility interfaces. LG receives the base model in its existing published catalog search. Apple, Xiaomi, Dreame and JBL use model-first discovery. Supplier identifiers remain available for exact matching, and are never promoted to official facts without evidence.

Normalized fields live in the existing DB identity JSON under `input_interpretation`. Existing identity/revision classes and readiness thresholds are unchanged. Original source cells remain in `original_values_json`; `name` and supplier article remain available unchanged. Configuration hints describe supplier input, not official configuration confirmation.

## Header aliases

| Role | Accepted required examples |
|---|---|
| Name | Наименование, Название, Товар, Product Name, Name |
| Supplier article | Артикул, Код, SKU, Part Number, Supplier SKU |
| Brand | Бренд, Brand, Производитель |

Matching is case/whitespace normalized. Existing additional aliases and optional Model/category/configuration columns are retained. Tests cover all five header triples without Model/category columns.

## Extraction examples

| Supplier title | Extracted model | Category | Input configuration |
|---|---|---|---|
| Паровой шкаф LG Styler S3WER | S3WER | Паровой шкаф | Article `S3WER.ALWPCOM` separate |
| Телевизор LG 86NANO81A6A | 86NANO81A6A | Телевизор | — |
| Стиральная машина Samsung WW90T554CAT | WW90T554CAT | Стиральная машина | — |
| Apple iPhone 18 Pro 256GB Silver | iPhone 18 Pro | Смартфон | storage 256GB, color Silver |
| Смартфон Xiaomi 15 12/256GB Black Global | Xiaomi 15 | Смартфон | RAM 12GB, storage 256GB, Black, Global |
| Пылесос Z30 Cordless Stick Vacuum Black, brand Dreame | Z30 | Вертикальный пылесос | Black; brand need not occur in title |
| Dreame H14 Pro Wet and Dry Vacuum | H14 Pro | Моющий пылесос | — |
| Dreame X50 Ultra Complete with auto-empty station | X50 Ultra | Робот-пылесос | Complete bundle and station separate |
| Наушники Tune 520BT White, brand JBL | Tune 520BT | Наушники | White |
| HyperX Alloy Origins 65 Black RU Red | Alloy Origins 65 | Клавиатура | Black, RU layout, Red switch (medium confidence) |
| LG S3WER / S5BB Black White | No chosen model; S3WER/S5BB candidates | Паровой шкаф if explicitly named | Black/White ambiguous; no chosen color |

Additional deterministic coverage includes Apple Watch 46mm, Razer 2022 generation/Quartz, Xiaomi Smart Air Purifier 4 Lite (not a smartphone), explicit-model validation and contradictory brand/name. RAM/storage labels are consumed by one capacity each: both `16GB RAM 512GB SSD` and `RAM 16GB SSD 512GB` produce RAM 16GB/storage 512GB. Recognized JBL Bar/HyperX QuadCast/Pulsefire/Razer Huntsman/Apple AirPods families also infer category without a generic product noun. Inferred brand provenance survives an unchanged confirmation even when no explicit Brand column exists.

## UI before and after

The identical workbook was uploaded through the old Stage 83 application in an isolated local baseline DB, and through the new working application. No frozen report or original user batch was edited.

- [Before screenshot](qa/preview_before.png), [DOM observations](ui_before.json): no extracted-model/configuration columns, Apple category empty, Dreame generic vacuum category.
- [Final screenshot](qa/preview_final84_retry.png), [DOM observations](ui_final84_retry.json): all eight rows show automatic model/category/configuration, field sources/confidence and ambiguity candidates. Confirmation used **zero field edits**. Optional correction controls remain available.
- [Input workbook](Ordinary_3_columns.xlsx), [render](qa/input.png), [input provenance](input.json). Exactly three columns; `SUP-*` identifiers are intentionally opaque synthetic QA supplier identifiers, not invented manufacturer SKUs.

Input/upload SHA256: `04bdc61c16bdab276e97fd84d2c8c1689d1c6cf447b58e6caa806739f32835f2`. It is unchanged before/after import, preview, confirmation and batch. XLSX was authored/rendered with Artifact Tool. The native renderer produced the verified workbook/PNG successfully, then returned exit 1 during shutdown; the saved files were independently opened by the actual application. Unit fixture workbooks use the repository's existing test utilities.

## Actual production batch

Final batch: `d126a07c15ea47b1a416430ed65cb89a`. Ordinary UI upload → unchanged preview confirmation → selected first five rows → ordinary batch POST → embedded worker/default factories/stages `[1,2,3,4,6]`. All eight rows were imported; the other three exercise preview hints/ambiguity and were not claimed as live runs. [Final summary](live_final84_retry/summary.json), [initial summary](live_initial/summary.json). Earlier recovery/release runs remain in separate directories; final qualification uses fresh jobs after all production fixes.

| Brand/model | Product | Initial specs / confirmed photos | Final specs / confirmed photos | Final readiness |
|---|---:|---:|---:|---|
| LG S3WER | 164 | 54 / 20 | 54 / 20 | export_ready |
| Apple iPhone 18 Pro | 165 | 80 / 0 | 82 / 1 | export_ready |
| Xiaomi 15 | 166 | 23 / 142 | 23 / 142 | export_ready |
| Dreame Z30 | 167 | 8 / 69 | 8 / 69 | export_ready |
| JBL Tune 520BT White | 168 | 0 / 0 | 30 / 11 | export_ready |

**5/5 actual live official data, 5/5 ready.** Each product JSON under `live_final84_retry/` contains runtime fingerprint, timestamps, dispatch/discovery trace, sources, raw facts, canonical specs, photos, input interpretation and readiness. Final live source fingerprint: `186ff8753fffb091a43a973bbf31a615023ff681a1ddaf3e767268b8971971c4`. Photos count identity-confirmed gallery entries; this stage does not claim a new byte-verification pass for every existing image. Optional manuals use existing policy; no thresholds were lowered.

Apple's actual catalog → exact PDP → model-scoped Tech Specs succeeded throughout. Early published Buy transitions returned HTTP 503; those runs honestly remained not_ready (80 model specs, no confirmed photo). Later fresh HTTP requests followed the published link to `https://www.apple.com/shop/buy-iphone/iphone-18-pro` and returned HTTP 200. The live Store payload confirms 256GB/Silver and supplies its exact-color image; final count is 82 specs / 1 photo / export_ready. No Store selection/configuration/photo facts were fabricated or copied from Stage 83 captures. The precise remote cause of earlier HTTP 503 is unknown; it is not attributed to the input parser.

JBL required a model-first integration fix in addition to parsing. An opaque supplier identifier cannot be expected to resolve as a JBL SKU. Native official search currently returns HTTP 404; several regions have persisted access stops, which were respected. The existing regional resolver now also tries the normalized extracted model token. Its actual `id.jbl.com/TUNE520BT.html` response publishes a master inventory (`utag_data_dynamic`, aligned product_name/product_sku/product_variant arrays), but no normal product details. The common adapter follows only published matching model/color variants, then **revalidates the returned PDP** using coherent Product name/SKU/MPN/context. The White PDP at `id.jbl.com/over-ear-headphones/JBLT520BTWHT.html` supplied 36 accepted raw specs, 30 final canonical attributes and 11 exact-color gallery photos. `SUP-TUNE520-WH` remains unconfirmed as a retail SKU; no supplier→official SKU relation is invented. The older no-input-context SKU path and its guards still pass tests. External Google/Bing fallback uses existing bounded search; no challenge or host stop was cleared/bypassed.

QA's first final-run console output hit Windows cp1252 encoding after it had successfully uploaded/queued jobs. The observation collector was restarted in UTF-8 **without enqueueing jobs again** (`--observe`); IDs/timestamps prove these are the same actual UI jobs. This was a report-output issue, not production failure.

## Regression and release

New deterministic cases cover header aliases, full upload/confirmation/default-worker dispatch, unchanged original bytes/cells, model/category/configuration separation, brand authority, ambiguous input, photos, opaque JBL supplier codes, published master inventory selection and mandatory final PDP identity revalidation. They also cover path-like supplier identifiers (hashed cache names, no path escape) and unknown-model title discovery (no premature invalid-SKU return). They are explicitly offline and do not count as live success. The final focused suite passed [73 tests](targeted_final.json), including the existing Stage 81 and JBL Stage 62/63 tests.

Early serial attempts were stopped for demonstrated extra-DB-read, RAM/SSD adjacency and supplier-derived cache-path issues; their logs are preserved separately and are not counted as passing suites. The first parallel run covered the standard suite plus inherited alias cases and exposed one real failure: monitor resolution `1920x1080` was treated as a second model, so the new ambiguity guard withheld 11 Samsung photos (98 instead of 109). The general token filter now excludes dimensions/resolutions, memory-standard tokens and technical quantities, without suppressing ambiguity or changing readiness thresholds. All 49 targeted Stage 84 + Samsung worker tests then passed with the original **109-photo** assertion unchanged. The failed full run remains in `regression_monitor_failure.*` and `regression_failed_groups/`.

The final parallel planner loads file modules selected by standard discovery, compares the exact test-ID multiset, and assigns every module exactly once. This corrects the earlier class.__module__ bookkeeping for inherited aliases. The final plan has **1938 tests / 118 modules**, with no omitted or duplicated test-ID counts relative to ordinary serial discovery. [regression_plan.json](regression_plan.json) records the complete module lists; each `full_group_*.json/log` records its actual count and exit status. Production bytes stay fixed across the entire run.

Final QA also observed bounded 30-second browser navigation timeouts before upload; these were not counted as import successes and no remote protection was bypassed. A subsequent actual UI upload succeeded on the same localhost and unchanged workbook. Intermediate batch runs remain distinct; qualification uses only the fresh final batch above. The browser timeout's exact cause is not inferred. The working app continues using its existing production transports.

Full result: [final_regression.json](final_regression.json), [log](final_regression.log). Existing negative identity/configuration/access guards remain in force; protected pipeline pins record the exact user-authorized changes. The test network blocker can log its intentionally caught exceptions; the runner's exit status and unittest summary determine success. `production_tree_unchanged` verifies the live and tested implementation remained fixed throughout the full run. Commit/push and clean-tree/origin equality are verified only after that result passes.
