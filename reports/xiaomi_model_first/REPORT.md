# Xiaomi identity — model-first

Применена новая пользовательская policy поверх Stage 74 (`355d602beb591bd16995d0d3c634bcbea0267005`). Исторический Stage 74 audit не переписан. Общий worker/discovery/evidence/readiness/UI/Excel сохранён; отдельный framework или configuration-resolution layer не создан.

## Новая policy

* Основной official object — **exact commercial model**, с проверкой Xiaomi/Redmi/POCO lineage, generation и connectivity suffix. Supplier part number не обязан присутствовать у Xiaomi.
* Input RAM/storage/color/region/supplier part number сохраняются отдельно; исходные значения Excel остаются в evidence. Они не превращаются в official facts и не блокируют readiness. Retail SKU остаётся `null`, `full_sku_confirmed=false` во всех десяти строках.
* Official источник другого региона полноценно подтверждает общие model specs. Названия NFC/bands/OS сами по себе не доказывают региональную вариативность. Отдельный scope применяется к опубликованным `may vary … country/region`, `may differ across … regions` и аналогичным ограничениям.
* SIM/Wi-Fi caveats отделены от common Bluetooth/codecs/bands. Original `section → raw label → value` сохраняется в `original_raw_specs`, component rows — в `raw_specs`; вариативный SIM/Wi-Fi не делает непроверенными остальные общие параметры.
* Официальные product gallery/hero images exact PDP подтверждаются **как фото модели**. Supplier color relation не выводится из изображения или пути URL. Если published DOM явно содержит `data-color`, official color сохраняется отдельно. Остальные диаграммы/логотипы не становятся gallery только потому, что находятся на PDP.
* Manual optional. Проверка official RU/UK inventory/PDF ограничена дополнительным 12-second deadline и bounded PDF GET; нет большого external search budget ради инструкции. Найденные guides проверяются, Safety/QR reference не принимается как guide.
* Readiness: exact model + прежний minimum sufficient official specs + подтверждённая model gallery, без реальных conflicts. Configuration и manual gates сняты только для Xiaomi; global thresholds других брендов не изменены.

## Gallery recovery

Actual CDN investigation: Xiaomi 15 Ultra hero URL с `.jpg` вернул HTTP 200, MIME `application/octet-stream`, **PNG signature**. Прежний verifier отвергал этот valid image по declared MIME. Теперь для существующих sources с full image decode допускается binary transport MIME только при проверке сигнатуры, PIL verify/load, dimensions, non-placeholder content и SHA-256. Declared `content_type` и `effective_content_type` сохраняются отдельно. Неподдерживаемый HTML, broken/blank image и ложное совпадение MIME по-прежнему отвергаются. Чтение HTTP content-type сделано case-insensitive. URL extension не определяет format.

Девять выбранных изображений скачаны actual live, byte-verified и отдельно просмотрены: [QA images](qa/). Xiaomi 15 показывает зелёный телефон при input Black; это корректное **фото модели**, без подтверждения supplier Black. G20 Max — official hero lifestyle с самим пылесосом; supplier bundle/color не заявлен.

## Frozen inputs и actual live result

Использованы те же [10 входов Stage 74](../xiaomi_stage74/dataset.json), SHA-256 неизменен:

`97007516b15fe88718a754b6c527da3646ebeb0f9dd911bbc727a315ed884c36`

Окончательный [actual live run](../xiaomi_stage74/model_first_release_live/results.json): **10/10 official data, 185 confirmed specs, 9 confirmed model photos, 9/10 ready**. У каждой строки есть actual PDP + specs HTTP trace; session catalog cache отмечен отдельно. Replay/offline rows не подставлялись. Jobs done = 10, conflicts = 0, duplicate image URLs = 0, confirmed supplier SKU = 0, claimed supplier color relation = 0.

| ID | Модель / input configuration | Specs | Model photos | Manual auto | Readiness |
|---|---|---:|---:|---|---|
| 1 | Xiaomi 15; 12/256 Black Global | 21 | 1 | Проверена | ready |
| 2 | Xiaomi 15 Ultra; 16/512 Black Global | 21 | 1 | Проверена | ready |
| 3 | Xiaomi 14T Pro; 12/512 Titan Black Global | 21 | 1 | Проверена | ready |
| 4 | Robot Vacuum X20+ Global | 12 | 0 | Проверена | not_ready: gallery |
| 5 | Robot Vacuum X20 Max Global | 15 | 1 | Не проверена | ready |
| 6 | Vacuum Cleaner G20 Max Global | 9 | 1 | Проверена | ready |
| 7 | TV A Pro 55 2026 Global | 34 | 1 | Проверена, не найдена | ready |
| 8 | 2K Monitor A27Qi Global | 19 | 1 | Проверена, не найдена* | ready |
| 9 | Router AX3000T Global | 18 | 1 | Проверена | ready |
| 10 | Redmi Note 14 Pro 5G; 8/256 Midnight Black EEA | 15 | 1 | Проверена, не найдена | ready |

Все четыре smartphone configurations остаются input-only, а cards готовы на exact-model evidence. X20 Max готов при непроверенной инструкции — manual действительно optional. У A27Qi остаётся документированный в Stage 74 image-only guide classifier gap; `не найдена` здесь означает автоматическое непринятие опубликованного guide, не его отсутствие. Эти manual ограничения не readiness blockers.

**X20+ не блокируется supplier configuration/region/manual.** На проверенном Global PDP hero опубликованы video и титульный PNG 809 × 153. PNG — логотип/название, не товарное фото. Его не повысили до gallery ради десяти ready. Статичное product gallery extraction остаётся отдельным scope gap; отсутствие supplier-color relation не является причиной отказа. Утверждение «статичных фото нигде нет» не делается.

Промежуточные `model_first_live` и `model_first_verified_live` — development runs до окончательных regional-note / binary-MIME fixes. Они сохранены отдельно, не используются в итоговой статистике и не выдаются за release success. Отдельные прерванные regression logs также не являются PASS.

## UI / Excel и проверки

[Xiaomi_Model_First.xlsx](Xiaomi_Model_First.xlsx): supplier fields имеют статус «Данные входного файла; не официальный факт». Photo sheet использует «Область подтверждения» и «Фото модели; цвет поставщика не подтверждён», вместо misleading variant confirmation. Новый model scope отображается в UI; карточки всех 10 inputs проверены HTTP TestClient на read-only копии live DB. [UI checks](ui_verification.json).

Read-only spreadsheet import/render выполнен, три PNG просмотрены: [readiness](qa/excel_readiness.png), [input configuration](qa/excel_input_configuration.png), [model photos](qa/excel_model_photos.png). Renderer создал все previews, но его процесс вернул exit 1 без error output — это не считается executable PASS. Workbook отдельно структурно проверен общим exporter и read-only openpyxl: 10 summary rows, 9 selected model photo rows, input-only statuses, no formula errors.

Старый дефект Cyrillic category metadata во frozen dataset не исправлялся; ограничения category-sheet QA из Stage 74 сохраняются. Model identifiers и configurations не менялись.

Targeted contracts: **25 tests, OK** — exact model/lineage, opaque supplier code, RAM/storage/color not official, other-region model sources, explicit regional caveats, component separation, model gallery vs logos/charts, official color metadata vs supplier color, MIME/header handling, optional manual/readiness, UI/Excel scope. Финальный полный regression: **1766 tests, OK, 368.969 s**, exit 0, source tree unchanged; [result](regression_release.json), [log](regression_release.log). Сохранён SHA-256 manifest всех проверенных исходников.

## Итог

**Model-first policy реализована. Девять карточек готовы естественно; X20+ остаётся not_ready только по gallery.** Broad production-ready для непроверенной X20+ gallery не заявляется. Exact supplier SKU/RAM/storage/color/region/manual не используются как mandatory gates; false supplier configuration/photo claims отсутствуют. Дальнейшее получение retail payload не требуется для common model specs или gallery.

После final regression PASS и `git diff --check` изменения публикуются как follow-up commit к Stage 74. Commit hash и remote/working-tree проверка сообщаются в финальном ответе.
