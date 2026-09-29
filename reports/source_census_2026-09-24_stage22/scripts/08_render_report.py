"""Stage 22 step 8 -- OFFLINE. Renders report.md from raw/*.json and numbers.json. Every number in the tables is read from those files."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


GROUP = {"first_pilot": "п1", "A": "A не в KZ", "B": "B суффикс", "C": "C нигде", "D": "D обе"}
INSTRUCTION_TEXT = {
    "instruction_confirmed_by_content": "подтверждена по содержимому",
    "instruction_by_content_model_not_named": "русская, но модель в тексте не названа (не сохранена)",
    "reachable_file": "файл доступен, не инструкция",
    "reachable_not_a_complete_pdf": "файл не PDF (архив) или больше 25 МБ",
    "candidate_link": "только ссылка-кандидат",
    "no_candidates": "нет списка руководств",
    "not_attempted": "не проверялась: нет страницы LG Россия",
}


def instruction_cell(c: dict) -> str:
    ins = c["instruction"]
    text = INSTRUCTION_TEXT.get(ins["state"], ins["state"])
    if ins["state"] == "instruction_confirmed_by_content":
        f = next(x for x in ins["files"] if x["state"] == "instruction_confirmed_by_content")
        language = ", ".join(ins["saved"]) or "?"
        evidence = "модель названа" if f["model_evidence"] == "exact" else "семейство по маске " + (f["masks"][0] if f["masks"] else "")
        return f"{text}: {language}; {evidence}"
    return text


def main() -> None:
    n = load(STAGE / "numbers.json")
    rows = load(STAGE / "raw/pilot2_comparison.json")
    estimate = load(STAGE / "raw/estimate_578_stage22.json")
    requests_ = load(STAGE / "raw/pilot2_requests.json")
    a, b, c = load(STAGE / "raw/docs_phase_a_result.json"), load(STAGE / "raw/docs_b_result.json"), load(STAGE / "raw/docs_c_result.json")
    docs_requests = a["requests_made"] + b["requests_made"] + c["requests_made"]

    table = ["| Строка | Группа | Задание: живой прогон → после правок | Готовность | Вариант KZ / RU | Характеристики KZ / RU | Фото с точных страниц | Инструкция | Конфликтов | Пробелы (кроме дилера) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        gaps = ", ".join(g for g in r["gaps"] if g != "dealer_cross_check_missing") or "—"
        history = ""
        if r["history"]["stage20_job"]:
            history = f" (Э20 {r['history']['stage20_job']}, Э21 {r['history']['stage21_job']})"
        table.append(f"| {r['seller_sku']} | {GROUP[r['group']]} | {r['live_job']} → **{r['job']}**{history} | {r['readiness']} | {r['variant']['kz'][0]} / {r['variant']['ru'][0]} | {r['facts']['kz']} / {r['facts']['ru']} | {r['gallery']['from_exact_pages']} | "
                     f"{instruction_cell(r)} | {len(r['real_conflicts'])} | {gaps} |")
    conflicts = ["| Строка | Поле | Значения |", "|---|---|---|"]
    for r in rows:
        for x in r["real_conflicts"]:
            conflicts.append(f"| {r['seller_sku']} | {x['raw_names'][0]} | {' / '.join(x['values'])} |")

    both, single = n["exact_rows_both_regions"], n["exact_rows_single_region"]
    conflict_both = n["exact_rows_both_regions_with_conflicts"]
    lo, hi = wilson(conflict_both, both)
    reg = estimate["exact_slug_by_region"]
    exact_total = estimate["expected_exact_page"]
    done_point = reg["exact_ru_only"] + reg["exact_kz_only"] + reg["exact_both_regions"] * (1 - conflict_both / both)
    done_lo = reg["exact_ru_only"] + reg["exact_kz_only"] + reg["exact_both_regions"] * (1 - hi)
    done_hi = reg["exact_ru_only"] + reg["exact_kz_only"] + reg["exact_both_regions"] * (1 - lo)
    ru_rows = n["rows_with_ru_page"]
    ru_ok = n["russian_instruction_saved_with_model_evidence"]
    ilo, ihi = wilson(ru_ok, ru_rows)
    ru_pages_578 = load(ROOT / "reports/source_census_2026-09-24_stage21/raw/estimate_578_stage21.json")["reachable_ru"]
    export_ready = n["readiness_after_fixes"].get("export_ready", 0)
    elo, ehi = wilson(export_ready, n["exact_page_rows"])
    est_export = exact_total * export_ready / n["exact_page_rows"]
    unnamed = n["instruction_states_among_ru_page_rows"].get("instruction_by_content_model_not_named", 0)
    unnamed_rows = [r["seller_sku"] for r in rows if r["instruction"]["state"] == "instruction_by_content_model_not_named"]
    no_ru_rows = [r["seller_sku"] for r in rows if r["variant"]["ru"][0] not in ("full_sku", "base_model")]
    base_ru_rows = [r for r in rows if r["variant"]["ru"][0] == "base_model"]
    support_equals_article = [r["seller_sku"] for r in base_ru_rows if r["instruction"].get("support_code", "") == r["seller_sku"].upper()]
    reqs = n["requests"]
    per_row_requests = reqs["real_new_rows"] / n["new_rows"]

    text = f"""# Этап 22: маршрут инструкций LG Россия, фото LG Россия, второй пилот (24 строки)

Числа взяты из `raw/*.json` и `numbers.json` скриптами `scripts/07_analyze.py` и `scripts/08_render_report.py`. Полный прогон 578 строк не запускался.

## Вывод
- **Полный прогон LG можно обоснованно запускать уже для страниц, характеристик и фото; инструкции — отдельным этапом. Четыре решения владельца (раздел 4) определяют, сколько строк станут `done` и `export_ready`, а не безопасность прогона.** За {n['requests']['real_total']} реальных запросов пилота (и 8 запросов пробы инструкций) блокировок не было; тип страницы по сохранённым картам сайта (точный слаг / только базовый код / нигде) совпал с фактическим результатом у {n['calibration_agree']} из {n['rows']} строк.
- Что реально охватить (оценка по 578 строкам, см. «Оценка»): страница LG есть у **{estimate['pages_reachable_now']}** ({round(100 * estimate['share_pages_reachable_now'])} %), точная страница с полным артикулом — около **{exact_total}** ({round(100 * estimate['share_expected_exact'])} %), только страница базовой модели — **{estimate['expected_base_model_only']}**, страницы нет — **{estimate['expected_no_page']}** (из них {estimate['market_tag_rows_currently_missed']} — артикулы с рыночным суффиксом `_KZ`/`_SU`, для {estimate['market_tag_rows_found_if_the_tag_were_stripped']} из них страница есть, если суффикс отбросить).
- Статус `done` без настоящих конфликтов: около **{round(done_point)}** строк (диапазон {round(done_lo)}–{round(done_hi)}, выборка мала). Готовность `export_ready` (страница, характеристики, фото, русская инструкция, нет конфликтов): около **{round(est_export)}** строк (диапазон {round(exact_total * elo)}–{round(exact_total * ehi)}).
- Пробелы, которые останутся при полном прогоне: инструкции (см. ниже), расхождения между KZ и RU на строках с двумя точными страницами, {estimate['expected_base_model_only']} строк только с базовой моделью, {estimate['expected_no_page']} без страницы, дилерская сверка (не блокирует).

## 1. Инструкции: маршрут установлен, что даёт и что нет
Бюджет и правило остановки записаны до первого запроса (`raw/docs_declaration.json`). Запросов всего {docs_requests} из 8 объявленных, блокировок нет.
- **Фаза A** ({a['requests_made']} запроса): скрипты `common-support.min.js` и `select-product-category.min.js`, напечатанные на сохранённой странице руководств. Объявленный текстовый признак (`data-detail | manual-select | modelDetail | retrieveGp`) в них не нашёлся, и **по объявленному правилу я остановился**. Признак был слишком узким: виджет читает адрес как `x.data("detail")` и вызывает `ajax.call(detailURL, {{categoryId, subCategoryId, modelName}}, "html")` — значения берутся из выбора категории, которого на странице товара нет, а способ передачи (GET/POST) описан в третьем скрипте. Этот путь без новых запросов не проверить.
- **Этап 22b** (новый, объявлен отдельно: `raw/docs_b_declaration.json`, {b['requests_made']} запроса): в том же скрипте есть обработчик для `.support-downloads li.manuals` — список руководств на странице поддержки товара, а ссылка `/ru/support/product/lg-<полный код>` напечатана на каждой странице товара LG Россия. Маршрут: страница товара → её страница поддержки → статический список → файл на `gscs-b2c.lge.com`. Нужен один запрос на страницу поддержки и по одному на файл. Правило «первый кандидат» оказалось неудачным: он выбрал краткое руководство (XL7S) и архив ZIP (MS2032GAS).
- **Этап 22c** (объявлен отдельно, `raw/docs_c_declaration.json`, {c['requests_made']} запроса): выбор по напечатанному типу «Руководства пользователя»; он лишь выбирает ссылку и ничего не подтверждает.

Три состояния, которые не смешиваются: ссылка-кандидат → доступный файл (200, целиком, `%PDF-`) → инструкция, подтверждённая по тексту файла. Язык определяется только по извлечённому тексту (по фрагментам ~600 символов; русская *инструкция* требует ≥ 2500 русских букв и ≥ 2 слов инструкции, чтобы юридическое уведомление на десяти языках не считалось инструкцией).

| Товар | Файл (тип, метка на странице) | Что оказалось по содержимому |
|---|---|---|
| XL7S | краткое руководство, «English,Русский» | PDF 2 стр.; фрагменты en/kk/ru/uk; есть русские разделы с реальными шагами — инструкция, модель названа |
| XL7S | руководство пользователя, «Русский» | PDF 42 стр.; русский текст 38 037 букв; модель названа — **русская инструкция подтверждена** |
| MS2032GAS | руководство пользователя, «Русский» | PDF 32 стр.; **текст казахский** (`kk-kz_main.book`, «ҚАЗАҚША»); модель названа только маской `MS203****` — инструкция на **казахском**, не на русском, вопреки метке |
| MS2032GAS | краткое руководство, «Русский» | это ZIP (путь внутри `kk-kz/res/…`), не PDF |

Ошибка в моём инструменте, которую нашёл этот же этап: существующий `verify_document` (написан для DNS) признал краткое руководство XL7S «регуляторным» из-за слова в юридическом разделе. Для LG написана своя оценка (`adapters/lg_documents.py`): «регуляторный» — только если заголовок в начале документа и почти нет слов инструкции.

Готовый адаптер: `LGRUDocumentAdapter` (`adapters/lg_documents_adapter.py`) — не более 1 страницы поддержки и 2 файлов на товар, только напечатанные ссылки, хосты `lg.com` и `*.lge.com`, при остановке хоста дальше не идёт. Инструкция сохраняется, только если по тексту файла названа модель или её **семейство маской** (`F2J3WS**`, `65UT80*` — так LG печатает семейства); язык записывается по тексту. Инструкция на другом языке сохраняется как такая, и готовность показывает `instruction_language_not_russian`.

## 2. Фото LG Россия
Прежний фильтр принимал только `/stylers/`, а на всех 11 сохранённых страницах галерея лежит в `/ru/images/<категория>/<md…>/gallery/`, поэтому фото RU не извлекались никогда. Теперь: миниатюра берётся в самом большом размере из `data-medium`/`data-large`, заглушка `obj-base.png` и всё вне папки модели отбрасываются, дубли (миниатюра и большая) сливаются. Проверка офлайн на 11 страницах: 7–15 снимков на страницу, без дублей и заглушек. **A9N-MASTERX: 0 → 15 снимков** с точной страницы. **27MD5KL-B.AEU: 8 снимков, совпадение осталось `base_model`** — фото не повышают совпадение (как и у 24MR400-B.ARUQ: 7 снимков, `base_model`). Второй пилот нашёл ещё одну раскладку (VC5316NNTS: файлы прямо в `md…/` без `gallery/`), она принята; VC5316NNTS: 0 → 10.

## 3. Второй пилот: выбор, запросы
Выборка: 12 прежних строк + 12 новых по правилу, записанному до запросов (`raw/pilot2_declaration.json`): группы A (нет в карте KZ, есть в карте RU) 5, B (артикул с точкой) 3, C (нигде) 1, D (в обеих, без точки) 3; внутри группы — категория с наименьшим числом выбранных, затем наименьший SHA-256 артикула. В карте KZ отсутствуют **{n['new_rows_not_in_kz_sitemap']}** из новых строк (требовалось не менее 5).
- Реальных запросов: **{reqs['real_total']}** из 180 (не более {reqs['max_real_in_one_row']} на строку при лимите 12); отказов по бюджету {reqs['refusals']}; ответов, взятых из сохранённых файлов, {reqs['replayed']} (для прежних 12 строк страницы LG уже были сохранены; новые запросы для них — страницы поддержки и файлы: {reqs['real_first_pilot_rows']}; для 12 новых строк: {reqs['real_new_rows']}, в среднем {per_row_requests:.1f} на строку).
- Скачано {reqs['real_downloaded_mb']} МБ, из них {reqs['real_document_files_mb']} МБ — {reqs['real_document_files']} файлов инструкций (0,4–25 МБ). Блокировок, 401/403/429 и подтверждённых проверок нет.
- Время на строку в живом прогоне: в среднем {n['seconds_per_row_live']['mean']} с, максимум {n['seconds_per_row_live']['max']} с; две строки ({', '.join(n['seconds_per_row_live']['rows_over_50_s'])}) — около предела 60 с на задание.

**Три правки после живого прогона** (сделаны после того, как я увидел результаты; проверены повтором тех же 24 строк на сохранённых ответах без сети): единичная глубина/ширина/высота и «глубина с учётом двери» получили свои имена (`F2T3HS6W`: «495» против тройки Ш×В×Г было ложным конфликтом); диапазон «87.5 ~ 108 MHz» и «87.5 - 108 МГц» равны (`CJ45`); раскладка фото VC5316NNTS. Плюс маска семейства в оценке инструкции. Поэтому в таблице два столбца: живой прогон и после правок. Живой результат не переписан: `raw/pilot2_rows.json`.

Итог по 24 строкам: `done` {n['job_live'].get('done', 0)} → **{n['job_after_fixes'].get('done', 0)}**, `needs_review` {n['job_live'].get('needs_review', 0)} → {n['job_after_fixes'].get('needs_review', 0)}; готовность `export_ready` {n['readiness_after_fixes'].get('export_ready', 0)}, `export_ready_with_gaps` {n['readiness_after_fixes'].get('export_ready_with_gaps', 0)}, `not_ready` {n['readiness_after_fixes'].get('not_ready', 0)}; настоящих конфликтов {n['conflicts_live']} → {n['conflicts_after_fixes']} (в {n['rows_with_conflicts_after_fixes']} строках). Строк со статусом `done`, но не `export_ready`: {n['done_but_not_export_ready']} — статус и готовность разведены.

Столбцы: «Вариант» — уровень совпадения страницы (full_sku — полный артикул есть на странице; base_model — только базовая модель); «Фото с точных страниц» — выбранные снимки страниц с полным артикулом.

{chr(10).join(table)}

«Э20/Э21» — статус этой строки в предыдущих пилотах. Пробелы, кроме дилера, во всех строках включают `instruction_missing`, если инструкция не сохранена (см. столбец «Инструкция»).

### Настоящие расхождения (остаются на проверке)
{chr(10).join(conflicts)}

Все — разные значения (цвет, глубина, комплектация пульта, число USB против «есть», значение «o» против «true»), а не формат. В выборке они бывают только там, где точные страницы есть **и на KZ, и на RU**: {conflict_both} из {both} таких строк, на строках с одной точной страницей — {n['exact_rows_single_region_with_conflicts']} из {single}.

### Инструкции: итог по 20 строкам со страницей LG Россия
Подтверждена по содержимому: **{n['instruction_states_among_ru_page_rows'].get('instruction_confirmed_by_content', 0)}** (русская с названной моделью или семейством: **{ru_ok}**, из них модель названа у {n['instruction_model_evidence'].get('exact', 0)}, семейство по маске у {n['instruction_model_evidence'].get('family_mask', 0)}; на казахском: {', '.join(n['kazakh_only_instruction_rows']) or '—'}). Русская инструкция, но её текст не называет модель ни точно, ни маской: **{unnamed}** ({', '.join(unnamed_rows)}) — не сохранены. Файл не PDF (архив) или крупнее 25 МБ: **{n['instruction_states_among_ru_page_rows'].get('reachable_not_a_complete_pdf', 0)}**. Без страницы LG Россия инструкции не проверялись вовсе ({len(no_ru_rows)} строки: {', '.join(no_ru_rows)}).
Выгрузка Excel: строки с фото {n['export']['rows_with_photo_rows']} из {n['rows']} ({n['export']['photo_rows']} строк листа), строки листа «Инструкции» {n['export']['instruction_rows']} (языки в листе: {', '.join(n['export']['instruction_languages_in_sheet'])}).

## 4. Оценка на 578 строк и что остаётся
Правило: по сохранённым картам сайта каждая строка попадает в один из трёх классов: точный слаг (страница самого артикула), только слаг базового кода, ничего. На 24 строках класс совпал с фактическим уровнем совпадения страницы в **{n['calibration_agree']} из {n['rows']}** случаев. Выборка расслоена, а не случайна, поэтому доли ниже — оценки с широкими границами.

| Класс | Строк из 578 |
|---|---|
| Точный слаг (ожидается full_sku) | {estimate['expected_exact_page']} (обе площадки {reg['exact_both_regions']}, только RU {reg['exact_ru_only']}, только KZ {reg['exact_kz_only']}) |
| Только базовый код (ожидается base_model → `needs_review`) | {estimate['expected_base_model_only']} |
| Нигде | {estimate['expected_no_page']} (рыночный суффикс `_XX`: {estimate['market_tag_rows_currently_missed']}; действительно нет: {estimate['truly_absent_without_tag_rows']}) |

Оценки по пилоту: `done` — строки с одной точной страницей (0 конфликтов из {single}) плюс строки с двумя (конфликт в {conflict_both} из {both}, доверительный интервал {round(100 * lo)}–{round(100 * hi)} %); русская инструкция с названной моделью у {ru_ok} из {ru_rows} строк со страницей RU ({round(100 * ru_ok / ru_rows)} %, интервал {round(100 * ilo)}–{round(100 * ihi)} %) — для {ru_pages_578} строк со страницей RU это ≈ {round(ru_pages_578 * ru_ok / ru_rows)} (с инструкциями, где модель не названа, — до {round(ru_pages_578 * (ru_ok + unnamed) / ru_rows)}).

**Пробелы, которые останутся, и что они требуют:**
1. **Рыночный суффикс `_KZ`/`_SU`** ({estimate['market_tag_rows']} строк, {estimate['market_tag_rows_found_if_the_tag_were_stripped']} найдены бы после его отбрасывания). Поиск сейчас их не находит (`DC90V9V9W.ABWPCOM_KZ` в пилоте — честный промах). Я не считаю суффикс частью модели LG без вашего решения: отбросив его, страница даст лишь `base_model`.
2. **{estimate['expected_base_model_only']} строк только с базовой моделью.** В пилоте у {len(support_equals_article)} из {len(base_ru_rows)} таких строк со страницей RU ссылка поддержки на самой странице (`/ru/support/product/lg-<код>`) печатает **полный артикул строки** ({', '.join(support_equals_article)}). Это подтверждение варианта на самой странице, но не видимым текстом; правило D4 я не менял без вашего решения.
3. **Расхождения KZ и RU** на строках с двумя точными страницами (≈ {round(100 * conflict_both / both)} % в пилоте): значения различаются по существу (цвет, глубина), автоматически я их не решаю. Нужно правило: чьё значение выбирать (например, площадка целевого рынка).
4. **Инструкции.** (а) русская инструкция без названия модели в тексте — {unnamed} из 20: принять ли связь «через страницу поддержки товара» как достаточную; (б) крупнее 25 МБ или только архив — 2 из 20; (в) на казахском вместо русского — 1 из 20; (г) строки без страницы RU (нет в карте RU): маршрут инструкций через KZ не исследован.
5. **Объём.** Один файл инструкции — в среднем около {reqs['real_document_files_mb'] / reqs['real_document_files']:.0f} МБ; на ≈ {ru_pages_578} строк со страницей RU это порядка {ru_pages_578 * reqs['real_document_files_mb'] / reqs['real_document_files'] / 1000:.1f} ГБ загрузки и ≈ {578 * n['seconds_per_row_live']['mean'] / 3600:.1f} ч по времени пилота ({n['seconds_per_row_live']['mean']} с на строку, последовательно). Две строки из 24 подошли к пределу 60 с на задание.
6. Дилерская сверка (`dealer_cross_check_missing`) — рекомендательный пробел, не блокирует.

## 5. Что изменено в коде
`adapters/lg_documents.py` (байтовая выдача PDF через policy-aware сессию, оценка документа, язык по тексту), `adapters/lg_documents_adapter.py` (адаптер инструкций), `adapters/lg_policy.py` (адаптер по умолчанию, хост документов, параметр темпа), `adapters/lg.py` (фото RU), `normalization.py` (глубина/ширина/высота отдельно, «с учётом двери»), `resolution.py` (диапазон и единицы), `worker.py` (сообщение: «подтверждено по содержимому: N; русских: M»), `readiness.py` (фото с точных страниц). Защищённые файлы — с записями миграции и новыми хэшами. Не менялись: каталог, реестр, отчёты этапов 2–21, `data/batches.sqlite3`.

## 6. Что сделано не по плану
- Фаза A ошибочно узким признаком дала остановку по правилу; новый этап объявлен отдельно.
- Правило 22b «первый кандидат» выбрало краткое руководство и архив — 22c выбирал по типу; оба заранее объявлены.
- Три правки и маска семейства сделаны после просмотра живых результатов пилота; проверены только повтором на сохранённых ответах.
- Тела PDF (176 МБ) после повтора удалены из `pilot2/responses`, оставлены текст (`pilot2/docs_extract`), sha256 и размеры; офлайн-повтор строк с инструкциями теперь требует повторной загрузки файлов.
"""
    (STAGE / "report.md").write_text(text, encoding="utf-8")
    print(text[:3000])


if __name__ == "__main__":
    with offline_only():
        main()
