# Stage 66 PlayStation baseline и перенос общего pipeline

Дата: 2026-10-08 (Asia/Tbilisi). Исходный commit: `d103864609a6809be7bd91e2b0b1cdc2ac047b1b`.

Вердикт: **PlayStation adapter not ready**. Stage 66 acceptance: **PASS — baseline, независимая выборка, разделение identity, отрицательные контроли и полный regression**. Это аудит переносимости и безопасная интеграция; производственную готовность бренда не объявляем. Все 10 карточек остаются `needs_review / not_ready`. Для Midnight Black доказаны SKU, цвет, комплект и два собственных рендера, но технических характеристик пока недостаточно. Цвет и комплектация не заполняют счётчик specs readiness.

## 1 Baseline

Обычный неизменённый `run_once()` Stage 65 для **CFI-2016A**, входное имя PlayStation 5 Slim Disc 1TB CFI-2016A: job `error`, 0 specs, 0 фото, 0 документов, readiness `not_ready`. Commercial name и Disc/1TB/Slim во входе были только hints; hardware identity, retail SKU, revision и точный PDP не были подтверждены. Официального PlayStation dispatch не существовало. Общий DNS fallback вернул `dealer_url_needed`, а не выдуманную URL-карточку. Официальный поиск и query variants в этой ветке не выполнялись: это systemic dispatch gap, а не доказанное отсутствие товара. `baseline.json` сохраняет input, job, source, факты, решения, photos, documents, readiness и events.

Контрольный повтор после интеграции сохранён отдельно в `baseline_final.json`: официальный CFI/support связан, объединённая таблица Slim остаётся кандидатом. Исходный baseline не перезаписан.

## 2 Официальная структура

- [PlayStation UK PS5](https://www.playstation.com/en-gb/ps5/) и [PS5 Pro](https://www.playstation.com/en-gb/ps5/ps5-pro/) — коммерческие family/model страницы на AEM. Текущая PS5 family page не является exact PDP старой CFI-1216A/B и не подтверждает параметры любой ревизии.
- [DualSense](https://www.playstation.com/en-gb/accessories/dualsense-wireless-controller/), [Portal](https://www.playstation.com/en-gb/accessories/playstation-portal-remote-player/) и [PULSE Elite](https://www.playstation.com/en-gb/accessories/pulse-elite-wireless-headset/) — модельные возможности, галереи и варианты. PULSE Elite JSON-LD Product содержит `mpn=CFI-ZWH2EC`; CMS `sku/productID=PSD001...` не объявлены retail SKU. Другие исследованные страницы часто дают BreadcrumbList/VideoObject вместо exact Product record.
- [RU manuals](https://www.playstation.com/ru-ru/support/hardware/manuals/) и [UK manuals](https://www.playstation.com/en-gb/support/hardware/manuals/) — CFI labels и реальные href для User Guide, Quick Start и Safety Guide. Встречаются combined A/B tables и отдельные accessory/component guides. Сходный prefix не связывает CFI-ZWH2 с CFI-ZWH2EC автоматически.
- [Direct Midnight Black PDP](https://direct.playstation.com/en-gb/buy-accessories/dualsense-wireless-controller-midnight-black-for-ps5-pc-mac-mobile) публикует `digitalData.product[0].productInfo.sku=1000050213-GB`. Own h1, SKU, own box list и image-cluster — отдельные доказательства. Опции другого SKU, включая USB Cable bundle, в confirmed gallery не входят.
- [Direct Fortnite PDP](https://direct.playstation.com/en-gb/buy-consoles/playstation5-digital-edition-console-825-gb-fortnite-flowering-chaos-bundle) публикует `1000049849-GB`, 825 GB и собственный Fortnite voucher/box list. Страница реально существует; текущий adapter discovery её не находит самостоятельно. Известный research URL не был внедрён в production SKU registry.
- [robots.txt](https://www.playstation.com/robots.txt) объявляет [sitemap index](https://www.playstation.com/sitemap_index.xml), а не root `/sitemap.xml` (404). Index содержит региональные sitemap, включая RU и GB. `sitemap_gpdc.xml` имеет отдельный robots запрет; это не запрет всех региональных карт. Adapter пока сохраняет index diagnostics, но не обходит региональные children — конкретный discovery blocker.
- Legacy `support.playstation.com` и SIE corporate pages исследованы как support/corporate surfaces; они не заменяют exact PDP. Наблюдённые embedded AEM endpoints Direct относятся к cart/session/checkout; как публичный specs API они не использованы. Полный runtime XHR trace не заявлен.

Наблюдения, returned URL/status, captured-body hashes, JSON-LD, embedded SKU и sitemap locs сохранены в `source_structure.json`. HTTP logs и captures относятся к текущему Stage 66. Capture hash для HTML относится к сохранённому decoded body; PDF hashes относятся к исходным binary bytes.

## 3 Identity и evidence

`playstation_model` — доказанная модель/family PDP, только model-stable facts. `playstation_hardware` — exact official CFI и cover-checked technical guide; status `hardware_confirmed_official`, **не** `full_sku_confirmed`. `playstation` — retail order SKU из собственного Direct PDP, status `full_sku_official` только для exact order facts.

Официальный CFI сохраняется типом `official_hardware_model_code`. Числовой regional suffix сам по себе не подтверждает radio, disc-region или retail bundle. `storefront=en-gb` означает регион магазина. Hardware family/revision выводится из наблюдённой структуры официального guide, а не из имени входной строки. CFI-2016A/B разворачивается в два отдельных identifier; CFI-2015A, другой chassis и suffix EC не подменяются похожими кодами.

Storage/color/bundle/Disc-Digital/region/revision/dimensions/weight не подтверждаются family options. Raw section → label → value сохраняется до mapping, неизвестные технические строки и условные опции остаются candidates. Общие возможности DualSense сохраняют брендированные Haptic Feedback / Adaptive Triggers, а текст рекламы не сравнивается как несколько конфликтующих numeric specs. Отрицательные feature statements не становятся «Да».

## 4 CFI, ревизии и габариты

На реально скачанных и отрендеренных страницах Safety Guide:

| Hardware | Размеры Ш × В × Г | Масса | Scope |
|---|---|---|---|
| CFI-1216A | 390 × 104 × 260 мм | около 3,9 кг | original Disc, без выступающих частей |
| CFI-1216B | 390 × 92 × 260 мм | около 3,4 кг | original Digital, без выступающих частей |
| CFI-2016 с disc drive | 358 × 96 × 216 мм | около 3,2 кг | строка объединённой Slim таблицы, candidate |
| CFI-2016 без disc drive | 358 × 80 × 216 мм | около 2,6 кг | другая строка Slim таблицы, candidate |
| CFI-7021 | 388 × 89 × 216 мм | около 3,1 кг | Pro guide; значения без добавленного disc drive |

Original 1200a/1200b технические таблицы, Slim combined table и Pro table визуально проверены. Slim dimensions/weight не повышаются до confirmed до row-level Disc/Digital routing. Console specs обрываются перед отдельной Wireless controller/DualSense таблицей: масса 280 г и controller battery не относятся к консоли. Package / with-stand размеры отдельный отрицательный контроль. UI/Excel: Ширина, Высота, Глубина, Вес; русские units, CFI scope отдельно от retail confidence.

## 5 Bundles и фотографии

Fortnite PDP parser принимает комплектацию только при собственном `1000049849-GB`. Для CFI-2016A та же страница не подтверждает SKU/storage/box contents. Bare console и bundle не эквивалентны по комплекту. Unit-test probe этого PDP не означает discovery success для frozen SKU: это остаётся blocker.

Midnight Black own box list: DualSense Wireless Controller; User manual. Slogan соседнего блока исключён. USB Cable bundle selector — фото-кандидат другого комплекта. Только два собственных image-cluster renders подтверждены для exact black order/color. Оба реально скачаны и визуально проверены: 400 × 400 JPG, 11953 и 9087 bytes. У других вариантов/ревизий нет автоматически выбранных подтверждённых фото. Gallery и lightbox проверены с измеренными metadata.

## 6 Frozen dataset и первый прогон

`dataset_frozen.json`, SHA-256 `c2cac5f22132a2061c2ad114b1fa6030188f1ad26ddfc665734d0a75014d1422`. Десять новых identifier после отдельного baseline; выбор не менялся после результатов. CFI hardware identifier и retail SKU явно различаются; White/storage/bundle слова входного имени не считаются доказательствами.

Все 10 первых неизменённых запусков получили `error / not_ready`, 0 specs/фото/manuals, общий dealer URL gap. `first_pass.json` сохранён. Последующий живой `final_live.json` прогнал те же 10 строк без model-specific SKU→URL registry. Финальный `release_replay_verified.json` — offline `run_once()` на реальных сохранённых HTTP/PDF bodies после safety fixes; это parser/evidence replay, не отдельный свежий сетевой успех.

| Identifier | Доказанная модель/guide family | Configuration identity | Technical specs¹ | Exact фото | RU User Guide | Главный gap |
|---|---|---|---:|---:|---|---|
| CFI-1216A | ps5_original | unproven | 9 | 0 | Не проверена | configuration_unresolved, exact_photo_missing |
| CFI-1216B | ps5_original | unproven | 9 | 0 | Не проверена | configuration_unresolved, exact_photo_missing |
| CFI-2016B | ps5_slim | unproven | 0 | 0 | Не проверена | configuration_unresolved, specifications_missing, exact_photo_missing |
| CFI-7021 | pro | unproven | 9 | 0 | Не проверена | configuration_unresolved, exact_photo_missing |
| CFI-ZCT1W | dualsense | unproven | 4 | 0 | Проверена | configuration_unresolved, exact_photo_missing |
| 1000050213-GB | модель PDP | exact_order_sku | 1 | 2 | Не проверена | specifications_missing |
| CFI-Y1016 | portal | unproven | 2 | 0 | Проверена | configuration_unresolved, specifications_missing, exact_photo_missing |
| CFI-ZWH2EC | модель PDP | unproven | 0 | 0 | Не проверена | configuration_unresolved, specifications_missing, exact_photo_missing |
| CFI-2015A | ps5_slim | unproven | 0 | 0 | Не проверена | configuration_unresolved, specifications_missing, exact_photo_missing |
| 1000049849-GB | модель PDP | unproven | 0 | 0 | Не проверена | configuration_unresolved, specifications_missing, exact_photo_missing |

¹ Счётчик readiness исключает цвет, комплектацию и storefront metadata. Сырых facts: 38; до canonical mapping сохранено 843 raw records. Во всех 10 итоговых строках job `needs_review`, readiness `not_ready`; реальные conflicts 0. `acceptance_summary.json` содержит по каждой строке exact PDP, support, sources, обе identity, hardware family, конфигурацию, facts, photos, guides, dealer и gaps.

## 7 Инструкции, support и dealer

Русский User Guide подтверждён actual complete PDF bytes, cover CFI и русским instruction content для CFI-ZCT1W и CFI-Y1016: «Проверена». Safety/QSG/Regulatory и support article отдельные роли; Safety не объявлен User Guide. Остальные: «Не проверена», поскольку полная exact-generation проверка не завершена. «Проверена, не найдена» после неполной проверки не ставится. Manual advisory и сам по себе не блокирует readiness.

PSN/account setup, repair/reset/update/warranty не включены в product description. Description для этих audit карточек пустое; это ограничение текущего extraction, а не подтверждённое описание товара. Общий DNS dealer fallback работает, возвращает `dealer_url_needed` без зарегистрированной exact URL. Dealer evidence хранится отдельно и не подтверждает official facts. Точные retailer bundle/packaging URL не найдены внутри этого pipeline run.

## 8 Edge cases и UI Excel

17 PlayStation tests проверяют: Disc/Digital dimensions; original/Slim/Pro guide families; regional и EC suffix; same model/different color; base vs bundle; own gallery vs USB-bundle selector; repeated gallery dedup; package/stand dimensions; модель не подтверждает configuration fields; hardware facts не retail SKU; safety/QSG не User Guide; negative feature statement; color/box metadata не заменяют specs; common worker/readiness/Excel aliases.

10 product pages HTTP 200. Группы core/features используют общий renderer, конфигурация вынесена отдельно. Все 10 descriptions без support/help copy. Native Excel экспорт сохранён read-only и проверен openpyxl для структуры, затем Artifact Tool inspect/render. Sheets: категории, common source/fact audit, Готовность PlayStation, Конфигурация PlayStation, Кандидаты PlayStation, Документы PlayStation, Фото-кандидаты. Formula errors 0. Визуально проверены identity/gaps, русские labels/units, candidate sheets и gallery/lightbox. Excel не переавторивался другим движком.

## 9 Архитектура и блокеры

**Отдельный hardware-configuration framework не обоснован.** Наблюдённые различия помещаются в общий pipeline с небольшим PlayStation adapter и двумя дополнительными source scopes. Нужен дальнейший разбор hardware table rows и configuration selectors внутри адаптера, а не отдельный search engine.

Systemic blockers: regional sitemap children и Direct catalog не подключены к autonomous exact discovery; external search provider не настроен; PS5 family page не маршрутизирует revision-specific facts; Slim combined table нуждается в row routing; Portal/PULSE/текущая DualSense revision требуют canonical specs extraction; retail SKU↔CFI и scoped color/bundle photos покрыты не полностью; description extraction пока отсутствует. Наличие Fortnite PDP проверено отдельно, поэтому его pipeline miss является discovery defect, а не реальным отсутствием official evidence.

Real evidence gaps: retail bundle/region/color нельзя вывести из bare CFI; discontinued original revisions не обязаны иметь актуальную коммерческую PDP; Safety Guide не заменяет User Guide; чужой цвет/комплект нельзя подтвердить по family gallery. Требуются exact official/dealer evidence или review. До устранения названных blockers итог — **PlayStation adapter not ready**.

## 10 Regression и Git

Полный offline regression: Ran 1559 tests in 684.386s / OK, immutable source tree: True. Command `.venv/Scripts/python.exe -m tests`, Chromium из `.venv/playwright-browsers`. Авторизованный Stage 66 migration record добавлен в существующий protected-hash registry; старые reports и hashes не переписаны. Git diff check и commit/push выполняются только после полного PASS. Commit hash публикуется отдельным итогом после операции, чтобы отчёт не содержал самоссылочный hash.
