# Stage 58 — Bosch Home baseline and transfer of the shared pipeline

Date: 2026-10-03. Starting commit: `44face0439689f76d29effffc46c5a85e5b6275b`. LG remains closed for controlled use. Verdict: **Bosch Home fits the existing production pipeline with a compact brand adapter, for controlled use**. The two suffix rows below remain `not_ready` because exact variant evidence was not established; no base-model facts or photos were promoted.

## Reproducibility and run order

- Original catalog: `data/catalog_2026-09-21_filtered.xlsx`, sheet `Товары`. The control and ten rows were read from this catalog. The independent sample was frozen in `dataset_frozen.json` before its first run; SHA256 `06a009b188058998efaebd8db0748e0c6d08d13bc8948e13de111d3ad950dc11`. No frozen article occurred in earlier `tests/` fixtures.
- `run_baseline.py` ran PUE611BB5E through the unchanged `worker.run_once()` on an isolated database, with a catalog-shaped persisted row. The old enqueue gate rejected it, so a pre-existing queued job was inserted to observe the unmodified worker. This is the limit of the baseline: it did not exercise Excel upload. `run_upload_control.py` later verified the actual production Excel upload → confirmation → queue → `run_once()` → UI → Excel export chain.
- `run_frozen_first.py` ran all ten frozen rows through the unchanged worker, before any Stage 58 code edit. `first_pass.json` is the immutable outcome. `run_pass.py` produced `batch_pass.json` after general fixes. All runs used isolated databases and normal `run_once()`; no per-model hardcode or identity threshold change was applied.

## Control PUE611BB5E

| Check | Unmodified baseline | After shared transfer |
|---|---|---|
| Queries | none: legacy two-product gate | `PUE611BB5E` |
| Official PDP | none | [Bosch Home KZ exact PDP](https://www.bosch-home.com/kz/ru/product/PUE611BB5E); JSON-LD `Product.mpn=PUE611BB5E`, URL slug matches, GTIN `4242005285082` |
| Support | none | [KZ support list](https://www.bosch-home.com/kz/support/list/PUE611BB5E); candidate revisions `/01`, `/35`, `/43`, `/51` are recorded separately |
| Manuals | none | [official PDF](https://media3.bsh-group.com/Documents/9001867766_G.pdf) appears as both User manual and Installation instructions on the PDP; binary and extracted text checked: 2,947,603 bytes, 12 pages, Russian present, exact model code not printed. The relation is PDP-linked family manual, not PDF-printed exact model. One URL is stored once, with both types in typed evidence. |
| Characteristics | 0 | 48 official grouped facts; raw section/label/value retained |
| Photos | 0 | 4 exact-model filename images selected; 6 generic/other-model images excluded but retained as candidates |
| Identity | none | commercial model exact; slash E-Nr revision unknown |
| Job / readiness | `needs_review` / `not_ready` | `done` / `export_ready`; advisory gaps: revision unknown, model code absent from PDF |
| Conflicts | 0 | 0 |

The actual Excel upload round trip returned HTTP 303 for upload and confirmation, then `done/export_ready`, HTTP 200 for the card and export. UI photo inspection measured one selected WEBP as 2342 × 2004 px, 24,780 bytes; lightbox and candidate separation rendered.

## Official Bosch structure and identity

- Regional Bosch Home PDPs use paths such as `/kz/ru/product/{model}` and longer market paths such as the [SA SMS4ECI26M PDP](https://www.bosch-home.com/sa/en/mkt-product/dishwashers/freestanding-dishwashers/freestanding-dishwashers-with-60cm-width/SMS4ECI26M). The [DE old PIE631FB1E PDP](https://www.bosch-home.com/de/de/product/PIE631FB1E) and [EG MMB6384M PDP](https://www.bosch-home.com/eg/en/product/kitchentools/blenders/blenders/MMB6384M) demonstrate other-region discovery.
- [Bosch robots.txt](https://www.bosch-home.com/robots.txt) lists regional sitemaps. `/kz/sitemap.xml` is valid; `/kz/ru/sitemap.xml` is not. A sitemap URL is a candidate only: an NE SMS4ECI26M URL returned HTTP 200 but was a search-results shell with no JSON-LD Product, so it was rejected and the SA exact PDP was accepted.
- PDP pages expose schema.org JSON-LD Product (`mpn`, GTIN, image and additional properties) plus server-rendered Next.js data for grouped `section → label → value` specifications and typed documents. No standalone stable API/XHR endpoint was verified; the adapter relies on validated public PDP content and embedded data.
- Support list/service pages enumerate revisions and may expose manuals. The [PUE611BB5E/01 service route](https://www.bosch-home.com/kz/ru/productservice/PUE611BB5E-01) was also observed independently; it identifies a particular revision, which the unsuffixed catalog row does not establish. These pages are support evidence, not PDPs. A base code and a slash revision are distinct: [Bosch’s E-Nr help](https://www.bosch-home.com/mt/service/identify-appliance-model) says the E-Nr identifies the appliance, while FD/Z-Nr can also matter. The adapter records `bosch_model_identifier_exact`, `bosch_enr_revision_of_model` or `commercial_suffix_of_model` as the requested relation; the PDP without a slash never proves a particular `/01` or `/43` E-Nr. Regional or catalog suffixes such as `_KZ` and `_1` are not silently stripped into exact identity.
- Direct KZ candidate, regional sitemap candidates, other-region direct candidates, and the existing browser search transport run in that order. Each candidate is accepted only after page-content identity validation; diagnostics retain query, provider, URL, region, decision, reason and identity. Dealer fallback uses the existing DNS adapter only when a verified dealer URL is available and the card is still `not_ready`.

## Extraction and presentation

- The adapter retains source `section → raw label → raw value` before canonical mapping. Product specifications remain separate from descriptive marketing copy. English and German generic labels are presented in Russian through a shared canonical dictionary; technology names may stay original. Explicit dimension axes map to width, height and depth for product or package; an unlabelled triple is never guessed. Units, gross weight, independent heater sizes, panel/door colours and yes/no values remain distinct.
- Model-bound gallery URLs are selected only when their filenames establish the exact commercial model. Drawings, lifestyle, accessories and other variant images are stored as excluded candidates, separately from confirmed photos. UI has preview, lightbox and on-demand measured width, height, bytes and format.
- Typed document evidence distinguishes User manual, Installation instructions, Datasheet/Product fiche, planning/assembly or interactive material when present. A shared PDF URL can carry multiple official types without duplicate document rows. Language `ru` and manual status `Проверена` require Russian text in the PDF and an official exact-PDP link. Other PDFs remain unverified for Russian instruction. `Проверена, не найдена` is reserved for a completed official manual search; it was not asserted for any of these four unchecked sample rows.

## Frozen ten-model sample and first run

The exact frozen list and categories are in `dataset_frozen.json`. The first, pre-fix run produced the same outcome for **all ten**: enqueue rejected by the two-selected-products gate; the already-queued job ended `needs_review/not_ready`, with zero queries, pages, documents, characteristics or photos. `first_pass.json` preserves each row. This is a systemic production gate, not ten separate Bosch source gaps.

The table below is the final evidence after general fixes. `Фото` means selected exact-model images; `канд.` means excluded candidates. All PDPs and manuals shown are official Bosch Home/BSH sources. `—` under support means no verified list was recorded, not proof that one cannot exist.

| Артикул / категория | PDP identity, region | Support list | PDF | Specs | Фото / канд. | Manual | Job / readiness | Главный gap |
|---|---|---|---:|---:|---:|---|---|---|
| PIE631FB1E / панель | exact DE | DE | 3 | 45 | 1 / 4 | Не проверена | done / export_ready_with_gaps | русский PDF не подтверждён |
| HBF534ES0Q_KZ / духовка | base KZ | — | 0 | 0 | 0 / 4 | Не проверена | needs_review / not_ready | `_KZ` не доказан как exact |
| KGN39LB316 / холодильник | exact KZ | KZ | 2 | 40 | 5 / 4 | Проверена | done / export_ready | slash revision unknown |
| WGA142X6OE / стиральная машина | exact KZ | KZ | 2 | 57 | 4 / 3 | Проверена | done / export_ready | slash revision unknown |
| SMS4ECI26M / посудомоечная машина | exact SA | — | 4 | 39 | 4 / 7 | Не проверена | done / export_ready_with_gaps | русский PDF не подтверждён |
| BCH86PET1_1 / пылесос | base KZ | — | 0 | 0 | 0 / 10 | Не проверена | needs_review / not_ready | `_1` не доказан как exact |
| MMB6384M / блендер | exact EG | — | 5 | 21 | 12 / 1 | Проверена | done / export_ready | slash revision unknown |
| WQB245B0ME / сушильная машина | exact KZ | KZ | 1 | 55 | 5 / 6 | Проверена | done / export_ready | slash revision unknown |
| TWK4M223 / чайник | exact KZ | KZ | 3 | 23 | 11 / 0 | Проверена | done / export_ready | slash revision unknown |
| BEL554MB2 / микроволновая печь | exact KZ | KZ | 1 | 33 | 5 / 5 | Проверена | done / export_ready | slash revision unknown |

**Metrics:** exact official PDP 8/10 (KZ 5, other Bosch Home regions 3); base-only 2; external browser search attempted 2, only after official miss; dealer fallback required 2, both ended `dealer_url_needed` because there was no preverified exact DNS/Technopark URL; export_ready 6, export_ready_with_gaps 2, not_ready 2; jobs done 8, needs_review 2; verified Russian instructions 6, unchecked 4; 313 official facts, 47 confirmed photos, 44 excluded candidates, 21 stored PDF documents; real conflicts 0; false confirmed facts/images found in audit 0. Browser Google navigation errors and Bing empty candidates affected only the two still-unresolved suffix rows; they were not treated as exact evidence. No CAPTCHA was bypassed.

## General fixes and regression boundaries

1. Legacy Bosch queue gate blocked PUE and the entire frozen sample. The gate was lifted for Bosch Home appliances; prior two selected products and Bosch Professional exclusion remain covered by tests. Result: eight exact cards processed; two base-only cases remain unconfirmed.
2. Immediately after lifting the gate, the general adapter found seven exact PDPs, but all seven were `export_ready_with_gaps`; three rows were `not_ready` (`batch_after.json`). Official Bosch URLs include regional sitemaps, nested market product paths and 200-status search shells. The small adapter validates JSON-LD `Product.mpn` and model slug, records every rejected candidate, and reuses the existing browser transport after official miss. Result: DE, SA and EG exact PDPs accepted; NE search shell rejected; suffix base pages never exported as exact.
3. Grouped EN/DE values and generic boolean/physical labels were not fit for Russian card presentation. General normalization and a Bosch label projection retain raw values while producing canonical Russian names and explicit dimensions. A complete header audit of the ten-model workbook left only Bosch technology names in Latin script. The first full regression found three LG snapshot mismatches because compact, explicitly labelled `ШxВxГмм` was missed by the strict axis parser; the shared parser now recognizes that spelling while leaving unlabelled triples untouched. The three LG snapshots, Bosch extraction and structural gates passed after the correction. Exact-model image selection excludes unrelated JSON-LD/gallery images.
4. Excel source audit formerly showed empty LG KZ/RU columns in Bosch batches. Columns are now driven by actual batch brands; the ten-model export has one Bosch Home source column and no empty LG/dealer columns; 44 excluded photo candidates have their own sheet.

No product-specific URL, threshold or fact override was added. The existing readiness thresholds were retained. DNS requires a verified dealer URL and exact manufacturer-code check; the two suffix rows have no such URL, so dealer facts/photos remain zero.

## UI and Excel verification

`qa_ui_batch.py` requested all ten product cards (HTTP 200), checked headings on eight evidence-bearing cards, manual label, photo lightbox and absence of generic `Дополнительная характеристика` or support/help copy. The export (HTTP 200, 64,898 bytes) contains ten category sheets plus source audit, sources, instructions, 47 confirmed photos, 44 excluded photo candidates and Bosch readiness. The audit sheet has Bosch Home only; documents retain regional source names, verified/unverified status and relationship, photos retain dimension/size/format columns. No Sulpak/DNS columns appear. There are no real conflicts in this sample, so both conflict sides were exercised by regression fixtures rather than invented in live evidence.

## Verification and final state

Full regression: `python -m unittest discover -s tests -v` — **1422 tests in 819.053s, OK**. The earlier LG compact-axis regression was repaired and the complete suite reran to PASS.

`git diff --check` and `git diff --cached --check`: PASS.

Commit message: `Stage 58`; commit hash and remote synchronization are verified in the final handoff.







