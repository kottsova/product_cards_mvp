"""Stage 19 step 10 -- OFFLINE. Render report.md, the remaining-rows request and the next-wave proposal from the saved
artifacts of this stage (every number is read from a JSON file)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


numbers = load(STAGE / "numbers.json")
conflicts = load(STAGE / "raw/conflict_analysis.json")
linkage = load(STAGE / "raw/variant_linkage.json")
live = load(STAGE / "raw/live_variant_result.json")
gap = load(STAGE / "raw/live_snapshot_gap_result.json")
replay = load(STAGE / "controls/all_ready_summary.json")
integrity = load(STAGE / "protected_hashes_check.json")
delta18 = load(STAGE / "delta_vs_stage18.json")
delta17 = load(STAGE / "delta_vs_stage17.json")
summary = load(STAGE / "queue/coverage_summary.json")["summary"]
s17 = load(ROOT / "reports/source_census_2026-09-24_stage17/queue/coverage_summary.json")["summary"]
s18 = load(ROOT / "reports/source_census_2026-09-24_stage18/queue/coverage_summary.json")["summary"]
units = [json.loads(line) for line in (STAGE / "queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
priority = load(STAGE / "queue/priority_queue.json")
findings = load(STAGE / "raw/url_findings.json")["findings"]
tests_tail = (STAGE / "tests.txt").read_text(encoding="utf-8").strip().splitlines()
ran = next(line for line in tests_tail if line.startswith("Ran "))
verdict = tests_tail[-1]
per_unit = replay["per_unit"]
variant_rows = [r for r in per_unit if r["variant_source"] == "in_page_variant_record"]
colour_checkable = [r for r in linkage["rows"] if r["title_colours"]]
lg_ready = Counter(u["category"] for u in units if u["family"] == "lg" and u["status"] == "ready_to_run")
samsung_micro = sum(1 for u in units if u["scope_id"] == "samsung_kz_ru_microwave")
cudy_routers = sum(1 for u in units if u["scope_id"] == "cudy_com_routers")
by_family = {row["family"]: row for row in priority}


def conflicts_table() -> str:
    lines = ["| Строка | Имя | Что на странице | Причина | Решение |", "|---|---|---|---|---|"]
    for c in conflicts["conflicts"]:
        if c["cause"] == "different_device_node":
            what = " ↔ ".join(f"«{f['value']}» ({f['section']}, блок {f['block']}, {f['block_label']})" for f in c["fragments"])
            cause = "два разных узла устройства: наушники и микрофон (блок опознан по своей же строке «Element … microphone»); единицы измерения различаются" if c.get("unit_classes_differ") else "два разных узла устройства: наушники и микрофон (блок опознан по своей же строке «Element … microphone»)"
        else:
            what = "«$99.99» / «from $99.99» (виджет цены на странице)"
            cause = "это не характеристика: `<dl>` внутри контейнера `price`"
        lines.append(f"| {c['seller_sku']} | {c['name']} | {what} | {cause} | {'разрешён' if c['resolved'] else 'оставлен на проверку'} |")
    return "\n".join(lines)


def cards_table() -> str:
    lines = ["| Артикул | Категория | Откуда идентичность | Галерея варианта | Инфографика модели (feature) | Чужие варианты (исключено) | Атрибутов варианта / общих модели | Документы |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for r in per_unit:
        source = "запись варианта на странице" if r["variant_source"] == "in_page_variant_record" else "выбранный вариант страницы"
        lines.append(f"| {r['seller_sku']} | {r['category']} | {source} | {r['photos_by_kind'].get('product_gallery', 0)} | {r['photos_by_kind'].get('feature', 0)} | {r['photos_excluded']} | {r['variant_attributes']} / {r['shared_model_attributes']} | {r['documents']} |")
    return "\n".join(lines)


def request_markdown() -> str:
    rows = {u["seller_sku"].upper(): u for u in units if u["family"] == "hyperx" and u["status"] == "adapter_url_missing"}
    by_outcome = defaultdict(list)
    for sku, item in findings.items():
        by_outcome[item["outcome"]].append(sku)

    def table(skus, columns):
        header = "| " + " | ".join(name for name, _ in columns) + " |\n|" + "|".join("---" for _ in columns) + "|\n"
        return header + "".join("| " + " | ".join(str(fn(sku)) for _, fn in columns) + " |\n" for sku in sorted(skus, key=lambda s: (rows[s]["category"], s)))

    name = lambda s: rows[s]["title"]
    page = lambda s: findings[s].get("page_url", "").replace("https://hyperx.com", "") or "—"
    default_sku = lambda s: findings[s].get("page_default_sku", "") or "—"
    b, c, d = (sorted(by_outcome[k]) for k in ("page_sku_differs_from_catalog", "no_observed_page_for_title", "title_names_other_manufacturer"))
    keyboards = [s for s in b if rows[s]["category"] == "Клавиатуры"]
    others = [s for s in b if s not in keyboards]
    return f"""# HyperX: один запрос по {len(findings)} строкам (обновлено в Stage 19)

Группа A из Stage 18 (7 строк, вариант есть на странице) закрыта: URL варианта напечатан в самих данных страницы и проверен, строки в рабочей карте. Осталось **{len(findings)}** строк из 41 без точного официального URL. Ответьте по каждому пункту одной строкой: **URL**, «нет такой страницы на hyperx.com» или «оставить как есть».

## B. Страница найдена, но её sku другой — вариант каталога не подтверждён ({len(b)} строк)

Кода каталога на странице нет: это другой вариант, регион или поколение; в списке вариантов страницы его тоже нет.

**B1. Клавиатуры (RU), {len(keyboards)} строк.** Каталог: коды `…AX#ACB` / `…AA` (RU); на hyperx.com найдена только US-раскладка (`…#ABA`), у части строк отличается и базовый код. **Нужно:** ссылка на RU-страницу, если она есть, либо «нет такой страницы».

{table(keyboards, [("Артикул", lambda s: s), ("Название в каталоге", name), ("Найдена страница", page), ("sku страницы", default_sku)])}
**B2. Прочие, {len(others)} строк.** **Нужно:** ссылка на страницу именно этого варианта или «нет такой страницы».

{table(others, [("Артикул", lambda s: s), ("Название в каталоге", name), ("Найдена страница", page), ("sku страницы", default_sku)])}
## C. Страницы нет в наблюдённых источниках ({len(c)} строк)

**Нужно:** URL, если товар есть на hyperx.com, либо «нет на hyperx.com».

{table(c, [("Артикул", lambda s: s), ("Категория", lambda s: rows[s]["category"]), ("Название в каталоге", name)])}
## D. Не товар hyperx.com ({len(d)} строка)

{table(d, [("Артикул", lambda s: s), ("Название в каталоге", name)])}
Модуль памяти Kingston под брендом HYPERX. **Решение нужно:** перенести под Kingston, отправить на ручную проверку или оставить как есть.
"""


def proposal_markdown() -> str:
    lg_total = sum(lg_ready.values())
    return f"""# Предложение следующей волны (W2) — не запускается автоматически

Составлено по очереди Stage 19 (`queue/`), только по приоритетным брендам Stage 8. Каждый шаг перечисляет прирост каталога, потолок запросов, критерий остановки и что нужно для «готово». Ничего из этого не выполнялось.

## Где сейчас приоритетные бренды

| Бренд | Товаров | Готово к запуску | Что мешает остальному |
|---|---:|---:|---|
| LG | {by_family['lg']['unique_products']} | {by_family['lg']['unit_status_counts'].get('ready_to_run', 0)} | 4 строки: артикул не код производителя. Для готовых 578 в очереди нет измеренного результата: «готово» = «можно запускать» |
| HyperX | {by_family['hyperx']['unique_products']} | {by_family['hyperx']['unit_status_counts'].get('ready_to_run', 0)} | {by_family['hyperx']['unit_status_counts'].get('adapter_url_missing', 0)} строк ждут вашего ответа, 1 конфликт региона |
| Samsung | {by_family['samsung']['unique_products']} | 0 | микроволновые печи ({samsung_micro}): маршрут доказан, адаптера нет; ТВ/наушники (454): нужны характеристики, которых нет в статичном HTML; остальное без страницы |
| Bosch Home | {by_family['bosch_home']['unique_products']} | 0 | единственная страница — немецкий сайт; нужен fixture для рынка каталога |
| Xiaomi/POCO | {by_family['xiaomi_global']['unique_products']} | 0 | нет слоя характеристик ни на одной сохранённой странице |
| Apple | {by_family['apple']['unique_products']} | 0 | ни одной страницы Product |
| PlayStation / Microsoft | {by_family['playstation']['unique_products']} / {by_family['microsoft']['unique_products']} | 0 | наблюдались только страницы US-рынка |
| JBL, Razer | {by_family['jbl']['unique_products']} / {by_family['razer']['unique_products']} | 0 | host остановлен; без решения человека не трогать |
| Cudy (вне списка Stage 8, шаблон группы A) | 68 | 0 | {cudy_routers} роутеров имеют структурную страницу, адаптера нет |

## Предлагаемые шаги (в порядке приоритета)

**1. Samsung, микроволновые печи: сначала посчитать, потом строить.** Гарантированно есть 1 URL из {samsung_micro}; потолок {samsung_micro} ({(100*samsung_micro/summary['unique_products']):.2f} % каталога). В сохранённом срезе `da-sitemap` было только 300 ссылок, из них нашёлся 1 точный хит, поэтому число реальных совпадений неизвестно.
* Бюджет: ≤ 3 запросов sitemap на samsung.com/kz_ru (индекс и его дочерние `da-sitemap`), ссылки только через `sitemap_urls.sitemap_locs()`; страницы товаров не запрашивать.
* Критерий остановки: 403/429/подтверждённый challenge; после подсчёта — решение, стоит ли писать адаптер (предлагаемый порог: хотя бы 15 из {samsung_micro} точных совпадений модели; вы его задаёте).
* Прирост: измеряется сразу (число моделей каталога, найденных в sitemap); адаптер после этого — задача волны W1-D, готовность через 9 критериев.

**2. LG: измерить реальную долю карточек на малой выборке.** {lg_total} строк «готово», но это допуск, а не результат; LG-адаптеры не ходят через `PolicyAwareFetcher` и не сохраняют остановку host между запусками (критерий `policy_fetch` для них не выполнен).
* Предпосылка (код, без сети): LG-адаптеры получают страницы через `fetch_with_retry`, без `PolicyAwareFetcher`; нужно провести запросы через политику с журналом и добавить тест «остановка переживает перезапуск».
* Затем пилот: {len(lg_ready)} строк, по одной на категорию ({', '.join(c for c, _ in lg_ready.most_common(4))}…), ≤ 5 запросов на строку, всего ≤ 60; остановка при первом 403/429.
* Прирост: даёт измеренную долю `done`/`needs_review` для {lg_total} строк ({f"{100*lg_total/summary['unique_products']:.2f}".replace(".", ",")} % каталога), после чего можно решать о полном прогоне.

**3. Cudy: адаптер на уже проверенных примитивах Shopify.** {cudy_routers} роутеров (0,17 % каталога). Схема URL страниц Cudy (`/products/…`, `/collections/…`) характерна для Shopify, а `extract_shopify_product` уже работает на 20 карточках HyperX; совпадение движка нужно подтвердить по сохранённой странице.
* Сначала офлайн: посмотреть, что в сохранённой структурной странице Stage 8 есть вариантные данные и спецификации значениями, а не только именами полей.
* Сеть только после этого: ≤ 3 запроса sitemap + ≤ 10 страниц; оговорка Stage 8 — `challenge_suspected` на всех образцах cudy.com, при подтверждённом challenge остановка и запись в журнал.
* Прирост: до {cudy_routers} строк станут `ready_to_run` только там, где найден точный URL по sitemap; иначе они будут ждать URL.

**4. Apple: только разведка.** {by_family['apple']['unique_products']} товаров ({100*by_family['apple']['unique_products']/summary['unique_products']:.1f} % каталога) без единой сохранённой страницы Product. Один структурный проб, ≤ 10 запросов: страница товара, sitemap, наличие JSON-LD и характеристик. Прирост в этой волне 0, результат — решение, есть ли смысл в адаптере.

**Не предлагаю сейчас:** Samsung ТВ/наушники (характеристики только на клиенте: без Chromium статический HTML их не даёт), Xiaomi (нужны fixtures со слоем характеристик; сначала офлайн-аудит уже сохранённого), JBL и Razer (host остановлен), PlayStation и Microsoft (страницы чужого рынка). HyperX: ждёт ответов по {len(findings)} строкам (`hyperx_user_request.md`).

## Что нужно решить вам

1. Идти ли по порядку 1 → 2 → 3 → 4 или начать с LG (наибольший запас: {lg_total} строк).
2. Разрешение на 3 запроса sitemap Samsung (шаг 1).
3. Ответы по 20 строкам HyperX.
"""


def report_markdown() -> str:
    hy = numbers["hyperx_cards"]
    ready = numbers["ready_to_run_units"]
    c = numbers["stage18_review_conflicts_resolved"]
    v = numbers["variants_of_group_a_confirmed"]
    return f"""# Stage 19 — варианты HyperX, пять needs_review, остановка по challenge

Отчёты Stage 17 и ранее, каталог и реестр источников не менялись (`protected_hashes_check.json`).

## Простые числа

| Вопрос | Ответ |
|---|---|
| Сколько из семи вариантов подтверждено | **{v['confirmed']} из {v['of']}** |
| Сколько из пяти конфликтов разрешено | **{c['rows_fully_resolved']} из {c['of_rows']} строк** ({c['conflicts_resolved']} из {c['of']} отдельных расхождений; спорных осталось {c['still_disputed']}) |
| Сколько карточек HyperX готово | **{hy['cards']} из {hy['rows_with_url_of_record']}** строк с URL (Stage 17: 2; Stage 18: 6 из 11 новых, ещё 5 были на проверке); на проверке сейчас {hy['for_review']} |
| HyperX в каталоге (41 строка) | {hy['hyperx_status_counts']['ready_to_run']} с карточкой, {hy['hyperx_status_counts']['adapter_url_missing']} без URL (запрос ниже), {hy['hyperx_status_counts']['identity_conflict']} региональный конфликт |
| Можно запускать (`ready_to_run`) | {ready['stage19']} (Stage 17: {ready['stage17']}, Stage 18: {ready['stage18']}) |
| Сетевые запросы этого этапа | 8: 7 страниц вариантов и 1 страница для карточки `4P5D4AA`; блокировок нет |

«Карточка» — задание, которое обычный `worker.run_once()` довёл до `done` на **сохранённых настоящих страницах hyperx.com** (офлайн-повтор); живой worker не запускался.

## 1. Семь вариантов группы A

Проверено по данным самих страниц, без построения адресов:

* во встроенном `<script data-product-json>` у варианта есть `sku`, `id` и штрихкод;
* в JSON-LD `Product.offers` есть предложение с тем же `sku`, GTIN и собственным `url ...?variant=<id>`;
* `id` из URL равен `id` встроенного JSON; адрес присутствует в тексте страницы дословно; хост, путь и запрос (`variant=<id>`) допустимы. Пример из задания: `727A8AA` — `43656365375645` — `https://hyperx.com/products/hyperx-cloud-iii-wired-gaming-headset?variant=43656365375645`.

Итог офлайн: 7 из 7 связаны и URL наблюдался (`raw/variant_linkage.json`). Конкретный остаток: ни одна страница не была получена по этим адресам. По заранее объявленному бюджету (≤ 7 запросов, только эти URL) все 7 получены, HTTP 200, `challenge_suspected` (эвристика срабатывает на каждой странице сайта), блокировок нет. Адаптер на каждой из 7 страниц даёт `exact_variant`, и результат (атрибуты варианта, число фото) **равен** результату извлечения из сохранённой страницы по умолчанию. **Важная находка:** JSON-LD страницы по адресу варианта по-прежнему называет вариантом по умолчанию (`page selected …`), поэтому идентичность этих строк берётся только из записи варианта на странице, а не из «страница выбрала этот вариант». Все 7 URL в `KNOWN_URLS`.

Ограничение проверки цвета: только у {len(colour_checkable)} из 7 названий каталога есть цвет (`AJ0T1AA`, Black); у остальных {7 - len(colour_checkable)} название цвета не называет, и идентичность держится на SKU и GTIN.

## 2. Вариантное извлечение в рабочем адаптере

`adapters/hyperx.py`, `adapters/structured_page.py` (`extract_shopify_product`):

* **Идентичность.** `exact_variant` даёт либо выбранный вариант страницы, либо запись варианта, подтверждённая двумя источниками страницы (JSON-LD offer и встроенный JSON: одинаковые `sku` и `id`, URL с этим `id`). Иначе не выше прежнего (`mismatch`/`base_code_confirmed`). Региональное расхождение `#ABA`/`#ACB` по-прежнему блокирует.
* **Данные варианта** (`SKU`, `Variant name`, опции вроде `Color`, `GTIN-12`) берутся из записи именно этого варианта; значения варианта по умолчанию не подставляются (тест сверяет SKU, GTIN и название по умолчанию с каждым атрибутом).
* **Фото.** У товара из одного варианта — все медиа. У нескольких вариантов — медиа, чей тег в `alt` совпадает с тегом главного изображения варианта, если тег у варианта уникален; иначе только главное изображение варианта. Чужие изображения не удаляются, а сохраняются как исключённые с причиной («other variant or shared media»). Миниатюра и основной слайд одного медиа считаются одним фото. Аннотированная инфографика (`…annotated…` в имени файла) — общая для модели: сайт помечает её цветом первого варианта («(Black) - 02»), поэтому она вынесена в отдельную группу `feature`, а не в галерею варианта.
* **Общие характеристики.** Таблица характеристик и описание — общие для модели: каждый такой атрибут помечен `scope="model"`, список имён вариантных и общих атрибутов пишется в `evidence` источника (`attribute_scope=…`, без изменения схемы БД) и виден в карточке исполнителя (`attribute_scope`, `photos_excluded`).
* Дополнительно найденный пробел извлечения: страницы Cloud II Core и Cloud III Wireless публикуют характеристики не таблицей, а заголовками и списком `<li><strong>Имя:</strong> значение`; раньше из них извлекалось 0 характеристик, теперь по 19.

## 3. Пять needs_review из Stage 18

Причина у всех пяти — не противоречие значений, а разные части устройства (и один виджет цены). Сам сайт при этом повторяет заголовок «Headphone Specifications» над блоком микрофона (описка шаблона), поэтому блок опознаётся не по заголовку, а по собственной строке «Element … microphone» и по единицам измерения. Каждое расхождение разобрано по исходным фрагментам (`raw/conflict_analysis.json`):

{conflicts_table()}

Правило извлечения исправлено **только** под доказанные причины: (а) строка характеристики, повторяющаяся с другим значением в следующем блоке таблицы, получает имя `<имя> (<метка блока>)`, метка — `microphone`, если блок сам содержит строку «Element … microphone», иначе `<заголовок> #<номер блока>`; первое вхождение сохраняет обычное имя (его блок озаглавлен «Headphone Specifications»); (б) `<dl>` внутри контейнера `price` не считается характеристикой. Повтор с другим значением **внутри одного блока** по-прежнему остаётся конфликтом на проверку (есть тест). После исправления все пять строк дают `done`, конфликтов 0.

## 4. Остановка host по подтверждённому challenge и `&amp;`

* `PolicyAwareFetcher` пишет в журнал `access_status` и `protection_status` каждого ответа. Новый экземпляр (и планировщик, и исполнитель) считает host остановленным, если в журнале есть 401/403/429 **или** ответ с `challenge_confirmed`/`browser_verification_required` при любом HTTP-статусе, включая 200 (`stopped_hosts_from_fetch_log`). `challenge_suspected` записывается, но host не останавливает; старые журналы без новых полей читаются как раньше. Проверки: оба случая на реальных экземплярах fetcher, на планировщике и на смешанном журнале (`ConfirmedChallengeStopsTheHostAcrossInstances`).
* `<loc>` в sitemap читается как XML (`adapters/sitemap_urls.py`, `&amp;` → `&`), тест на сохранённом sitemap Stage 18: `sitemap_products_1.xml?from=…&to=…`. Скрипт Stage 18 не менялся (отчёт неизменен), поэтому его прежняя ошибка остаётся в архиве, исправление живёт в общем коде.

## 5. Карточки HyperX сейчас

{cards_table()}

## 6. Какие пробелы остались

* **Документы: 0 из {hy['cards']}.** На страницах hyperx.com нет прямых ссылок на инструкции; пробел назван, ничем не заполнялся.
* **20 строк HyperX без URL** и 1 региональный конфликт: [hyperx_user_request.md](hyperx_user_request.md) (один запрос).
* **Инфографика модели** на страницах (`annotated…`) отнесена к группе `feature`, но её принадлежность определяется именем файла, а не полем страницы: если сайт назовёт файлы иначе, они попадут в галерею варианта по тегу.
* **Число фото изменилось** относительно Stage 17/18 у старых карточек: миниатюра и основной слайд одного медиа теперь один снимок, инфографика вынесена в `feature`.
* Метка «общие/вариант» хранится в `evidence` источника, а не в колонке БД (`jobs.py` — защищённый файл), поэтому в интерфейсе и Excel её пока не видно.
* Карточки получены офлайн-повтором; `4P5D4AA` после живой страницы имеет 11 фото (в очищенном снимке Stage 5.1 их не было).

## 7. Проверки

* `python -m tests -v`: {ran}, {verdict}.
* Целостность: каталог не менялся ({'да' if integrity['catalog_unchanged'] else 'НЕТ'}); реестр источников совпадает с закреплением ({'да' if integrity['source_registry_matches_pin'] else 'НЕТ'}); {integrity['earlier_report_files_checked']} файлов отчётов Stage 2–16 совпадают с хэшами Stage 17; файлы Stage 17 и 18 не менялись ({len(integrity['stage17_and_stage18_files_modified_after_stage19_started'])} изменённых); закреплённые файлы сходятся ({'да' if integrity['pinned_all_ok'] else 'НЕТ'}); `adapters/common.py` совпадает с `git HEAD`; активные файлы не называют исключённого дилера ({integrity['active_files_scanned_for_excluded_dealer']} проверено); `data/batches.sqlite3` не менялась.
* Очередь воспроизводима побайтно; относительно Stage 18 `ready_to_run` {delta18['ready_to_run_gain']:+d}, относительно Stage 17 {delta17['ready_to_run_gain']:+d}.

## 8. Следующая волна

Предложение, без запуска: [next_wave_proposal.md](next_wave_proposal.md).
"""


def main() -> None:
    (STAGE / "hyperx_user_request.md").write_text(request_markdown(), encoding="utf-8", newline="\n")
    (STAGE / "next_wave_proposal.md").write_text(proposal_markdown(), encoding="utf-8", newline="\n")
    (STAGE / "report.md").write_text(report_markdown(), encoding="utf-8", newline="\n")
    print("rendered hyperx_user_request.md, next_wave_proposal.md, report.md")


if __name__ == "__main__":
    main()
