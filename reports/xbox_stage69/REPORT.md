# Stage 69 — Xbox exact discovery + retail/hardware resolution

**Audit PASS. Xbox adapter production-ready for controlled use.** Два независимых холодных ordinary-worker live-прогона и replay первого из них: **10/10 / 10/10 / 10/10**. Нового framework нет. Frozen inputs Stage 68 не изменены; SHA-256 `556dfe669181b1959e1d21dd52ed491f78719744bdbdab3442bef981de76191c`.

## 1. Root causes discovery 1 / 2 / 8

**1:** ищется Series X, 1 TB, чёрный, с оптическим приводом, en-US. Найденный ранее [own Store](https://www.microsoft.com/en-us/d/xbox-series-x/8wj714n3rbtl) терял exact status потому, что commercial input не содержит Product ID. Публичный regional `allConsoles` публикует PID/SKU **8WJ714N3RBTL/490G**, 1TB, black, disc. Теперь tuple сверяется с own BuyBox row, own storage/drive, семейством и регионом. Имя само по себе конфигурацию не подтверждает.

**2:** ищется Series S 512GB White, en-US. Аналогичная потеря identity у [own Store](https://www.microsoft.com/en-us/d/xbox-series-s/942j774tp9jn). Опубликованный catalog tuple **942J774TP9JN/2JBX**, 512GB, white, digital теперь подтверждён own Store. Отдельный controller из gallery остаётся candidate; консоль вместе с контроллером допускается без вывода о комплекте из изображения.

**8:** ищется собственный PID **8N1BB8DSBKNT**, Diablo IV Bundle. В текущем public catalog/sitemap его нет. Tracking/configure/fragment варианты занимали ограниченные slots, а общий официальный search declaration не читался. URL дедуплицируются; JSON-LD SearchAction homepage задаёт реальную query. Запрос PID возвращает [own Diablo PDP](https://www.microsoft.com/en-us/d/xbox-series-x-diablo-iv-bundle/8n1bb8dsbknt), PID подтверждён own BuyBox/JSON-LD, bundle и included game — собственным текстом. Заранее известный URL в discovery не передаётся.

Полный `input → normalized queries → family/catalog → sitemap/Store → official search → Support → other regions → external-if-miss` trace содержит query/provider/URL/source type/accepted/rejected/reason и три identity scopes: [live E](live_final_e.json), [live F](live_final_f.json). Успешная official discovery останавливает ненужные downstream поиски.

## 2. Hardware ↔ retail mapping

Runtime UK поиск hardware-входа читает опубликованные `searchUrl`/`queryParameterName` из `uhf-search`, вместо предположения о JSON-LD во всех регионах. Normalized query сначала **Xbox Series S**, затем 1883/полное имя при miss; own page должна явно подтвердить Model Number 1883. Runtime найдена [own UK Store 942J774TP9JN](https://www.microsoft.com/en-gb/d/xbox-series-s/942j774tp9jn); собственные SKU: **24K9**. В диагностическом live C реально найден и [Series S 1TB Black / 8ZCBGTT29H9C](https://www.microsoft.com/en-gb/d/xbox-series-s-1tb-black/8zcbgtt29h9c) с тем же **Model Number 1883**, без опубликованного SKU. Пустые поля не подменяются известными идентификаторами.

Отдельно реально проверенная [UK Store 942J774TP9JN](https://www.microsoft.com/en-gb/d/product-name/942J774TP9JN) публикует own SKU **24K9** и тот же model **1883**: source capture в `observed`, разбор проверен regression. Product ID, SKU, hardware model и manufacturer part сохраняются в разных полях; отсутствующий MPN не подменяется SKU. Это **один hardware → несколько retail configurations**, а не unique commercial SKU.

У строки 10 selected identity только `hardware_model_number=1883`; storage/color/bundle/Game Pass/kit/retail SKU не выбраны. Runtime PID и SKU-кандидаты остаются relations с URL/region. Physical axis triples, варианты массы/storage и clock/revision-specific значения остаются candidates. Готовность ограничена **hardware/model card**, для точной retail карточки нужен PID/SKU/конфигурация. [Relations + all facts](acceptance_summary.json); UI и Excel содержат отношения отдельно от selected identifiers.

## 3. Live vs replay

Stage 68 live 2/10 и replay 6/10 были не чистым сравнением transport: SHA application sources различались (6 файлов, список в summary). Live имел временные network failures строк 3/9; URL отмечался visited до успешного fetch, failed exact fetch не восстанавливался. Региональное ranking, CDN admission и default-title fixes были в replay версии. Нет доказательств, что основная причина Stage68 была CAPTCHA, rate limit, JS error или session. Stage69 диагностический live D отдельно показал HTTP200 search content variability: bare hardware number возвращал только replacement parts, verbose hardware query давал miss; после этого Google остановился на429. Добавлен normalized model query с обязательной own hardware-number проверкой, title anchor не стирается display-URL duplicate. Доказанные причины: transient fetch + premature candidate consumption + неодинаковая версия кода.

Теперь общий `fetch_with_retry`: максимум 2 попытки только network/5xx, успешные ответы cache, failed fetch не cache/visited. 429/403 challenge не ретраятся этим механизмом. Канонические URL не тратят slots на tracking duplicates, own region имеет приоритет. Google challenge/429 использует существующий attended flow; CAPTCHA автоматически не решается, host stop сохраняется. Диагностический `live_initial` имеет Google 429 и не выдан за финальный успех.

Последняя неизменная production версия: live E 205.3s, live F 251.7s. [Stability](stability.json): selected values/units/statuses/scopes, selected photos, selected source relations, identity, configuration и readiness совпадают по всем 10. DB IDs/timestamps исключены. Unselected candidate routes могут отличаться после bounded transient retries; это сохранено в исходных traces. Replay только HTTP responses live E, не registry и не доказательство live успеха. External fallback не требовался финальным 10 official successes.

## 4. Extraction и photos

Confirmed specs **123 → 138**, selected photos **15**. Own JSON-LD, embedded BuyBox, SKU payload, technical tables, published catalogs, Support GET API и PDFs проверены. Raw facts, accepted facts со source/scope и rejected candidates со reason доступны в JSON, UI и новых native Excel sheets.

Восстановлены CPU continuation после `<br>`, process 7nm, Elite assignable buttons/app requirements/own kit, compatibility prefix до Drivers available и own variant metric weight из двух единиц. Driver procedure suffix остаётся raw/rejected. Не выводятся оси из непомеченных triples, неоднозначная assembly weight, SoC `mm` вместо `mm²`, revision runtime/clock и модельный набор storage. Retail facts не заимствуются из related products. У hardware1883 storage/color/kit отсутствуют.

| ID | Raw до | Raw после | Accepted observations | Rejected/candidate observations | Confirmed до→после |
|---|---|---|---|---|---|
| 1 | 51 | 49 | 45 | 7 | 17→21 |
| 2 | 48 | 48 | 79 | 10 | 16→18 |
| 3 | 44 | 44 | 41 | 6 | 17→18 |
| 4 | 5 | 5 | 11 | 0 | 5→5 |
| 5 | 8 | 8 | 16 | 0 | 5→5 |
| 6 | 13 | 13 | 21 | 5 | 7→10 |
| 7 | 17 | 17 | 11 | 7 | 7→7 |
| 8 | 51 | 57 | 109 | 13 | 17→21 |
| 9 | 44 | 44 | 42 | 5 | 17→18 |
| 10 | 26 | 49 | 54 | 17 | 15→15 |


Counts raw/accepted/rejected — observations по найденным страницам, не взаимоисключающее partition: один raw value может дать accepted compatibility и rejected procedure suffix; duplicate observations не увеличивают confirmed fields. Exact color/gallery и own bundle packaging разделены. Storage варианты допускаются только для own одинакового цвета/внешнего вида; другой цвет/bundle остаётся candidate. Hardware-only фотографии — иллюстрации hardware family, **не выбранный цвет/комплект retail**. [Image byte checks](photo_inspection.json), [contact sheet](photo_contact.png), [full decode](image_validation.json).

## 5. Все 10 frozen inputs

| ID / input | Было live | Было replay | Root cause | Specs до→после | Photos | Identity | Стало |
|---|---|---|---|---|---|---|---|
| 1 / `Xbox Series X` | not_ready | not_ready | Catalog PID/SKU relation отсутствовала; имя не является SKU | 17→21 | 2 | published_catalog_configuration | export_ready |
| 2 / `Xbox Series S 512GB` | not_ready | not_ready | Catalog PID/SKU relation отсутствовала; отдельный controller был фото-кандидатом | 16→18 | 2 | published_catalog_configuration | export_ready |
| 3 / `8R02LKF9Q26R` | not_ready | export_ready | Live fetch/ranking; одиночный Store PID и фото | 17→18 | 2 | exact_store_product | export_ready |
| 4 / `8XN59CRBSQGZ/KPRJ` | export_ready | export_ready | Региональный own SKU/цвет; готовность сохранена | 5→5 | 1 | exact_store_sku | export_ready |
| 5 / `8QRF79K7JSR6/ZHP2` | not_ready | export_ready | Региональная фильтрация/цвет; общий retry | 5→5 | 1 | exact_store_sku | export_ready |
| 6 / `8RSN7J6375GG/99WM` | export_ready | export_ready | Табличное extraction: buttons/app/compatibility/kit | 7→10 | 2 | exact_store_sku | export_ready |
| 7 / `9203Q8W23LHN/HFXZ` | not_ready | export_ready | Официальный CDN/own PID; готовность сохранена | 7→7 | 1 | exact_store_sku | export_ready |
| 8 / `8N1BB8DSBKNT` | not_ready | not_ready | Дубли URL съедали budget; SearchAction отсутствовал | 17→21 | 1 | exact_store_product | export_ready |
| 9 / `8ZB8Z8MM10V0` | not_ready | export_ready | Временный fetch miss; повтор и exact PID | 17→18 | 1 | exact_store_product | export_ready |
| 10 / `1883` | not_ready | not_ready | Hardware ошибочно требовал retail SKU; UK search declaration | 15→15 | 2 | official_hardware_model_number | export_ready |


Новые ready: **1, 2, 3, 5, 7, 8, 9, 10** относительно старого live; относительно старого replay: **1, 2, 8, 10**. Not_ready в frozen 10 не осталось. Минимум confirmed specs≥3, подтверждённое selected photo и отсутствие conflicts сохранены. Manual optional; readiness не зависит от отсутствия User Guide. Row10 относится к hardware/model scope, а не exact retail readiness.

## 6. Manuals

Официальный русский Support content API и опубликованные family links проверены для consoles/controllers/Elite/headset. Русский Series X|S PDF визуально прочитан: **«Руководство по продукту и нормативным актам, ограниченная гарантия и соглашение»** — Safety/Regulatory, не User Guide. Accessories/Elite covers: Product and Regulatory Guide. PDFium и pypdf не восстанавливают кириллицу legacy fonts, поэтому автоматическая language verification и полный User Guide/Quick Start search остаются **«Не проверена»** во всех 10. Это честный advisory, не readiness blocker.

В проверенном индексе отдельный подтверждённый User Guide/Quick Start не найден; общий поиск не объявлен завершённым. Статус **«Проверена, не найдена»** не повышен из неполной проверки, Safety не переименован в User Guide. Визуальная RU Safety проверка отражена отдельно в [manual audit](manual_audit.json), [PDF renders](document_render.json). Автоматические три статуса сохранены: Проверена / Проверена, не найдена / Не проверена.

## 7. Regression, UI/Excel и integrity

Полный offline regression: **Ran 1633 tests in 680.832s; OK**, exit0, 684.5s, source_tree_unchanged=true. [Regression manifest](regression_release.json). 26 Stage68 +23 Stage69 targeted tests; negative controls: чужой регион/storage/SKU, 18830≠1883, other color/bundle, accessory-only photo, hardware one-to-many, 429 no retry, no name-only exact facts, optional manual.

10 native UI HTTP200; native exporter/openpyxl проверяет readiness/scopes/relations, error cells отсутствуют. [QA](qa_ui_excel.json), [Excel](export.xlsx). ArtifactTool импорт/inspection/render read-only, preview QA отдельная; известная Windows native exit failure после сохранения previews указана в render log, не подменяет native export проверку. UI screenshots строк 1/2/4/8/10 и White lightbox сохранены. Source manifest перед/после regression неизменен; prior reports/pins и frozen dataset не переписаны.

## 8. Verdict

**Xbox adapter production-ready for controlled use.** Ограничения controlled use: regional own official evidence; unknown retail остается hardware/model scope; unproved physical axes/revision specifics withheld; manual advisory; внешняя challenge требует attended flow. Результат 10/10 ограничен frozen набором и двумя реальными live повторениями; неизвестные SKU не получают гарантии готовности.

## 9. Git delivery

После этого PASS: `git diff --check`, commit **Stage 69**, push main, проверка HEAD==origin/main и clean working tree. Hash сообщается после commit, без self-referential report. В capture файлах сохранены точные bytes (`-text`); DB, browser profile/node_modules и temporary logs в commit не входят.

Воспроизведение из root: `PYTHONPATH=.`; `python reports/xbox_stage69/run_audit.py <fresh_phase>`; `python reports/xbox_stage69/replay.py <fresh_phase>` (transport из финального live E); `python reports/xbox_stage69/run_regression.py`. Live/replay DB требуют новое имя, существующие результаты не перезаписываются.
