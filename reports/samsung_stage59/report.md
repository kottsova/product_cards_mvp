# Stage 59 — Samsung baseline audit and shared-pipeline transfer

Date: 2026-10-04. Starting commit: `3394aadf5c606543af41789cbc3c70005dd033b3`. Verdict: **Samsung fits the existing production pipeline with a small brand adapter for controlled use.** Two catalog-annotated vacuum codes remain under review; their base-model facts and photos are not exported as confirmed.

## Reproducibility

- Catalog: `data/catalog_2026-09-21_filtered.xlsx`, sheet `Стиральные машины`. Frozen sample: `dataset_frozen.json`, SHA256 `72a428a075f77622bc11820eb9cd233540b7b934fb2ee8c9cb50ef4560a472ad`. The ten articles differ from the control and were absent from regression fixtures before the first run.
- The control was processed by unchanged production `worker.run_once()` in `baseline.sqlite3`. Then `run_frozen_first.py` processed the ten frozen rows through the unchanged worker, before any Stage 59 product edit. `first_pass.json` preserves each outcome. `run_final_repeat.py` ran the same ten through the final production worker and checked evidence stability.
- The SQLite files and policy access logs are local, ignored runtime state. Committed JSON evidence and runners make the sequence auditable. No model-specific production hardcode or identity-threshold change was added.

## Control: WW90T554CAT/LD

| Field | Unmodified production result |
|---|---|
| Original/base/category | `WW90T554CAT/LD` / `WW90T554CAT` / Стиральные машины |
| Lookup variants | Full code `WW90T554CAT/LD`, then base `WW90T554CAT` within the KZ `da-sitemap.xml` route. |
| PDP | [exact Samsung KZ product page](https://www.samsung.com/kz_ru/washers-and-dryers/washing-machines/ww5000t-front-loading-eco-bubble-ai-control-add-wash-9kg-white-ww90t554cat-ld/); KZ `da-sitemap.xml` 200, PDP 200, canonical/JSON-LD `Product.sku` and embedded `digitalData.product.model_code` show the full code. |
| Support | [exact KZ support](https://www.samsung.com/kz_ru/support/model/WW90T554CAT/LD/) and [exact UZ support](https://www.samsung.com/uz_ru/support/model/WW90T554CAT/LD/) observed separately. Support is `page-support-detail`, not a PDP. The similarly named `/LP` page is a distinct variant. |
| Evidence | 77 specifications in 9 PDP groups; 11 selected full-gallery photos and 11 excluded thumbnails. No dealer facts. |
| Manual | One official `User Manual` PDF, 36,987,971 bytes, 216 pages; Russian and Kazakh text verified. Exact code is absent from the PDF; official exact PDP link and matching family masks tie it with an advisory. Support also lists two Quick Guides and one User Manual as typed candidates. |
| Status | `done` / `export_ready`; 0 real conflicts; advisories: `instruction_exact_code_not_in_pdf, dealer_cross_check_missing`. Russian manual: `Проверена`. |

## Official Samsung source structure and identity

- KZ product URLs are listed by `da-sitemap.xml` (appliances) and `vd-sitemap.xml` (TV/audio/monitors); the official RU sub-sitemaps use the same division. A KZ sitemap miss is only a regional miss. The RU fallback yielded three exact sample PDPs.
- A PDP has a canonical URL, JSON-LD `Product` with SKU/name, embedded `digitalData.product.model_code/model_name`, server-rendered `.pdd32-product-spec` groups, and a model-bound gallery. Exactness is decided from page content, never from the URL slug alone. Page model name, base model, full sales SKU, region and color suffix are retained as distinct facts.
- Explicit PDP links lead to `/support/model/<code>/` (some older support routes use `model.<code>`). Support pages carry `page-support-detail` and embedded typed `manuals` JSON; their FAQ, account, repair and troubleshooting content is not product description or specification evidence.
- Official files use `org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx`. `CDCttType` separates PDF User Manual (`UM`), online manual (`PM`) and other guides (`EM`); the support list also names Quick Guide, Installation Guide, Remote control and Simple User Guide. Declared language and filename only rank candidates. Russian verification requires PDF text plus an accepted exact/family relation.
- The PDP contained site-search API markers, but no product-data API/XHR endpoint was validated. The adapter uses verified HTML/embedded JSON and does not guess an API route. Regional support and product pages stay separate source types.
- Extraction preserves the PDP section, raw label and raw value before canonical mapping. Marketing blocks, service/help content and account copy do not become specifications. The shared dimension projection distinguishes product/package axes and leaves stand-specific labels distinct; raw source values remain available in the audit.

## Frozen independent sample and unchanged first run

First-run metrics: **exact PDP 5/10 (KZ 5, RU 0); export_ready 3, export_ready_with_gaps 2, not_ready 4, needs_verification 1**. The unchanged Samsung adapter checked KZ only, so four articles appeared absent although official RU PDPs existed. The robot page was weaker than the catalog suffix. This is a pipeline gap, not evidence that those products do not exist.

| Catalog article / category | Lookup variants (first run) | PDP and support | Specs | Selected/candidate photos | Russian manual | Dealer fallback | Job / readiness | Main gap |
|---|---|---|---:|---:|---|---|---|---|
| `QE55QN90FAUXCE` / Телевизоры | `QE55QN90FAUXCE` | [KZ PDP](https://www.samsung.com/kz_ru/tvs/qled-tv/qn90f-55-inch-neo-qled-4k-mini-led-smart-tv-qe55qn90fauxce/); [support](https://www.samsung.com/kz_ru/support/model/QE55QN90FAUXCE/) (PDP link only) | 103 | 8/8 | Не проверена | `dealer_url_needed` | `done` / `export_ready_with_gaps` | `instruction_missing` |
| `LS32D700EAIXCI` / Мониторы | `LS32D700EAIXCI` | [KZ PDP](https://www.samsung.com/kz_ru/monitors/high-resolution/viewfinity-s7-32-inch-uhd-hdr10-easysetupstand-ls32d700eaixci/); [support](https://www.samsung.com/kz_ru/support/model/LS32D700EAIXCI/) (PDP link only) | 64 | 13/13 | Проверена | `not_needed` | `done` / `export_ready` | `—` |
| `RB33A32N0SA/WT` / Холодильники | `RB33A32N0SA/WT`, `RB33A32N0SA` | [KZ PDP](https://www.samsung.com/kz_ru/refrigerators/bottom-mount-freezer/rb33a32n0sa-350l-silver-rb33a32n0sa-wt/); [support](https://www.samsung.com/kz_ru/support/model/RB33A32N0SA/WT/) (PDP link only) | 52 | 5/5 | Не проверена | `dealer_url_needed` | `done` / `export_ready_with_gaps` | `instruction_file_not_confirmed` |
| `WW90T554CAX/LD` / Стиральные машины | `WW90T554CAX/LD`, `WW90T554CAX` | [KZ PDP](https://www.samsung.com/kz_ru/washers-and-dryers/washing-machines/ww5000t-front-loading-eco-bubble-ai-control-add-wash-9kg-platinum-silver-ww90t554cax-ld/); [support](https://www.samsung.com/kz_ru/support/model/WW90T554CAX/LD/) (PDP link only) | 77 | 11/11 | Проверена | `not_needed` | `done` / `export_ready` | `—` |
| `DV90T5240AW/LP` / Сушильные машины | `DV90T5240AW/LP`, `DV90T5240AW` | none; support not reached | 0 | 0/0 | Не проверена | `dealer_url_needed` | `needs_review` / `not_ready` | `no_official_page,instruction_no_exact_page` |
| `Jet_VS20A95973B/EV_Bespoke` / Пылесосы | `Jet_VS20A95973B/EV_Bespoke`, `Jet_VS20A95973B` | none; support not reached | 0 | 0/0 | Не проверена | `dealer_url_needed` | `needs_review` / `not_ready` | `no_official_page,instruction_no_exact_page` |
| `MC32DG7646KKBW` / Микроволновые печи | `MC32DG7646KKBW` | none; support not reached | 0 | 0/0 | Не проверена | `dealer_url_needed` | `needs_review` / `not_ready` | `no_official_page,instruction_no_exact_page` |
| `HW-B650F/RU` / Саундбары | `HW-B650F/RU`, `HW-B650F` | [KZ PDP](https://www.samsung.com/kz_ru/audio-devices/soundbar/b650f-black-hw-b650f-ru/); [support](https://www.samsung.com/kz_ru/support/model/HW-B650F/RU/) (PDP link only) | 44 | 15/15 | Проверена | `not_needed` | `done` / `export_ready` | `—` |
| `QE32LS03CBUXRU` / Телевизоры | `QE32LS03CBUXRU` | none; support not reached | 0 | 0/0 | Не проверена | `dealer_url_needed` | `needs_review` / `not_ready` | `no_official_page,instruction_no_exact_page` |
| `VR30T80313W/EV_1` / Роботы-пылесосы | `VR30T80313W/EV_1`, `VR30T80313W` | [KZ PDP](https://www.samsung.com/kz_ru/vacuum-cleaners/robot/vr8000t-white-vr30t80313w-ev/); support not reached (none) | 45 | 0/46 | Не проверена | `dealer_url_needed` | `needs_review` / `needs_verification` | `variant_code_only_in_page_text,photos_not_selected_variant_open,unresolved_conflicts,instruction_file_not_confirmed` |

The original query variants did not remove catalog annotations such as `Jet_` or `_Bespoke`. The first pass stored 45 robot facts as raw official candidate evidence and selected 0 of 23 gallery images. An audit found that the pre-fix product Excel row nevertheless displayed weaker Samsung values; the Stage 59 exact gate fixes that false export.

## General fixes after the frozen first run

| Before | Root cause | Shared correction | After |
|---|---|---|---|
| Four rows had no PDP in KZ | Samsung discovery stopped after KZ sitemap miss | Content-validate KZ/RU official sitemap candidates; use existing browser transport only after official exact misses | Dryer, microwave and second TV gained exact RU PDPs; the vacuum gained a KZ base-model candidate only |
| QN90F lacked a manual | PDP had no manual anchor; exact support page had embedded manual JSON | Follow the PDP exact support link and inspect typed manual list; read PDF bytes/text | One accepted Russian User Manual, `export_ready_with_gaps -> export_ready` |
| Source sections were blank; dryer had a spurious `49` vs `49 kg` conflict | Samsung groups were dropped and a bare overview number lost an explicit unit already printed on the same page | Persist `section -> raw label -> value`; infer a unit only for the same canonical field and identical number with one explicit unit | Dryer conflict cleared; raw values remain `49` and `49 кг` |
| Annotated catalog codes could inherit ordinary page evidence and Excel exported their values | Query normalization, identity and shared resolver/export gates were disconnected | Treat SKU inside annotations as base-only; confirm exact Samsung facts in the shared resolver only for content-validated full SKU; gate product Excel on that flag | Jet and robot stay `needs_verification`; their product rows are empty, audit facts remain |
| UI/Excel presented weak PDFs and photos as verified | Generic non-LG presentation assumed identity tie | Use Samsung acceptance and model-bound photo checks; reuse common Russian label and dimension projection | 10 cards and generated workbook show candidates separately; no extra dealer columns |

## Final production evidence on the same frozen articles

Final metrics: **exact PDP 8/10 (KZ 5, RU 3); export_ready 7, export_ready_with_gaps 1, not_ready 0, needs_verification 2**. Exact official PDPs: 8 (KZ 5, RU 3); base-only candidates: 2; confirmed dealer pages: 0. External browser search ran only after the official exact-sitemap search missed; no external result was promoted without PDP-content validation. All ten rows have 0 accepted dealer facts. Manual status uses the three-state model and no unverified file is labeled Russian. Dealer fallback reports dealer_url_needed where no verified DNS/Technopark URL exists; no dealer page is guessed.

| Article | Official PDP / identity | Support | Facts | Selected/candidate photos | Manual | External / dealer | Job / readiness | Open issue |
|---|---|---|---:|---:|---|---|---|---|
| `QE55QN90FAUXCE` | [KZ PDP](https://www.samsung.com/kz_ru/tvs/qled-tv/qn90f-55-inch-neo-qled-4k-mini-led-smart-tv-qe55qn90fauxce/) / `full_sku` | [exact support](https://www.samsung.com/kz_ru/support/model/QE55QN90FAUXCE/) (checked) | 103 | 8/8 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `LS32D700EAIXCI` | [KZ PDP](https://www.samsung.com/kz_ru/monitors/high-resolution/viewfinity-s7-32-inch-uhd-hdr10-easysetupstand-ls32d700eaixci/) / `full_sku` | [exact support](https://www.samsung.com/kz_ru/support/model/LS32D700EAIXCI/) (PDP link only) | 64 | 13/13 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `RB33A32N0SA/WT` | [KZ PDP](https://www.samsung.com/kz_ru/refrigerators/bottom-mount-freezer/rb33a32n0sa-350l-silver-rb33a32n0sa-wt/) / `full_sku` | [exact support](https://www.samsung.com/kz_ru/support/model/RB33A32N0SA/WT/) (PDP link only) | 52 | 5/5 | Не проверена | 0 / `dealer_url_needed` | `done` / `export_ready_with_gaps` | `instruction_file_not_confirmed` |
| `WW90T554CAX/LD` | [KZ PDP](https://www.samsung.com/kz_ru/washers-and-dryers/washing-machines/ww5000t-front-loading-eco-bubble-ai-control-add-wash-9kg-platinum-silver-ww90t554cax-ld/) / `full_sku` | [exact support](https://www.samsung.com/kz_ru/support/model/WW90T554CAX/LD/) (PDP link only) | 77 | 11/11 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `DV90T5240AW/LP` | [RU PDP](https://www.samsung.com/ru/washers-and-dryers/dryers/dv5000t-front-loading-ai-control-reversible-door-wrinkle-prevent-9kg-white-dv90t5240aw-lp/) / `full_sku` | [exact support](https://www.samsung.com/ru/support/model/DV90T5240AW/LP/) (PDP link only) | 55 | 16/16 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `Jet_VS20A95973B/EV_Bespoke` | [KZ PDP](https://www.samsung.com/kz_ru/vacuum-cleaners/stick/vs9500al-vc-with-all-in-one-clean-station-blue-vs20a95973b-ev/) / `base_model` | — | 38 | 0/128 | Не проверена | 4 / `dealer_url_needed` | `needs_review` / `needs_verification` | `variant_base_model_only,photos_not_selected_variant_open,instruction_tied_by_weaker_page` |
| `MC32DG7646KKBW` | [RU PDP](https://www.samsung.com/ru/microwave-ovens/convection/mw7300b-mc32db7746ke-convection-mwo-all-in-one-microwave-oven-smart-control-mc32dg7646kkbw/) / `full_sku` | [exact support](https://www.samsung.com/ru/support/model/MC32DG7646KKBW/) (PDP link only) | 55 | 9/9 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `HW-B650F/RU` | [KZ PDP](https://www.samsung.com/kz_ru/audio-devices/soundbar/b650f-black-hw-b650f-ru/) / `full_sku` | [exact support](https://www.samsung.com/kz_ru/support/model/HW-B650F/RU/) (PDP link only) | 44 | 15/15 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `QE32LS03CBUXRU` | [RU PDP](https://www.samsung.com/ru/lifestyle-tvs/the-frame/32ls03c-32-inch-the-frame-qled-smart-tv-black-qe32ls03cbuxru/) / `full_sku` | [exact support](https://www.samsung.com/ru/support/model/QE32LS03CBUXRU/) (PDP link only) | 102 | 10/10 | Проверена | 0 / `not_needed` | `done` / `export_ready` | `—` |
| `VR30T80313W/EV_1` | [KZ PDP](https://www.samsung.com/kz_ru/vacuum-cleaners/robot/vr8000t-white-vr30t80313w-ev/) / `base_model` | — | 45 | 0/46 | Не проверена | 4 / `dealer_url_needed` | `needs_review` / `needs_verification` | `variant_base_model_only,photos_not_selected_variant_open,unresolved_conflicts,instruction_file_not_confirmed` |

For each post-fix lookup, `page_evidence.query_variants`, `route.addresses`, `candidates`, `external_search` and `external_results` preserve the query/provider/URL/region/title/snippet/accepted-or-rejected reason. The first unsuitable search candidate cannot end the search; support URLs are skipped as PDP candidates. Browser CAPTCHA/rate limits are not bypassed.

## False-confirmation review

- **Exact full SKU**: control `WW90T554CAT/LD` and sample `MC32DG7646KKBW` show matching page-content SKU. PDP facts and gallery are confirmed; support/manual evidence supplies neither specs nor photos.
- **Base/annotation**: `Jet_VS20A95973B/EV_Bespoke` points to a PDP whose Samsung SKU is `VS20A95973B/EV`. The extra catalog words are not declared by Samsung. Raw facts, manual and images remain candidate evidence; 0 selected photos and 0 main-sheet attribute values.
- **Regional suffix**: `DV90T5240AW/LP` is exact on Samsung RU, while `VR30T80313W/EV_1` is not exact on its KZ page (`VR30T80313W/EV`). The latter has 0 selected photos, an unaccepted Russian PDF candidate and two preserved real size/weight conflicts. No base/family relation upgrades the `_1` suffix.
- Confirmed false facts **after fixes: 0**. The first-pass Excel export leak for weak Samsung rows was repaired and explicitly checked. Unresolved source contradictions remain visible with both raw values.

## UI, Excel, photos and regression

- TestClient: 10 cards returned HTTP 200; each exposed `Основные характеристики`, `Особенности модели`, manual status, candidate photos and lightbox markup. No generic `Дополнительная характеристика` or support/help copy appeared. Robot conflict displayed both `350x99.8x350` and `350x105x430` (plus 3.4 and 3.81 kg).
- Generated Excel: 111256 bytes; source audit has no Sulpak/dealer column, photo candidates are separate (261 rows). The Jet and robot product rows have 0 confirmed attributes; exact dryer and QN90F rows are populated. Raw facts and conflict sides remain on `Проверка источников`.
- Measured official QN90F gallery asset: 2052 x 1641 px, 1,086,711 bytes, JPG; the UI photo inspect route and generated Excel agreed on all four fields. Other unmeasured photos show unknown metadata rather than inferred dimensions.
- Final repeat: 10/10 preserved page, PDF, selected photos, uniqueness and readiness. Any remaining `needs_verification` is explained by catalog annotations rather than a false exact promotion.
- Full regression: 1,429 tests, OK (929.997 s). `git diff --cached --check`: PASS. No readiness threshold changed.
