"""Stage 26 step 3 -- OFFLINE. Renders report.md from raw/run_result.json, raw/stop_and_dealer_checks.json, raw/replay_calls.json and raw/batch3_proposal.json. Nothing is requested."""
from __future__ import annotations

import json
from pathlib import Path

STAGE = Path(__file__).resolve().parents[1]
RAW = STAGE / "raw"
run = json.loads((RAW / "run_result.json").read_text(encoding="utf-8"))["cards"]
checks = json.loads((RAW / "stop_and_dealer_checks.json").read_text(encoding="utf-8"))
calls = json.loads((RAW / "replay_calls.json").read_text(encoding="utf-8"))
batch3 = json.loads((RAW / "batch3_proposal.json").read_text(encoding="utf-8"))

LEVEL = {"full_sku": "полный артикул (разметка/заголовок)", "code_in_page_text": "код только в тексте страницы", "base_model": "только базовая модель", "unknown": "не подтверждён"}
TIE = {"exact_page": "страница с полным артикулом", "page_with_code_in_text_only": "страница, где код только в тексте", "base_model_page": "страница базовой модели", None: "—"}
GAP = {
    "no_official_page": "нет официальной страницы", "no_official_specifications": "нет характеристик", "no_official_photo": "нет фото",
    "variant_base_model_only": "подтверждена только базовая модель", "variant_code_only_in_page_text": "код найден только в тексте страницы", "variant_not_shown_on_page": "артикул на странице не показан",
    "photos_not_selected_variant_open": "фото не выбраны: вариант не подтверждён", "unresolved_conflicts": "нерешённые конфликты", "dealer_dispute": "спор дилера с официальным значением",
    "instruction_not_checked": "инструкция не проверялась", "instruction_missing": "инструкции нет (ссылки на странице нет)", "instruction_file_not_confirmed": "ссылка есть, файл не подтверждён",
    "instruction_language_not_russian": "инструкция не на русском", "instruction_text_not_extractable_manual_check": "текст файла не извлекается: ручная проверка",
    "instruction_tied_by_weaker_page": "инструкция связана страницей без строгого подтверждения артикула", "instruction_model_not_named_in_text": "точный код каталога в тексте не назван",
    "instruction_names_family_not_exact_code": "названо семейство (маска), а не точный код", "instruction_names_only_the_link_model": "назван только код из ссылки страницы", "dealer_cross_check_missing": "нет подтверждения дилера",
}
VERDICT = {"export_ready": "готова к выгрузке", "export_ready_with_gaps": "готова с пробелами", "needs_verification": "нужна проверка варианта", "not_ready": "не готова"}


def gaps(items):
    return "; ".join(GAP.get(g, g) for g in items) or "—"


def named(instruction):
    if not instruction["saved"] and instruction["russian_by_text"] is None:
        return "—"
    if instruction["names_catalog_code_exactly"]:
        return "точный код каталога"
    if instruction["names_family_mask"]:
        return "семейство: " + ", ".join(instruction["names_family_mask"][:2])
    if instruction["names_link_model_only"]:
        return "только код из ссылки страницы"
    return "не назван"


def yn(value):
    return "—" if value is None else "да" if value else "нет"


lines = ["# Stage 26: адаптер Samsung в обычном рабочем процессе (`run_once()`), офлайн", ""]
verdicts = {}
for card in run:
    verdicts.setdefault(card["readiness"]["verdict"], []).append(card["category"])
status = {}
for card in run:
    status.setdefault(card["job_status"], []).append(card["category"])
served = len(calls["served"])
lines += [
    "## Итог", "",
    f"- Через обычный `worker.run_once()` прошли **{len(run)} из 11** уже проверенных карточек (по одной на категорию; планшеты пропущены: подходящей новинки нет). Заданий закончено: `done` — {len(status.get('done', []))}, `needs_review` — {len(status.get('needs_review', []))}, `error` — {len(status.get('error', []))}.",
    f"- Готовность карточки к выгрузке (отдельно от статуса задания): **готовы {len(verdicts.get('export_ready', []))}**, готовы с пробелами {len(verdicts.get('export_ready_with_gaps', []))}, нужна проверка варианта {len(verdicts.get('needs_verification', []))}, не готовы {len(verdicts.get('not_ready', []))}.",
    f"- Сеть: 0 запросов. Транспорт — сохранённые ответы этапов 24–25 ({served} ответов отдано, 2 обращения отклонены: сохранённого текста инструкции микроволновой печи нет), дилерская сессия отклонила бы любой вызов и **вызовов не было**.",
    "- Не запускались: другие строки каталога, новая партия категорий, новый пилот LG. Каталог, реестр источников и `data/batches.sqlite3` не менялись (см. `protected_hashes_check.json`).", "",
    "## Что подключено", "",
    "- `product_tool/adapters/samsung_source.py` — адаптер: маршрут (карты сайта `vd`/`da` для техники, хабы для смартфонов и планшетов; для носимой техники маршрута нет — запросов не делается), страница, страница покупки смартфона по разметке самой страницы, файлы инструкций. Все запросы идут через `PolicyAwareSession` (список разрешённых хостов, проверка перенаправлений, постоянный журнал остановок `<каталог данных>/samsung_fetch_log.json`, бюджет запросов на строку — не более 7).",
    "- `product_tool/samsung_pipeline.py` — этапы Samsung в `run_once()` (официальная страница, инструкции, ограничитель дилера, проверка споров, итоговый статус); `worker.py` только направляет бренд в них (`samsung_adapter_factory`, `SAMSUNG_BRAND_ALIASES`). Этап инструкций Samsung выполняется **до** дилера, чтобы дилера спрашивали только о том, чего ещё нет.",
    "- `product_tool/samsung_readiness.py` — готовность карточки с уровнями доказательств; `product_tool/card_evidence.py` — структурные доказательства рядом с карточкой и открытые проверки в общей таблице `human_reviews`.",
    "- Ярлыки и выгрузка: `resolution.py` (Samsung — официальный источник), `display.py`, `jobs.py` (текст «Полный артикул найден на Samsung» и т. п.), `exporter.py` (столбец Samsung, лист «Готовность Samsung»; выгрузка без Samsung не меняется), `normalization.py` (см. ниже), шаблон карточки.",
    "- Закреплённые файлы (`worker.py`, `jobs.py`, `resolution.py`, `display.py`, `exporter.py`, `normalization.py`) изменены через записи в `tests/_pipeline_migration.py` с новыми контрольными суммами.", "",
    "## Путь `run_once()` по категориям", "",
    "| Категория | Артикул | Задание | Готовность | Вариант по странице | Характеристики | Фото (выбрано/найдено) | Инструкция: рус. по тексту / связь / код в PDF | Блокирующие пробелы |", "|---|---|---|---|---|---|---|---|---|",
]
for card in run:
    r = card["readiness"]
    i = r["instruction"]
    doc = f"{yn(i['russian_by_text'])} / {TIE.get(i['tied_by_official_page'])} / {named(i)}" if i["saved"] else ("файл без извлекаемого текста, не сохранён" if i["manual_check_files"] else "нет")
    lines.append(f"| {card['category']} | {card['article']} | `{card['job_status']}` | {VERDICT[r['verdict']]} | {LEVEL.get(r['page_match_level'], r['page_match_level'])} | {card['facts']['samsung']} | {card['photos']['gallery_selected']}/{card['photos']['gallery_found']} | {doc} | {gaps(r['blocking_gaps'])} |")
lines += ["", "«Задание `done`» — это состояние сравнения источников (страница с полным артикулом по содержимому, нет конфликтов), как у LG; готовность карточки считается отдельно и пробелы не прячутся за `done`.", ""]

lines += ["## Что требует проверки и почему", ""]
for card in run:
    r = card["readiness"]
    if r["verdict"] == "export_ready":
        continue
    why = gaps(r["blocking_gaps"])
    extra = f" Открыто по варианту: {'; '.join(r['open_variant_differences'])}." if r["open_variant_differences"] else ""
    reviews = ", ".join(x["review_type"] for x in card["open_reviews"]) or "—"
    lines.append(f"- **{card['category']}** ({card['article']}): {VERDICT[r['verdict']]} — {why}.{extra} Открытые проверки: {reviews}.")
lines += ["", "Готовы к выгрузке без блокирующих пробелов: " + ", ".join(f"{c['category']} ({c['article']})" for c in run if c["readiness"]["verdict"] == "export_ready") + ". У трёх из них инструкция называет семейство (маску), а не точный код, — это справочный пробел, он показан в выгрузке и не блокирует.", ""]

tv = next(c for c in run if c["category"] == "Телевизоры")
vac = next(c for c in run if c["category"] == "Пылесосы")
phone = next(c for c in run if c["category"] == "Смартфоны")
hob = next(c for c in run if c["category"] == "Варочные панели")
lines += ["## Уровни доказательств сохранены", "",
          "| Карточка | Русский язык по тексту | Связь файла со страницей | Точный код каталога в PDF | Код, названный ссылкой страницы | Хранится (модель каталога / модель ссылки) |", "|---|---|---|---|---|---|"]
for card in (tv, vac):
    facts = next(e["facts"] for e in card["document_files_assessed"] if e.get("facts"))
    doc = card["documents"][0]
    lines.append(f"| {card['category']} {card['article']} | {yn(facts['russian_by_text'])} | {TIE[facts['tied_by_official_page']]} | {yn(facts['names_catalog_model']['exact'])} | {('да: ' + facts['names_link_model']['model_name']) if facts['names_link_model']['exact'] else 'нет'} | {doc['product_model']} / {doc['support_model']} |")
lines += ["", "Коды `SC…` и `VC…` нигде не приравниваются: код из ссылки страницы и код каталога хранятся и показываются раздельно, общего правила равенства нет.", "",
          f"- **Galaxy A37** ({phone['article']}): страница базовой модели `{phone['sources']['samsung']['found_model']}`. Открыто: " + "; ".join(phone["readiness"]["open_variant_differences"]) + ". Пробелы шире отсутствующей инструкции: " + gaps(phone["readiness"]["blocking_gaps"]) + f". Фото ({phone['photos']['gallery_found']}) лежат на странице покупки из разметки самой страницы и **не выбраны** для карточки, пока вариант не подтверждён (цвет ZA и DG может различаться).",
          "- **Код только в тексте страницы** (холодильник, варочная панель): уровень `code_in_page_text`, не `full_sku`; задание `needs_review`, фото не выбраны, поставлена проверка варианта.",
          f"- **Варочная панель**: файл {hob['document_files_assessed'][0]['file']} — текст не извлекается ({hob['document_files_assessed'][0]['facts']['empty_pages']} из {hob['document_files_assessed'][0]['facts']['pages']} страниц пусты). Он **не сохранён** как инструкция и стоит в ручной проверке; в текстовых признаках языка и модели ничего не выводилось.", ""]

lines += ["## Дилерский фолбэк", "",
          "- Без проверенного точного URL DNS не делает запросов: во всём прогоне вызовов дилерской сессии — " + str(len(calls["dealer_session_calls"])) + ". Готовый запрос дилеру (бренд, модель и вариант, недостающие поля; URL не угадывается) сформирован для: " + "; ".join(f"{c['category']} — {c['sources']['dns']['evidence'].split('Не хватает: ')[1].split('.')[0] if 'Не хватает: ' in c['sources']['dns']['evidence'] else '?'}" for c in run if c["sources"]["dns"]["match_level"] == "dealer_url_needed") + ". Остальным карточкам дилер не нужен (`not_needed`: недостающих полей нет).",
          "- Дилер добавляет только отсутствующие поля, только при точном совпадении модели и варианта, у каждого поля свой источник (`dns`), значение проходит как «нужна проверка», а не как подтверждённое. Страница дилера без точного совпадения не вносит никаких значений (ограничитель до сохранения).",
          f"- Спор с официальным значением: официальное значение остаётся, поле уходит в открытую проверку `dealer_dispute`, задание становится `needs_review`, готовность — с блокирующим пробелом. Проверено на синтетическом дилере: добавлено полей {len(checks['dealer_exact_model_and_code']['dealer']['added_fields'])} (источник `dns`, статус `{checks['dealer_exact_model_and_code']['dealer_only_field']}`), споров {len(checks['dealer_exact_model_and_code']['dealer']['disputes'])}, значение официального поля после прогона: `{checks['dealer_exact_model_and_code']['official_field_after_run']['value']}` из `{checks['dealer_exact_model_and_code']['official_field_after_run']['source']}`; неточный дилер: строк фактов дилера {checks['dealer_not_exact']['dealer_fact_rows']}, статус задания `{checks['dealer_not_exact']['job_status']}`.", ""]

total = sum(c["requests"]["spent"] for c in run)
lines += ["## Доступ и журнал остановок", "",
          f"- Реальных запросов не было (сохранённые ответы). Тот же путь в боевом режиме сделал бы {total} обращений к серверу по журналу бюджета: {served} отдано транспортом, карты сайта `vd` и `da` прочитаны по одному разу на весь прогон и дальше отдавались из кэша, отклонённые обращения не считаются. На строку — от {min(c['requests']['spent'] for c in run)} до {max(c['requests']['spent'] for c in run)} при пределе 7. Только адреса под `www.samsung.com/kz_ru/` и `org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx`, увиденные на страницах; адресов не строится.",
          f"- Остановка: ответ 403 остановил хост (запросов транспорту: {checks['stop']['first_run']['requests_to_transport']}, журнал: {checks['stop']['first_run']['log_status_codes']}, задание `{checks['stop']['first_run']['status']}`); **новый запуск** на том же каталоге данных сделал {checks['stop']['second_run_same_directory']['requests_to_transport']} запросов (`{checks['stop']['second_run_same_directory']['halted']}`). Исчерпанный бюджет строки отказывает до запроса (`policy_budget_exhausted`).", ""]

lines += ["## Что нашла интеграция", "",
          "1. **Ложные конфликты внутри одного источника.** Нормализация LG сворачивала в одно имя разные величины Samsung: размер дисплея и размер изделия (смартфон), поворотный стол и изделие (микроволновая печь), «размер изображения: да» и класс экрана (монитор), глубина/высота с ручкой, без ручки, без дверей, с петлями и без, упаковка (холодильник), а также два поля, отличающихся только скобками («Количество ящиков…»). Было 6 ложных конфликтов на 4 карточках; словарь величин расширен (записано в миграции), адаптер различает поля по скобкам. Теперь конфликтов 0 на всех 11 карточках; незнакомая формулировка по-прежнему даст конфликт для человека, а не тихое слияние.",
          "2. **Ярлыки.** Статус «Найдено только у базовой модели LG» для значений Samsung был бы ложным; источник `samsung` теперь называется «Samsung Казахстан», статус читается как «Значение официального сайта Samsung; вариант оценивается отдельно», в списке источников есть уровень «Артикул только в тексте страницы».",
          "3. **Инструкция микроволновой печи** подтверждена на этапе 8.6 (русская по содержимому, точный код в колонтитулах), но текст файла в материалах не сохранился, поэтому офлайн он заново не оценивался: карточка помечена «ссылка есть, файл не подтверждён». Это ограничение прогона, а не вывод о документе.",
          "4. **Сопоставление названий характеристик** Samsung с именами конвейера: свои имена получают все поля (по слагу названия); известные величины (размеры, вес, диагональ, цвет…) сворачиваются в общие имена. Полного словаря соответствий для сравнения с дилером или LG нет.", ""]

lines += ["## Вопросы владельцу (не решались за вас)", "",
          "1. Инструкция, чей русский текст не называет точный код каталога (телевизор — код не назван вовсе; пылесос, монитор — назван только код из ссылки страницы): принимать ли её по аналогии с правилом 4 LG (русский по содержимому + страница с полным артикулом + нет чужой модели) с пометкой? Сейчас — блокирующий пробел, документ сохранён и показан с тремя фактами.",
          "2. Считать ли инструкцию с названным **семейством** (маской) достаточной без пометки (сейчас — справочный пробел, карточка готова)?",
          "3. Выбирать ли фото при `code_in_page_text` (сейчас нет, до проверки варианта человеком)?", ""]

lines += ["## Следующая небольшая партия (предложение, ничего не запрашивалось)", "",
          "Правило партии 2: среди строк категории с чистым артикулом и точной страницей в полных картах сайта — наименьший SHA-256 артикула. Путь — тот же `run_once()`.", "",
          "| Категория | Артикул | Страница |", "|---|---|---|"]
for category, item in batch3["products"].items():
    lines.append(f"| {category} | {item['article']} | {item['page_url'].split('/kz_ru/')[1]} |")
budget = batch3["request_budget"]
lines += ["", f"Бюджет (объявляется до запросов): карты сайта — {budget['sitemaps']}, страницы товаров — {budget['product_pages']}, файлы инструкций — {budget['instruction_files']}, итого не более {budget['total_cap']}; не более 7 на строку; пауза 1,5 с; лимит файла 40 МБ; остановка при 401/403/429/подтверждённом челлендже; дилер — 0 запросов.", "",
          "Остальные категории очереди (15) без страницы в сохранённых картах сайта:", ""]
for category, entry in batch3["queued_categories"].items():
    if "proposed" not in entry:
        lines.append(f"- {category} (строк в каталоге: {entry['catalog_rows']}): {entry['route']}")
lines += ["", "Они остаются в очереди без изменений: сначала нужен небольшой объявленный поиск маршрута, затем карточка.", ""]
(STAGE / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("report.md", len(lines), "lines")
