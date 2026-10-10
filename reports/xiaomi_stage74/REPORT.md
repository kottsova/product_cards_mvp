# Stage 74 — Xiaomi baseline audit и перенос общего pipeline

Дата наблюдений: 10 октября 2026. База: `7b87776f396b550d7f21a4ef8e8a9137de3691b3` (Stage 73).

**Audit verdict: PASS. Adapter verdict: Xiaomi adapter not ready.** Это аудит переноса архитектуры, а не закрытие production readiness. Реальные live источники получены для 10/10 входов, повторены пять входов; 172 confirmed specs, 0 ready, 0 confirmed retail SKU, 0 confirmed photos. Thresholds не снижены. Дефекты первого запуска и оставшиеся ограничения сохранены, а не скрыты финальным снимком.

## 1. Baseline до Xiaomi adapter

Обычный `worker.run_once()` выполнен для **Xiaomi 14**, без Xiaomi factory, adapter, PDP seed или model-specific URL. Поисковый артикул — marketing identifier `Xiaomi 14`, имя `Xiaomi 14 [RAM=12GB;storage=256GB;color=Black;region=Global]`; generation 14, model number и SKU неизвестны. Официальный [PDP Xiaomi 14](https://www.mi.com/global/product/xiaomi-14/) был наблюдён отдельно и **не передавался worker**.

Результат: `job=error`, `readiness=not_ready`, specs/photos/manuals = 0/0/0, official source отсутствует, trace пуст. Общий worker не имел Xiaomi dispatch и дошёл до существующего DNS fallback, требующего проверенный URL. Query variants/official search/support не запускались: их отсутствие — зафиксированный baseline root cause, а не пропущенное evidence. Сохранены input, job stages/message, sources, facts, photos, documents и исходный readiness: [baseline.json](baseline.json), воспроизводящий [baseline.py](baseline.py).

## 2. Official source structure и discovery

Исследованы Global/UK/RU home, support, HTML sitemap, PDP/specs, JSON-LD/SSR JSON и опубликованные региональные JS. Первичные точки: [Global](https://www.mi.com/global/), [Global sitemap](https://www.mi.com/global/sitemap/), [UK sitemap](https://www.mi.com/uk/sitemap/), [Global support](https://www.mi.com/global/support/), [RU User Guide](https://www.mi.com/ru/support/user-guide/), [UK User Guide](https://www.mi.com/uk/support/user-guide/).

* HTML sitemap и SSR содержат опубликованные href, commercial titles и product navigation. Это discovery inventory, а не доказательство retail configuration.
* PDP title доказывает точную marketing model/line/generation; отдельная опубликованная ссылка ведёт на specs. Specs представлены двухколоночными HTML grids, в том числе с многострочными значениями, подзаголовками и компонентами. Некоторые поля присутствуют в bounded embedded JSON. JS не исполняется парсером, нет `eval`.
* На UK Xiaomi 15 опубликован **Buy Now** → [official BuyBox](https://www.mi.com/uk/buy/product/xiaomi-15). Actual HTTP вернул `Data loading...`, 0 embedded retail identity records. В опубликованном JS есть `commodityId`, `goodsId`, `productId` и GET `/v2/item/productdetail` с `withCredentials`. Это описание клиентского API, **не** полученный payload и **не** связь запроса 12/256 Black с SKU. Отдельные captures: [regional census](retail_structure/result.json), [script census](script_structure/result.json), [BuyBox census](buybox_structure/result.json).
* Attended browser inspection динамического BuyBox не состоялся: две инициализации browser tool завершились runtime/kernel error (`windows sandbox ... setup refresh had errors`). Нет browser/XHR success; защита не обходилась. Динамический configuration payload остаётся coverage gap.
* Xiaomi, Redmi и POCO — отдельные lineage. Redmi Note 14 Pro 5G в live batch подтверждён как **Redmi**, не как exact Xiaomi 14 Pro. Official navigation публикует отдельный POCO Brand; whole-title/lineage tests запрещают смешивание POCO/Xiaomi/Redmi. POCO retail PDP в десяти входах отсутствует; его extraction coverage не заявляется.

Adapter использует regional root/catalog → опубликованный sitemap → другие official регионы → support → существующий `LGBrowserSearch` fallback → существующий dealer fallback. PDP URL строится **не** из имени модели: только опубликованный href/SSR URL, затем проверка exact title. Нет словаря моделей/URL или нового search engine. Prefix `All Specs, Features of …` убирается общим title normalization; `+` и `Plus` нормализуются как написания модели. Support inventory проверяется отдельно даже при найденном PDP. External search не понадобился для этих десяти official hits; его live устойчивость этим audit не доказана.

Каждый `rows[].trace` в [final_results.json](final_results.json) содержит query, provider, URL, region, source type, accepted/rejected, reason, timestamp, observation и identity relation; события принятия дополняют model/hardware/retail identity. HTTP 200 не равно accepted identity. Dealer запускается после оставшихся gaps: по всем десяти `dealer_url_needed`, 0 dealer facts; marketing model не выдан за retail code.

## 3. Identity и region/configuration

Существующая resolution/evidence модель переиспользована с scoped official sources `xiaomi_model`, `xiaomi_region`, `xiaomi_configuration`.

| Уровень | Что может подтверждать | Чего не доказывает |
|---|---|---|
| Model | Exact commercial family, общие specs, камеры/дисплей/архитектура/компоненты | Выбранные RAM/storage/color, retail SKU или другой generation/4G/5G |
| Hardware relation | Буквальный model number из exact-model specs/guide; отдельный station component | Региональный retail SKU по суффиксу/codename |
| Region | Поля из совпадающего official source region | Global = CN = EEA; DE автоматически = EEA |
| Configuration | Явно доказанная комбинация RAM/storage/color/region/bundle | Default/семейные options или похожий код |

Для смартфонов exact model подтверждена, но 4 запрошенные retail configurations остаются `partial`: 1/2/3/10. Regional NFC/eSIM/bands/charger/software/package требуют собственного evidence; `Vary by markets` не становится confirmed. Для Redmi EEA common Global specs допустимы, Global bands/NFC/software не переносятся. У устройств 4–9 подтверждена только запрошенная model/Global configuration без дополнительных retail options; `configuration_confirmed` здесь **не** означает доказанный full SKU. Все retail_sku остаются `null`, `full_sku_confirmed=false`.

## 4. Model-number findings

| Commercial model | Official literal code | Наблюдение / relation |
|---|---|---|
| Xiaomi 15 | `24129PN74G` | Actual live exact-model UK guide, поле Model |
| Xiaomi 15 Ultra | `25010PN30G` | Actual live exact-model UK guide, поле Model |
| Xiaomi 14T Pro | `2407FPN8EG` | Actual live exact-model RU guide, поле Модель |
| Robot Vacuum X20 Max | `D109GL` | Actual live specs, robot hardware |
| X20 Max station | `D109-JZEU` | Literal Omni Station Model; current **offline** parser supplement на live capture |
| Vacuum Cleaner G20 Max | `D206` | Actual live specs, device hardware |
| 2K Monitor A27Qi | `P27QCA-RAGL` | Actual live specs, device hardware |

X20+, TV A Pro 55 2026, AX3000T, Redmi EEA — exact hardware/retail mapping не доказан в этом прогоне. Codes/codenames не декодируются в SKU, suffix не доказывает регион. Station code добавлен после основного live snapshot: он явно находится в `offline_parser`, не подменяет live evidence или готовность.

## 5. Frozen dataset и реальные результаты

Baseline Xiaomi 14 исключён. Десять новых входов зафиксированы до первого batch в [dataset.json](dataset.json), SHA-256:

`97007516b15fe88718a754b6c527da3646ebeb0f9dd911bbc727a315ed884c36`

**Дефект audit input metadata:** PowerShell stdin при создании файла заменил Cyrillic `category` на `?`. Frozen bytes не исправлялись. Commercial identifiers, имена, RAM/storage/color/region и фактический набор категорий сохранены. Семантически набор соответствует 3 смартфонам + 2 роботам + вертикальному пылесосу + ТВ + монитору + роутеру + сложному EEA smartphone. Проверка category-specific Excel sheet names на этих повреждённых исходных labels ограничена: видны fallback «Категория», `-`. Это ошибка audit harness, не доказательство исправной импортной category metadata; будущий новый dataset должен создаваться через UTF-8-safe writer.

Все PDP/spec URLs в таблице **открыты actual live**, получены discovery из published catalog, не seeded.

| ID | Frozen модель / configuration | Exact specs | Первый specs/job | Финальный specs/job | Config | Фото candidate | Manual auto | Ready |
|---|---|---|---|---|---|---|---|---|
| 1 | Xiaomi 15; 12/256 Black Global | [official](https://www.mi.com/global/product/xiaomi-15/specs/) | 16/error | 20/done | partial | 64 | Проверена EN QSG | not_ready |
| 2 | Xiaomi 15 Ultra; 16/512 Black Global | [official](https://www.mi.com/global/product/xiaomi-15-ultra/specs/) | 16/error | 20/done | partial | 77 | Проверена EN QSG | not_ready |
| 3 | Xiaomi 14T Pro; 12/512 Titan Black Global | [official](https://www.mi.com/global/product/xiaomi-14t-pro/specs/) | 17/error | 20/done | partial | 71 | Проверена RU | not_ready |
| 4 | Robot Vacuum X20+; Global | [official](https://www.mi.com/global/product/xiaomi-robot-vacuum-x20-plus/specs/) | 8/error | 12/done | model/region | 53 | Проверена EN | not_ready |
| 5 | Robot Vacuum X20 Max; Global | [official](https://www.mi.com/global/product/xiaomi-robot-vacuum-x20-max/specs/) | 12/error | 12/done | model/region | 46 | Не проверена: size cap | not_ready |
| 6 | Vacuum Cleaner G20 Max; Global | [official](https://www.mi.com/global/product/xiaomi-vacuum-cleaner-g20-max/specs/) | 8/error | 8/done | model/region | 48 | Проверена EN | not_ready |
| 7 | TV A Pro 55 2026; Global | [official](https://www.mi.com/global/product/xiaomi-tv-a-pro-55-2026/specs/) | 2/error | 33/done | model/region | 42 | Проверена, не найдена | not_ready |
| 8 | 2K Monitor A27Qi; Global | [official](https://www.mi.com/global/product/xiaomi-2k-monitor-a27qi/specs/) | 18/error | 18/done | model/region | 33 | Авто: не найдена; visual gap* | not_ready |
| 9 | Router AX3000T; Global | [official](https://www.mi.com/global/product/xiaomi-router-ax3000t/specs/) | 0/error | 16/done | model/region | 36 | Проверена EN | not_ready |
| 10 | Redmi Note 14 Pro 5G; 8/256 Midnight Black EEA | [official](https://www.mi.com/global/product/redmi-note-14-pro-5g/specs/) | 12/error | 13/done | partial | 72 | Проверена, не найдена | not_ready |

Общий photo gap блокирует все десять; configuration gap дополнительно 1/2/3/10. Manual optional и не блокирует. Job done означает завершённую проверку, а не ready. Основной gap остальных шести — verified gallery; у 5/8 есть ещё document coverage gap.

Первый actual batch сохранён полностью: [first_pass](first_pass/results.json). Job error по всем десяти вызван нашей интеграционной ошибкой: trace не имел обязательного timestamp; частично найденные facts всё равно записались. Дополнительно SEO title prefix терял AX3000T/Global robot sources, двухколоночный extractor терял TV continuation rows. Общие исправления устранили эти причины, не модельные URL exceptions.

Промежуточный [corrected_live](corrected_live/results.json) дал 10/10 data, но ещё два `needs_review` из-за смешанных robot/station dimensions и одинакового Stand label в Design/Material. Исправлены общие component scope и qualified labels. Исторические ответы не перезаписаны. Основной [verified_live](verified_live/results.json) — 10/10 sources и done; финальный [snapshot](final_results.json) заменяет только пять строк более поздними **actual live** повторениями.

## 6. Extraction, runtime, dimensions и фото

Сначала сохраняются `section → raw label → value`, затем scope/acceptance, затем canonical mapping. Сырой и отвергнутый факт не теряется. Offline-проверка финальных live captures текущим парсером дала **188 raw rows → 161 accepted raw rows + 27 rejected rows → 172 model fields** (charging composites распадаются на отдельные поля). Это **offline parser validation**, не дополнительный live success. Counters доступны в `offline_parser`.

Исправлены common continuation lines, numeric unit-as-label, mobile/parent duplicates, section boundaries, exact title prefixes, HTML/SSR links. Для батареи отдельно выделены capacity, wired power, wireless power, reverse, protocols/port и Surge labels, когда источник явно их публикует. «Up to» не превращается в гарантированную длительность. Eco/Standard/Turbo/combined различаются в scoped fixtures; полное actual runtime extraction из marketing/PDF для пылесосов пока не выполнено и не заявляется confirmed.

Robot vs base/station vs package различаются. У X20+ `350 × 350 × 97 mm` robot и `586 × 427 × 340 mm` station не конфликтуют как dimensions одного устройства. Base specs не становятся доказательством дополнительного retail bundle; упаковка и непроверенный комплект отвергаются. Общая station heading normalization уточнена, прежние brand dimensions не расслаблены.

542 URLs из official PDP — **кандидаты**, включая product/lifestyle/component/banners. Первые два на модель проверены bounded byte download общим photo pipeline; семь успешных измерений (JPEG/PNG/WebP, dimensions/file size/content-type/full decode). Это не семь verified product renders: часть — graphic/logo. Все exact_photo_assets пусты, выбранных фото 0. Другой цвет/appearance/bundle не подтверждается только по пути URL; требуется classification и exact relation. Для неуспешных скачиваний остаётся diagnostic, не выдуманные размеры.

## 7. Manuals и visual false-negative

Actual support inventory: RU затем UK exact model links. PDF безопасно ограничен размером/страницами/текстом. Guide/Quick Start отделены от Safety/Warranty; упоминание guide по QR в Safety не считается инструкцией. Комбинированный QSG+Safety допускается только при настоящем guide heading/operations. Язык определяется по страницам **guide**, не по всему multilingual Safety document.

Автоматический итог: 6 `Проверена`, 3 `Проверена, не найдена`, 1 `Не проверена`. У Xiaomi 15/15 Ultra подтверждён EN QSG; русский Safety в том же файле не даёт RU guide. 14T Pro — RU guide. X20+, G20 Max, AX3000T — EN guides. X20 Max official guide link найден, файл превосходит 15 MB cap; это реальный технический блокер, не отсутствие инструкции. TV и Redmi: exact link не найден в проверенных inventory; это ограниченный inventory miss, не глобальное утверждение «инструкции нет».

**A27Qi:** опубликован [official User Guide PDF](https://i05.appmifile.com/User-Guide-Upload-mi.com/Instruction-manual/63063-Xiaomi-2K-Monitor-A27Qi-UserGuide-UK.pdf), exact title/model code есть, но многие надписи преобразованы в curves/images. Live auto-classifier отверг его из-за отсутствия instruction markers. Отдельный offline visual audit полученного actual PDF показывает model cover и четырёхшаговую assembly diagram, поэтому нельзя сообщать, что manual отсутствует. Сохранены [visual audit](manual_visual_audit.json), [cover](qa/monitor_manual_page_0.png), [assembly](qa/monitor_manual_page_1.png). Требуется общий OCR/visual document review flow; ad hoc A27Qi exception не внедрён. Автостатус в UI/Excel остался честно видимым parser gap.

## 8. Stability, UI/Excel и edge cases

Повторены actual live IDs **1/2/3/6/9**, телефон/пылесос/роутер. Fresh jobs, те же input/configuration, повторная загрузка PDP/spec/PDF в том же adapter lifecycle. Sources/spec counts/readiness сохранены, raw fact duplicates = 0, нет challenge/429 в этих наблюдениях. [Stability](stability/results.json). Session catalog cache отмечен `catalog_cache`; он не выдан за свежий catalog HTTP. Product data остаются live. Статистика 10/10 и 5/5 не обещает будущую глобальную availability.

21 targeted test проверяет RAM/storage options, другой цвет, Global/CN, EEA, station/bundle, региональные NFC/bands/charger, opaque article/code ≠ SKU, generation/lineage, charging/runtime modes, qualified sections, Safety/guide language, worker default dispatch, manual optional, Russian UI/Excel. Fixtures — offline captured HTML, тесты не обращаются к сети. UI сохраняет identity/configuration/raw candidates/manual статус отдельно; help/setup/troubleshooting не используется как description. HyperAI/core features и брендовые HyperOS/Leica/Surge/LDS сохраняются.

Файл общего exporter: [Xiaomi_Stage74.xlsx](Xiaomi_Stage74.xlsx). Проверены 172 source-backed facts, candidate sheets, 0 confirmed photo rows, 0 formula errors, Russian canonical labels, separate configuration/manual/identity sheets. Read-only ArtifactTool import/render выявил обрезку новых audit columns; widths/wrap/row heights исправлены в существующем exporter. Повторный render визуально проверен: [readiness](qa/excel_readiness.png), [configuration](qa/excel_configuration.png), [photo candidates](qa/excel_photo_candidates.png), [model numbers](qa/excel_model_numbers.png). Renderer создал все PNG, но его процесс завершился exit 1 без error output: это не заявляется успешным executable check; workbook структурно проверен общим экспортом и openpyxl read-only validation. Frozen category metadata defect ограничивает category-sheet QA, как указано выше.

## 9. Нужен ли отдельный configuration layer?

**На этом audit необходимость отдельного слоя не доказана.** Xiaomi укладывается в существующий worker/discovery/policy/resolution/evidence/readiness/UI/export с небольшим brand adapter и общими published-page/extraction primitives. Region и retail fields используют существующий scoped contract. Доказанные дефекты — dispatch, title normalization, continuation extraction, component labels, guide language и Excel presentation.

Следующая работа — получить actual dynamic BuyBox/XHR variant relations и научить общий gallery/manual pipeline подтверждать appearance и image-only guides. Это coverage/integration gaps в существующей архитектуре, а не основание заранее строить framework. Если будущий official payload докажет новый несводимый configuration graph, его необходимость нужно подтвердить отдельно.

## 10. Regression и release evidence

До Excel visual fix полный regression: **1762 tests / 621.220s / OK**, source tree unchanged. [Initial regression](regression_before_excel_qa.json). После fix targeted: **21 tests / 1.599s / OK**. Финальный полный regression и immutable source manifest: [regression_release.json](regression_release.json), [log](regression_release.log); Финальный результат: **Ran 1762 tests in 674.149s / OK**, source tree unchanged; elapsed 677.576s. Public captures проверены SHA-256, frozen input hash неизменен. [verification.json](verification.json) содержит counters и workbook digest. Авторизация/source pins append-only в Stage 74 block, прежние stage blocks не менялись.

## 11. Verdict и конкретные блокеры

**Xiaomi adapter not ready.**

1. Verified appearance/color gallery отсутствует: 542 candidates, семь byte measurements, ноль confirmed photos. Текущий readiness policy требует gallery.
2. Exact smartphone RAM/storage/color и EEA retail payload не связан: четыре partial configurations, ноль retail SKU. Static UK BuyBox возвращает loading shell; attended browser runtime unavailable, API request payload не проверен.
3. Manual coverage: X20 Max size cap; A27Qi image-only guide false-negative. Manual optional и не является readiness blocker.
4. Actual vacuum runtime/mode coverage неполное; marketing claims не подставлены как confirmed specs.
5. Frozen audit category labels повреждены до первого batch; dataset не менялся. Category-specific presentation/import conclusions на этих labels ограничены.

Audit PASS требует baseline trace, понятную source structure включая ограничения, model/config separation, scoped regional fields, неизменные десять входов, отсутствие false confirmed configurations и успешный regression. Production readiness этим PASS не заявляется.

## 12. GitHub

После финального regression PASS: `git diff --check`, commit **Stage 74**, push main, проверка HEAD = origin/main = remote main и clean working tree. Hash сообщается в финальном ответе; не встраивается в собственное commit содержимое.
