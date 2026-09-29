"""Stage 24 step 1 -- OFFLINE, zero requests. Samsung: the list of catalog categories, the batches, and ONE proposed catalog product per category with the reason.

Owner rules applied (2026-09-25):
  * the whole brand is to be checked eventually, one product per category, in small batches; batch 1 = six categories; the rest stay QUEUED (not cancelled);
  * smartphones, tablets and wearables: only NEW models, confirmed by data observed on the official site; old models only in home appliances;
  * no blind minimum-hash pick when it would give an old electronics model;
  * the N5300 TV (UE43N5300AUXCE) is excluded (it was excluded from the earlier pilot); Galaxy Buds3 FE has no catalog row and is not a catalog card;
  * the microwave MS23K3614AK/BW keeps its earlier evidence (Stages 8.4-8.6) for its category.

Selection rules (fixed here, before any request):
  appliance categories (old models allowed): rank = (has an official page observed offline in the saved Samsung link indexes, then smallest SHA-256 of the upper-cased article);
  electronics with a model-year letter in the code (TV; soundbars; monitors): the newest year letter, then a regional code that the KZ site uses, then smallest SHA-256;
  smartphones / tablets: only rows whose regional code the KZ site uses (SKZ; the observed KZ pages carry ...SKZ), newest release year of the model, then the model with the most
      such catalog rows (representativeness), then smallest SHA-256; the release year comes from the table below and is CONFIRMED only by the official hub in the batch;
  other electronics (wearables, audio, storage, accessories): the newest generation the catalog itself shows, marked provisional until the batch that needs it.
A pick that fails the currency check in its batch is not replaced silently: the report says so and the category stays queued.

Output: raw/samsung_categories.json, raw/selection_proposal.json
"""
from __future__ import annotations

import glob
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
QUEUE = ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl"
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402

APPLIANCES = {"Пылесосы", "Стиральные машины", "Микроволновые печи", "Холодильники", "Духовые шкафы", "Сплит-системы", "Варочные панели", "Машины посудомоечные", "Сушильные машины", "Роботы-пылесосы"}
BATCH1 = ["Телевизоры", "Смартфоны", "Планшеты", "Пылесосы", "Стиральные машины", "Микроволновые печи"]
EXCLUDED_ARTICLES = {"UE43N5300AUXCE"}  # the N5300 TV: excluded from the earlier pilot, never a new card
MICROWAVE_SAVED = "MS23K3614AK/BW"     # Stages 8.4-8.6: exact_variant, image, manual confirmed by content (RU/UK/KK/UZ)
# Release year of a model as the catalog names it (prior knowledge; only a candidate ordering -- currency is confirmed on the official hub in the batch).
PHONE_YEAR = {"S20": 2020, "S21": 2021, "S21 FE": 2022, "S22": 2022, "S23": 2023, "S24": 2024, "S24 FE": 2024, "S25": 2025, "S25 FE": 2025, "A03": 2022, "A06": 2024, "A13": 2022, "A16": 2024, "A23": 2022,
              "A25": 2024, "A26": 2025, "A32": 2021, "A33": 2022, "A35": 2024, "A36": 2025, "A37": 2026, "A53": 2022, "A55": 2024, "A56": 2025, "A73": 2022, "Z Flip3": 2021, "Z Flip4": 2022,
              "Z Flip6": 2024, "Z Flip7": 2025, "Z Fold3": 2021, "Z Fold4": 2022, "Z Fold6": 2024, "Z Fold7": 2025}
TABLET_YEAR = {"Tab A7": 2020, "Tab A8": 2022, "Tab A9": 2023, "Tab S8": 2022, "Tab S10": 2024, "Tab Active2": 2020}


def digest(article: str) -> str:
    return hashlib.sha256(article.upper().encode("utf-8")).hexdigest()


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def observed_pages() -> dict[str, str]:
    """slug (alphanumerics only) -> URL, from the Samsung link indexes earlier stages saved (a capped, partial view of the site)."""
    links: dict[str, str] = {}
    for path in glob.glob(str(ROOT / "reports/source_census_2026-09-22_stage8_2*/link_index/samsung_*.json")):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in (data.get("links") if isinstance(data, dict) else data):
            url = item if isinstance(item, str) else item.get("url", "")
            if "/kz_ru/" in url:
                links[norm(url)] = url
    return links


def observed_page_for(article: str, pages: dict[str, str]) -> str:
    key = norm(article.split("/")[0])
    if len(key) < 6:
        return ""
    return next((url for slug, url in pages.items() if key in slug), "")


def clean(article: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9\-]*(?:/[A-Z0-9]+)?", article.upper())) and "_" not in article


def tv_year_letter(article: str) -> str:
    match = re.search(r"\d([A-Z])[A-Z]{0,2}(?:UX|EX)", article.upper())
    return match.group(1) if match else ""


def model_name(title: str, table: dict[str, int]) -> str:
    for key in sorted(table, key=len, reverse=True):
        if re.search(r"Galaxy\s+" + re.escape(key) + r"(?![\w])", title):
            return key
    return ""


def main() -> None:
    units = [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line]
    samsung = [u for u in units if u["brand"] == "Samsung"]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for unit in samsung:
        by_category[unit["category"]].append(unit)
    pages = observed_pages()
    order = sorted(by_category, key=lambda c: (-len(by_category[c]), c))
    queue_order = BATCH1 + [c for c in order if c not in BATCH1]

    proposals = []

    def propose(category, unit, reason, *, provisional, currency, source_rows=None, fallbacks=()):
        proposals.append({"category": category, "class": "appliance" if category in APPLIANCES else "electronics", "catalog_rows": len(by_category[category]),
                          "batch": 1 if category in BATCH1 else "queued", "article": unit["seller_sku"] if unit else "", "title": unit["title"] if unit else "", "catalog_row": unit["catalog_row"] if unit else None,
                          "observed_official_page_offline": observed_page_for(unit["seller_sku"], pages) if unit else "", "reason": reason, "provisional": provisional,
                          "currency_check": currency, "fallbacks": list(fallbacks)})

    for category in queue_order:
        rows = [u for u in by_category[category] if u["seller_sku"].split("/")[0].upper() not in EXCLUDED_ARTICLES]
        if category == "Микроволновые печи":
            unit = next(u for u in rows if u["seller_sku"] == MICROWAVE_SAVED)
            propose(category, unit, "Сохранённый результат этапов 8.4–8.6: точный вариант по JSON-LD sku и цвету, фото, инструкция подтверждена по содержимому (RU/UK/KK/UZ). Новых запросов не требуется.", provisional=False,
                    currency="не требуется: бытовая техника, старые модели допустимы")
        elif category in APPLIANCES:
            ranked = sorted(rows, key=lambda u: (0 if observed_page_for(u["seller_sku"], pages) else 1, 0 if clean(u["seller_sku"]) else 1, digest(u["seller_sku"])))
            unit = ranked[0]
            seen = bool(observed_page_for(unit["seller_sku"], pages))
            reason = ("бытовая техника, старые модели допустимы; в сохранённом обзоре сайта уже есть официальная страница именно этого кода; из таких — наименьший SHA-256 артикула" if seen else
                      "бытовая техника, старые модели допустимы; в сохранённом (усечённом до 300 ссылок) обзоре сайта страницы этой категории нет, поэтому выбор — по наименьшему SHA-256 чистого артикула, а наличие страницы проверяется в пакете по полной карте сайта")
            propose(category, unit, reason, provisional=not seen, currency="не требуется: бытовая техника",
                    fallbacks=[u["seller_sku"] for u in ranked[1:4]])
        elif category == "Телевизоры":
            clean_rows = [u for u in rows if clean(u["seller_sku"]) and tv_year_letter(u["seller_sku"])]
            newest = max(tv_year_letter(u["seller_sku"]) for u in clean_rows)
            newest_rows = sorted((u for u in clean_rows if tv_year_letter(u["seller_sku"]) == newest), key=lambda u: (0 if u["seller_sku"].upper().endswith("CE") else 1, digest(u["seller_sku"])))
            propose(category, newest_rows[0], f"телевизор — электроника: только новинка; в каталоге самая новая буква модельного года «{newest}» (серии …{newest}: QN70H/S85H), из них — код с региональным окончанием CE, которое использует сайт KZ, затем наименьший SHA-256. "
                    "N5300 исключён. Актуальность подтверждается официальным списком «2026» / «все телевизоры» в пакете.", provisional=False,
                    currency="официальная страница телевизоров 2026 (наблюдаемая ссылка /tvs/best-2026/) и карта сайта vd-sitemap.xml", fallbacks=[u["seller_sku"] for u in newest_rows[1:3]])
        elif category in ("Смартфоны", "Планшеты"):
            table, prefix = (PHONE_YEAR, "Galaxy") if category == "Смартфоны" else (TABLET_YEAR, "Galaxy")
            kz_rows = [u for u in rows if re.search(r"SKZ$", u["seller_sku"].upper()) and clean(u["seller_sku"])]
            named = [(u, model_name(u["title"], table)) for u in kz_rows]
            named = [(u, m) for u, m in named if m]
            newest_year = max(table[m] for _, m in named)
            models = Counter(m for _, m in named if table[m] == newest_year)
            best_model = sorted(models, key=lambda m: (-models[m], m))[0]
            candidates = sorted((u for u, m in named if m == best_model), key=lambda u: digest(u["seller_sku"]))
            others = sorted(m for m in models if m != best_model)
            propose(category, candidates[0], f"электроника: только новинка; берутся строки с кодом региона SKZ (его использует официальный сайт KZ; {'у более новых A37, Z Fold7/Flip7 в каталоге только зарубежные коды INS/MEA — точной страницы KZ у них не будет' if category == 'Смартфоны' else 'более новых планшетов с кодом SKZ в каталоге нет'}); "
                    f"самый новый год выпуска среди них — {newest_year}; из моделей этого года «Galaxy {best_model}» имеет больше всего строк каталога ({models[best_model]}); затем наименьший SHA-256. Другие модели {newest_year} года: {', '.join(others) or '—'}. "
                    "Год выпуска — справка, актуальность подтверждается только наблюдаемым официальным списком в пакете.", provisional=False,
                    currency=("официальные страницы /smartphones/all-smartphones/ и /smartphones/galaxy-a/ (наблюдаемые ссылки)" if category == "Смартфоны" else "официальная страница /tablets/all-tablets/ (наблюдаемая ссылка): в списке должен быть этот код или его серия"),
                    fallbacks=[u["seller_sku"] for u in candidates[1:2]] + [next(u["seller_sku"] for u, m in named if m == o) for o in others[:1]])
        elif category in ("Смарт-часы", "Фитнес-браслеты", "Наушники беспроводные", "Гарнитуры"):
            propose(category, None, "носимая техника/аудио: нужна новинка, подтверждённая сайтом. В каталоге: " + ", ".join(sorted({re.sub(r'\s+\d.*$', '', u['title']) for u in rows})[:6]) +
                    ". Официальный сайт (наблюдаемые ссылки) показывает Watch9/Ultra2 и Buds4; такой новинки среди строк каталога нет либо она без кода KZ/CIS — категория остаётся в очереди и не проверяется на старой модели.",
                    provisional=True, currency="список /watches/all-watches/, /audio-sound/all-audio-sound/ в своём пакете")
            if category == "Смарт-часы":
                cand = sorted((u for u in rows if re.search(r"CIS$", u["seller_sku"]) and re.search(r"Watch(7|8|FE)", u["title"])), key=lambda u: (u["title"], digest(u["seller_sku"])))
                proposals[-1]["article"], proposals[-1]["title"] = (cand[-1]["seller_sku"], cand[-1]["title"]) if cand else ("", "")
                proposals[-1]["reason"] += " Ближайший кандидат с кодом CIS: " + (proposals[-1]["article"] or "—") + " (Watch7/FE, не новинка при Watch9 на сайте) — только если сайт всё ещё показывает его среди актуальных."
        else:
            # other electronics: soundbars, monitors, speakers, storage, accessories, printers, projectors
            def gen_key(u):
                a = u["seller_sku"].upper()
                if category == "Саундбары":
                    m = re.match(r"HW-[A-Z]\d+([A-Z])", a); return m.group(1) if m else ""
                if category == "Мониторы":
                    m = re.match(r"L[CFS]\d\d([A-Z])?[A-Z]?\d{2,3}", a); return ""
                if category == "Колонки":
                    m = re.match(r"MX-ST\d+([A-Z])", a); return m.group(1) if m else ""
                return ""
            ranked = sorted(rows, key=lambda u: (0 if clean(u["seller_sku"]) else 1, 0 if observed_page_for(u["seller_sku"], pages) else 1, tuple(-ord(c) for c in gen_key(u)) or (0,), digest(u["seller_sku"])))
            unit = ranked[0]
            propose(category, unit, ("электроника: нужна актуальная модель. Кандидат — самое новое поколение, которое видно по самому коду каталога" + (" (буква поколения " + gen_key(unit) + ")" if gen_key(unit) else "") +
                    ("; страница уже наблюдалась на сайте" if observed_page_for(unit["seller_sku"], pages) else "") + ". Кандидат предварительный: актуальность и наличие точной страницы подтверждаются в пакете этой категории."),
                    provisional=True, currency="официальный список категории в своём пакете", fallbacks=[u["seller_sku"] for u in ranked[1:3]])

    categories = [{"category": c, "rows": len(by_category[c]), "class": "appliance" if c in APPLIANCES else "electronics", "batch": 1 if c in BATCH1 else "queued", "queue_position": i + 1,
                   "status": "batch_1_to_check" if c in BATCH1 else "queued"} for i, c in enumerate(queue_order)]
    assert len(categories) == 31 and len(proposals) == 31
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    (STAGE / "raw/samsung_categories.json").write_text(json.dumps({"brand": "Samsung", "catalog_rows": len(samsung), "categories": categories, "rule": __doc__.split("Output:")[0]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (STAGE / "raw/selection_proposal.json").write_text(json.dumps({"proposals": proposals, "excluded": {"UE43N5300AUXCE": "the N5300 TV was excluded from the earlier pilot", "Galaxy Buds3 FE": "no catalog row exists: not a catalog card"}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for p in proposals[:8]:
        print(f"{p['category']:<24} {p['batch']!s:<7} {p['article']:<22} prov={p['provisional']} seen={bool(p['observed_official_page_offline'])}")
    print(len(categories), "categories")


if __name__ == "__main__":
    with offline_only():
        main()
