"""Stage 23 step 1 -- OFFLINE, zero requests. The LG results gathered so far, one verified card per category, the effect of the owner's four answers on the
saved evidence, and the proposal for the next brand.

Nothing is fetched and no LG row is (re)processed: every number is read from files that earlier stages saved.
Output: raw/category_table.json, raw/owner_rules_evidence.json, report.md
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S22 = ROOT / "reports/source_census_2026-09-24_stage22"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.lg_documents import assess_document  # noqa: E402
from product_tool.adapters.lg_documents_adapter import support_page_ties_article  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# What each category's card taught, in words; the numbers next to it come from the saved rows.
LESSONS = {
    "XL7S": ("D3: «Вес брутто» и «Вес нетто» получали одно имя (ложный конфликт); маршрут инструкций через страницу поддержки", "дилерская сверка (не запрашивалась)"),
    "MS2032GAS": ("D3: цвет дверцы/корпуса/внутри и габариты полости/поворотного стола; язык инструкции по тексту файла, не по метке", "русской инструкции нет (файл с меткой «Русский» на казахском); 2 расхождения KZ/RU"),
    "24MR400-B.ARUQ": ("D4: поиск по базовой модели без повышения до точного варианта", "полный артикул нигде на странице не показан (обе площадки base_model)"),
    "CK43": ("D3: размеры сабвуфера/основного модуля/колонок в одном имени", "страницы LG Россия нет в карте сайта; инструкции не проверялись"),
    "A9N-MASTERX": ("маршрут страниц LG Россия по карте сайта; фильтр фото RU (0 → 15); решение 4 по инструкции", "страницы LG Казахстан нет в карте сайта"),
    "SN4": ("сравнение по канонической форме («1шт»/«1 шт.», «3,840»/«3840»); имена «Главный»/«Сабвуфер» получали разные величины", "расхождение USB: «1» против «true»"),
    "27MD5KL-B.AEU": ("D4 и фото RU при base_model; в каталоге монитор лежит в категории «Смарт-часы»", "полный артикул не подтверждён; инструкция — архив, не PDF"),
    "AC09BK": ("D3: внутренний и наружный блок; лимит 25 МБ на файл", "инструкция: файл крупнее лимита / архив — не подтверждена"),
    "F2J3WS1W": ("D3: «Макс. вес белья» и «Масса», ящик и продукт; маска семейства `F2J3WS**` как подтверждение модели в документе", "—"),
    "DC90V5V9S": ("D3: «Макс. вес белья для сушки» и «Масса»; цвет частей", "2 расхождения KZ/RU (цвет корпуса, глубина 660/690)"),
    "50UT91006LA": ("D3: телевизор с подставкой и без; решение 4 по инструкции (общая краткая инструкция)", "расхождение KZ/RU: Magic Remote «в комплекте»/«встроенный»"),
    "GC-B509SEUM": ("чистый проход; решение 4 по инструкции", "страница LG Россия бедная: 6 характеристик"),
}


def main() -> None:
    comparison = load(S22 / "raw/pilot2_comparison.json")
    first = [r for r in comparison if r["group"] == "first_pilot"]
    assert len(first) == 12 and len({r["category"] for r in first}) == 12
    # ---- rule 4 on the saved evidence: the four Russian instructions whose text names no model -------------------------------
    replay = {r["seller_sku"]: r for r in load(S22 / "raw/pilot2_replay_rows.json")["rows"]}
    extract = {r["url"]: r for r in load(S22 / "pilot2/docs_extract/index.json") if r.get("text_file")}
    support_pages = {}
    responses = S22 / "pilot2/responses"
    for line in (responses / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if "/support/product/" in entry["url"] and entry["saved_as"]:
            with gzip.open(responses / entry["saved_as"], "rt", encoding="utf-8") as handle:
                support_pages[entry["url"]] = handle.read()
    evidence, comp = [], {r["seller_sku"]: r for r in comparison}
    for sku, row in replay.items():
        report = row.get("documents_report")
        if not report:
            continue
        for f in report["files"]:
            if f["state"] != "instruction_by_content_model_not_named":
                continue
            record = extract[f["href"]]
            pages = gzip.open(S22 / "pilot2/docs_extract" / record["text_file"], "rt", encoding="utf-8").read().split("\n\f\n")
            support_code = report["support_url"].rsplit("/lg-", 1)[-1]
            ru = row["sources"]["lg_ru"]
            tie, printed = support_page_ties_article(support_pages[report["support_url"]], ru["found_model"] if ru["match_level"] == "full_sku" else "")
            assessment = assess_document(pages, [report["product_model"], support_code.split(".")[0]])
            accepted = assessment["kind"] == "instruction_model_not_named" and assessment["languages"]["russian_instruction"] and tie
            blocking_after = [g for g in comp[sku]["blocking"] if g != "instruction_missing"] if accepted else comp[sku]["blocking"]
            evidence.append({"seller_sku": sku, "ru_match_level": ru["match_level"], "found_model": ru["found_model"], "support_page_model": printed, "support_page_names_the_article": tie,
                             "russian_instruction_by_content": assessment["languages"]["russian_instruction"], "conflicting_models": assessment["conflicting_models"], "accepted_by_rule_4": accepted,
                             "blocking_gaps_before": comp[sku]["blocking"], "blocking_gaps_after": blocking_after,
                             "readiness_after": "export_ready" if accepted and not blocking_after else comp[sku]["readiness"]})
    table = []
    for r in sorted(first, key=lambda x: x["category"]):
        ins = r["instruction"]
        ev = next((e for e in evidence if e["seller_sku"] == r["seller_sku"] and e["accepted_by_rule_4"]), None)
        table.append({"category": r["category"], "article": r["seller_sku"], "job": r["job"], "readiness": ev["readiness_after"] if ev else r["readiness"], "readiness_before_rule_4": r["readiness"], "rule_4": bool(ev), "kz": r["variant"]["kz"][0], "ru": r["variant"]["ru"][0], "facts": r["facts"],
                      "gallery_from_exact_pages": r["gallery"]["from_exact_pages"], "instruction_state": ins["state"], "saved_languages": ins["saved"], "conflicts": [c["name"] for c in r["real_conflicts"]],
                      "found_by_rule": LESSONS[r["seller_sku"]][0], "not_found": LESSONS[r["seller_sku"]][1]})
    (STAGE / "raw/category_table.json").write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    est = load(S22 / "raw/estimate_578_stage22.json")
    rules = {"rule_1_market_tag": {"rows_with_tag": est["market_tag_rows"], "rows_found_after_dropping_the_tag_for_search": est["market_tag_rows_found_if_the_tag_were_stripped"],
                                   "match_level_they_can_reach": "base_model (a tagged article is never on the page)", "pages_reachable_before": est["pages_reachable_now"],
                                   "pages_reachable_after": est["pages_reachable_now"] + est["market_tag_rows_found_if_the_tag_were_stripped"]},
             "rule_3_regional_differences": {"pilot_rows_with_differences": sum(1 for r in comparison if r["real_conflicts"]), "values_chosen_automatically": 0},
             "rule_4_saved_evidence": evidence}
    (STAGE / "raw/owner_rules_evidence.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---- the next brand ---------------------------------------------------------------------------------------------------------
    queue = [json.loads(line) for line in (ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    per = defaultdict(Counter)
    for u in queue:
        per[u["brand"]][u["category"]] += 1
    lg_categories = {r["category"] for r in first}

    def top(brand: str, n: int = 6):
        return [(c, k, c in lg_categories) for c, k in per[brand].most_common(n)]

    def rows_md(items):
        return "; ".join(f"{c} ({k}{', как у LG' if same else ''})" for c, k, same in items)

    samsung, bosch = top("Samsung"), top("BOSCH")
    ev_rows = "\n".join(f"| {e['seller_sku']} | {e['ru_match_level']} / {e['found_model']} | {e['support_page_model']} | {'да' if e['support_page_names_the_article'] else 'нет'} | "
                        f"{'да' if e['russian_instruction_by_content'] else 'нет'} | {', '.join(e['conflicting_models']) or '—'} | {'принимается' if e['accepted_by_rule_4'] else 'нет'} | {e['readiness_after']} |" for e in evidence)
    lines = ["| Категория | Карточка | Найдено | Не удалось | Правило адаптера, которое пришлось исправить |", "|---|---|---|---|---|"]
    for t in table:
        instr = {"instruction_confirmed_by_content": "русская инструкция подтверждена по тексту", "instruction_by_content_model_not_named": "русская инструкция найдена, модель в тексте не названа",
                 "reachable_not_a_complete_pdf": "файл инструкции не PDF/больше лимита", "not_attempted": "инструкции не проверялись"}[t["instruction_state"]]
        if t["rule_4"]:
            instr = "русская инструкция без модели в тексте, принимается по правилу 4 (связь через страницу поддержки)"
        if t["saved_languages"] == ["Казахский"]:
            instr = "инструкция только на казахском"
        conflicts = f"; расхождений KZ/RU: {len(t['conflicts'])}" if t["conflicts"] else ""
        lines.append(f"| {t['category']} | {t['article']} | KZ {t['kz']} / RU {t['ru']}; характеристик {t['facts']['kz']}/{t['facts']['ru']}; фото с точных страниц {t['gallery_from_exact_pages']}; {instr}{conflicts}; "
                     f"задание `{t['job']}`, готовность `{t['readiness']}` | {t['not_found']} | {t['found_by_rule']} |")
    text = f"""# Этап 23: сводка LG по категориям, решения владельца, следующий бренд

Новых сетевых запросов и обработки LG на этом шаге нет: числа взяты из сохранённых файлов этапов 20–22 (`scripts/01_summary.py`). Новый пилот LG и массовый прогон не проводились.

## Одна проверенная карточка на категорию (LG)
Карточка — строка первого пилота (по одной на категорию, выбрана по правилу этапа 20); состояние — по коду после правок этапов 21–22; для строк с правилом 4 готовность пересчитана по сохранённым данным (столбец «Найдено»).

{chr(10).join(lines)}

Итог по 12 категориям: `done` {sum(1 for t in table if t['job'] == 'done')}, `needs_review` {sum(1 for t in table if t['job'] == 'needs_review')}; `export_ready` {sum(1 for t in table if t['readiness'] == 'export_ready')}, `export_ready_with_gaps` {sum(1 for t in table if t['readiness'] == 'export_ready_with_gaps')}, `not_ready` {sum(1 for t in table if t['readiness'] == 'not_ready')}. Повторяющиеся причины исправлений: разные физические величины под одним именем (D3, {sum(1 for v in LESSONS.values() if v[0].startswith('D3'))} из 12 карточек), уровень совпадения страницы (D4), маршрут и фильтр LG Россия, язык и модель инструкции по содержимому файла.

## Четыре ответа владельца: что сделано
1. **`_KZ`/`_SU`** — `lg_base_model()` отбрасывает только эти метки и только чтобы найти страницу-кандидата; совпадение остаётся `base_model`, пока полный артикул не показан официальной страницей (тест: страница с `43LM5772PLA` даёт `base_model`, с `43LM5772PLA_KZ` — `full_sku`; задание с базовой страницей идёт на проверку). По сохранённым картам сайта страница находится у {rules['rule_1_market_tag']['rows_found_after_dropping_the_tag_for_search']} из {rules['rule_1_market_tag']['rows_with_tag']} таких строк: охват страниц {rules['rule_1_market_tag']['pages_reachable_before']} → {rules['rule_1_market_tag']['pages_reachable_after']} из 578 (все они — `base_model`, то есть на проверке).
2. **URL поддержки с артикулом не подтверждает вариант.** Вариант по-прежнему подтверждает только официальный контент (полный артикул на странице товара). Для инструкций проверяется, что заголовок самой страницы поддержки называет полный артикул строки (`support_page_ties_article`); адрес страницы во внимание не берётся. Ссылка поддержки с полным артикулом **не** используется как подтверждение варианта страницы товара (4 строки `base_model` остаются `base_model`).
3. **Расхождения KZ и RU.** Значение не выбирается: `selected_value` пусто, статус `official_regions_conflict`, оба факта хранятся с источниками, задание — `needs_review`, готовность — `unresolved_conflicts` (тест на цвете корпуса). Выбранных автоматически значений: 0.
4. **Русская инструкция без модели в тексте** принимается, если одновременно: содержание PDF — русская инструкция (не декларация); страница товара показывает полный артикул строки (`full_sku`), а официальная страница поддержки называет этот артикул своим товаром и держит файл в своём списке; в тексте нет конфликтующей модели (код с теми же 4 первыми символами, но другой). Документ сохраняется с пометкой в названии: «{' · связь с моделью подтверждена страницей поддержки, а не текстом PDF'.strip(' ·')}». Условие, не выполненное хотя бы одним пунктом, — инструкция не сохраняется (тесты на каждый пункт).

Применение правила 4 к сохранённым данным (без новых запросов; тексты PDF — из `stage22/pilot2/docs_extract`):

| Строка | Страница LG Россия | Заголовок страницы поддержки | Называет артикул | Русская по тексту | Конфликтующая модель | Правило 4 | Готовность после |
|---|---|---|---|---|---|---|---|
{ev_rows}

## Следующий бренд для точечной проверки: Samsung
Правило то же: по одной представительной карточке на категорию, без массового запуска.
- **Почему Samsung.** Второй по объёму бренд каталога с официальным сайтом (1182 строки; `samsung_kz` в реестре, площадка Казахстана — рынок каталога); его сайт в переписи давал прямой доступ (этап 8: `direct_access`); два реальных полных карточных результата уже есть (этапы 8.2–8.3: телевизор `UE43N5300AUXCE` и Galaxy Buds3 FE), но адаптера нет (этап 13). Категории пересекаются с LG, поэтому исправленные правила (варианты и суффиксы, разные физические величины, язык и модель инструкции, региональные расхождения) переносятся, а не изобретаются заново.
- **Какие категории (по одной карточке, только крупные, по числу строк каталога):** {rows_md(samsung)}. Остальные из 31 категорий — после первых шести и только по вашему запросу.
- **Первый шаг (когда скажете начинать):** без запросов — выбор по одной карточке на категорию по правилу этапа 20 (наименьший SHA-256 артикула) и объявление бюджета; затем маршрут страниц (карта сайта или поиск) и правило идентификации варианта (у Samsung код вида `WD10T654CBH/LD` — базовая модель плюс региональный суффикс).
- **Запасной вариант — Bosch Home** (682 строки, бытовая техника; этап 13: группа A, характеристики и медиа подтверждены, идентичность самая сильная — gtin+mpn, нет только документов): {rows_md(bosch)}. **Xiaomi** — самый большой (1474 строки), но 94 категории и наименее решённая структура, для правила «одна карточка на категорию» неудобен.

## Что изменено в коде
`adapters/lg.py` (`lg_base_model`), `adapters/lg_documents.py` (конфликтующая модель), `adapters/lg_documents_adapter.py` (проверка страницы поддержки, приём по правилу 4 с пометкой). Защищённый файл `lg.py` — с записью миграции и новым хэшем. Тесты: `tests/test_stage23_owner_rules.py`.
"""
    (STAGE / "report.md").write_text(text, encoding="utf-8")
    print(text[:2500])


if __name__ == "__main__":
    with offline_only():
        main()
