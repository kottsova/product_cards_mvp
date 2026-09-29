"""Stage 24 step 5 -- OFFLINE. Reads raw/*.json and the saved batch responses, writes raw/batch1_table.json and report.md. No request is made."""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from product_tool.offline_guard import offline_only  # noqa: E402


def load(name: str):
    return json.loads((STAGE / name).read_text(encoding="utf-8"))


def body(directory: str, needle: str) -> str:
    base = STAGE / directory / "responses"
    for line in (base / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if needle in entry["url"] and entry["saved_as"]:
            with gzip.open(base / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                return handle.read()
    raise SystemExit(needle)


def assets(html: str, code: str) -> dict:
    urls = set(re.findall(r"https://images\.samsung\.com/[^\"'\s<>\\)]+", html))
    keep = sorted({re.sub(r"\?.*$", "", u) for u in urls if code in re.sub(r"[^a-z0-9]", "", u.lower())})
    three_d = [u for u in keep if re.search(r"\.(glb|usdz)$", u)]
    return {"assets": len(keep), "three_d_models": len(three_d), "photo_assets": len(keep) - len(three_d)}


LABEL = re.compile(r"(Вес|Масса|Размеры|Габариты|Мощность|Емкость|Ёмкость|Загрузка|Диагональ|Разрешение|Экран|Память|Аккумулятор|Батарея|Объем|Объём|Уровень шума|Энергопотребление|Процессор|Камера)"
                   r"[^<>{}\n]{0,25}?[:\s]\s*([0-9][0-9.,]*\s*(?:кг|Вт|мм|см|л|дБ|ГБ|Гб|мАч|Гц|дюйм|″|МП|Мп|кВт)\b)", re.I)


def prose_pairs(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return len(LABEL.findall(" ".join(soup.get_text(" ").split())))


def main() -> None:
    categories = load("raw/samsung_categories.json")
    proposals = load("raw/selection_proposal.json")["proposals"]
    b1, b1b = load("raw/batch1_result.json"), load("raw/batch1b_result.json")
    cats, r1, r1b = b1["categories"], b1["categories"], b1b["result"]

    tv, ph, tab, vac, wash = cats["Телевизоры"], cats["Смартфоны"], cats["Планшеты"], cats["Пылесосы"], cats["Стиральные машины"]
    tv_html, s25_html = body("batch1", "qe48s85haexce/"), body("batch1", "galaxy-s25-ultra/")
    vac_html, wash_html, a37_html = body("batch1", "vc18m21d0vg-ev/"), body("batch1", "wd10t754cbx-ld/"), body("batch1b", "a376edggskz/")
    vac_kk = vac["page"]["document"]
    table = [
        {"category": "Телевизоры", "card": tv["chosen"], "official_page": tv["page"]["url"], "exact_page": "да: код в адресе карты сайта, заголовке и тексте; sku в JSON-LD нет", "currency": f"да: заголовок «(2026)»; серия s85h названа на {tv['hub']['url'].split('/kz_ru/')[1]}",
         "specs": f"структурных нет; отрывочные значения в тексте: {prose_pairs(tv_html)}", "photos": assets(tv_html, "qe48s85haexce"), "instruction": "русское руководство пользователя, 330 стр., подтверждено по содержимому; модель в тексте не названа (общее для линейки), связь — ссылка на официальной странице (ModelName=QE48S85HAE)",
         "requests": 4},
        {"category": "Смартфоны", "card": "Galaxy A37 (строки каталога SM-A376E…INS)", "official_page": r1b["a37"]["url"], "exact_page": f"только базовая модель: страница KZ — {r1b['a37']['json_ld_fields']['sku'][0]} (256 ГБ, зелёный), в каталоге строки с кодом INS",
         "currency": "да: страница есть на официальном хабе galaxy-a, серия A37 новее A36/A56/A26 из каталога (на том же хабе A17, A27, A37, A57)", "specs": f"JSON-LD: 1 свойство; отрывочные значения в тексте: {prose_pairs(a37_html)}; таблицы нет", "photos": assets(a37_html, "sma376edggskz"), "instruction": "ссылки на инструкцию на странице нет (поддержка Samsung отрисовывается на клиенте)",
         "requests": 5 + 1, "note": "по заявленному правилу сначала взята семейная страница Galaxy S25 Ultra (прошлое поколение, без sku и без JSON-LD Product, без ссылок на документы); вторая карточка в категории — исправление, оговорено заранее"},
        {"category": "Планшеты", "card": "нет подходящей новинки", "official_page": "", "exact_page": "нет", "currency": "нет: на официальном списке планшетов A11, A11+, S10 Lite, S11 Ultra; строк каталога (Tab S10+/Ultra, SM-X826/X926) там нет",
         "specs": "—", "photos": "—", "instruction": "—", "requests": 2, "note": "заявленное правило «серия tab s10» совпало с Galaxy Tab S10 Lite (SM-X406), а это другая модель; следующий запрос ушёл на адрес картинки из встроенного JSON хаба и вернул 404 (1 зря потраченный запрос). Вывод правильный: каталожных планшетов на текущем списке нет, категория остаётся в очереди."},
        {"category": "Пылесосы", "card": vac["chosen"], "official_page": vac["page"]["url"], "exact_page": "да: карта сайта + JSON-LD sku = артикул каталога", "currency": "не требуется (бытовая техника)",
         "specs": f"JSON-LD: только имя/sku/описание; отрывочные значения в тексте: {prose_pairs(vac_html)}", "photos": assets(vac_html, "vc18m21d0vgev"), "instruction": "русская инструкция, 20 стр., подтверждена по содержимому; модель названа кодом SC18M21D0VG — так Samsung называет документ (ModelName на ссылке), а не VC18M21D0VG; казахская версия тоже есть на странице",
         "requests": 3, "note": "первый кандидат VC18M2150SG/EV в карте сайта не найден — по заявленному порядку взят следующий; из двух ссылок сначала попала казахская, русская загружена отдельным объявленным шагом 1b"},
        {"category": "Стиральные машины", "card": wash["chosen"], "official_page": wash["page"]["url"], "exact_page": "да: карта сайта + JSON-LD sku = артикул каталога", "currency": "не требуется (бытовая техника)",
         "specs": f"JSON-LD: только имя/sku/описание; отрывочные значения в тексте: {prose_pairs(wash_html)}", "photos": assets(wash_html, "wd10t754cbxld"), "instruction": "единственная ссылка — файл 28 МБ с «UZ» в имени; он больше лимита 25 МБ и не проверен — инструкция не подтверждена",
         "requests": 2},
        {"category": "Микроволновые печи", "card": "MS23K3614AK/BW", "official_page": "https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/", "exact_page": "да (этап 8.4): JSON-LD sku = артикул, цвет на странице", "currency": "не требуется (бытовая техника)",
         "specs": "мощность потребления 1150 Вт, выходная 800 Вт, объём 23 л (текст); остальное — на клиенте", "photos": "1 (1164×776 PNG, проверено)", "instruction": "80 стр., подтверждена по содержимому (этап 8.6): RU/UK/KK/UZ, модель названа полным кодом с цветом", "requests": 0, "note": "прежние доказательства, новых запросов нет"},
    ]
    (STAGE / "raw/batch1_table.json").write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def cell(v):
        return v if isinstance(v, str) else f"{v['photo_assets']} фото-актив(ов), 3D-моделей {v['three_d_models']}"

    lines = ["| Категория | Карточка | Точная официальная страница | Характеристики | Фото | Инструкция |", "|---|---|---|---|---|---|"]
    for t in table:
        lines.append(f"| {t['category']} | {t['card']} | {t['exact_page']}{'; актуальность: ' + t['currency'] if t['currency'] not in ('—',) else ''} | {t['specs']} | {cell(t['photos'])} | {t['instruction']} |")
    cat_lines = ["| № | Категория | Строк | Класс | Пакет | Предлагаемый товар | Почему |", "|---|---|---|---|---|---|---|"]
    by_cat = {p["category"]: p for p in proposals}
    for c in categories["categories"]:
        p = by_cat[c["category"]]
        article = p["article"] or "— (нет подходящей новинки в каталоге)"
        reason = re.sub(r"\s+", " ", p["reason"])[:230] + ("…" if len(p["reason"]) > 230 else "")
        cat_lines.append(f"| {c['queue_position']} | {c['category']} | {c['rows']} | {'быт. техника' if c['class'] == 'appliance' else 'электроника'} | {'1' if c['batch'] == 1 else 'очередь'} | {article}{' (предв.)' if p['provisional'] and p['article'] else ''} | {reason} |")

    steps = b1["steps"] + b1b["steps"]
    total = b1["requests_made"] + b1b["requests_made"]
    text = f"""# Этап 24: Samsung — категории, выбор товаров, первая партия

Правило владельца: по всему бренду проверить по одному товару из каждой категории, небольшими партиями; партия 1 — шесть категорий из предложения этапа 23, остальные 25 стоят в очереди (не отменены). Массовой обработки строк каталога нет. Реальных запросов в этом этапе: **{total}** ({b1['requests_made']} в партии 1 при объявленных 30 и {b1b['requests_made']} в поправке 1b при объявленных 3), блокировок нет.

## 1. Категории Samsung в каталоге (офлайн) и предложение по одному товару
В каталоге {categories['catalog_rows']} строк Samsung в {len(categories['categories'])} категориях. Правила выбора записаны до запросов (`scripts/01_categories_and_selection.py`): бытовая техника — старые модели допустимы, приоритет строкам с уже наблюдавшейся официальной страницей, затем наименьший SHA-256; электроника (телевизоры, смартфоны, планшеты, носимая техника, аудио, накопители, аксессуары) — только актуальные модели, наименьший хеш не используется вслепую; для смартфонов и планшетов берутся строки с кодом региона SKZ (его использует официальный сайт KZ) и самый новый год выпуска. Исключены: телевизор N5300 (`UE43N5300AUXCE`, исключён из прежнего пилота) и Galaxy Buds3 FE (в каталоге нет такой строки). Для микроволновых печей используется сохранённый результат MS23K3614AK/BW.

{chr(10).join(cat_lines)}

«предв.» — кандидат предварительный: его актуальность и наличие точной страницы проверяются в пакете своей категории; при отрицательном результате категория остаётся в очереди без карточки. Для носимой техники и наушников в каталоге нет новинок с кодом KZ/CIS (только Watch7/FE, Fit 3, Buds2/Live/Pro), поэтому кандидата нет.

## 2. Партия 1: что найдено
Маршруты — только наблюдаемые официальные: `vd-sitemap.xml` (622 адреса) и `da-sitemap.xml` (682 адреса), хабы `tvs/best-2026`, `smartphones/all-smartphones`, `smartphones/galaxy-a`, `tablets/all-tablets`, ссылки на документы, напечатанные самой страницей (`org.downloadcenter.samsung.com … CDCttType=UM`).

{chr(10).join(lines)}

Пояснения по строкам:
""" + "\n".join(f"- **{t['category']}**: {t['note']}" for t in table if t.get("note")) + f"""

## 3. Что умеет общий экстрактор, а что требует адаптера Samsung
Общий экстрактор (`adapters/structured_page.py`) применён к сохранённым страницам без изменений.

| Слой | Общий экстрактор | Нужно в адаптере Samsung |
|---|---|---|
| Идентичность | JSON-LD Product (имя, sku, картинка) работает на пылесосе, стиральной машине, смартфоне A37 (и на микроволновке, этап 8.4). На телевизоре 2026 года узла Product нет: `ItemPage` ссылается сам на себя, sku нет; на семейной странице смартфона (S25 Ultra) только Article/Video/FAQ | идентичность по адресу карты сайта, заголовку, тексту и году «(2026)» в заголовке; сравнение sku с артикулом каталога с учётом региона (`…SKZ` против `…INS`) и цвета (`/BW`) |
| Поиск страницы | — | карта `vd-sitemap.xml` (телевизоры) и `da-sitemap.xml` (техника) по подстроке артикула; смартфоны и планшеты в картах отсутствуют — только хабы с ссылками, содержащими код; на хабе есть адреса картинок, их нельзя принимать за страницы |
| Характеристики | таблица `dl/dt/dd` и `details`: **0 строк на всех страницах** — панель характеристик отрисовывается на клиенте | разбор отрывочных значений из текста (5–11 пар на страницу) или поиск данных панели; без этого карточка неполная |
| Фото | галерея по `data-media-id`/`data-fancybox` (Shopify) — на Samsung не срабатывает; JSON-LD image даёт 1 миниатюру | правило по `images.samsung.com/...{{код}}...`: один актив встречается в нескольких размерах (`$1164_776_PNG$`, `$624_468_PNG$`), у телевизора среди активов есть `.glb`/`.usdz` (3D-модели) — их надо исключать |
| Инструкции | нет | ссылки `…ContentsFile.aspx?…CDCttType=UM&ModelName=…` на странице; язык в имени файла (`_RU_`, `_KK_`, `_UZ_`, `RUS`, `ENG`) — годится лишь для порядка запросов, язык — по тексту; файлы 5–28 МБ, 330 страниц (лимит 25 МБ мал); модель в документе может называться иначе (SC↔VC) или не называться вовсе (общее руководство линейки); маска семейства (`SC18M21****`) — как у LG |
| Актуальность | — | хабы «2026» и списки категорий; год в заголовке страницы |

## 4. Расхождения с объявленным и ошибки
- Планшеты: правило «серия tab s10» совпало с S10 Lite; 1 запрос ушёл на адрес картинки (404).
- Смартфоны: по объявленному правилу выбрана семейная страница S25 Ultra; затем исправление на A37 (вторая карточка в категории), объявлено до запроса (`raw/batch1b_declaration.json`).
- Пылесосы: первый кандидат не найден в карте сайта; язык первой ссылки казахский — русская загружена шагом 1b.
- Стиральная машина: файл больше лимита — инструкция не проверена.
- Правило приёма русской инструкции без модели в тексте (ответ 4 по LG) для Samsung в код не переносилось: телевизор подпадает под него по критериям (русская инструкция по содержимому, официальная страница с точным артикулом печатает ссылку, конфликтующей модели нет) — это статус, а не сохранённый документ.

## 5. Очередь
Остаётся 25 категорий в порядке размера каталога (таблица выше); не отменены. Ближайшая партия 2, когда скажете: Холодильники, Духовые шкафы, Сплит-системы, Варочные панели (бытовая техника, страницы Духовых/Сплит-систем/Варочных уже наблюдались в карте сайта) и Мониторы, Саундбары (актуальность проверяется). Что стоит сделать в коде до партии 2 — только по вашему указанию: адаптер Samsung (поиск страницы, sku с регионом, фото, инструкции).
"""
    (STAGE / "report.md").write_text(text, encoding="utf-8")
    print(text[:1500])


if __name__ == "__main__":
    with offline_only():
        main()
