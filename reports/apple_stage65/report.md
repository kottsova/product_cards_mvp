# Stage 65 — Apple model-level specs + configuration overrides

Дата: 2026-10-08. Исходный commit Stage 64: `780d5bad122624fd7b667cce668a6084f5f9b40d`.

Stage 65: PASS после финального regression. Вердикт: **Apple adapter production-ready for controlled use** в перечисленном ниже объёме. Готовность не означает, что каждый возможный raw field нормализован или что неподтверждённые варианты можно экспортировать как exact facts.

## 1. Model/configuration identity

Точная модель/поколение связывается с SKU через официальный single-SKU PDP, согласованные exact partNumber selection records либо уникальную строку официального публичного каталога. Tech Specs проверяется по собственному h1 модели/поколения. `Axxxx` не используется вместо commercial SKU.

Два отдельных источника: `apple` хранит order/configuration evidence, `apple_model` — scoped model Tech Specs. Resolver помечает общие факты `model_confirmed_official` без `full_sku_confirmed`; точные order overrides сохраняют отдельный уровень. Общий worker, storage, normalization, evidence, UI и native Excel exporter переиспользованы. Общая readiness вызывает Apple gate. Глобальные thresholds других брендов не менялись.

Поддерживаемый registry: iPhone 16; iPhone 15 Pro; iPad (A16); MacBook Air 13-inch M4 (2025); MacBook Pro 14-inch M4 (2024); Watch Series 10 с отдельно подтверждённым размером; AirPods 4 ANC. Другие модели не повышаются до confirmed по похожему названию. Например, M4 Pro/Max не считается базовым M4.

## 2. iPhone results

MYAP3LL/A, MYAQ3LL/A, MYAR3LL/A: точная модель iPhone 16, разные официальные selection image/color records. Все carrier-записи одного partNumber согласованы по model/color/storage. `seoUrlToken` каждой exact записи содержит 128gb; это самостоятельное configuration evidence, не список ёмкостей Tech Specs. Получены 22 model-level + 2 exact order facts на SKU.

FTUV3ZD/A: refurbished iPhone 15 Pro, 128GB, Black Titanium; точная UK storefront PDP и отдельная model Tech Specs. Refurbished не превращает модель в отдельное поколение. Region здесь означает подтверждённый официальный storefront; SKU suffix сам по себе не доказывает SIM/radio configuration.

Retail new status не выведен из отсутствия слова Refurbished. У retailer selection records нет явного itemCondition — new/refurb остаётся неизвестным там, где источник его не публикует.

## 3. iPad results

FD3Y4LL/A и FD4A4CL/A: одна модель iPad (A16), отдельные exact PDP titles подтверждают 128GB, Silver/Blue, refurbished и Wi-Fi. Список 128/256/512GB на модельной странице остаётся candidate. Wi-Fi weight 477 g не смешивается с Cellular 481 g. Для Wi-Fi конфигурации Cellular runtime не подтверждается.

## 4. Watch result

FWWU3LW/A: Series 10, 46 mm, aluminum, GPS, Rose Gold. Scoped таблица даёт height 46 mm, width 39 mm, depth 9.7 mm, weight 36.4 g. Размеры 42 mm и другие material/connectivity weights отклонены. Общие технологии дисплея/сенсоры/runtime — model-level, размеры — применимы только после проверенного size/variant routing. Точные аксессуары и ремешок, которые ещё не разобраны в отдельные поля, остаются metadata, а не confirmed комплектацией.

## 5. AirPods result

Redirect Store на AirPods 5 отвергнут. Проверен сам публичный NASPO Apple Branded PDF: page 8 содержит exact MXP93LL/A → AirPods 4 with Active Noise Cancellation. URL: https://www.apple.com/education/purchase/contracts/docs/NASPO_PSS_Apple_Branded.pdf . SHA-256: `551a7a0255c7697eb97fb4536538aaa3fab362a2d8356667071c30899ee04ab7`. Страница визуально проверена в naspo_page8.png. PDF является catalog identity source, а не PDP, manual или спецификацией.

Штатный повторный run_once после добавления общего official catalog fallback получил 8 model-level facts и 1 официальный render exact ANC model (1000×1000 PNG). Источник: https://support.apple.com/en-us/121204 . Цвет не опубликован в exact catalog row: White из имени входной строки не становится confirmed color fact. Render имеет exact model relation; SKU-specific color relation не заявлена. Память и color overrides для модели, у которой источник не задаёт этих конфигурационных полей, readiness не требует.

Отрицательный контроль: свежий Education Institution Price List содержит уже AirPods 5 и не содержит MXP93LL/A, хотя search index показывал старую версию. Cached search snippet не принят. Файлы catalog_audit.json и official_catalog.pdf сохраняют отрицательный результат. Актуальность наличия/цены по старому NASPO каталогу не утверждается.

## 6. Classification

`classification(canonical_attribute, category)` и category-aware admission различают model-stable и configuration-sensitive. Stable: chip, экран, камеры, Wi-Fi/Bluetooth, IP, sensors, charging, mode-specific runtime. Sensitive: storage, RAM, color, condition, region, size, cellular, accessories. Mac GPU тоже sensitive: Air M4 предлагает 8/10 GPU cores, поэтому family GPU options не подтверждены; точный PDP override даёт 8 baseline и 10 FC6U4. Watch dimensions/resolution/weight требуют case size; iPad weight/runtime требуют connectivity.

До mapping сохраняются section/raw label/value. Неизвестные поля, family options, conditional accessories, региональные SIM/cellular bands и другие неподтверждённые возможности остаются кандидатами. Отдельный тяжёлый configuration-resolution framework не создан.

## 7. Battery/runtime

iPhone: видео, потоковое видео, аудио — разные canonical fields (iPhone 16: up to 22/18/80 hours). Mac: wireless web, streaming video, Wh отдельно. iPad: web Wi-Fi и video представлены отдельно с одной исходной цитатой up to 10 h; Cellular 9 h только у подтверждённого Cellular variant. Watch: normal 18 h, Low Power 36 h, fast charge до 80% около 30 min отдельно; короткая зарядка для normal use/sleep tracking — отдельные поля. AirPods: single charge/case и ANC on/off отдельно (4/5/20/30 h).

Raw up to/max заявления сохранены как опубликованные максимумы; гарантированная автономность и сторонние mAh не добавлены.

## 8. Manuals

Проверены official RU guide pages. Для iPhone 16, iPhone 15 Pro и iPad (A16) прочитаны главы с exact h1 модели, русским lang и содержимым — статус «Проверена». Итого 6/10 dataset карточек. Mac Getting Started, Watch и AirPods User Guide найдены на русском, но exact generation chapter coverage не доказана — «Не проверена». «Проверена, не найдена» не применяется после неполной проверки. Руководства advisory; support/repair/safety articles не объявлены User Guide. Support/setup/help не внесены в description.

## 9. Photos and Excel

Storage не блокирует exact model/color photos. Сохранены отдельные цвета iPhone и iPad; packaging/multi-color/conflicting/unknown-color assets не повышены до product gallery. В dataset 23 selected фото, baseline ещё 4: всего 27 скачанных и проверенных файлов. 11 кандидатов включая baseline экспортированы отдельно.

Лист «Фото-кандидаты» создаётся только при candidates > 0. Apple-only headers: SKU, модель, URL, причина, model relation, color relation, width, height, bytes, format. Все 11 candidate-файлов измерены по фактическим байтам (1000×1000 JPG), не по параметрам URL. Основной фото-лист содержит confirmed gallery. Mixed-brand export сохраняет прежние колонки кандидатов и добавляет Apple relation columns. Проверен тест отсутствия пустого candidate sheet.

UI: 11 страниц HTTP200, model/config evidence и manual status; проверены gallery/lightboxes и 15 скриншотов. Native exporter проверен read-only, затем artifact-tool inspect/render. Excel не переавторивался альтернативным движком.

## 10. Frozen dataset before/after

Dataset Stage 64 не изменён, SHA-256: `8df1c4527b47f2c2103ff7fe70dc55e607dea50aa5cab20fb7ea6fcab5f41f81`.

| SKU | Model identity | Configuration identity | Model specs | Order specs¹ | Фото | RU manual | Было → стало |
|---|---|---|---:|---:|---:|---|---|
| MYAP3LL/A | iPhone 16 | exact_order_record | 22 | 2 | 1 | Проверена | not_ready → export_ready |
| MYAQ3LL/A | iPhone 16 | exact_order_record | 22 | 2 | 1 | Проверена | not_ready → export_ready |
| MYAR3LL/A | iPhone 16 | exact_order_record | 22 | 2 | 1 | Проверена | not_ready → export_ready |
| FW2U3LL/A | MacBook Pro (14-inch, M4, 2024) | exact_part_number | 6 | 15 | 5 | Не проверена | export_ready → export_ready |
| FC6U4LL/A | MacBook Air (13-inch, M4, 2025) | exact_part_number | 6 | 15 | 5 | Не проверена | export_ready → export_ready |
| FD3Y4LL/A | iPad (A16) | exact_part_number | 14 | 8 | 2 | Проверена | not_ready → export_ready |
| FWWU3LW/A | Apple Watch Series 10 | exact_part_number | 16 | 4 | 2 | Не проверена | not_ready → export_ready |
| MXP93LL/A | AirPods 4 with Active Noise Cancellation | exact_part_number | 8 | 0 | 1 | Не проверена | not_ready → export_ready |
| FTUV3ZD/A | iPhone 15 Pro | exact_part_number | 13 | 11 | 3 | Проверена | not_ready → export_ready |
| FD4A4CL/A | iPad (A16) | exact_part_number | 14 | 8 | 2 | Проверена | not_ready → export_ready |

¹ Order specs — количество resolved фактов выбранного exact order source, не число только конфигурационных полей: PDP также содержит общие технические факты. Конфигурационные поля отдельно перечислены в release_verification.json. Model specs — факты выбранного model source, без повторов, которые закрывает order override.

Итог: 10/10 export_ready вместо 2/10; все прежние 8 not_ready вышли естественно. 210 подтверждённых resolved характеристик dataset, из них 143 выбраны из model source. Baseline: 21 resolved facts / 4 photos.

## 11. Edge cases / regression

Offline tests покрывают разные цвета одной модели, несовпадение storage в exact records, refurb/new model relation, A-number vs commercial SKU, Watch 42/46, iPad Wi-Fi/Cellular, AirPods generation rejection, Mac M4 Pro mismatch, family options, runtime modes, model facts без ложного full_sku, manual advisory и photo candidate export.

11 model parser replays на сохранённых actual response bodies совпали с live admission. 27 image SHA-256 проверены. Configuration facts сверены вручную с exact titles/selection records/scoped tables. Ложных confirmed configuration facts на проверенной выборке не найдено.

23 новых Stage 65 теста; вместе с 14 Stage 64 целевых проверок — 37 тестов. Mac wireless web использует один canonical label на PDP и Tech Specs, без дублирования.

Финальный полный regression и неизменность source tree зафиксированы в regression_release.json. Git diff --check обязателен перед release.

## 12. Verdict and controlled-use limits

**Apple adapter production-ready for controlled use** для registry выше, с показанными scopes/candidates и advisory manuals. Это не blanket confirmation для всех Apple моделей/SKU. Неподдерживаемые модели, неразрешённый storage/RAM/Mac GPU/Watch size/connectivity, другой цвет или поколение не повышаются автоматически.

Оставшиеся ограничения: расширение model registry/discovery, полный русский mapping редких features, AirPods H2 и отдельные earbud/case dimensions, typed accessories/band overrides; точная радио/SIM regional configuration и condition отсутствующего в payload retail new SKU не заявлены. Для нового SKU нужна действительная official relation; существование семейства и suffix недостаточны. Эти ограничения не скрываются за ready и не дают ложных exact фактов.

## 13. GitHub release

Commit message: Stage 65. Полный hash, push, HEAD == origin/main и clean tree сообщаются после release; commit hash не встраивается в собственное содержимое commit.
