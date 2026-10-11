# Stage 78 — Electrolux baseline audit

Audit verdict: **PASS**. Adapter verdict: **Electrolux adapter not ready**.
Основание: Dreame `86325a806d760ecf29230f6195a67559bdb94303`; frozen dataset SHA256 `92cc16f718f98b20aafed5a6cc247b72c57fe4b034592078cf0ec58527d69176`.

## Baseline и происхождение данных

`baseline.json`: обычный, неизменённый `run_once()` для EFI61141B до добавления адаптера — job error, not_ready, specs/photos/documents 0. DNS не запускает guessed search без проверенного dealer URL. Отдельный Chrome probe показал redirect exact EFI61141B URL в каталог: старый search index не является live PDP.
`exact_pdp_baseline/baseline.json`: повторён тот же **неизменённый** worker для реально доступной EOF6P46X с official PDP — те же 0 specs/photos, error/not_ready. Причина обоих baseline: Electrolux official dispatch отсутствовал. Research PDP/identity не были подставлены в этот результат.
Исходный артикул EOF6P46X, model EOF6P46X, product code / base PNC 944032051, regional source UK, 11-digit revision не напечатана. Это значения последующего actual native research, а не успех baseline worker.

## Official structure

Regional PDP: exact `PDPContainer` в `__NEXT_DATA__.props.pageProps.pageData.components`. Его `TopArea.modelId`, `productCode`, `ean`, `pageHeading` — разные identity fields. Header/footer/recommendations/reviews не владеют спецификациями товара. JSON-LD в проверенном UK PDP — Organization, не Product; его name/logo нельзя использовать как модель/галерею.
`FullSpecification.attributes`: section → label → infoText. `Specification`, Swedish `Specifikationer` — feature/marketing prose, не технические пары. Сохраняются в raw/rejected inventory. KeySpecification не перекрывает detailed rows.
`TopArea.imageGallery.galleryItems`: exact published product gallery через regional `/services/eml/transform/...`. `DocumentsContent`: `productCode` может быть **model name**, `pnc` — numeric PNC; их нельзя считать одним полем. `document.documents` и `installation.documents` разделены.
API/XHR: published `PIServices/EdenService.svc/.../GetDatasheetPDF` и `/services/eml/transform/...` — read-only document/media GET routes. Native `functionEndpoints` также содержат user-manual-request/review/cart actions; они не используются для extraction и формы с email не отправлялись. SSR достаточен для большинства specs/gallery/documents.
Documents: `productinformation.electrolux.com` datasheets; published `electrolux.bynder.com` PDF guides; `support.electroluxgroup.eu/external/compliance-documents/GBEnergyLabel/...` label/fiche. 301 требует безопасного redirect handling. `/support/user-manuals/` и `/support/product-fiches/` — отдельные inventories; fiche UI просит первые 9 цифр PNC. Official parts site `/model/m/...` публикует 11-digit PNC versions.
`robots.txt` публикует `.../globalassets/sitemaps/.../sitemapindex.xml`; не guessed `/sitemap.xml` (последний probe неуспешен). Published site search `searchPageName` + наблюдённый input `q` используются перед catalog; общий external `LGBrowserSearch` — после official miss и support, DNS — последним.

## Identity и реальные PNC findings

Marketing model, published numeric product code/base PNC, optional 11-digit service revision, EAN, region и family сохраняются отдельно. Если supplier PNC не задан, карточка описывает **опубликованный региональный продукт с его PNC**, без утверждения о неизвестной supplier revision. Если PNC задан, сравнение точное; 9 цифр не дополняются `00`.
Actual official EOF6P46X parts menus UK/SE: 94949823900, 94949822300, 94403205100, 94403205200, 94403205101, 94949823901, 94928801101. Один model name связывается с несколькими base PNC и revisions. Это **не доказательство** равенства технических конфигураций. Поэтому dimensions/energy/finish/voltage/accessories/documents и programs/capacity неподтверждённого PNC не переносятся. При partial остаётся только классификация модели; thresholds сохранены.
Same-model UK/IE research PDP показал EOF6P46X + 944032051 в обоих регионах; это supplemental research, не injected production discovery и не доказательство одинаковости всех региональных specs. Native UK и SE parts relation также проверены отдельно.
Строка 9: input PNC 914606627 → official EWD746PCBI / 914606627, exact base-product relation. Строка 10: input 94949957800 специально сформирован как **synthetic revision challenge** до первого batch, не выдан за существующий supplier SKU. PDP печатает 949499578: revision не подтверждена, partial. Dataset bytes не менялись.

## Extraction, energy, installation, documents

Общий pipeline сохранён: Excel importer → ordinary queued worker → existing policy/browser/search/dealer → native adapter → normalization/resolution → evidence/readiness → native UI/export. Нового framework нет.
Исправлены доказанные общие root causes: installation_dimensions больше не product_dimensions; only-machine mass — отдельный qualifier; bounded safe Chrome binary redirects — вместо возврата первого 301. LED color canonical label использует существующий backlight_color, не color корпуса. Другие бренды/thresholds не переопределены.
PNC raw rows сохранены с section/raw label/value до canonical mapping; Русский словарь label поддерживает washing/drying/dishwasher/fridge/oven/hob/vacuum. Product, niche и package scopes раздельны. Swedish bare device mass 4.998 kg и net mass 7.273 kg не конфликтуют как одна сущность. Actual EOF6P46X: width product 595 mm vs niche 560 mm; height product 594 mm vs niche 590 mm. Явный `max` не теряется. Неуказанные единицы/период/оси не достраиваются.
Programs — один список в parent `Программы`; функции управления отдельно. SupportModule/FAQ/troubleshooting/reviews не попадают в ProductDescription/specs.
Energy: annual consumption, 100 wash cycles, 100 wash/dry cycles и conventional/fan oven cycles — разные поля. Spin class и noise class не energy class. PDP source label не выдаётся за новую шкалу. EDHI618WD actual Energy Label: **A++ на A+++–D, 392/2012**, 235 kWh/year; fiche — 234.7, basis 160 drying cycles. E52LE100S actual label: **E на A–G**, 94 kWh/100 cycles, 9.9 L/cycle, 47 dB/C noise class. Стандарты и периоды не конвертируются/не смешиваются. Fiche dimensions в cm с округлением не заменяют PDP exact mm.
Energy Label/Product Fiche/Specification Sheet/User Manual/Installation Drawing сохранены как разные types, с language, model, PNC, region, source relation, byte-verification/SHA. Installation drawing не основной manual и не primary product photo. PDF facts не merged автоматически с PDP specs. Safety не подменяет User Manual.
В финале: 24 verified PDFs из 42 inventory entries. EN User Manuals actual downloaded для IDs 2,3,5,6,7,9; ID4 — User Manual отсутствует в завершённом PDP inventory (bounded scope, не утверждение отсутствия во всей сети); ID8 — technical PDF failure; ID1 — exact source не получен; ID10 — PNC revision relation не проверена. RU guide отдельно не подтверждён. Manual optional, ID4/8 ready при этих статусах.

## Frozen dataset и результаты

10 разных моделей: 2 washers, dryer, dishwasher, fridge, oven, hob, vacuum, washer-dryer по PNC и ещё oven с revision challenge. Набор заморожен до первого job; предварительная ошибка подготовки DB случилась до jobs и dataset не изменила.
First actual pass `first_live_v1`: 9/10 PDP, 16 byte-verified selected gallery assets; normalization collisions и 301 documents наблюдались честно. `final_live` — diagnostic run до окончательного document-field semantics fix, не release результат. **Только `qualified_live`** — итог: 9/10 actual fresh PDP, 7/10 ready, 268 resolved confirmed fields, 16 selected byte-verified images. Catalog cache — только same-session discovery; PDP всегда fresh. Captures/offline parser tests не считаются live success.

| ID | Модель / вход | PNC PDP | Live | Было specs → стало | Фото | Инструкция | Готовность |
|---|---|---|---|---|---|---|---|
| 1 | EFI61141B / EFI61141B | — | Нет | 0 → 0 | 0 | Не проверена | not_ready |
| 2 | EF7742OBI / EF7742OBI | 914580516 | Да | 29 → 29 | 2 | Проверена | not_ready |
| 3 | EDHI618WD / EDHI618WD | 916099992 | Да | 29 → 29 | 2 | Проверена | export_ready |
| 4 | E52LE100S / E52LE100S | 911570103 | Да | 34 → 34 | 2 | Проверена, не найдена | export_ready |
| 5 | LNT6TE18S5 / LNT6TE18S5 | 925504322 | Да | 34 → 40 | 2 | Проверена | export_ready |
| 6 | EOF6P46X / EOF6P46X | 944032051 | Да | 33 → 39 | 2 | Проверена | export_ready |
| 7 | EIV84550 / EIV84550 | 949599217 | Да | 23 → 27 | 2 | Проверена | export_ready |
| 8 | EB71U1WB / EB71U1WB | 900258750 | Да | 45 → 39 | 2 | Не проверена | export_ready |
| 9 | EWD746PCBI / 914606627 | 914606627 | Да | 30 → 30 | 2 | Проверена | export_ready |
| 10 | EOD6C46K2 / 94949957800 | 949499578 | Да | 4 → 1 | 0 | Не проверена | not_ready |

Job/readiness, exact source URLs, raw/accepted/rejected facts, photos, typed documents, query/provider/accept/reject/reason/identity traces и dealer reason — в `qualified_live/ID/result.json`. Dealer не запускался для optional manual gap/доступного official PDP. ID1 common DNS вернул missing verified dealer URL; accepted dealer evidence 0.
Не готовы: 1 — redirected/missing exact PDP и bounded discovery/fallback не восстановил его; 2 — два разных official `Push Button Functions` списка, оставлены conflict; 10 — partial revision и недостаток допустимых variant facts/gallery. Остальные 7 естественно ready, без снижения thresholds.

## Edge cases и границы qualification

1. Same model/different PNC: actual UK/SE parts menus + conservative test, no transfer energy/physical/config fields.
2. Same model/different region: actual UK/IE owner relation + explicit region negative fixture.
3. Product/install/package axes: actual oven/fridge/hob, separate normalization keys.
4. Old/new energy: actual old A+++–D dryer PDF vs new A–G dishwasher PDF, units/periods separate.
5. Different finish: mismatched input color rejects PNC facts/gallery; LED red does not alter black hob finish.
6. Family vs exact: actual EFI61141B redirect and native catalog; ProductList/Organization cannot prove exact product.
30 offline fixture/transport tests cover these cases, document URL wrong PNC, wrong owner, manual type ownership, foreign/active-stop redirect refusal, explicit no-redirect, bounded loops. Они не заменяют live acquisition.
Финальная Chrome session: contexts 1, navigations 39, cookie **counts only** 17→33, closed True. Наблюдённых official 403/429 в final acquisition нет; default HTTP probe дал network errors до ответа. CAPTCHA автоматизированно не решалась; access guards/cooldowns не снимались.

## UI / Excel / визуальная проверка

`qa_ui_excel.json`: native TestClient проверил все 10 cards; workbook `Electrolux_Stage78.xlsx`, 15 sheets, formula errors 0. Русские canonical labels, parent groups и отдельные metadata/typed documents. 12 screenshots по 6 карточкам; визуально проверены identity/specs, actual gallery contact sheet (16 assets, включая один model + included-accessories infographic), EN manual cover и old/new energy labels. Файлы images/PDF измерены и SHA сверены; standalone diagram/accessory не primary product image. No supplier-color claim без evidence.

## Нужен ли отдельный PNC/document framework?

**Нет.** Существующие typed evidence, SourceDocument/ProductDocument, jobs, resolution и UI/export достаточны. Нужны небольшие brand-specific PNC relations/document ownership rules в адаптере, дальнейшая exact revision/support qualification и recovery после official miss. Parts menus — typed relations, а не разрешение переносить specifications между ними.

## Regression и verdict

Полный regression: ['Ran 1847 tests in 735.322s', 'OK'], exit 0, source tree unchanged True; offline real-network guard активен. `git diff --check` проверяется перед commit. Исторические reports/datasets не правились; test preservation registry расширен append-only только на Stage78 authorized files.
Audit PASS отделён от production qualification: **Electrolux adapter not ready**. Блокеры: exact discovery после redirect/official miss, настоящий source conflict EF7742OBI, неподтверждённый exact revision path, не квалифицированный default HTTP access. Manual RU/отсутствие instruction не являются readiness blocker. Commit/push и HEAD==origin/main проверяются после full regression PASS.

## Public release evidence

85 public HTML captures содержат прозрачные cookie/clientIpAddress redactions. `redactions.json` сохраняет original response SHA и stored SHA; все product identities/accepted facts после редактирования сверены с actual live result и совпадают. Повторный affected fixture regression: 30 tests / OK. Runtime DB, input workbooks и browser profile исключены; cookie values не публикуются. `evidence_manifest.json` описывает каждый публичный artifact exact bytes/SHA.
