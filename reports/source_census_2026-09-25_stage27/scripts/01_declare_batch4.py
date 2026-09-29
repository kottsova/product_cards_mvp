"""Stage 27 step 1 -- OFFLINE. Declares batch 4 of the Samsung check BEFORE any request: exactly one product in each of four categories, the request budget, and the stop rules.

The four products are the ones proposed in Stage 26 (raw/batch3_proposal.json there): for each queued category with an exact page in the saved full Samsung sitemaps, the smallest SHA-256
of the article. Nothing else is selected; the other 15 queued categories stay queued.

Output: raw/batch4_declaration.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from product_tool.offline_guard import offline_only  # noqa: E402

CATEGORIES = ["Машины посудомоечные", "Сушильные машины", "Колонки", "Роботы-пылесосы"]


def main() -> None:
    proposal = json.loads((ROOT / "reports/source_census_2026-09-25_stage26/raw/batch3_proposal.json").read_text(encoding="utf-8"))
    import _samsung_replay as R
    from product_tool.adapters.samsung_source import route_for

    products = {}
    for category in CATEGORIES:
        item = proposal["products"][category]
        unit = R.catalog_units({item["article"]})[item["article"]]
        kind, addresses, _ = route_for(item["article"], unit["category"])
        products[category] = {"article": item["article"], "title": unit["title"], "catalog_row": unit["catalog_row"], "page_url_listed_in_saved_sitemaps": item["page_url"], "route_kind": kind, "route_addresses_in_order": list(addresses),
                              "reason": "наименьший SHA-256 артикула среди строк категории с чистым артикулом и точной страницей в сохранённых полных картах сайта (правило партии 2)"}
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": "27 / batch 4", "brand": "Samsung", "market": "kz_ru",
        "path": "the ordinary path: Excel upload -> confirmed batch -> one search job per product (stages 1, 2, 3, 4, 6) -> worker.run_once() with the default Samsung adapter -> export through the web route",
        "products": products,
        "budget": {
            "max_real_requests_total": 14, "max_real_requests_per_product": 7, "pacing_seconds": 1.5, "document_cap_mb": 40, "hosts": ["www.samsung.com", "org.downloadcenter.samsung.com", "downloadcenter.samsung.com"],
            "plan": {"sitemaps": "2 at most: da-sitemap.xml (appliance rows are looked up there first) and vd-sitemap.xml (the speaker row is looked up there first; the other sitemap only if the first has no page); each read once for the whole batch",
                     "product_pages": 4, "instruction_files": "at most 2 per product (8): the file whose name says RU first; the search stops at the first Russian instruction accepted on the exact page's tie, or at one a weaker page tie leaves to a person; nothing else is fetched",
                     "buy_pages": 0, "images": 0},
            "enforced_by": "PolicyAwareSession + RequestBudget (max_total 14, max_per_row 7): a request over the budget is refused before it is made"},
        "stop_rules": {"statuses": "a 401, 403 or 429, or a confirmed challenge, on any Samsung host stops that host in <workdir>/samsung_fetch_log.json; no further request is made to it, in this run or a later one",
                       "batch": "after every job the batch script re-reads the log; if any host is stopped, no further job is started (the rest stay queued)",
                       "no_retries_elsewhere": "no other host, no changed headers, no guessed address"},
        "url_construction": "none: a page address comes only from the official sitemap; a document address only from a link the official page prints",
        "dealer": {"source": "DNS", "requests": 0, "rule": "no verified exact dealer URL exists for these products, so the dealer adapter makes no request and only writes the ready-to-ask request for missing fields"},
        "recording": "every real response is saved (gzip + index) for offline replay; document bodies are then reduced to their extracted text (docs_extract) as in Stages 24-25",
        "instruction_rules_applied": "Stage 27 owner decisions: a Russian instruction that names no model is accepted with the mark 'связь с моделью подтверждена точной официальной страницей' only on a page that shows the full article in its markup or title; a PDF naming another code is accepted only when the page's own data declares that code as its model name beside the catalog code as its model code, else it stays for a person; a family mask is accepted and always marked",
        "photo_rule_applied": "gallery selected only when the page's markup or title shows the article; otherwise only photos whose own asset path names exactly the catalog code, or photos a person confirms",
        "not_done": "the other 15 queued categories; any bulk processing of catalog rows; a new LG pilot",
    }
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    (STAGE / "raw/batch4_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for category, item in products.items():
        print(f"{category:<22} {item['article']:<18} {item['route_kind']} {item['route_addresses_in_order'][0].rsplit('/', 1)[-1]}")
    print("declared_at", declaration["declared_at"], "budget", declaration["budget"]["max_real_requests_total"])


if __name__ == "__main__":
    with offline_only():
        main()
