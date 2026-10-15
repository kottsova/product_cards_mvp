# Apple: восстановление первого actual production UI товара

Проверена исходная карточка **84**, партия `70c329c089c2432fbe042651944c6acd`, файл `Создать_НМ_Apple_KVN.xlsx`, строка 2.

## Причина мгновенного завершения

Исходные значения: категория `смартфоны`, бренд `Apple`, hardware-код `A3714`, название `iPhone 18 Pro 256GB`, цвет `Серебристый`.

Сохранённое сопоставление: brand=2, search_code=3, fallback_code=2, name=3, category=1. Поэтому название стало `A3714`, запасная модель — `Apple`. Заголовок `Наименование на сайте` ранее не входил в распознаваемые aliases. Предпросмотр также не предупреждал о назначении колонки бренда запасной моделью.

Worker выбрал Apple adapter. `AppleAdapter.find_source` возвращал ошибку до первого HTTP-запроса, если код не соответствовал commercial SKU `…/A`. Затем pipeline сохранял пустой результат, рассчитывал readiness и вызывал неуспешный dealer fallback. Поэтому `model_identity_missing` описывал невыполненный поиск, а не официальный model miss.

Исторические времена: импорт 12:00:01 UTC, очередь 12:00:03 UTC, worker и finish 12:00:04 UTC. Детальных исторических timestamps каждой функции не было; ветка возврата устанавливается по сохранённому входу, production коду и отсутствию official discovery trace. Нельзя приписывать историческим функциям выдуманные времена.

Stage 65 подтверждал общие specs через exact order/catalog relation для квалифицированных входов; независимый marketing-model lookup при hardware-only input отсутствовал. `git blame` относит gate к commit `780d5ba` (**Stage 64**). Это доказанный незакрытый production путь, а не изменение общих readiness thresholds после Stage 82.

Дополнительно обнаружены: Apple browser fallback без собственного classifier применял Lenovo URL rules; native Tech Specs содержит разделённые model/shared continuation cells; Buy опубликован как `shop/goto` redirect; additive display/button rows нельзя классифицировать как альтернативные значения одного скалярного поля.

## Исправление

- Commercial SKU gate больше не останавливает поиск модели для hardware input. Новый iPhone путь использует существующий policy-aware HTTP и общий browser fallback; каталог → опубликованная PDP → её опубликованные specs/Buy links.
- Pro и Pro Max, поколения, чужие цвета и неподтверждённые hardware relations отделены. Позиция первой колонки не доказывает модель. Shared cells допускаются по явному colspan, exact cells — по опубликованной model heading/figure relation.
- Model-level specs используют общий Stage 65/82 scoped mapper. Configuration overlay читает явные model/capacity/color Store records. Supplier SKU, carrier, регион и radio identity не выводятся из выбранного по умолчанию варианта.
- Добавлен Apple classifier общего external fallback; Lenovo правила больше не отбрасывают официальные Apple URL.
- Исправлены `Pro/Max/Ultra chip` labels, объединение additive display continuation, отдельные Action button / Camera Control функции и различие nominal diagonal / rounded-corner rectangle measurement.
- `Наименование на сайте` распознаётся. Collision колонки бренда с моделью/артикулом/названием вызывает предупреждение. Единственная явно названная колонка `Цвет` переносится как input configuration в существующий identity JSON; произвольные колонки не угадываются.
- UI photos подтверждаются по exact asset relations, включая модель/цвет; чужая gallery не становится confirmed по одному бренду Apple.
- Append-only `discovery_trace` и журнал UI показывают dispatch, normalization, navigation start/end/URL/status, extraction, overlay, photos, documents, persistence и readiness. Различаются `discovery_not_started`, `discovery_started`, `official_source_not_found`, `source_found_but_identity_rejected`, `extraction_empty`, `readiness_failed`.

Сначала название и input color карточки 84 восстановлены из исходных ячеек; сохранён SQLite backup в `data/backups/apple_first_card_before_repair.sqlite3`. После успешной квалификации также восстановлены **7 остальных строк этой же партии**, только после проверки того же доказанного шаблона ошибки: name равен hardware-коду, alternate_code равен бренду, исходные ячейки и бренд совпадают. Название/цвет восстановлены из D/E, ошибочная запасная модель очищена, batch mapping исправлен. Их source jobs не запускались и official facts/readiness не квалифицировались автоматически; см. `remaining_input_repairs.json`. Другие партии не менялись.

Для повторного импорта этого файла: бренд B/2, основной hardware-код C/3 (у него нет заголовка), название D/4, категория A/1; запасную модель не назначать колонке бренда.

## Actual production run через рабочий UI

Playwright/установленный Chrome нажал штатную кнопку формы `http://localhost:8765/products/84`; POST `/products/84/search` вернул 303. Задание исполнил обычный embedded worker уже перезапущенного Uvicorn. Adapter/session не подменялись. Сохранённые прежние fixtures не использовались как live источники.

| Этап | Время UTC последнего запуска | Результат |
|---|---|---|
| UI queue / worker dispatch | 12:33:09–10 | job `a41d4d1686f343ac88c2b525e22e39d0`, stages 1/2/3/4/6 |
| Normalization / discovery started | 12:33:10 | iPhone 18 Pro; A3714 отдельным input identifier |
| Official catalog | 12:33:10–12 | HTTP 200, опубликованный PDP candidate |
| PDP navigation | 12:33:12–13 | HTTP 200, exact family identity |
| Specs / DOM extraction | 12:33:14–16 | HTTP 200; 270 raw fields, 50 admitted fields; чужие cells исключены |
| Store / configuration overlay | 12:33:16–19 | Buy redirect → HTTP 200; явные model/256GB/silver records |
| Gallery relation | 12:33:19 | exact model + silver; без supplier retail identity claim |
| Documents | 12:33:19–22 | русское платформенное руководство iPhone проверено |
| Extraction / persistence | 12:33:22 | модель и конфигурация сохранены до readiness |
| Photo byte verification | 12:33:22–24 | PNG 940×1112, 589628 bytes; общий UI photo inventory хранит SHA и byte_verified=true |
| Readiness | 12:33:24 | export_ready; 50 confirmed canonical specs, conflicts=0 |

Official route: [catalog](https://www.apple.com/iphone/) → [PDP](https://www.apple.com/iphone-18-pro/) → [native Tech Specs](https://www.apple.com/iphone-18-pro/specs/) и опубликованный Buy redirect → [Store](https://www.apple.com/shop/buy-iphone/iphone-18-pro).

Identity: `model=model_confirmed`, `configuration=model_configuration_supported`, `variant=exact_model_color`, `hardware=published_store_key`. Store публикует `a3714_energy_compliance` у iPhone 18 Pro records. Это relation на опубликованный Store key; она не доказывает региональную radio/SIM конфигурацию. `MJQ44LL/A` сохранён как retail candidate; supplier commercial part number остаётся пустым. Не выбрана default carrier configuration.

Три успешных live UI прогона: 12:20:47–12:21:01 (14 секунд), 12:26:42–12:26:57 (15 секунд), 12:33:10–12:33:24 (14 секунд worker / 15 секунд от очереди). Sources и asset key стабильны; источник, цвета и facts не дублируются при upsert; readiness совпадает. Первый диагностический live 12:16:56–12:17:05 честно сохранён как needs_review, а не скрыт успешным replay.

Manual — проверенное русское платформенное User Guide, не exact hardware/SKU manual. Readiness от инструкции не зависит.

## Проверки и пределы

61 целевой regression: upload → mapping → confirmation сохраняет исходный цвет; actual UI route → очередь → worker начинает discovery до readiness; hardware/model/color negatives; Pro Max/generation cell isolation; scope/continuation; Stage 64/65 и Stage 82 guards. Синтетические transport tests помечены offline и не используются как live qualification.

Полный regression: **1916 tests / 1028.340 секунд**, 0 assertion failures, **1913 прошли сразу**. Три browser tests завершились environment error: отсутствовал штатный Playwright `chromium_headless_shell-1243`. Исходный полный invocation честно сохранён с exit_code=1 в `regression.json`/`regression.log`; production tree в ходе suite не изменялся.

Официальный Headless Shell установлен в `data/playwright_browsers` через `python -m playwright install chromium --only-shell`. Те же три теста повторены без изменения tests/production кода: **3 tests / 1.542 секунд / OK**, см. `environment_recheck.json`. Нет оставшихся regression ошибок. Это квалификация двумя прогонами, а не утверждение о нулевом exit code первого full-run. В повторном test process задан `PLAYWRIGHT_BROWSERS_PATH=A:/work/dev/product_cards_mvp/data/playwright_browsers`; системный браузерный профиль пользователя не менялся.

`git diff --check` проходит. Старые protected-file guards сохранены; текущие user-authorized изменения квалифицированы по точным SHA. Изменения находятся локально; новый commit/push для этой ненумерованной задачи не выполнялся.

Новый независимый native model-first recovery квалифицирован на iPhone пути. Существующие commercial-order routes остальных Apple категорий сохранены; этот первый товар не доказывает автоматически работу всех новых Mac/iPad/Watch/AirPods моделей.

## Артефакты

- `original_failure.json`, `input_repair.json`: исходный сбой/вход, repair provenance.
- `actual_production_round1.json`: честный первый диагностический live с оставшимися пробелами.
- `actual_production_round2.json`, `actual_production_round3.json`, `actual_production.json`: три успешных actual production UI runs, полный trace/events/facts/photos.
- `final_gallery.json`, `qualification.json`: конечные identity/byte/SHA/color flags и trace последнего реального задания.
- `ui_before.png`, `ui_after.png`, `ui_after.html`: native UI результата последнего запуска.
- В `data/apple_captures`: свежие official response bodies и URL/status/query/SHA метаданные; `data/apple_fetch.json` и `data/apple_image_fetch.json`: actual HTTP journals. Probe/capture parser QA отдельно от production run.
