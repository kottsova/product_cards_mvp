"""Stage 21 step 6 -- OFFLINE. Builds raw/comparison.json, numbers.json and report.md from the saved raw files.

The tables are computed from raw/*.json; nothing is typed by hand except the prose around them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE20 = ROOT / "reports/source_census_2026-09-24_stage20"
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    old = {r["seller_sku"]: r for r in load(STAGE20 / "raw/pilot_analysis.json")["rows"]}
    phase1 = {r["seller_sku"]: r for r in load(STAGE / "raw/replay_phase1.json")["rows"]}
    phase2 = load(STAGE / "raw/replay_phase2.json")
    new = {r["seller_sku"]: r for r in phase2["rows"]}
    estimate = load(STAGE / "raw/estimate_578_stage21.json")
    verify, probe1, probe2 = load(STAGE / "raw/verify_result.json"), load(STAGE / "raw/probe_result.json"), load(STAGE / "raw/probe_result_2.json")

    rows = []
    for sku, o in old.items():
        n = new[sku]
        ks, rs = n["sources"].get("lg_kz", {}), n["sources"].get("lg_ru", {})
        rows.append({
            "seller_sku": sku, "category": o["category"],
            "stage20": {"job": o["job"]["status"], "readiness": o["readiness"]["verdict"], "conflicts": o["resolved"]["conflicts"], "facts_kz_ru": [o["facts"]["lg_kz"], o["facts"]["lg_ru"]]},
            "stage21_phase1_no_ru_pages": {"job": phase1[sku]["job_status"], "conflicts": len(phase1[sku]["real_conflicts"])},
            "stage21": {"job": n["job_status"], "readiness": n["readiness"]["verdict"], "conflicts": len(n["real_conflicts"]), "gaps": n["readiness"]["gaps"], "kz": [ks.get("match_level"), ks.get("facts")], "ru": [rs.get("match_level"), rs.get("facts")],
                        "conflict_detail": n["real_conflicts"]},
        })
    count = lambda key, fn: sum(1 for r in rows if fn(r[key]))  # noqa: E731
    numbers = {
        "rows": len(rows),
        "stage20_done": count("stage20", lambda x: x["job"] == "done"), "stage21_done": count("stage21", lambda x: x["job"] == "done"),
        "stage21_phase1_done": count("stage21_phase1_no_ru_pages", lambda x: x["job"] == "done"),
        "stage20_conflicts": sum(r["stage20"]["conflicts"] for r in rows), "stage21_conflicts": sum(r["stage21"]["conflicts"] for r in rows),
        "stage21_readiness": {v: count("stage21", lambda x, v=v: x["readiness"] == v) for v in ("export_ready", "export_ready_with_gaps", "not_ready")},
        "stage21_done_but_not_ready": sum(1 for r in rows if r["stage21"]["job"] == "done" and r["stage21"]["readiness"] == "not_ready"),
        "requests": {"probe": probe1["requests_made"] + probe2["requests_made"], "probe_budget": 3, "verify": verify["requests_made"], "verify_budget": 14, "replay": 0},
        "estimate_578": {k: estimate[k] for k in ("reachable_kz", "reachable_ru", "reachable_either", "reachable_both", "reachable_neither", "ru_only_gain_over_kz")},
    }
    (STAGE / "raw/comparison.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (STAGE / "numbers.json").write_text(json.dumps(numbers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def gaps(r):
        return ", ".join(g for g in r["stage21"]["gaps"] if g not in ("instruction_missing", "dealer_cross_check_missing")) or "—"

    table = ["| Строка | Этап 20: задание | Этап 20: конфликтов | Этап 21: задание | Готовность карточки | Настоящих конфликтов | KZ / RU (страница, фактов) | Пробелы кроме инструкции и дилера |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s = r["stage21"]
        table.append(f"| {r['seller_sku']} | {r['stage20']['job']} | {r['stage20']['conflicts']} | **{s['job']}** | {s['readiness']} | {s['conflicts']} | {s['kz'][0]}/{s['kz'][1]} · {s['ru'][0]}/{s['ru'][1]} | {gaps(r)} |")
    left = []
    for r in rows:
        for c in r["stage21"]["conflict_detail"]:
            left.append(f"| {r['seller_sku']} | {c['raw_names'][0]} | {' / '.join(c['values'])} |")
    n = numbers
    text = f"""# Этап 21: D2/D3/D4, маршрут LG Россия, повтор 12 строк

Всё ниже посчитано из `raw/*.json` скриптом `scripts/06_render_report.py`. Полный прогон 578 строк не запускался.

## Итог
- Строки, доведённые до `done`: {n['stage20_done']} → {n['stage21_done']} из {n['rows']} (с исправлениями D2/D3, но ещё без страниц LG Россия, было {n['stage21_phase1_done']}: когда страница RU появилась, 4 строки — MS2032GAS, SN4, DC90V5V9S, 50UT91006LA — ушли обратно на проверку из-за настоящих расхождений RU и KZ, а A9N-MASTERX стала `done` благодаря точной странице RU; это не улучшение «в целом», а честный эффект второго источника). Настоящих конфликтов: {n['stage20_conflicts']} → {n['stage21_conflicts']}.
- Готовность карточки: {n['stage21_readiness']}. Строк со статусом `done`, но `not_ready`: {n['stage21_done_but_not_ready']} (A9N-MASTERX: нет фото галереи LG Россия) — статус и готовность разведены, как требовал D2.
- Русская инструкция не найдена ни у одной строки, потому что маршрут документов не установлен, а не потому что инструкций нет (см. «D1/D5»).

## Запросы
- Проба маршрута LG Россия: {n['requests']['probe']} из {n['requests']['probe_budget']} (`ru/index.xml`, `ru/sitemap.xml`, страница XL7S). Бюджет объявлен до запроса (`raw/probe_declaration.json`).
- Поправка после R1 (`raw/probe_amendment.json`): объявленное правило шага 2 ('pdp'/'product' в имени дочерней карты) не подходило ни к одной из четырёх дочерних карт и по своему тексту означало «стоп». Я заменил его на `ru/sitemap.xml` — аналог `kz/sitemap.xml`, который адаптер уже читает, — и записал поправку до запроса, но после R1. Это отступление от объявленного правила.
- Проверка нового маршрута для повтора: {n['requests']['verify']} из {n['requests']['verify_budget']} (11 страниц из тех же карт, 1 страница документов и 1 переход по ссылке со страницы документов). Переход оказался бесполезным (ссылка на опрос) — правило выбора ссылки было слишком широким, один запрос потрачен зря.
- Повтор 12 строк: 0 запросов (сохранённые ответы; любой незаписанный адрес отклонялся).
- Блокировок нет: 401/403/429 и подтверждённых проверок не было; журнал `data/lg_fetch_log.json` без остановленных хостов.

## По строкам
{chr(10).join(table)}

«Пробелы кроме инструкции и дилера» — у всех строк дополнительно `instruction_missing` (маршрут документов не установлен) и `dealer_cross_check_missing` (дилер не запрашивался, не блокирует).

## Что осталось на проверке (настоящие расхождения)
| Строка | Поле | Значения |
|---|---|---|
{chr(10).join(left)}

Все они — разные значения (другой цвет, другая глубина, другая формулировка комплектации), а не форматирование; формат («23.8» и «23.8"», «1шт» и «1 шт.», «менее/меньше», «(r/l)/(п/л)») сравнение теперь прощает, значение — нет. Исключение, оставленное на проверке сознательно: SN4 `USB` — «1» против «true» (число портов против наличия), совместимо, но не одинаково записано; автоматически не сливаю.
Строки 24MR400-B.ARUQ и 27MD5KL-B.AEU остались на проверке не из-за конфликтов, а потому что полного артикула нет ни на одной странице: у 24MR400-B.ARUQ на KZ и RU найдена только базовая модель, у 27MD5KL-B.AEU KZ страницы не даёт, RU — только базовая модель (D4: базовый код не повышается до точного варианта).

## D4
Правило: суффикс региона из 3+ заглавных букв отбрасывается при поиске страницы базовой модели; совпадение по базовому коду остаётся `base_model` и не становится `full_sku` без полного артикула на странице. По сохранённой карте KZ достижимость 578 строк выросла с 426 до {n['estimate_578']['reachable_kz']}. Суффиксы, различающие варианты (часть после точки не из 3+ букв), базовым кодом не считаются — тесты есть.

## D1/D5: маршрут LG Россия
- Страницы: маршрут существует. `lg.com/sitemap.xml` (снимок этапа 7) → `ru/index.xml` (индекс) → `ru/sitemap.xml` (карта страниц). Из 12 строк пилота карта даёт страницу для 11, включая две строки, которых нет в карте KZ (A9N-MASTERX, 27MD5KL-B). Адреса берутся только из карты; шаблон не строится.
- Оценка по 578 строкам (по сохранённым картам, без запросов; это верхняя граница, полный артикул проверяется на странице): KZ {n['estimate_578']['reachable_kz']}, RU {n['estimate_578']['reachable_ru']}, хотя бы одна площадка {n['estimate_578']['reachable_either']}, обе {n['estimate_578']['reachable_both']}, RU добавляет к KZ {n['estimate_578']['ru_only_gain_over_kz']}, ни там ни там {n['estimate_578']['reachable_neither']}.
- Документы: маршрут НЕ установлен. `/ru/support/manuals` — страница с выбором, руководства подгружаются скриптом (в статическом HTML нет ссылок на файлы). Точный остаток: 1 запрос к `/lg5-common-gp/js/common-support.min.js` (узнать адрес ajax `manual-select-category-result` и его параметры), затем по 1 запросу на товар. Пока это не сделано, отсутствие инструкций не доказано ни для одной из 578 строк.
- Фото LG Россия: экстрактор отбрасывает всё, чего нет в `/stylers/`, а на всех 11 сохранённых страницах галерея лежит в `/ru/images/<категория>/<md…>/gallery/`, так что фото RU не извлекаются вовсе. Исправление затрагивает выбор фото (размерные дубли, заглушка `obj-base.png`), поэтому в этом этапе не делалось; записано как пробел.

## Рекомендация
Полный прогон LG пока не обоснован. Нужен второй пилот, небольшой (порядка 20–25 строк: те же 12 плюс строки с разными категориями и суффиксами, включая ≥5 строк, которых нет в KZ), после двух ограниченных шагов:
1. документы: 1 запрос за скриптом + запрос на 1–2 товара, чтобы установить, есть ли русская инструкция и в каком виде;
2. фото RU: исправить фильтр и правило дедупликации по размерам с тестом на сохранённых страницах.
Остальное готово: статус `done` и готовность разведены, ложных конфликтов на сохранённых страницах нет, страницы RU достижимы. Оставшиеся расхождения между площадками остаются на проверке человеком — это ожидаемая доля, а не дефект.
"""
    (STAGE / "report.md").write_text(text, encoding="utf-8")
    print(json.dumps(numbers, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    with offline_only():
        main()
