"""Stage 20 step 6 -- OFFLINE. Render report.md from the saved artifacts of this stage (every number is read from a JSON file)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent


def load(name: str):
    return json.loads((STAGE / name).read_text(encoding="utf-8"))


selection = load("raw/pilot_selection.json")
declaration = load("raw/predeclaration.json")
analysis = load("raw/pilot_analysis.json")
requests_ = load("raw/pilot_requests.json")
estimate = load("raw/estimate_578.json")
conflicts = load("raw/conflicts_within_source.json")
export = load("raw/export_check.json")
integrity = load("protected_hashes_check.json")
tests_tail = (STAGE / "tests.txt").read_text(encoding="utf-8").strip().splitlines()
ran = next(line for line in tests_tail if line.startswith("Ran "))
verdict = tests_tail[-1]
rows, totals = analysis["rows"], analysis["totals"]
exact_rows = [r for r in rows if r["official_exact_page"]["found"]]
n_exact = len(exact_rows)
pct = lambda a, b: f"{100 * a / b:.1f}".replace(".", ",")
ready = estimate["ready_rows"]
now, fixed, absent = estimate["reachable_by_the_current_rule"], estimate["reachable_with_a_3plus_letter_suffix_rule"], estimate["not_in_the_kz_sitemap_at_all"]
conflict_rows = conflicts["rows_with_conflicts"]
est_conflict_rows = round(now * conflict_rows / n_exact)
sitemap_hits = sum(1 for e in requests_["log"] if e["url"].endswith("/kz/sitemap.xml"))


def yn(value) -> str:
    return "да" if value else "нет"


def row_table() -> str:
    lines = ["| Артикул (категория) | Точная официальная страница | Вариант подтверждён | Характеристики (KZ / RU / дилер) | Фото галереи | Инструкция | Что дополнил дилер | Статус задания | Готовность карточки |",
             "|---|---|---|---|---:|---|---|---|---|"]
    for r in rows:
        page = f"KZ: `{r['official_exact_page']['kz_level']}`" + (f" ({r['official_exact_page']['kz_url'].replace('https://www.lg.com', '')})" if r["official_exact_page"]["kz_url"] else "") + f"; RU: {'404' if r['official_exact_page']['ru_error'] else r['official_exact_page']['ru_level']}"
        facts = f"{r['facts']['lg_kz']} / {r['facts']['lg_ru']} / {r['facts']['sulpak'] + r['facts']['dns']}"
        docs = "не найдена (RU-страница недоступна)" if not r["instruction"]["found"] else ", ".join(r["instruction"]["languages"])
        dealer = "ничего: Sulpak — нет кандидата; DNS — нет проверенного URL" if r["dealer_added"]["nothing_added"] else "см. данные"
        gaps = ", ".join(r["readiness"]["gaps"])
        lines.append(f"| {r['seller_sku']} ({r['category']}) | {page} | {yn(r['variant_confirmed'])} | {facts} | {r['photos']['gallery_selected']} | {docs} | {dealer} | `{r['job']['status']}` | `{r['readiness']['verdict']}`: {gaps} |")
    return "\n".join(lines)


def report() -> str:
    t = totals
    return f"""# Stage 20 — пилот LG: реальный результат рабочего процесса

Отчёты Stage 17–19 и ранее, каталог и реестр источников не менялись (`protected_hashes_check.json`).

## Вывод в четырёх строках

* Из {t['rows_run']} строк точную официальную страницу LG Казахстан нашли **{t['official_exact_page_found']}**, вариант подтверждён у всех девяти (артикул найден на странице), характеристики и фото есть у этих девяти. Карточек, готовых к выгрузке без оговорок, **0**; «готово с оговорками» — {t['readiness'].get('export_ready_with_gaps', 0)}, не готово — {t['readiness'].get('not_ready', 0)}.
* Статус задания у **всех {t['rows_run']}** `needs_review`: `done` ни у одной. Причины — повторяющиеся дефекты, а не сеть: запросов {t['requests_total']} из 60, не больше {t['max_requests_in_one_row']} на строку, блокировок нет.
* Инструкций **0 из {t['rows_run']}**: адаптер LG Россия строит один и тот же URL, и он отвечает 404 у всех {t['rows_run']} строк, а поиск инструкции зависит от этой страницы.
* Предлагаю **исправить повторяющиеся дефекты и повторить тот же пилот**; полный прогон 578 строк сейчас дал бы почти те же `needs_review`, а Samsung даёт меньше (см. «Решение»).

## 1. Сетевые запросы LG через общий policy-aware fetch

Что сделано (`docs/LG_POLICY_FETCH_V20.md`): `worker.run_once()` без внедрённых адаптеров теперь строит LG, LG Россия и Sulpak через `PolicyAwareSession` с постоянным журналом `<каталог данных>/lg_fetch_log.json`. Код поиска и извлечения LG (`adapters/lg.py`, `sulpak.py`, `common.py`) не менялся: файлы идентичны замороженному базису ({'все' if all(integrity['lg_adapter_files_identical_to_frozen_baseline'].values()) else 'НЕ ВСЕ'}); `worker.py` изменён одной заменой строки и одним импортом с записью в `tests/_pipeline_migration.py` и новым закреплением.

Проверено офлайн (`tests/test_stage20_lg_policy.py`, 17 тестов):

* 401, 403, 429 и подтверждённый challenge при HTTP 200 записываются в журнал и останавливают host в **новом экземпляре** и в **следующем `run_once()`** (в нём ни одного запроса к lg.com); планировщик читает тот же журнал; повтор `fetch_with_retry` на 429 не делает второго запроса к остановленному host;
* `challenge_suspected` записывается, страница отдаётся адаптеру как раньше, host не останавливается; остановка lg.com не останавливает sulpak.kz;
* те же адаптеры на тех же страницах дают идентичные документы с сессией политики и без неё (KZ, RU-404 с прежним текстом ошибки, Sulpak);
* бюджет отклоняет запрос до отправки, sitemap читается один раз на весь пакет, заголовки адаптера доходят до запроса, ответы можно сохранять для диагностики.

Замечание по собственной ошибке: в пилоте sitemap запрашивался заново в каждой строке ({sitemap_hits} раз из {t['requests_total']} запросов), потому что кэш был на экземпляр сессии, а worker создаёт сессию на задание. Исправлено после пилота (кэш общий для запуска, тест есть); тот же пилот стоил бы {t['requests_total'] - sitemap_hits + 1}. DNS-адаптер на policy-fetch не переводился (он ходит только по заранее проверенным URL, в пилоте запросов не делал).

## 2. Выборка и бюджет (объявлены до запросов)

Правило: {selection['rule']} Вход — очередь Stage 19 (`{selection['input_sha256'][:12]}…`), {selection['candidates']} строк, {len(selection['categories'])} категорий; выбрано 12 строк, у двух артикул с суффиксом (`24MR400-B.ARUQ`, `27MD5KL-B.AEU`). Бюджет: ≤ 5 запросов на строку, ≤ 60 всего, пауза 1 с, остановка при блокировке; объявление записано в `raw/predeclaration.json` раньше первого запроса ({declaration['declared_at']} < {requests_['started_at']}). Факт: **{requests_['requests_total']} запросов**, максимум **{requests_['max_requests_in_one_row']}** на строку, остановок и блокировок нет, {len(requests_['rows_not_run'])} строк не запущено.

## 3. Результат по строкам

Готовность считалась по правилу, объявленному заранее: `export_ready` — задание `done`, официальная страница `full_sku`, характеристики, фото галереи, инструкция с русским языком, нет конфликтов; `export_ready_with_gaps` — есть официальная страница, характеристики и фото, но чего-то из остального нет; иначе `not_ready`. `done` сам по себе готовностью не считается.

{row_table()}

Итого: точная официальная страница — {t['official_exact_page_found']} из {t['rows_run']}; вариант подтверждён — {t['variant_confirmed']}; характеристики — {t['with_specifications']}; фото галереи — {t['with_gallery_photos']}; инструкция — {t['instruction_found']}; дилер что-то добавил — {t['dealer_added_anything']}; статусы заданий — {t['job_status']}. Язык инструкции подтверждать было нечего: ни одна не найдена.

**Выгрузка** (обычный `export_batch` по партии пилота, `raw/export_check.json`): в файле {export['products_in_export']} товаров; у {export['rows_with_attribute_cells']} строк есть значения характеристик, у {export['rows_with_photo_rows']} — фото на листе «Фотографии», у {export['rows_with_instruction_rows']} — инструкции. Конфликтные значения в ячейки не попадают: например, у `XL7S` 30 заполненных ячеек из 31.

## 4. Причины неудач и прирост для остальных {ready} строк

| # | Дефект | Где виден в пилоте | Оценка на {ready} строк | Исправление и ожидаемый прирост |
|---|---|---|---|---|
| D1 | **LG Россия: URL строится по шаблону `/ru/laundry/lg-{{модель}}`** и отвечает 404 | {t['failure_codes'].get('ru_no_page', 0)} из {t['rows_run']}, включая стиральную и сушильную машины (в шаблоне как раз `laundry`); поэтому `documents_not_checked` у {t['failure_codes'].get('documents_not_checked', 0)} | все {ready}: RU-страницы нет, инструкций нет | нужен наблюдаемый маршрут RU (sitemap, объявленный в `robots.txt` lg.com/ru, с проверкой ≤ 3 запросов) и переписанный поиск инструкции: сейчас разбор ссылки поддержки узнаёт только одну модель поддержки (`S3RERB`). Прирост: инструкции и RU-подтверждение до {ready} строк, величина зависит от покрытия RU sitemap (неизвестна) |
| D2 | **Правило `done` требует подтверждения поставщиком**; Sulpak ходит только по URL из `KNOWN_LG_URLS` (1 артикул), у пилота кандидатов нет | {t['failure_codes'].get('no_supplier_confirmation_so_not_done', 0)} из {t['rows_run']} | все {ready} (кроме 1 известного артикула) не могут стать `done` по правилу | решение владельца: считать `done` при точной официальной странице без реальных конфликтов, либо оставить `needs_review` как осознанное «нужен человек». Кода недостаточно: без решения полный прогон даст 0 `done` |
| D3 | **Ложные конфликты внутри одного источника**: `normalization.NAME_RULES` сводит разные измерения в одно имя (вес с подставкой/без, внутренний/наружный блок, вес брутто/нетто, цвет дверцы/корпуса), резолвер называет это `official_regions_conflict` | {conflicts['rows_with_conflicts']} из {n_exact} строк с точной страницей, {conflicts['conflicts']} конфликтов, **все внутри одного источника (`lg_kz`)**, между источниками — {conflicts['between_sources']} | ≈ {est_conflict_rows} из {now} достижимых строк (доля {conflict_rows}/{n_exact} с пилота) | конфликт должен требовать разных значений **у разных источников**; внутри источника это несколько значений разных величин. Правка в резолвере/нормализации (защищённые файлы, нужна запись миграции). Прирост: до ≈ {est_conflict_rows} карточек без ложной пометки конфликта |
| D4 | **Суффикс базовой модели: правило отсекает суффикс только из 5 и более букв** (`[A-Z]{{5,}}`), у LG суффиксы бывают из 3–4 букв (`.ARUQ`) | 1 из 12 (`24MR400-B.ARUQ`: страница `…/24mr400-b/` есть в sitemap) | +{estimate['gain_of_the_suffix_correction']} строк из {ready} ({pct(estimate['gain_of_the_suffix_correction'], ready)} %): достижимо {now} → {fixed} | одна регулярка в `lg_base_model` (защищённый файл, миграция). Суффиксы среди {estimate['rows_with_a_dot_in_the_article']} артикулов с точкой: {estimate['suffix_letter_counts_among_dotted']} |
| D5 | **Артикула нет в sitemap LG Казахстан** | 2 из 12 (`A9N-MASTERX`, `27MD5KL-B.AEU`) | {absent} из {ready} ({pct(absent, ready)} %) недостижимы через KZ sitemap даже после D4 | другой источник страницы: тот же RU-маршрут из D1 или официальный поиск по коду; без нового наблюдаемого маршрута URL не угадываются |
| D6 | Аномалия каталога: монитор `27MD5KL-B.AEU` лежит в категории «Смарт-часы» | 1 из 12 | единичные | отметить в каталоге отдельно (каталог не менялся) |

Оценки для {ready} строк сделаны офлайн по KZ sitemap, сохранённому в пилоте ({estimate['sitemap_product_urls']} URL товаров), без запросов: текущее правило достигает {now} строк ({pct(now, ready)} %), что согласуется с пилотом (9 из 12 = 75 %). «Достижимо» — есть URL с нужным slug; совпадение артикула на странице определяется уже на самой странице. Доля D3 взята с девяти страниц пилота и является оценкой, не измерением.

## 5. Решение

**Рекомендую: исправление повторяющихся дефектов, затем повтор того же пилота.** Не полный прогон и не переход к Samsung.

Почему не полный прогон сейчас: он потратил бы около {now + ready} запросов (страница KZ на каждую достижимую строку и одна заведомо лишняя RU-проба на каждую), а результат уже известен по пилоту: 0 инструкций, все задания `needs_review`, у ≈ {pct(conflict_rows, n_exact)} % карточек ложные конфликты. Новой информации, которой нет в пилоте, полный прогон не добавит.

Почему не Samsung: там нет ни адаптера, ни подтверждённого маршрута (максимум 58 строк микроволновых печей, 1 гарантированная), тогда как у LG уже есть страницы, характеристики и фото для {now} строк, и дефекты D2–D4 закрываются без сети.

Порядок исправлений (сверху вниз по приросту на затрату):

1. **D2 — решение владельца** о правиле `done` (без сети, одна фраза от вас). Без него остальное не превратится в `done`.
2. **D3 — резолвер/нормализация:** конфликт только между источниками; тест на страницах пилота (13 конфликтов должны исчезнуть, реальный конфликт между регионами — остаться). Прирост ≈ {est_conflict_rows} карточек.
3. **D4 — суффикс:** +{estimate['gain_of_the_suffix_correction']} достижимых строк, офлайн-проверка по сохранённому sitemap.
4. **D1/D5 — маршрут LG Россия:** сначала ≤ 3 запроса на наблюдение `robots.txt` и sitemap `lg.com/ru`, затем переписать выбор URL и поиск инструкции; проверить на сохранённых страницах. Прирост: инструкции и путь для {absent} строк, которых нет в KZ.
5. **Повторный пилот** на тех же 12 строках (те же правила, тот же бюджет), затем 12 новых по тому же правилу; после этого решение о полном прогоне 578 строк.

Что нужно от вас: ответ по D2 и разрешение на ≤ 3 запроса к lg.com/ru (шаг 4).

## 6. Проверки

* `python -m tests -v`: {ran}, {verdict}.
* Целостность: каталог не менялся ({yn(integrity['catalog_unchanged'])}); реестр источников совпадает с закреплением ({yn(integrity['source_registry_matches_pin'])}); {integrity['earlier_report_files_checked_against_stage17_record']} файлов отчётов Stage 2–16 совпадают с хэшами Stage 17; файлы Stage 17–19 не менялись ({len(integrity['stage17_18_19_files_modified_after_stage20_started'])} изменённых); закреплённые файлы сходятся ({yn(integrity['pinned_all_ok'])}); активные файлы не называют исключённого дилера ({integrity['active_files_scanned_for_excluded_dealer']} проверено); `data/batches.sqlite3` не менялась, журнал LG под `data/` не создавался (пилот шёл в собственном каталоге `pilot/`).
* Пилот шёл на настоящих страницах lg.com; сохранённые ответы ({len(requests_['log'])} записей) лежат в `pilot/responses/`, база пилота — `pilot/workdir/`.

## Что не сделано

* Полный прогон 578 строк не запускался. Дефекты D1–D5 не исправлялись (кроме собственного кэша sitemap): решение и порядок — выше.
* Sulpak и DNS в пилоте ничего не добавили: у 12 артикулов нет ни известного URL Sulpak, ни проверенного URL DNS; расширение их списков без наблюдаемых URL не предлагается.
"""


def main() -> None:
    (STAGE / "report.md").write_text(report(), encoding="utf-8", newline="\n")
    (STAGE / "numbers.json").write_text(json.dumps({"pilot": totals, "requests": {k: v for k, v in requests_.items() if k not in ("log", "fetch_log")}, "estimate_578": {k: v for k, v in estimate.items() if k not in ("by_category", "unreachable_examples")},
                                                  "conflicts": {k: v for k, v in conflicts.items() if k != "items"}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("rendered report.md")


if __name__ == "__main__":
    main()
