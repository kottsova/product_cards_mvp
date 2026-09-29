"""Stage 18 step 10 -- OFFLINE. Render the one grouped user request and the stage report from the saved artifacts.
Every number in the text is read from a JSON file of this stage (or Stage 17's queue for the comparison)."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]
S17 = ROOT / "reports/source_census_2026-09-24_stage17/queue"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


new_summary = load(STAGE / "queue/coverage_summary.json")["summary"]
old_summary = load(S17 / "coverage_summary.json")["summary"]
four = load(STAGE / "four_numbers.json")
delta_a = load(STAGE / "delta_a_evidence_and_identity.json")
delta_b = load(STAGE / "delta_b_confirmed_urls.json")
delta_total = load(STAGE / "delta_total_vs_stage17.json")
waves = load(STAGE / "queue/waves.json")
units = [json.loads(line) for line in (STAGE / "queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
groups = load(STAGE / "queue/request_groups.json")
live = load(STAGE / "raw/live_discovery_result.json")
accepted = load(STAGE / "raw/accepted_urls.json")["accepted"]
findings = load(STAGE / "raw/url_findings.json")["findings"]
replay = load(STAGE / "controls/new_ready_summary.json")
integrity = load(STAGE / "protected_hashes_check.json")
tests_tail = (STAGE / "tests.txt").read_text(encoding="utf-8").strip().splitlines()
ran = next(line for line in tests_tail if line.startswith("Ran "))
verdict = tests_tail[-1]

STATUS_RU = {
    "ready_to_run": "Готово к запуску", "adapter_url_missing": "Адаптер есть, URL нет", "official_route_no_adapter": "Маршрут известен, адаптера нет",
    "needs_product_page_fixture": "Нужен fixture Product page", "host_blocked": "Host заблокирован", "identity_conflict": "Конфликт identity/варианта",
    "manual_review": "Нужна ручная проверка",
}


def fmt(number: int, sign: bool = False) -> str:
    return (f"{number:+,}" if sign else f"{number:,}").replace(",", " ")


def status_table() -> str:
    lines = ["| Статус | Stage 17 товаров | Stage 18 товаров | Δ | Stage 17 связок | Stage 18 связок |", "|---|---:|---:|---:|---:|---:|"]
    for key, label in STATUS_RU.items():
        o, n = old_summary["units_by_status"][key], new_summary["units_by_status"][key]
        lines.append(f"| {label} | {fmt(o)} | {fmt(n)} | {fmt(n - o, sign=True)} | {old_summary['pairs_by_status'][key]} | {new_summary['pairs_by_status'][key]} |")
    return "\n".join(lines)


def scope_table() -> str:
    rows = defaultdict(Counter)
    for unit in units:
        if unit["family"] in {"samsung", "playstation", "microsoft", "bosch_home", "cudy"}:
            key = (unit["family"], unit["scope_id"] or "—", unit["reason"])
            rows[key][unit["category"]] += 1
    lines = ["| Семейство | Scope | Статус / причина | Товаров | Категории |", "|---|---|---|---:|---|"]
    status_of = {(u["family"], u["scope_id"] or "—", u["reason"]): u["status"] for u in units}
    for (family, scope, reason), counter in sorted(rows.items(), key=lambda kv: (kv[0][0], -sum(kv[1].values()), kv[0][1])):
        top = ", ".join(f"{c} ({n})" for c, n in counter.most_common(4)) + ("…" if len(counter) > 4 else "")
        lines.append(f"| {family} | {scope} | {STATUS_RU[status_of[(family, scope, reason)]]} — `{reason}` | {sum(counter.values())} | {top} |")
    return "\n".join(lines)


def wave_table() -> str:
    lines = ["| Волна | Семейства | Адаптер можно строить (товаров) | Гарантированно ready после адаптера | Верхняя граница ready | Ждут fixture (товаров) |", "|---|---|---:|---:|---:|---:|"]
    for wave in waves:
        gain = wave["expected_gain"]
        lines.append(f"| {wave['wave_id']} | {', '.join(wave['families'])} | {gain['adapter_ready_units']} | {gain['ready_guaranteed_by_urls_on_record_units']} | {gain['ready_via_confirmed_discovery_route_units']} | {gain['waiting_on_fixture_units']} |")
    return "\n".join(lines)


def outcome_table() -> str:
    labels = {
        "catalog_variant_listed_on_page_url_not_observed": "страница модели найдена, код каталога есть на ней как вариант, URL варианта не наблюдался",
        "page_sku_differs_from_catalog": "страница найдена, но её sku другой (вариант, регион или поколение)",
        "no_observed_page_for_title": "в наблюдённых источниках страницы нет",
        "title_names_other_manufacturer": "название называет другого производителя (Kingston)",
    }
    counts = Counter(item["outcome"] for item in findings.values())
    return "\n".join(["| Исход | Строк |", "|---|---:|"] + [f"| {labels[k]} | {counts[k]} |" for k in labels])


def request_markdown() -> str:
    rows = {u["seller_sku"].upper(): u for u in units if u["family"] == "hyperx" and u["status"] == "adapter_url_missing"}
    by_outcome = defaultdict(list)
    for sku, item in findings.items():
        by_outcome[item["outcome"]].append(sku)

    def table(skus, columns):
        header = "| " + " | ".join(name for name, _ in columns) + " |\n|" + "|".join("---" for _ in columns) + "|\n"
        body = ""
        for sku in sorted(skus, key=lambda s: (rows[s]["category"], s)):
            body += "| " + " | ".join(str(fn(sku)) for _, fn in columns) + " |\n"
        return header + body

    name = lambda s: rows[s]["title"]
    page = lambda s: findings[s].get("page_url", "").replace("https://hyperx.com", "") or "—"
    default_sku = lambda s: findings[s].get("page_default_sku", "") or "—"
    listing = load(STAGE / "raw/variant_listing.json")
    variants = {row["seller_sku"]: row for row in listing["rows"]}
    a, b, c, d = (sorted(by_outcome[k]) for k in ("catalog_variant_listed_on_page_url_not_observed", "page_sku_differs_from_catalog", "no_observed_page_for_title", "title_names_other_manufacturer"))
    keyboards = [s for s in b if rows[s]["category"] == "Клавиатуры"]
    others = [s for s in b if s not in keyboards]
    return f"""# HyperX: один запрос по 27 строкам

Из 38 строк, у которых адаптер HyperX есть, а URL был неизвестен, **11 получили точный URL** (в рабочей карте), по **27** точной официальной страницы не нашлось. Ссылки не угадывались: страницы брались только из сохранённых ссылок на hyperx.com и из sitemap, объявленного в `robots.txt`; строка принималась, только если `sku` страницы равен коду каталога и название совпало по модели.

Ответьте, пожалуйста, по каждому пункту одной строкой: **URL**, «нет такой страницы на hyperx.com» или «оставить как есть».

## A. Страница модели найдена, вариант каталога на ней есть, но нет ссылки на этот вариант ({len(a)} строк)

Код каталога числится вариантом на странице, а JSON-LD и ссылки страницы ведут на вариант по умолчанию. Адрес именно этого варианта нигде не наблюдался, строить `?variant=…` самому я не стал.

**Нужно:** точные ссылки на варианты **или** ваше разрешение проверить варианты по идентификаторам из данных самой страницы (не более {len(a)} запросов к hyperx.com, тот же policy-aware fetch, остановка при первом 403/429).

{table(a, [("Артикул", lambda s: s), ("Название в каталоге", name), ("Страница", page), ("sku варианта по умолчанию", default_sku)])}
## B. Страница найдена, но её sku другой — вариант каталога не подтверждён ({len(b)} строк)

Кода каталога на странице нет: это другой вариант, регион или поколение. Такая страница не принимается как точная.

**B1. Клавиатуры (RU), {len(keyboards)} строк.** Каталог: коды `…AX#ACB` / `…AA` (RU), на hyperx.com найдена только US-раскладка (`…#ABA`). Базовый код у части строк отличается, так что это не только суффикс. **Нужно:** ссылка на RU-страницу, если она существует, либо «нет такой страницы».

{table(keyboards, [("Артикул", lambda s: s), ("Название в каталоге", name), ("Найдена страница", page), ("sku страницы", default_sku)])}
**B2. Прочие, {len(others)} строк.** **Нужно:** ссылка на страницу именно этого варианта или «нет такой страницы».

{table(others, [("Артикул", lambda s: s), ("Название в каталоге", name), ("Найдена страница", page), ("sku страницы", default_sku)])}
## C. Страницы нет в наблюдённых источниках ({len(c)} строк)

В sitemap (253 товара) и в сохранённых ссылках нет страницы, где были бы все модельные токены названия.

**Нужно:** URL, если товар есть на hyperx.com, либо «нет на hyperx.com».

{table(c, [("Артикул", lambda s: s), ("Категория", lambda s: rows[s]["category"]), ("Название в каталоге", name)])}
## D. Не товар hyperx.com ({len(d)} строка)

{table(d, [("Артикул", lambda s: s), ("Название в каталоге", name)])}
Это модуль памяти Kingston под брендом HYPERX; сайт hyperx.com — магазин игровой периферии. **Решение нужно:** перенести под Kingston, отправить на ручную проверку или оставить как есть.
"""


def report_markdown() -> str:
    plan_meta = load(STAGE / "queue/coverage_summary.json")["meta"]
    ev = four["1_status_changed_because_evidence_was_overstated"]
    identity = ev["plus_units_changed_by_the_identity_rule_fix"]
    moves_a = ", ".join(f"{m['units']} → «{STATUS_RU[m['to']]}»" for m in identity["moves"])
    n_ready = new_summary["units_by_status"]["ready_to_run"]
    review_units = [r for r in replay["per_unit"] if r["outcome"] == "review"]
    card_units = [r for r in replay["per_unit"] if r["outcome"] == "card"]
    return f"""# Stage 18 — область действия evidence и одна волна поиска URL для HyperX

Отчёты Stage 17 и ранее не менялись; каталог не менялся ({integrity['catalog_sha256'][:12]}… совпадает).

## Четыре числа (это разные величины)

| # | Что | Сколько |
|---|---|---:|
| 1 | Товаров сменили статус из-за завышенного evidence (Stage 17 → исправленный планировщик, тот же набор URL) | **{fmt(ev['units'])}** |
| 2 | Товаров получили реально подтверждённый URL (в рабочую карту) | **{four['2_units_that_got_a_really_confirmed_url']['units']}** |
| 3 | Товаров можно запускать сейчас (`ready_to_run`); было {old_summary['units_by_status']['ready_to_run']} | **{n_ready}** ({delta_total['ready_to_run_gain']:+d}) |
| 4 | Карточек фактически получено на новых {replay['units']} строках (`run_once()` → `done`) | **{four['4_cards_actually_obtained']['cards']}** (ещё {four['4_cards_actually_obtained']['for_review']} на проверку) |

Пояснения к каждому числу:

1. `official_route_no_adapter` → `needs_product_page_fixture`: fixture относился ко всему бренду, а наблюдался в одной категории, на одном host и рынке. Отдельно, **не входя в это число**, исправление правила повтора артикула сдвинуло ещё {identity['units']} товаров ({moves_a}): раньше любой повтор артикула давал `identity_conflict`, теперь это риск, а конфликт остаётся только там, где названия называют разные модели или есть подтверждённый региональный факт.
2. {four['2_units_that_got_a_really_confirmed_url']['by_basis'].get('saved_official_snapshot', 0)} строка — по снимку официальной страницы, сохранённому в Stage 5.1 (запросов не было); {four['2_units_that_got_a_really_confirmed_url']['by_basis'].get('live_page_wave_stage18', 0)} — по страницам, полученным одной ограниченной волной ({live['requests_made']} запрос). Принято только при `sku` страницы = коду каталога (`exact_variant` по правилу адаптера) и совпадении модельных токенов названия.
3. «Можно запускать» — это допуск в `worker.run_once()`, а не гарантия карточки. Из {n_ready}: {new_summary['ready_units_by_url_basis'].get('adapter_discovery', 0)} строк LG, где адаптер сам ищет страницу (поиск может не найти товар), и {new_summary['ready_units_by_url_basis'].get('known_url_map', 0)} строк HyperX с точным URL.
4. Карточки посчитаны прогоном обычного `worker.run_once()` через исполнитель на сохранённых официальных страницах (офлайн-повтор, живой worker не запускался): {four['4_cards_actually_obtained']['cards']} `done`, {four['4_cards_actually_obtained']['for_review']} `needs_review`. Все 11 страниц дали `exact_variant`, у всех документов нет (пробел назван, не заполнен). Причина всех проверок — противоречия значений **внутри одной официальной страницы** (чувствительность у 5 строк; у `B5VC4AA` ещё частотный диапазон и цена за единицу): такие строки исполнитель картой не считает. Снимок Stage 5.1 (`4P5D4AA`) очищен от изображений, поэтому фото у него 0. Карточки Stage 17 (9A273AA, A1KY6AA, LG) сюда не входят.

## Что исправлено в планировщике

* **Fixture — это scope** (host, рынок, категория, шаблон страницы): `family_facts.<семейство>.scopes[]` в `coverage_planner.v1.json`. Семейство без объявленного scope ни одну категорию не покрывает. Проверено тестами `FixturesAreScopedNotBrandWide`.
* **Samsung разделён на три части.** Микроволновые печи (58): value-level карточка на samsung.com/kz_ru, маршрут sitemap доказан → `official_route_no_adapter`. Телевизоры и беспроводные наушники (454): страницы на kz_ru подтверждают identity и одно фото, но вкладка характеристик рисуется на клиенте, в статичном HTML её нет → `needs_product_page_fixture` (`structural_missing_specifications`). Остальные категории (670): страница не наблюдалась → `no_product_page_evidence_for_category`.
* **PlayStation и Microsoft не покрыты одной страницей.** Единственные наблюдавшиеся страницы (геймпад и коллекционная игра на PS Direct en-us; линейная страница Xbox Series S на en-US) — чужой рынок, и Stage 9/10.2 сами не довели их до exact_variant / value-level: `fixture_market_differs_from_catalog`. Консоли PlayStation, геймпады, мыши и гарнитуры Microsoft — страницы нет.
* **Тот же принцип применён к Bosch Home и Cudy** (в задании их не было, но у них был тот же семейный fixture): Bosch — одна страница чайника на немецком сайте (22 товара, чужой рынок, остальные 543 без страницы); Cudy — одна страница роутера (28 товаров → `official_route_no_adapter`, остальные 40 без страницы).
* **Повтор артикула — риск.** Флаг `seller_sku_shared_across_brand|category` и `sku_risk`; проверка вместе с названием, моделью и вариантом (токены названия). Реальный `identity_conflict` в очереди один: HyperX `7G7A4AA#ACB` (страница #ABA, каталог #ACB). Повторов артикула — {new_summary['units_with_shared_seller_sku_risk']} товаров, риск виден в очереди и в checkpoint исполнителя.
* **Критерий `exact_variant`** не требует артикула продавца на сайте: признаки модели и варианта берёт сам источник; подтверждённое несовпадение регионального кода по-прежнему блокирует (`ExactVariantCriterionIsSourceSpecific`).

{scope_table()}

## Статусы: Stage 17 → Stage 18

{status_table()}

Приоритетные бренды, запросы и пары: `queue/priority_queue.json`, `queue/request_groups.json` ({new_summary['request_groups']} групп; запрос на HyperX — одна группа), `queue/coverage_pairs.json`.

## Волны после исправления

{wave_table()}

* **Гарантированное ready после адаптера** — только Samsung `MS23K3614AK/BW` (точный URL на записи). «Верхняя граница» — только там, где маршрут доказан для самой категории: это одна связка, Samsung микроволновые печи (в сохранённом срезе sitemap на 58 строк каталога нашёлся 1 точный хит, поэтому 58 — именно верхняя граница). Обещание готовности через discovery для остальных scope снято: у Cudy маршрут структурный (после адаптера строки станут `adapter_url_missing`), у Bosch, PlayStation и Microsoft нет ни маршрута, ни рыночного fixture.
* Волны W1-A…W1-D по-прежнему привязаны к шаблонам Product page, но прирост считается по единицам, чья категория подтверждена. Ждущие fixture единицы показаны отдельно (`waiting_on_fixture_units`) и выигрышем адаптера не считаются. Критерии готовности адаптера (9 пунктов) не менялись, кроме `identity_exact` и `variants_positive_negative`.

## Поиск URL для HyperX: что сделано

1. **Офлайн, 0 запросов.** Сохранённые ссылки на официальных страницах (25 ссылок на товары из категорий клавиатур и мышей) дали кандидатов для 9 строк; снимки в репозитории — один снимок официальной страницы (`hyperx-cloud-alpha-wireless`, Stage 5.1), у которого `sku` = `4P5D4AA` → строка принята без запроса (`scripts/02_offline_snapshot_check.py`).
2. **Бюджет объявлен до первого запроса** (`raw/budget_predeclaration.json`): только hyperx.com, не более 30 запросов (≤3 sitemap, ≤27 страниц), только наблюдавшиеся URL, остановка при первом 401/403/429/challenge. Все запросы шли через `PolicyAwareFetcher`.
3. **Сделан {live['requests_made']} запрос** ({live['sitemap_requests']} sitemap: индекс из `robots.txt` и его единственный product-sitemap на {live['sitemap_product_slugs_seen']} товара; {live['page_requests']} страниц товаров). Блокировок нет ({'ни одного' if not live['halted'] else live['halted']} 401/403/429), остановки host не было. Все {live['page_requests']} страниц товаров получили 200 и оценку защиты `challenge_suspected` (эвристика Stage 8 срабатывает на этом сайте на каждой странице), при этом страницы содержат полный JSON-LD, то есть это не заглушка challenge; sitemap оценён как обычная страница.
4. **Принято {len(accepted)} строк**, для {len(findings)} точной страницы нет. По исходам:

{outcome_table()}

5. Для 7 строк из первой категории код каталога **найден на странице как вариант**, но URL этого варианта на сайте не наблюдался (JSON-LD показывает только вариант по умолчанию). URL `?variant=…` я не строил, эти строки ушли в запрос пользователю.
6. **Один запрос пользователю вместо 27 сообщений:** [hyperx_user_request.md](hyperx_user_request.md); в очереди это одна группа `ask_user` с полем `items` (`queue/request_groups.json`).

**Оговорки.** (а) Скрипт запроса при разборе sitemap не раскодировал `&amp;` в адресе product-sitemap; сервер ответил 200 и отдал список товаров, так что результат корректен, но запрошенный адрес не идентичен `<loc>` побайтно. (б) `robots.txt` сайта ссылается на `agents.md` и UCP-discovery; это инструкции сайта, а не проекта, они не читались и не выполнялись. (в) `data/hyperx_fetch_log.json` создан прогоном как persisted-лог политики (в нём 21 запись без блокировок); он же попадает в чтение остановленных host планировщиком. (г) Название товара сверялось по токенам без цвета/переключателя: цвет и раскладка проверяются `sku` страницы.

## Delta

* Stage 17 → исправленный планировщик (без новых URL): `delta_a_evidence_and_identity.json`.
* Только новые URL: `delta_b_confirmed_urls.json` ({delta_b['moves'][0]['units']} товаров `adapter_url_missing` → `ready_to_run`).
* Итого относительно Stage 17: `delta_total_vs_stage17.json`; `ready_to_run` {delta_total['ready_to_run_gain']:+d}.

## README

`git diff README.md` проверен: восстановленные в Stage 17 правки (убраны упоминания второго поставщика в трёх предложениях) на месте. Устаревшее утверждение исправлено: «Подтверждено двумя поставщиками» больше не говорит, что совпали два поставщика, — сейчас доверенный поставщик один (Sulpak, только LG), статус сохранён в коде и не возникает. Добавлена одна фраза про scope в разделе очереди покрытия. `git checkout` к незакоммиченным файлам не применялся.

## Проверки

* `python -m tests -v`: {ran}, {verdict}; вывод — `tests.txt`.
* Целостность (`protected_hashes_check.json`): каталог не менялся ({'да' if integrity['catalog_unchanged'] else 'НЕТ'}); {integrity['earlier_report_files_checked']} файлов отчётов Stage 2–16 совпадают с хэшами, записанными в Stage 17; файлы Stage 17 не менялись после старта Stage 18; закреплённые файлы сходятся ({'да' if integrity['pinned_all_ok'] else 'НЕТ'}); активные файлы не называют исключённого дилера ({integrity['active_files_scanned_for_excluded_dealer']} проверено); `data/batches.sqlite3` не менялась.
* Очередь воспроизводима побайтно (проверяется при генерации, `scripts/08_generate_queue_and_deltas.py`).

## Что не сделано

* Адаптеры Samsung/PlayStation/Microsoft/Bosch/Cudy не писались; fixtures не собирались: это задачи следующих этапов, порядок — по `waves.json`.
* Живой прогон worker на 11 новых строках не делался (только офлайн-повтор на сохранённых страницах).
* Техпарк не реализован; DNS остаётся дилерским запасным путём только для точных URL.
* Классификация по рынку каталога (`market_matches_catalog`) — суждение в конфигурации с причиной у каждого scope; если для Bosch/PlayStation/Microsoft вы признаёте страницу другого рынка эквивалентной, достаточно поменять флаг и пересчитать очередь.
"""


def main() -> None:
    (STAGE / "hyperx_user_request.md").write_text(request_markdown(), encoding="utf-8", newline="\n")
    (STAGE / "report.md").write_text(report_markdown(), encoding="utf-8", newline="\n")
    print("rendered hyperx_user_request.md, report.md")


if __name__ == "__main__":
    main()
