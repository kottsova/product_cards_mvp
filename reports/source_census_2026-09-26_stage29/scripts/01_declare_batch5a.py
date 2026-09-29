"""Stage 29 step 1 -- OFFLINE. Declares group 5A (memory storage) of the Samsung check BEFORE any request: exactly one product in each of four categories, the request budget, the stop rules.

The four products are the ones proposed in Stage 28 (raw/batch5_proposal.json there). Nothing else is selected. Group 5B is not run; cables stay a candidate for a later batch.

Output: raw/batch5a_declaration.json
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


def main() -> None:
    proposal = json.loads((ROOT / "reports/source_census_2026-09-26_stage28/raw/batch5_proposal.json").read_text(encoding="utf-8"))
    group = proposal["groups"]["5A (memory storage)"]["products"]
    import _samsung_replay as R
    from product_tool.adapters.samsung_source import route_for

    products = {}
    for category, item in group.items():
        unit = R.catalog_units({item["article"]})[item["article"]]
        kind, addresses, _ = route_for(item["article"], unit["category"])
        products[category] = {"article": item["article"], "title": unit["title"], "catalog_row": unit["catalog_row"], "page_url_listed_in_saved_sitemap": item["page_url"], "route_kind": kind, "route_addresses_in_order": list(addresses),
                              "reason": "наименьший SHA-256 артикула среди строк категории с чистым артикулом и точной страницей в сохранённой карте memory-sitemap.xml (правило партий 2 и 4)"}
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": "29 / group 5A", "brand": "Samsung", "market": "kz_ru",
        "path": "the ordinary path: Excel upload -> confirmed batch -> one search job per product (stages 1, 2, 3, 4, 6) -> worker.run_once() with the default Samsung adapter -> export through the web route",
        "products": products,
        "budget": {
            "max_real_requests_total": 13, "max_real_requests_per_product": 7, "pacing_seconds": 1.5, "document_cap_mb": 40, "hosts": ["www.samsung.com", "org.downloadcenter.samsung.com", "downloadcenter.samsung.com"],
            "plan": {"sitemaps": "1: memory-sitemap.xml (all four rows are looked up there first), read once for the whole batch; im-sitemap.xml only if memory-sitemap.xml has no page",
                     "product_pages": 4, "instruction_files": "at most 2 per product (8): the file whose name says RU first; only files the official page itself prints; nothing else is fetched",
                     "buy_pages": "0 expected (a buy page is asked for only when the page's own markup names one and the page has no gallery; the per-row cap still applies)", "images": 0},
            "enforced_by": "PolicyAwareSession + RequestBudget (max_total 13, max_per_row 7): a request over the budget is refused before it is made"},
        "stop_rules": {"statuses": "a 401, 403 or 429, or a confirmed challenge, on any Samsung host stops that host in <workdir>/samsung_fetch_log.json; no further request is made to it, in this run or a later one",
                       "batch": "after every job the batch script re-reads the log; if any host is stopped, no further job is started (the rest stay queued)",
                       "no_retries_elsewhere": "no other host, no changed headers, no guessed address"},
        "url_construction": "none: a page address comes only from the official sitemap (a code in the address only makes the page a candidate; the exact variant is confirmed from the fetched page's content); a document address only from a link the official page prints",
        "dealer": {"source": "DNS", "requests": 0, "rule": "no verified exact dealer URL exists for these products, so the dealer adapter makes no request and only writes the ready-to-ask link request for the missing fields"},
        "recording": "every real response is saved (gzip + index) for offline replay; document bodies are then reduced to their extracted text (docs_extract)",
        "not_done": "group 5B (watch, band, cable); the eight categories without an observed page; any bulk processing of catalog rows",
    }
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    (STAGE / "raw/batch5a_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for category, item in products.items():
        print(f"{category:<26} {item['article']:<16} {item['route_kind']} {item['route_addresses_in_order'][0].rsplit('/', 1)[-1]}")
    print("declared_at", declaration["declared_at"], "budget", declaration["budget"]["max_real_requests_total"])


if __name__ == "__main__":
    with offline_only():
        main()
