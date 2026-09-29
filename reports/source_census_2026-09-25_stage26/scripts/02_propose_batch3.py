"""Stage 26 step 2 -- OFFLINE, zero requests. A PROPOSAL for the next small Samsung batch: one product per category, from the queued categories only; nothing is requested and nothing is declared as done.

Rule (the one Stage 25 used for batch 2): among the catalog rows of a queued category with a clean article that have an EXACT page in the saved full Samsung sitemaps (kz_ru/vd-sitemap.xml,
kz_ru/da-sitemap.xml, fetched in Stage 24), the smallest SHA-256 of the upper-cased article. A category with no such row has no established official route yet: it is listed with the reason,
not guessed. The owner's rules stay: appliances may be old; phones, tablets and wearables need a current model; other technology is judged product by product.

Output: raw/batch3_proposal.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S24 = ROOT / "reports/source_census_2026-09-25_stage24"
sys.path.insert(0, str(ROOT))

from product_tool.adapters import samsung  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

CHECKED = {"Телевизоры", "Смартфоны", "Планшеты", "Пылесосы", "Стиральные машины", "Микроволновые печи", "Холодильники", "Духовые шкафы", "Сплит-системы", "Варочные панели", "Мониторы", "Саундбары"}
WEARABLES = {"Смарт-часы", "Фитнес-браслеты", "Наушники беспроводные", "Гарнитуры"}
APPLIANCES = {"Машины посудомоечные", "Сушильные машины", "Роботы-пылесосы"}


def saved(name: str) -> str:
    base = S24 / "batch1/responses"
    for line in (base / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["url"].endswith(name) and entry["saved_as"]:
            with gzip.open(base / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                return handle.read()
    raise SystemExit(name)


def main() -> None:
    urls = sitemap_locs(saved("vd-sitemap.xml")) + sitemap_locs(saved("da-sitemap.xml"))
    units = [json.loads(line) for line in (ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    categories: dict[str, list] = {}
    for unit in (u for u in units if u["brand"] == "Samsung"):
        categories.setdefault(unit["category"], []).append(unit)
    queued = {}
    for category, rows in sorted(categories.items(), key=lambda item: (-len(item[1]), item[0])):
        if category in CHECKED:
            continue
        clean = [u for u in rows if re.fullmatch(r"[A-Z0-9][A-Z0-9\-]*(?:/[A-Z0-9]+)?", u["seller_sku"].upper()) and "_" not in u["seller_sku"]]
        hits = sorted((hashlib.sha256(u["seller_sku"].upper().encode()).hexdigest(), u["seller_sku"], samsung.find_in_sitemap(urls, u["seller_sku"]), u) for u in clean)
        hits = [h for h in hits if h[2]]
        entry = {"catalog_rows": len(rows), "clean_articles": len(clean), "rows_with_exact_page_in_saved_sitemaps": len(hits),
                 "class": "wearable (novelty rule)" if category in WEARABLES else "appliance (old models allowed)" if category in APPLIANCES else "other technology (judged per product)"}
        if hits:
            _, article, page, unit = hits[0]
            entry["proposed"] = {"article": article, "title": unit["title"], "catalog_row": unit["catalog_row"], "page_url": page}
        else:
            entry["route"] = ("страницы нет в сохранённых картах сайта, хаба нет: сначала небольшой объявленный поиск маршрута (несколько запросов), затем карточка" if category not in WEARABLES else
                              "носимая техника: сначала нужен официальный список, подтверждающий текущую модель; хаб для неё не установлен")
        queued[category] = entry
    proposed = {c: e["proposed"] for c, e in queued.items() if "proposed" in e}
    n = len(proposed)
    declaration = {
        "proposed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "PROPOSAL -- nothing has been requested", "brand": "Samsung", "market": "kz_ru", "path": "worker.run_once() with the Samsung adapter, stages 1-4 and 6",
        "products": proposed,
        "request_budget": {"sitemaps": "2 (vd и da, каждая читается один раз на всю партию)", "product_pages": n, "instruction_files": f"не более {n * 2} (адаптер читает не более 2 файлов на товар и останавливается на первой русской инструкции)", "per_row_cap": 7,
                           "total_cap": 2 + n + n * 2, "pacing_seconds": 1.5, "document_cap_mb": 40},
        "stop_rule": "401/403/429 or a confirmed challenge on a Samsung host stops it in <data dir>/samsung_fetch_log.json and ends the batch", "url_construction": "none", "dealer": "DNS only on a pre-verified exact URL: none exists for these products, so 0 dealer requests",
        "queued_categories": queued,
    }
    (STAGE / "raw/batch3_proposal.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for category, item in proposed.items():
        print(f"{category:<24} {item['article']:<18} {item['page_url'].split('/kz_ru/')[1][:70]}")
    print(len(queued), "queued categories;", n, "with an exact page in the saved sitemaps")


if __name__ == "__main__":
    with offline_only():
        main()
