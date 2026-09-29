# Очередь покрытия: правила Stage 18

Дополнение к `docs/COVERAGE_QUEUE_V17.md`. Планировщик по-прежнему офлайн; отчёт этапа — `reports/source_census_2026-09-24_stage18/report.md`.

## Fixture Product page — это область действия, а не свойство бренда

Сохранённая страница подтверждает только то, что на ней реально наблюдалось: **host, рынок, категорию каталога и шаблон страницы**. В `product_tool/config/coverage_planner.v1.json` это `family_facts.<семейство>.scopes[]`:

| поле | смысл |
|---|---|
| `categories` | точные строки колонки «Категория»; по ключевым словам и по бренду ничего не сопоставляется |
| `hosts`, `market`, `market_matches_catalog` (+ `market_reason`) | где страница наблюдалась и совпадает ли это с рынком каталога |
| `layers` | `identity`, `specifications`, `media`: `observed` / `partial` / `absent` |
| `discovery` | `confirmed` / `structural_only` / `no_crawl` / `none` — доказан ли маршрут **для этой категории** |
| `evidence`, `observed_urls`, `caveat` | ссылки на артефакты, сами страницы, оговорки |

Правила статуса единицы (`product_tool/coverage/classify.py`):

* категория единицы есть в scope, рынок совпадает, слои полные → `official_route_no_adapter`;
* категории нет ни в одном scope → `needs_product_page_fixture`, причина `no_product_page_evidence_for_category`;
* страница из чужого рынка (US web-store, немецкий country-сайт) → `needs_product_page_fixture`, `fixture_market_differs_from_catalog`;
* не хватает слоя → `needs_product_page_fixture`, `structural_missing_<слои>`;
* у семейства без объявленных scope family-wide fixture не применяется вовсе (`fixture_scope_not_declared`).

Семейства со scope: Samsung (микроволновые печи; телевизоры и беспроводные наушники; остальное без страницы), PlayStation (геймпады и диски — оба на US web-store), Microsoft (консоли — линейная страница en-US), Bosch Home (чайники — немецкий сайт), Cudy (роутеры), HyperX (микрофоны, мыши, клавиатуры).

## Волны считаются по подтверждённым scope

`waves.json`: `adapter_ready_units` — единицы, для которых адаптер можно строить на evidence их собственной категории; они уходят из `official_route_no_adapter`. Они становятся `ready_to_run` только при точном URL (`ready_guaranteed_by_urls_on_record_units`) или при подтверждённом маршруте **этого scope** (верхняя граница). `waiting_on_fixture_units` — отдельная величина: этим единицам сначала нужен fixture, это не выигрыш адаптера. Маршрут поиска, доказанный для другой категории или рынка, готовности не обещает.

## Повтор артикула — риск, а не конфликт

Один артикул продавца у разных категорий или брендов получает флаг `seller_sku_shared_across_category|brand` и поле `sku_risk` (`shared_across_…;titles_agrees|uninformative`); единица классифицируется по своему маршруту. Проверять такую строку нужно вместе с названием, моделью и вариантом — флаги и `sku_risk` попадают в checkpoint исполнителя. `identity_conflict` ставится, только если названия единиц содержат модельные токены (буквы+цифры, не количества) и ни один не общий, либо есть подтверждённый факт по товару (HyperX `7G7A4AA#ACB`: страница #ABA, каталог #ACB).

## Критерий `exact_variant`

Не требует, чтобы артикул продавца встречался на официальном сайте (у PlayStation `CFI-ZCT1W_cosmic_red` — метка каталога). Используются признаки модели и варианта, которые публикует сам источник: название/код модели плюс различитель варианта (цвет, размер, объём, раскладка) из структурированного поля. Без различителя результат не выше `exact_model`. Код, который страница публикует, не должен противоречить каталогу: подтверждённое расхождение регионального кода по-прежнему блокирует `exact_variant`. Для HyperX это `sku` из JSON-LD страницы (`adapters/hyperx.py`).

## Поиск URL для строк с адаптером

Рабочая карта — `hyperx.KNOWN_URLS`. В неё попадает строка только если: страница наблюдалась (сохранённая ссылка на официальной странице, снимок, `<loc>` из sitemap, объявленного в `robots.txt`), `sku` страницы равен коду каталога (`exact_variant` по правилу адаптера) и все модельные токены названия есть в названии товара на странице. Тест `KnownUrlsMatchTheirEvidence` держит карту равной `reports/source_census_2026-09-24_stage18/raw/accepted_urls.json` плюс две строки Stage 15. Остальные строки описаны в `coverage_planner.v1.json` → `url_findings`; из них планировщик строит **один** запрос пользователю на бренд и host (`request_groups.json`, поле `items`).

## Прирост измеряется четырьмя разными числами

`python -m product_tool.coverage delta` разносит движения по причинам (`moves_by_cause`): `evidence_scope_corrected`, `identity_rule_corrected`, `exact_url_confirmed`. Четвёртое число — карточки — не из очереди, а из исполнителя (`executor`): `done` от `worker.run_once()`.
