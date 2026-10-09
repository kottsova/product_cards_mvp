# Stage 68 — Xbox baseline audit и перенос общего pipeline

Audit: **PASS**. Brand verdict: **Xbox adapter not ready**.
Набор неизменен; обычный первый запуск 0/10 ready, последний сохранённый live 2/10, окончательная проверка на захваченных публичных ответах 6/10. Captured transport проверяет extraction/identity/integration, но не доказывает live discovery success. Ложных подтверждённых configuration facts в окончательном прогоне нет; отрицательные контроли проверяют также название и описание выбранного цвета.

## 1. Baseline

Исходный HEAD `aba854121464779dccf909d817d50d315a31018e`. До адаптации обычный `run_once()` получил артикул **1882**, commercial name **Xbox Series X**, brand Xbox, category consoles. Ссылка Learn была исследовательским обоснованием входа и не передавалась worker. Region audit en-US; retail SKU/part, color, storage не известны.
Job **error**, readiness **not_ready**; official PDP, support/manual, facts и photos отсутствуют. Общая ветка использовала только DNS и получила `dealer_url_needed`, без проверенного URL. Query variants `1882`, `Xbox Series X 1882`, `Xbox Series X` зафиксированы, но Xbox official discovery в исходном worker отсутствовал; отдельная discovery trace пуста, фактическое исполнение полностью видно в семи job events. Не приписываем выполненные запросы предложенным вариантам. Worker SHA совпал до/после baseline. [Полный baseline](baseline.json), [скрипт](baseline.py).

## 2. Official Xbox / Microsoft structure

| Источник | Что действительно публикует | Граница доказательства |
|---|---|---|
| [Xbox Series X](https://www.xbox.com/en-US/consoles/xbox-series-x), [Series S](https://www.xbox.com/en-US/consoles/xbox-series-s) | Bounded specs drawer: PROCESSOR, MEMORY & STORAGE, VIDEO, SOUND, PORTS, DESIGN; варианты накопителя/привода/веса | Семейство и общие specs; таблица с несколькими вариантами не выбирает SKU |
| Xbox accessory PDP / technical tables | Battery, connectivity, controls, haptics, compatibility и варианты массы/комплектации | Не доказывает текущую hardware revision по одному имени |
| Declared `allConsoles.js`, `allAccessories-Sheet1.js` | Locale rows, `detailsURL`, `poPid`, `gaPid`, `specPid` | Catalog IDs — кандидаты для discovery; это не manufacturer part number |
| Xbox robots → CMS sitemap; Microsoft robots → Store sitemap index → hardware maps | Product links; региональные `xhtml:link` alternates; gzip | Реальный опубликованный маршрут; Unicode XML не декодируется как binary PDF |
| [Store controller](https://www.microsoft.com/en-us/d/xbox-wireless-controller/8xn59crbsqgz) | JSON-LD Product ID и `window.__BuyBox__.product.skuInfo`: SKU/title/display/gallery | Own row нужен для SKU; H1 и даже SKU gallery могут содержать другой default color |
| [Xbox Support manuals](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | SPA shell → declared public GET content API → ContentList/SectionItems → family PDF links | HTTP 200 shell не является проверенной инструкцией |
| [Learn Series X device ID](https://learn.microsoft.com/en-us/xbox/service-guides/series-x-console/series-x-device-id-and-disassembly), [Series S device ID](https://learn.microsoft.com/en-us/xbox/service-guides/series-s-console/series-s-device-id-and-disassembly) | Explicit Models 1882 / 1883; service document and spare-part IDs | Hardware number отдельно; service document part и replacement part не являются retail SKU |

Public Support GET строится только после проверки endpoint/method/path/query declaration в bundle: `https://content.support.xboxlive.com/content?path=/SXC/hardware-network/console/manuals-specs&language=ru-RU&market=RU`. Это опубликованный anonymous content contract. JSON assignments читаются `JSONDecoder.raw_decode`, JavaScript не исполняется. Источники и исходные ответы: [survey log](explore_http.json), `observed/`, [runtime HTTP](xbox_fetch.json), `xbox_captures/`.

Discovery: regional family → declared official sitemap/catalog → own Store pages → Support/device ID → other official regions → existing LG browser/search contracts → existing DNS fallback. Five family route hints служат стартовыми страницами; каждое собственное H1 проверяется. Нет registry десяти SKU→URL, нового search engine или hardware framework. Store ссылки берутся из опубликованных страниц и sitemap; регион и exact ID проверяются после ответа. Query/provider/URL/region/type/accepted/reason/relation сохраняются в per-job trace. Shared Bing/Google browser не дал надёжных PDP кандидатов в этих live runs; access/policy stops сохранены в [search log](xbox_search.json). Dealer evidence отдельно, неподтверждённый URL не становится official fact.

## 3. Identity rules

Family, commercial configuration, Store Product ID, Store SKU ID, manufacturer part number, hardware model number, region и revision различаются. Четырёхзначный вход типизируется как hardware number, но подтверждается только собственным источником; типизация не является evidence. `8XN59CRBSQGZ/KPRJ` означает Product ID плюс SKU, а не manufacturer part.
Exact Store identity требует своего URL/Product ID, own payload/JSON-LD и совпавшего storefront. При нескольких `skuInfo` Product ID один не выбирает default color; нужен собственный SKU/title. Catalog старый White `LK4W` не принимается за текущий `KPRJ`. Название строки Excel остаётся query hint. `manufacturer_part_number` не изобретён ни для одной строки. Model facts допускаются без retail SKU; storage/color/disc/kit/weight/axes не допускаются из model-only источника. Для запроса `1883` опубликованная hardware identity не подтверждает retail конфигурацию и физическую ревизию.

Default H1 Store Carbon Black сохранён как `page_default_titles` evidence; белая SKU row задаёт Robot White в `found_model` и description. У model-only документа название ограничено семейством. Проверены оба цвета и Product ID без SKU.

## 4. Storage / configuration / physical values

До canonical mapping сохраняется `section → raw label → value`. Advertised storage, usable storage, expansion-card support и USB external storage — отдельные поля. Own S 1 TB Store даёт `1TB Custom NVME SSD`; own Starter bundle — `512GB Custom NVME SSD`. Ни 512 GB из query hint, ни список 512 GB / 1 TB / 2 TB не становится exact storage. Usable capacity не опубликована в подтверждённых источниках и не вычисляется.
Disc/Digital и цвета из общей многовариантной таблицы остаются candidates. Масса/габариты без собственных variant/revision, явных осей и assembly binding удерживаются. Store S 1 TB даже публикует необычный общий dimensional triple — он не превращается в axis facts. Elite `345g ±15g` со сборкой не становится bare controller weight. Headset own SKU публикует 320 g, отображение — 0.32 кг. Common axis keys и cm→mm/g→kg проверены отдельно; синтетический metric control не выдаётся за найденные физические размеры frozen consoles.
CPU/GPU architecture — model-level. Для hardware-number запроса частоты CPU/GPU, runtime и radio revision удерживаются без exact revision linkage. Store и family могут публиковать разные clock values; own exact Store факты имеют scoped priority, исходные альтернативы остаются видимыми.

## 5. Bundles, photos, manuals, descriptions

[Diablo IV bundle](https://www.microsoft.com/en-us/d/xbox-series-x-diablo-iv-bundle/8n1bb8dsbknt) реально существует и доступен в исследовательском capture. Его own includes подтверждает Diablo IV и бонусные игровые предметы; Game Pass продаётся отдельно. Own parsing проверен тестом, но ordinary discovery не нашёл этот отсутствующий в актуальных catalog links товар — frozen row 8 остаётся not_ready. Это discovery gap, а не отсутствие PDP.
[Starter bundle](https://www.microsoft.com/en-us/d/xbox-series-s-starter-bundle/8zb8z8mm10v0) подтверждает собственные 512 GB и 3 months Game Pass Ultimate. Second controller, packaging contents или цвет не выводятся из базового комплекта/названия/картинки. Обе bundle rows независимы; base console не получает их game/kit.

Каждое gallery asset отдельно проверяется на family/color, даже если gallery находится в собственной SKU row. Black QP6M не становится фото White KPRJ; special Arctic Camo подтверждается своим ZHP2. Other color/bundle/lifestyle assets остаются photo candidates. Exact storage не требует отдельного рендера при явно связанном own Store asset; generic family exterior без связи не становится exact. Семь реальных official JPEG полностью декодированы, измерены и визуально просмотрены: S 1 TB 1, White controller 1, Arctic 1, Elite 2, headset 1, Starter 1. У Starter фактическое изображение — коробка bundle, несмотря на generic Series S alt; оно принадлежит own Store row, не используется для вывода комплекта или для base-console фото. Metadata: [photo inspection](photo_inspection.json), [contact sheet](photo_contact.png), [independent decode](image_validation.json).

User Guide / Setup Guide / Safety-Regulatory / Support article — отдельные роли. Три PDF реально проверены на bytes/структуру и отрисованы: console RU 16 pages, accessory multilingual 132, Elite multilingual 88. Обложки — product/regulatory/warranty, не User Guide. В RU PDF ToUnicode повреждает извлечение кириллицы и в pypdf, и в PDFium: визуально русский текст есть, runtime language verification недостаточна. Поэтому все десять User Guide statuses **«Не проверена»**, а не «Проверена, не найдена». Optional manual — advisory, не блокирует ready. [PDF render evidence](document_render.json), [RU cover](cab906c49b3dbd25fd6b_page_1.png). Статусы «Проверена» и «Проверена, не найдена» предусмотрены лишь для реально проверенного User Guide / полного проверенного поиска соответственно.
Descriptions строятся из scoped product title и допущенных характеристик. Account setup, activation, reset, repair, warranty и firmware procedures не используются; raw support/source candidates остаются доказательствами, а не описанием.

## 6. Frozen ten inputs

Frozen **2026-10-08T15:41:00.748965+00:00**, перед первым adapted run **2026-10-08T15:47:48.653338+00:00**. SHA-256 **`556dfe669181b1959e1d21dd52ed491f78719744bdbdab3442bef981de76191c`**. Baseline 1882 не повторяется как отдельная frozen row; frozen сложный hardware case — 1883 / GB. Имена могут содержать желаемые опции, но не подтверждают их. Входы не менялись после первого запуска. [Dataset](dataset.json), [digest](dataset.sha256).

| № | Вход / identifier type | Модель — только query hint | Регион |
|---|---|---|---|
| 1 | Xbox Series X / commercial_configuration | Xbox Series X 1TB Carbon Black Disc | en-US |
| 2 | Xbox Series S 512GB / commercial_configuration | Xbox Series S 512GB Robot White | en-US |
| 3 | 8R02LKF9Q26R / store_product_id | Xbox Series S 1TB Robot White | en-US |
| 4 | 8XN59CRBSQGZ/KPRJ / store_product_id/store_sku_id | Xbox Wireless Controller Robot White | en-US |
| 5 | 8QRF79K7JSR6/ZHP2 / store_product_id/store_sku_id | Xbox Wireless Controller Arctic Camo Special Edition | en-US |
| 6 | 8RSN7J6375GG/99WM / store_product_id/store_sku_id | Xbox Elite Wireless Controller Series 2 | en-US |
| 7 | 9203Q8W23LHN/HFXZ / store_product_id/store_sku_id | Xbox Wireless Headset | en-US |
| 8 | 8N1BB8DSBKNT / store_product_id | Xbox Series X Diablo IV Bundle | en-US |
| 9 | 8ZB8Z8MM10V0 / store_product_id | Xbox Series S Starter Bundle | en-US |
| 10 | 1883 / hardware_model_number | Xbox Series S hardware model 1883 | en-GB |

## 7. First-pass and final results

Первый adapted pass — обычный worker, без transport/adapter factory, без PDP URL во входах. Все десять family identities подтверждены, exact configurations не подтверждены, selected photos 0; все jobs needs_review, readiness not_ready. Колонки Raw/facts/confirmed различают исходные строки, нормализованные facts и подтверждённые технические поля. [First-pass JSON](first_pass.json).

| № | Official PDP | Support | Model / configuration identity | Raw / facts / confirmed specs | Фото | Manual | Dealer | Job / readiness | Главный gap |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-x) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 24 / 20 / 16 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing, conflicts |
| 2 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-s) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 21 / 19 / 15 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing, conflicts |
| 3 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-s) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 21 / 19 / 15 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing, conflicts |
| 4 | [семейство](https://www.xbox.com/en-US/accessories/controllers/xbox-wireless-controller) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 3 / 5 / 5 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing |
| 5 | [семейство](https://www.xbox.com/en-US/accessories/controllers/xbox-wireless-controller) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 3 / 5 / 5 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing |
| 6 | [семейство](https://www.xbox.com/en-US/accessories/controllers/elite-wireless-controller-series-2) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 9 / 7 / 7 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing |
| 7 | [семейство](https://www.xbox.com/en-US/accessories/headsets/xbox-wireless-headset) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 11 / 6 / 6 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing |
| 8 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-x) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 24 / 20 / 16 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing, conflicts |
| 9 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-s) | [индекс](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 21 / 19 / 15 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing, conflicts |
| 10 | [семейство](https://www.xbox.com/en-GB/consoles/xbox-series-s) | [индекс](https://support.xbox.com/en-GB/help/hardware-network/console/manuals-specs) | model_confirmed / unproven | 26 / 19 / 15 | 0 | Не проверена | dealer_url_needed | needs_review / not_ready | configuration_unresolved, exact_photo_missing, conflicts |

Последний сохранённый live run готовит строки 4 и 6: **2/10**. Network timeouts / budget / blocked search и ещё не исправленные на тот момент extraction guards сохранены честно. Окончательные sources проверены transport-only replay на собственных захваченных публичных ответах; factories заменяют HTTP/search transport, не discovery registry. Captured readiness **6/10**, это не новая live гарантия. Все десять model identities сохранены. [Final live](final_live.json), [final captured acceptance](acceptance_release_final.json).

| № | Exact PDP / family | Configuration identity | Hardware identity | Confirmed specs | Фото | Live / captured readiness | Remaining blockers |
|---|---|---|---|---|---|---|---|
| 1 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-x) | unproven | unproven | 17 | 0 | not_ready / not_ready | configuration_unresolved, exact_photo_missing |
| 2 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-s) | unproven | unproven | 16 | 0 | not_ready / not_ready | configuration_unresolved, exact_photo_missing |
| 3 | [Store](https://www.microsoft.com/en-us/d/xbox-series-s-1tb-white/8r02lkf9q26r) | exact_store_product | unproven | 17 | 1 | not_ready / export_ready | нет; manual — advisory |
| 4 | [Store](https://www.microsoft.com/en-us/d/xbox-wireless-controller/8xn59crbsqgz) | exact_store_sku | unproven | 5 | 1 | export_ready / export_ready | нет; manual — advisory |
| 5 | [Store](https://www.microsoft.com/en-us/d/xbox-wireless-controller-arctic-camo-special-edition/8qrf79k7jsr6) | exact_store_sku | unproven | 5 | 1 | not_ready / export_ready | нет; manual — advisory |
| 6 | [Store](https://www.microsoft.com/en-us/d/xbox-elite-wireless-controller-series-2/8rsn7j6375gg) | exact_store_sku | unproven | 7 | 2 | export_ready / export_ready | нет; manual — advisory |
| 7 | [Store](https://www.microsoft.com/en-us/d/xbox-wireless-headset/9203q8w23lhn) | exact_store_sku | unproven | 7 | 1 | not_ready / export_ready | нет; manual — advisory |
| 8 | [семейство](https://www.xbox.com/en-US/consoles/xbox-series-x) | unproven | unproven | 17 | 0 | not_ready / not_ready | configuration_unresolved, exact_photo_missing |
| 9 | [Store](https://www.microsoft.com/en-us/d/xbox-series-s-starter-bundle/8zb8z8mm10v0) | exact_store_product | unproven | 17 | 1 | not_ready / export_ready | нет; manual — advisory |
| 10 | [семейство](https://www.xbox.com/en-GB/consoles/xbox-series-s) | unproven | official_hardware_model_number | 15 | 0 | not_ready / not_ready | configuration_unresolved, exact_photo_missing |

Ранние промежуточные `validation_live`, `acceptance_replay`, `acceptance_final`, `acceptance_release` не переписывались. Они показывают развитие исправлений и не являются окончательной приёмкой. Окончательная production SHA manifest в `acceptance_release_final.json` совпадает с текущими файлами.

## 8. Six edge cases and UI / Excel

| Edge | Результат отрицательного контроля |
|---|---|
| Series X vs S | Own H1 family mismatch отклоняется, атрибуты не принимаются |
| 512 GB vs 1 TB | Own Starter 512 GB / own S 1 TB независимы; options и usable storage не изобретаются |
| Same controller, different color | KPRJ Robot White / QP6M Carbon Black: независимые photos, title и description; чужой цвет candidate |
| Base vs bundle | Diablo game / Starter Game Pass из own evidence; base не получает bundle kit, second controller или packaging |
| Regional SKU | en-US ответ не подтверждает en-GB SKU; stale catalog LK4W не равен own KPRJ |
| Revision values | Model 1883 подтверждён Learn, но weight/axes/clocks/runtime/radio другой ревизии удерживаются |

Штатный FastAPI UI: **10 HTTP 200**; проверены русские labels, existing parent sections и roles core/feature, отдельные identity/configuration/storage/bundle/candidate/manual blocks. Сейчас admitted Xbox rows проходят как core; отсутствующие feature specs не создавались ради заполнения. Имена фирменных технологий сохраняют регистр, hours отображаются как ч, общая metric projection использует mm/kg. Support procedures отсутствуют в descriptions. Скриншоты overview/evidence строк 3,4,7,9,10 и White photo lightbox сохранены. [UI/Excel QA](qa_ui_excel.json), [presentation controls](presentation_checks.json), [White UI](ui_4_evidence.png), [lightbox](ui_4_lightbox.png).
Native openpyxl export валиден, ten readiness rows, ошибок ячеек/формул нет. Дополнительные sheets: «Готовность Xbox», «Конфигурация Xbox», «Идентификаторы Xbox», «Кандидаты Xbox», «Документы Xbox», общий «Фото-кандидаты». Исходные labels/sections сохранены в candidates. [Excel](export.xlsx), [readiness preview](excel_readiness.png), [configuration preview](excel_configuration.png). ArtifactTool read-only import/render записал все пять final previews; независимый PNG decode проходит. Его процесс завершился ошибкой после вывода (final shell exit 1, предыдущий native exit -1073740791). Это ограничение renderer runtime; успех процесса renderer не заявляется, native exporter проверен отдельно.

## 9. Нужен ли отдельный hardware-resolution layer

**В этом Stage отдельный framework не требуется.** Brand adapter уложился в существующие policy HTTP, shared sitemap/search/dealer, jobs/storage, normalization/resolution, evidence/readiness, UI/export. Существующие brand thresholds сохранены; добавлены отдельные Xbox source scopes и короткие typed identity guards.
Открытая задача — доказанная связь hardware model/revision ↔ retail SKU/manufacturer part и exact discovery по commercial configuration. Это расширение evidence/resolution contracts, не доказательство необходимости нового framework. Набора из десяти недостаточно, чтобы объявить весь Xbox production-ready.

## 10. Regression and integrity

`A:\work\dev\product_cards_mvp\.venv\Scripts\python.exe -m tests`: **Ran 1610 tests in 580.946s; OK**, exit **0**, 583.8 с. SHA-256 всех application/test `.py`, `.js`, `.html` до и после совпадают: `source_tree_unchanged=true`.
[Regression summary](regression_release.json). Targeted Xbox: **26 tests OK**; neighboring Stage 66/67 PlayStation: **41 tests OK**. Полный набор ожидает 1584 прежних + 26 новых tests. Два ранних полных прогона остановлены для реальных найденных исправлений; они не засчитываются. В финальном полном прогоне application/test sources не меняются.
Archive source protection: только новый Stage 68 authorization/pins block в `tests/_pipeline_migration.py`, все предыдущие pins/reports сохранены. Ten changed shared production files имеют финальные SHA pins; новые Xbox files входят в regression source manifest. [Migration evidence](migration_record.json). `.gitattributes` задаёт `-text` для Stage 68 evidence, чтобы Windows autocrlf не менял frozen/captured bytes. Перед commit обязательны `git diff --check`, staged dataset SHA verification и full regression PASS.

## 11. Verdict and concrete blockers

Audit **PASS**; **Xbox adapter not ready**.

Исправленные системные ошибки: Unicode sitemap ошибочно прошёл binary document conversion; gzip bytes терялись; региональные sitemap URLs были в alternates; несколько audio formats стали ложным конфликтом; photo `box` regex совпадал с Xbox; собственный published image CDN исключался; default Black title ошибочно описывал White SKU; normalization меняла регистр branded terms. Исправления проверены реальными captures и отрицательными контролями.
Остаются реальные/не закрытые gaps:

- Rows 1/2: commercial name не подтверждает exact retail storage/color/disc; нужны own configuration relations и exact photos.
- Row 8: исследованный Diablo PDP существует, но обычная discovery chain его не нашла через текущие опубликованные catalog/sitemap links и blocked browser fallback.
- Row 10: published 1883 не связывает hardware revision с конкретным GB retail SKU/physical table; перенос массы/габаритов запрещён.
- Live discovery нестабилен: captured 6/10 нельзя выдавать за live 6/10.
- Canonical extraction coverage неполна: некоторые SoC/process/control fields и многовариантные physical values остаются candidates; не все platform features извлечены.
- RU PDF text/language verification остаётся незавершённой; manual optional, поэтому это advisory, но статус не повышен.

## 12. Git delivery

После full PASS: commit **`Stage 68`**, push main, проверка `HEAD == origin/main` и clean working tree. Сам hash сообщается после commit в финальном ответе, чтобы не создавать self-referential report commit. Предыдущие Stage 66/67 evidence не переписаны.

Воспроизведение (из repository root, `PYTHONPATH=.`):

```powershell
.venv\Scripts\python.exe -m tests test_xbox_stage68.py
.venv\Scripts\python.exe reports/xbox_stage68/replay.py acceptance_new
.venv\Scripts\python.exe reports/xbox_stage68/run_regression.py
```

Replay требует нового имени фазы и не перезаписывает предыдущую DB. Final QA использует `acceptance_release_final.sqlite3`; reproducible capture scripts и все PDF/HTML/JSON inputs архивированы, SQLite не коммитится. `build_report.py` сверяет final source hashes, configuration scope, descriptions, UI groups и только после успешной полной регрессии выставляет audit PASS.
