# Stage 61 — Lenovo extraction recovery и readiness

Дата: 2026-10-07. Предыдущий audit PASS: `c067074a2079cbc83b3205cec20de300e2bf7b24`.

## Результат и границы

Финальный production `run_once()` на неизменной выборке Stage 60: 10/10 exact identity, 378 подтверждённых характеристик вместо 68, 440 исходных строк, 62 условных/служебных/вариантных строки отдельно, 10 проверенных русских User Guide. 2 карточки готовы, 8 не готовы из-за неподтверждённой связи фото с конфигурацией. Baseline отдельно: 9 фактов, exact Support identity, русский User Guide проверен, карточка не готова из-за фото.

**Stage 61 PASS. Lenovo adapter production-ready for controlled use.** Уровень готовности адаптера относится к контролируемому использованию с официальными attended captures и проверенными локальными доказательствами; он не означает автоматическую готовность любого Lenovo MTM или всех карточек выборки.

## 1. Baseline 21ML005BUS

ThinkPad T14 Gen 5 (Intel), machine type 21ML, полный MTM/part number 21ML005BUS. Support сообщает именно исходный полный MTM. Из 9 безусловных Support Description извлечённых фактов дополнительных exact configuration данных не получено; условное WLAN и family options не подтверждаются.

Причина ограничения доказана для проверенных публичных каналов: официальный frontend PSREF Info GET вернул HTTP 200, `code:0`, `No corresponding model found` ([сырой ответ](baseline_psref_frontend_info.json)). Первая legacy hierarchical ссылка ушла на 404; она сама по себе не доказывала отсутствие. Проверка наблюдавшегося frontend Info endpoint с параметром исходного MTM дала окончательный code 0. Support browser XHR показывает каталог/помощь без дополнительных exact спецификаций. Региональный storefront ведёт на family LEN101T0089. Это предел проверенных каналов, а не утверждение, что сведений нет нигде.

Русский HTML User Guide SG10265 проверен по содержимому RU, `<html lang=ru>`, prodname с machine type 21ML. Он относится к семейству/типу, не доказывает внутреннюю конфигурацию. Job `done`, readiness `not_ready`, единственный blocking gap `exact_gallery_not_confirmed`. Query variants, источники, identity и события сохранены в [baseline_final.json](baseline_final.json); before-run Stage 60 остаётся без изменения.

## 2. Official structure и причина 403

PSREF — основной технический источник exact configuration; Support — identity, документация и fallback; региональные product/storefront — маркетинг и фото; другие official regions/search и dealer — только оставшиеся gaps. JSON-LD storefront с семейным URL не становится exact PDP. Sitemap/Support ссылки полезны для discovery, не для повышения identity.

HTTP-клиент Stage 60 получал API 403. Обычный видимый браузер без stealth, proxy, cookie import и обхода challenge загрузил официальный frontend: публичный anonymous `/api/home/auth/issue` вернул 200, после него Info, SpecData, Photo, ShowDocumentations также 200. Токены и cookies не сохраняются в captures, только `authorization_present: true`. При защищённом challenge/status capture прекращается.

Наблюдавшиеся официальные пути: `/api/model/Info/GetInfoByKey`, `/api/model/Info/SpecData`, `/api/product/Photo/{ProductId}`, `/api/product/Info/ShowDocumentations`. Frontend Excel экспорт `/api/model/Transfer/ExportCompareModelExcel` также возвращает Product/Model и одиночную конфигурацию. SpecData и ModelGroupTable дают section → raw label → value + notes; исходные payload сохранены отдельно. Учитываются только HTTPS official responses 200 с проверенными SHA256, article/query и product relation. Browser capture — явный operator step, не фоновый способ обходить 403.

## 3. Exact PSREF и identity rules

Точный технический факт разрешён только если Info.Model равен исходному full article, ModelGroupTable содержит ровно одну строку Model с этим article, ProductKey и ProductID согласованы между Info и SpecData. CTO/XXXX не становятся resolved. Параметр URL, family name или похожий MTM сами по себе ничего не доказывают. Все 10 соответствий доступны в [final_verified.json](final_verified.json) и исходных [captures](psref_captures).

Marketing name, family, generation, machine type, полный MTM, part number и regional SKU сохраняют свои роли. `exact_mtm` для PSREF full article — конфигурационное отношение; для мониторов этот full article является полным manufacturer part number. User Guides остаются `family_model`, фото без дополнительного доказательства — candidates. 83EM00KVMX относится к Nordics, а не автоматически к Mexico; 83LY00JCRK PSREF относит к Kazakhstan. Суффикс не заменяет official regional evidence.

## 4. Configuration facts и варианты

440 raw rows: 378 exact accepted, 62 rejected/candidates. `up to`, `optional`, `starting at`, `around/approximately`, `varies`, квалифицирующие notes, несколько CPU/display/storage alternatives остаются candidate metadata. Max/supported capabilities и service/warranty/BIOS/driver поля не входят в подтверждённые продуктовые характеристики. Реально сконфигурированные порты сохраняются; их перечень не считается несколькими конфигурациями. Возможные CPU/дисплеи из family PSREF или manuals не импортируются как exact facts.

[before_after.json](before_after.json) содержит по каждой модели CPU, GPU, RAM, storage, display, ports, wireless, battery, dimensions, weight, camera, keyboard, OS, color, accessories с исходными подтверждёнными и кандидатными строками. `not_present_in_exact_source` означает отсутствие строки в этой конфигурационной выдаче, а не доказательство отсутствия устройства/опции. Raw label/section/value не заменяются русским отображением.

Русские canonical labels и parent groups применяются общей проекцией. Thunderbolt, Wi-Fi, Dolby, TPM и branded terms остаются техническими терминами. Однозначные metric WxDxH проецируются в Ширина/Глубина/Высота товара, мм; исходная строка сохранена. Вес starting at/приблизительный и размеры с несколькими положениями подставки не становятся exact числом. Упаковочные значения не придумываются.

## 5. Manuals

Все 10 моделей и baseline имеют проверенный русский User Guide. Для пяти моделей проверен полный PDF: X1 Carbon (98 страниц), ThinkBook (44), T27i-30 (40), P40w-20 (58), Tab P12 (49). Для остальных — реальное RU HTML body SG10252/SG10115/SG10260 и покрывающий machine type prodname. Порог определения русского документа существующий: не ослаблен; индексный RU переключатель или filename сам по себе недостаточен.

Официальные PDF: [X1 Carbon](https://download.lenovo.com/pccbbs/mobiles_pdf/x1_carbon_gen12_2in1_gen9_ug_ru.pdf), [ThinkBook](https://download.lenovo.com/consumer/mobiles_pub/lenovo_thinkbook_14_16_gen_6_ug_ru.pdf). Остальные точные URLs и language assessments приведены в [pdf_language_audit.json](pdf_language_audit.json) и [manual_reviews.json](psref_captures/manual_reviews.json).

User Guide, Setup Guide, Hardware Maintenance Manual, Safety/Warranty Guide, Regulatory Notice разделены; 423 непроверенных index candidates сохранены отдельно. HMM не принимается за пользовательскую инструкцию; repair/driver/BIOS/help не попадает в description. PDF обложка с другими региональными part numbers не переносит конфигурационные характеристики: relation family/type. Статус `Проверена` требует фактического локального body/PDF proof и сохранённого verified User Guide. Если proof отсутствует, `Не проверена` с technical blocker, а не `Проверена, не найдена`.

## 6. Photos

Официальный model-filtered PSREF Photo endpoint имеет null color/tags и потому сам по себе не доказывает exact фото. У 83EM007FLK (Arctic Grey) и 83EM00KVMX (Abyss Blue) один family ProductKey, но разные assets. Реальные PNG 2000×2000 загружены и визуально проверены: серый и синий цвет совпадают с exact Case Color. Два reviewed color-bound renders выбраны; 110 остальных фото остаются кандидатами.

Подтверждение относится к цвету иллюстративного рендера. Раскладка клавиатуры и внутренняя CPU/RAM конфигурация на фото не подтверждены; ограничение показано в UI. Нельзя автоматически повышать lifestyle, схемы портов, family render или другие цвета. Новые проверенные assets выбираются при первом импорте; повторный запуск сохраняет ручное снятие выбора. Readiness требует выбранное verified фото, чтобы UI и Excel не расходились.

## 7. Monitor recovery

63A4ZAR1U1 → ThinkVision T27i-30: Info.Model + одиночная ModelGroupTable + ProductKey/ID совпадают, 35 фактов. 62C1GAT6EU → ThinkVision P40w-20: та же цепочка, 34 факта. Причина Stage 60 unresolved — отсутствие exact PSREF payload в extraction/evidence routing, а не необходимость hardcode или отдельного Google engine. Формат part numbers существующая нормализация уже допускает. Габариты/вес с несколькими положениями и условиями остаются кандидатами. Оба job done, но not_ready из-за фото.

## 8. Frozen 10: before → after

Dataset SHA256: `968208f0640ce837e0e0a519b2b427274c4d7bb11eb9f16c1594c18df12607a9`. Исходный [dataset Stage 60](../lenovo_stage60/dataset_frozen.json) не менялся. 4 серии ноутбуков, 2 монитора, desktop, tablet и 2 сложных regional SKU сохранены.

| Article | Confirmed facts before → after | Candidates | After readiness |
|---|---:|---:|---|
| 21KC0029MH | 9 → 42 | 10 | Не готова: фото |
| 21KG0004AT | 9 → 40 | 7 | Не готова: фото |
| 83EM007FLK | 8 → 38 | 6 | Готова |
| 83LY0066PB | 10 → 40 | 7 | Не готова: фото |
| 63A4ZAR1U1 | 0 → 35 | 4 | Не готова: фото |
| 62C1GAT6EU | 0 → 34 | 5 | Не готова: фото |
| 12E4S96402 | 6 → 43 | 6 | Не готова: фото |
| ZACH0134PL | 7 → 27 | 5 | Не готова: фото |
| 83EM00KVMX | 9 → 38 | 6 | Готова |
| 83LY00JCRK | 10 → 41 | 6 | Не готова: фото |

До: 8 exact, 2 unresolved, 0 ready. После: 10 exact, 0 unresolved, 2 ready. У всех 10 PSREF exact, User Guide RU проверен, job done, real conflicts 0. Dealer fallback не понадобился для этих 10: exact technical facts получены из official PSREF. DNS manufacturer code должен совпасть с full part number/MTM, если fallback потребуется позже.

## 9. False/ambiguous config audit и architecture

Независимо проверены exact MTM, family-only relation и многовариантный PSREF; другие Model/MTM, mismatched ProductKey, CTO, множественные CPU/display, qualified weights, color-null galleries, HMM вместо UG, RU UI при EN body, другой machine type и отсутствующий proof отклоняются. Эти случаи зафиксированы регрессионными тестами. Ложных confirmed configurations в проверенных 10 и baseline не обнаружено; это не утверждение обо всех моделях Lenovo.

Отдельный configuration-resolution layer на выборке не нужен. Общий Excel → discovery → identity → extraction → normalization → evidence → readiness → UI → Excel работает с небольшими Lenovo-specific parsers/capture adapter. Exact-row extraction и source routing восстановили факты, оба монитора разрешены без модельных исключений. CTO/custom-config за пределами доказанного scope; без exact relation консервативный gap сохраняется.

## 10. UI, Excel, regression и controlled workflow

10 HTML product pages HTTP 200; labels/parent groups, raw audit, configuration/photo/manual candidates и readiness проверены; support-service полей в продуктовых фактах нет. Excel содержит 378 fact audit rows, 10 инструкций, 2 выбранных confirmed цветных фото, 110 фото-кандидатов, 62 configuration candidates и 423 document candidates. Ready 2, not_ready 8. Screenshots UI и три read-only Excel renders просмотрены; PNG рендеры сверяют presentation, исходные фото проверены отдельно.

Для нового article оператор выполняет обычный attended capture и использует `psref_captures` рядом с рабочей DB/fetch log:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.venv/playwright-browsers'
.venv/Scripts/python.exe -m product_tool.census.attended_psref --article FULL_ARTICLE --output data/psref_captures --profile data/lenovo_attended_profile
```

При challenge/403 capture останавливается; protected API не ретраится обходными средствами. Photo/manual proofs проверяются отдельно; readiness не повышается по одному article параметру. Production capture CLI прошёл live smoke на 63A4ZAR1U1 (4 official JSON responses, challenge false).

Публичные PDF книги и browser profile не коммитятся; URLs, SHA256, полные language assessments и SG body proofs сохранены. На свежем checkout ранее проверенные PDF можно восстановить без изменения review decisions:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.venv/Scripts/python.exe reports/lenovo_stage61/restore_manual_proofs.py --captures reports/lenovo_stage61/psref_captures
```

Несовпадающий SHA или неполное содержимое останавливает восстановление и требует новой проверки. Для повторения выборки используйте новый DB name в `run_final_verified.py`: существующая DB намеренно не перезаписывается. Production thresholds не снижены.

## 11. Release verification

Полный regression: **1464 tests, OK**, 720.807 s; runner exit 0, source_tree_unchanged true. Targeted Stage 60/61: 35 tests OK; structural pipeline suite: 18 tests OK. [Regression summary](regression_release.json), [полный лог](regression_release.log). Commit/push выполняются только после PASS; hash сообщается в финальном ответе, чтобы не создавать самоссылочный hash внутри commit.

## Полная readiness / root-cause таблица

Все строки до исправления — not_ready; общая причина: exact PSREF frontend payload не импортировался, official evidence учитывал Support/storefront. Исправление: attended capture → exact-row parser → primary PSREF evidence; RU document verification. У двух мониторов это также исправило unresolved identity.

| Модель / full article | Exact identity / PSREF | Raw → accepted / rejected | Фото | RU manual | Before → after / blocker |
|---|---|---:|---|---|---|
| ThinkPad X1 Carbon Gen 12 / 21KC0029MH | exact / exact | 52 → 42 / 10 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| ThinkBook 14 G6 IRL / 21KG0004AT | exact / exact | 47 → 40 / 7 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| IdeaPad Slim 3 15IRH8 / 83EM007FLK | exact / exact | 44 → 38 / 6 | Проверен цвет, выбрано 1 | Проверена | not_ready → export_ready, нет blocking gaps |
| Legion 5 15IRX10 / 83LY0066PB | exact / exact | 47 → 40 / 7 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| ThinkVision T27i-30 Monitor / 63A4ZAR1U1 | exact / exact | 39 → 35 / 4 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| ThinkVision P40w-20 Monitor / 62C1GAT6EU | exact / exact | 39 → 34 / 5 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| ThinkCentre M70q Gen 4 / 12E4S96402 | exact / exact | 49 → 43 / 6 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| Tab P12 / ZACH0134PL | exact / exact | 32 → 27 / 5 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |
| IdeaPad Slim 3 15IRH8 / 83EM00KVMX | exact / exact | 44 → 38 / 6 | Проверен цвет, выбрано 1 | Проверена | not_ready → export_ready, нет blocking gaps |
| Legion 5 15IRX10 / 83LY00JCRK | exact / exact | 47 → 41 / 6 | Только candidates | Проверена | not_ready → not_ready, exact_gallery_not_confirmed |

Official User Guide URLs (PDF):

- [21KC0029MH — 98 страниц](https://download.lenovo.com/pccbbs/mobiles_pdf/x1_carbon_gen12_2in1_gen9_ug_ru.pdf)
- [21KG0004AT — 44 страниц](https://download.lenovo.com/consumer/mobiles_pub/lenovo_thinkbook_14_16_gen_6_ug_ru.pdf)
- [63A4ZAR1U1 — 40 страниц](https://download.lenovo.com/consumer/monitor/t27i_30_user_guide_ru.pdf)
- [62C1GAT6EU — 58 страниц](https://download.lenovo.com/consumer/monitor/thinkvision_p40w_20_russian_user_guide_20240621.pdf)
- [ZACH0134PL — 49 страниц](https://download.lenovo.com/consumer/mobiles_pub/tab_p12_ug_ru.pdf)
