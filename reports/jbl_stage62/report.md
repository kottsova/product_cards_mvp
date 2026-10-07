# Stage 62 — JBL baseline audit и перенос общего pipeline

Дата: 2026-10-07. Исходный HEAD Lenovo: `1677d9b68c6907b66d5d256294257c30ee236382`.

**Stage 62: audit PASS. Verdict: `JBL adapter not ready`.** Аудит и безопасный перенос завершены; весь бренд пока не закрыт для controlled use. Общий pipeline подходит JBL с небольшим адаптером, необходимость отдельного discovery/extraction framework на выборке не доказана. Блокеры: четыре полных региональных SKU без exact evidence, штатный внешний search provider не подключён, PDF Go 4 требует проверки извлечённого названия модели.

## 1. Baseline: обычный worker до изменений

`JBLFLIP6BLKEU`, JBL Flip 6 Black EU; base model JBL Flip 6. В [baseline_before.json](baseline_before.json) зафиксирован обычный `run_once()` до JBL-кода: `error`, только dealer_url_needed, 0 характеристик, 0 фото, 0 документов. Причина системная: отсутствие official JBL dispatch, а не отсутствие товара.

После переноса: [официальный PDP](https://de.jbl.com/JBLFLIP6BLKEU.html), возвращённые SKU/MPN/data-pid совпадают с полным артикулом, 21 raw/21 confirmed normalized specs, 8 изображений точного Product, один проверенный RU QSG, job `done`, readiness `export_ready`, 0 конфликтов. [Family support link](https://support.jbl.com/de/de/product-registration/FLIP-6-.html) наблюдалась на PDP, отдельный support endpoint недоступен; не является exact SKU proof.

Query variants: `site:jbl.com "JBLFLIP6BLKEU"`; `site:support.jbl.com "JBLFLIP6BLKEU"`; `JBL "JBLFLIP6BLKEU" JBL Flip 6`. Полные sources, документы, фото, raw labels и trace сохранены в [release_pass.json](release_pass.json) и [before_after.json](before_after.json).

## 2. Official source structure

Исследованы DE, UK, US/global, RU/KZ, DK, IN и ID. Первый обычный видимый браузерный DE baseline дал HTTP 200 и сохранённый публичный HTML; последующие защищённые регионы дали 403, RU/KZ — сетевые ошибки. Индонезийский официальный регион доступен и дал шесть exact PDP. Никаких challenge bypass, proxy, stealth, UA override или импорта browser cookies. В начальном dataset capture helper шесть закрытых адресов были повторно запрошены до остановки; после этого helper исправлен на остановку по host, защищённые страницы не импортированы.

Два общих шаблона: (1) JSON-LD Product + `.product-wrapper[data-pid]`, `#pdp-specs--specifications-content`; (2) `.product-info.product-detail` SKU microdata + MPN в `.pdp-specs`, `.spec-accordion` / `.spec-row`, gallery hero `img[itemprop=image]`. Варианты/цвет доступны в `data-current` и Product-Variation URL. Поля SKU/MPN проверяются в контексте товара, URL лишь кандидат.

`robots.txt` US отдаёт ссылку `https://www.jbl.com/sitemap_index.xml`; production fetch sitemap заблокирован 403, рекурсивный обход не подтверждён. Отказ policy_host_not_allowed в раннем probe — ограничение списка hosts самого probe, отдельно от фактического production 403. В HTML наблюдаются Demandware Product-Variation, Product-FaqInclude и Salesforce Knowledge__kav endpoints; ответы отдельных XHR/API не получены. Их наличие не принято за новый exact источник. Harman masterCatalog обслуживает официальные images/PDF; support family связан с PDP, но не повышает SKU identity.

## 3. Identity и discovery

Exact требует совпадающих полного returned SKU и MPN, согласованного product PID/context и разрешённого официального HTTPS host. Marketing name, family, generation, цветовые и региональные suffix не взаимозаменяемы. EU/EP не отрезаются; BLK/BLU/WHT не подменяются. Bundle/multiple Product не подтверждается автоматически. Family support/manual может иметь family relation без права подтвердить exact specs или gallery.

Discovery: сохранённый hash-verified exact response → RU exact candidate → advertised official sitemap → другие official regions → support → существующий injected external search interface → общий dealer fallback. Результаты query/provider/URL/region/source type/accepted/reason/relation записываются в discovery trace. Новый JBL Google engine не создавался. В обычном worker внешний provider пока не подключён: это отражено как системный gap, а не успешный поиск. Общий DNS fallback запускается при official gaps; в live выборке exact dealer URL не найден. DNS может подтвердить только совпадающий полный Код производителя; dealer не переименовывается в official.

## 4. Battery, audio, размеры и вес

Raw `section → label → value` сохранены перед canonical projection. Description берётся только из PDP product description; FAQ, reset, firmware, warranty, app setup не импортируются. Parent groups и русский canonical словарь отделены от raw labels; фирменные Bluetooth, Ambient Aware, TalkThru, JBL Pure Bass, Spatial Sound, Auracast сохранены.

Live 770NC: ANC off 65 ч, ANC on 50 ч, разговоры 33 ч, зарядка 3 ч. Tune 770NC: 70/44/39 ч и зарядка 2 ч. Tune Buds: ANC off 12 ч, ANC on 10 ч, разговоры 6.6 ч; общее максимальное 48 ч сохраняется отдельно и не подменяет эти режимы. Быстрая зарядка как булева feature не превращается в придуманный runtime.

W×H×D cm с явно указанными осями превращаются в общие ширину/высоту/глубину мм; g товара — в kg. Вес кейса Tune Buds 38.8 г хранится отдельно. Источник earpiece weight 10.8 г не поясняет один наушник/пара: label явно сохраняет неоднозначность; деление на два не производится. Вес всего товара 52.8 г также отдельный. Имперские дубли остаются в raw audit, не засоряют итоговую карточку. Наушниковые внутренние размеры не называются габаритами всего изделия.

Проверены мощность, частоты, Bluetooth/version/profiles, multipoint, микрофоны, ANC, Ambient Aware, TalkThru, Spatial Sound, Auracast, charging/runtime, IP, комплектация. Кодеки, SNR, ёмкость и материалы не добавляются, когда нет отдельных source specs. Региональное service-only/OTA и conditional options остаются candidates, не confirmed; тесты покрывают эти случаи.

## 5. Manuals

Отдельные типы: User Guide, Quick Start Guide, Safety Sheet, Warranty, App Guide, Spec Sheet, Regulatory/Other. Safety/legal/App не считаются пользовательской инструкцией. User Guide использует существующую полную оценку RU текста. Для короткого QSG добавлена отдельная content assessment: фактический title QSG, model relation, ≥500 русских букв, RU marker и ≥2 русских операционных темы; одних имени файла/языкового заголовка недостаточно. Общие LG thresholds не ослаблены.

Полные PDF извлечены pypdf + fonttools (JBL CFF fonts). После фактического Tune 770NC QSG ~43 MB лимит загрузки повышен с 25 до ограниченных 50 MB; предел 300 страниц. Проверка SHA-256 byte cache сопровождается новой content assessment текущим кодом. Baseline DE QSG восстановлен из байт идентичного Flip 6 ID QSG только после совпадения ранее записанного SHA.

Baseline Flip 6, Tune 770NC, Live 770NC, Tune Buds и Flip 6 Blue: RU `Проверена`. Charge 5: в проверенном двухстраничном QSG RU не найден → `Проверена, не найдена` (не утверждение об отсутствии RU во всех источниках). Go 4: русские операции есть, но извлечённое model/title содержит некорректные glyphs → `Не проверена`, требуется визуальная/OCR проверка. Четыре unresolved SKU: `Не проверена`. В Excel verified guide и typed candidate index разделены.

## 6–7. Frozen dataset и first pass

10 новых моделей, baseline исключён. SHA-256 dataset: `b6cd9ed36c3920aa176c3ac7ed3cb47ce17660f0899db247dc059ebe833a2634`; [dataset_frozen.json](dataset_frozen.json) не менялся. 4 колонки, 4 headphones, 1 soundbar, 1 TWS; сложные EU/EP/color SKU присутствуют. Все записи запускались штатным `run_once()`; model-specific extraction hardcode отсутствует.

First pass — отдельный исторический результат [first_pass.json](first_pass.json), окончательный — [release_pass.json](release_pass.json). Первые legacy exact PDP уже подтверждали specs, но gallery scope и краткие QSG требовали общих исправлений. Dataset не подменялся между прогонами.

| Полный SKU | Модель / категория | Первый readiness | Итог raw / confirmed | Job | Итог readiness | RU / главный gap |
|---|---|---|---:|---|---|---|
| `JBLCHARGE5BLK` | JBL Charge 5 Black | not_ready | 21 / 21 | done | export_ready_with_gaps | Проверена, не найдена; RU в проверенном QSG не найдена |
| `JBLGO4BLK` | JBL Go 4 Black | not_ready | 24 / 24 | done | export_ready_with_gaps | Не проверена; PDF model/title требует визуальной проверки |
| `JBLXTREME4BLUEP` | JBL Xtreme 4 Blue | not_ready | 0 / 0 | needs_review | not_ready | Не проверена; exact региональный SKU не подтверждён |
| `JBLT770NCBLK` | JBL Tune 770NC Black | not_ready | 51 / 51 | done | export_ready | Проверена; нет блокирующих пробелов |
| `JBLLIVE770NCBLK` | JBL Live 770NC Black | not_ready | 51 / 51 | done | export_ready | Проверена; нет блокирующих пробелов |
| `JBLT520BTBLKEU` | JBL Tune 520BT Black EU | not_ready | 0 / 0 | needs_review | not_ready | Не проверена; exact региональный SKU не подтверждён |
| `JBLBAR500PROBLKEP` | JBL Bar 500 Black EP | not_ready | 0 / 0 | needs_review | not_ready | Не проверена; exact региональный SKU не подтверждён |
| `JBLTBUDSBLK` | JBL Tune Buds Black | not_ready | 45 / 44 | done | export_ready | Проверена; нет блокирующих пробелов |
| `JBLFLIP6BLU` | JBL Flip 6 Blue | not_ready | 20 / 20 | done | export_ready | Проверена; нет блокирующих пробелов |
| `JBLT520BTWHTEU` | JBL Tune 520BT White EU | not_ready | 0 / 0 | needs_review | not_ready | Не проверена; exact региональный SKU не подтверждён |

Итог dataset: 6 exact identities, 212 raw facts / 211 normalized confirmed (у Tune Buds один alias схлопнут), 4 ready, 2 with gaps, 4 not ready, 0 conflicts. Baseline отдельно: 21/21 и ready. Для шести exact dataset PDP по одному scoped hero фото; baseline 8 Product images: всего 14 подтверждённых выбранных изображений. Для всех десяти sources/support/documents/photos/identity/dealer trace полностью перечислены в release JSON, пустые поля сохранены как gaps.

Exact URLs: [Charge 5](https://id.jbl.com/bluetooth-portables/JBLCHARGE5BLK.html), [Go 4](https://id.jbl.com/bluetooth-portables/JBLGO4BLK.html), [Tune 770NC](https://id.jbl.com/over-ear-headphones/JBLT770NCBLK.html), [Live 770NC](https://id.jbl.com/over-ear-headphones/JBLLIVE770NCBLK.html), [Tune Buds](https://id.jbl.com/in-ear-headphones/JBLTBUDSBLK.html), [Flip 6 Blue](https://id.jbl.com/bluetooth-portables/JBLFLIP6BLU.html). Авторитетны фактически сохранённые final URL в release JSON; категории маршрута сами по себе не доказывают identity.

## 8. Identity edge cases

[identity_manual_review.json](identity_manual_review.json): реальный DE baseline HTML принимается для JBLFLIP6BLKEU; тот же HTML отклоняется как exact для JBLFLIP6BLU (другой цвет), JBLFLIP6BLK (потерян регион) и JBLFLIP6BLKEP (другой suffix). Семейный support-only контекст не даёт exact. Для rejected случаев 0 confirmed specs. Это offline повторное чтение сохранённого реального ответа; family-only markup — явно синтетический сценарий, а не полученный support response. 23 Stage62 tests дополнительно проверяют PID/MPN mismatch, foreign host, bundle, gallery чужого цвета, family images, typed legal docs и hash tampering.

## 9–10. Системные проблемы и verdict

**`JBL adapter not ready`** для закрытия бренда. Нужны: подключить общий attended search provider/добрать exact evidence для Xtreme 4 BLUEP, Tune 520BT BLKEU, Bar 500 PROBLKEP и Tune 520BT WHTEU; проверить Go 4 PDF визуально/OCR; расширить sitemap traversal после доступного index. Региональный 403/404 не доказывает глобальное отсутствие SKU. Soundbar exact extraction в live выборке не подтверждён, переносимость его полей пока лишь код/test coverage.

Реальные source gaps: Charge 5 RU не найдена в проверенном документе; неоднозначность one/pair в earpiece weight; часть аудиопараметров не публикуется отдельными specs. Это не ошибки identity. Системные ошибки baseline dispatch, legacy gallery, QSG title spacing и CFF extraction исправлены общими правилами. Marketing/conditional/family values не повышаются до exact facts. Для готовых четырёх dataset карточек и baseline доказательства достаточны в проверенном scope, но это не означает закрытие всего бренда.

## UI / Excel / photos

11 UI страниц (baseline+10) HTTP 200; raw labels/sections сохранены, support/FAQ поля не протекли. [qa_ui_excel.json](qa_ui_excel.json) и семь UI PNG включают unresolved case, typed docs, selected gallery и реальный lightbox. Исправлена оставшаяся подпись LG на JBL-card. Три фактически прочитанных PNG (Charge black, Tune Buds black, Flip blue) визуально соответствуют цвету; все 1605×1605, file bytes/format измерены, не взяты из URL. [photo_inspection.json](photo_inspection.json).

Штатный exporter: 12 строк readiness с header, 233 строки источниковых фактов с header, 6 строк verified instructions с header, 15 photos с header, 50 typed-doc entries с header. 5 ready включают baseline, 2 with gaps, 4 not ready. Candidates отдельно; пустой live facts-candidate sheet корректен, conditional examples покрыты тестами. Formula errors отсутствуют; export статический. Spreadsheets artifact-tool импортировал Excel только для read-only inspect/render; не переписывал workbook. [excel_readiness.png](excel_readiness.png), [excel_battery.png](excel_battery.png), [excel_tws_components.png](excel_tws_components.png), [excel_documents.png](excel_documents.png). Длинные gap/URL в стандартных cells могут визуально обрезаться, полные значения сохранены. Одинаковые canonical labels разных языков в speakers sheet пока получают raw suffix для предотвращения collision: это оставшийся presentation gap, не новый exact факт.

## 11. Regression и воспроизводимость

Полный release regression: `python -m tests`, 1487 tests, OK; [regression_release.json](regression_release.json) содержит exit code, elapsed и fingerprint source tree. 23 новых JBL tests + 35 Lenovo + 54 structural ранее прошли targeted проверку. После финальных UI/weight уточнений full regression повторён. `git diff --check` должен быть чистым перед release.

Установить `product_tool/requirements.txt`. Из repo root: восстановить публичные PDF `PYTHONPATH=. python reports/jbl_stage62/restore_manual_proofs.py`, затем `run_release_pass.py` в checkout без существующего release_pass.sqlite3. Script отказывается перезаписывать существующую DB. Исходные exact HTML + manifests и frozen dataset хранятся с `-text` для сохранения byte SHA. PDF/XLSX/DB/browser profile/node_modules игнорируются; восстановление PDF проверяет фактический official host, PDF header и SHA, изменившаяся редакция требует нового аудита. Перезапуск свежего discovery при текущих protected regions может дать новый gap; сохранённые evidence не утверждают будущую доступность сети.

## 12. GitHub

Commit message: `Stage 62`. После PASS выполнены commit/push и сверка `HEAD == origin/main`, clean working tree; фактический hash сообщается в ответе и выводе Git, чтобы не включать self-referential hash в commit.
