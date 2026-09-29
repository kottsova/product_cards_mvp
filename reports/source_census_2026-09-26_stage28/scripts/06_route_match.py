"""Stage 28 step 6 -- OFFLINE, zero requests. Matches the 15 queued categories' catalog articles against the addresses the fetched sitemaps LIST (route_study/responses, plus vd and da of Stages 24-25).

Rule (the one used for batches 2 and 4): among the catalog rows of a category with a clean article and an EXACT page listed in a sitemap, the smallest SHA-256 of the upper-cased article. For phones,
tablets and wearables a page listed in the CURRENT official sitemap is the official evidence that the model is current. A category with no such row has no observed route yet: it is listed with the
reason, and nothing is guessed.

Output: raw/route_match.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.adapters import samsung  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

S24 = ROOT / "reports/source_census_2026-09-25_stage24"
WEARABLES = {"Смарт-часы", "Фитнес-браслеты", "Наушники беспроводные", "Гарнитуры"}


def load_responses(directory: Path) -> dict[str, str]:
    result = {}
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["saved_as"] and entry["url"].endswith(".xml"):
            with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                result[entry["url"]] = handle.read()
    return result


def main() -> None:
    sitemaps = {**load_responses(S24 / "batch1/responses"), **load_responses(STAGE / "route_study/responses")}
    lists = {url.rsplit("/", 1)[-1]: sitemap_locs(text) for url, text in sitemaps.items() if not url.endswith("b2c-sitemap.xml")}
    index = sitemap_locs(next(t for u, t in sitemaps.items() if u.endswith("b2c-sitemap.xml")))
    queued = json.loads((ROOT / "reports/source_census_2026-09-25_stage26/raw/batch3_proposal.json").read_text(encoding="utf-8"))["queued_categories"]
    done_in_batch4 = {"Машины посудомоечные", "Сушильные машины", "Колонки", "Роботы-пылесосы"}
    units = [json.loads(line) for line in (ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    by_category: dict[str, list] = {}
    for unit in (u for u in units if u["brand"] == "Samsung"):
        by_category.setdefault(unit["category"], []).append(unit)
    result = {}
    for category in queued:
        if category in done_in_batch4:
            continue
        rows = by_category[category]
        clean = [u for u in rows if re.fullmatch(r"[A-Z0-9][A-Z0-9\-]*(?:/[A-Z0-9]+)?", u["seller_sku"].upper()) and "_" not in u["seller_sku"]]
        hits = []
        for unit in clean:
            for name, urls in lists.items():
                page = samsung.find_in_sitemap(urls, unit["seller_sku"])
                if page:
                    hits.append((hashlib.sha256(unit["seller_sku"].upper().encode()).hexdigest(), unit["seller_sku"], name, page, unit))
                    break
        hits.sort(key=lambda h: h[0])
        entry = {"catalog_rows": len(rows), "clean_articles": len(clean), "rows_with_exact_page": len(hits), "by_sitemap": dict(Counter(h[2] for h in hits)), "class": "wearable (novelty rule)" if category in WEARABLES else "other technology (judged per product)"}
        if hits:
            _, article, name, page, unit = hits[0]
            entry["proposed"] = {"article": article, "title": unit["title"], "catalog_row": unit["catalog_row"], "sitemap": name, "page_url": page, "section": page.split("/kz_ru/")[1].split("/")[0] + "/" + page.split("/kz_ru/")[1].split("/")[1]}
            if category in WEARABLES:
                entry["currency"] = "the exact page is listed in the current official sitemap"
        else:
            entry["reason"] = "no catalog article of this category has a page listed in any sitemap of the observed route (b2c index: memory, im, assorted, vd, da)"
        result[category] = entry
    out = {"b2c_index_lists_now": index, "sitemap_sizes": {n: len(u) for n, u in lists.items()}, "categories": result}
    (STAGE / "raw/route_match.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out["b2c_index_lists_now"], out["sitemap_sizes"])
    for category, entry in result.items():
        p = entry.get("proposed")
        print(f"{category:<28} rows={entry['catalog_rows']:<3} clean={entry['clean_articles']:<3} exact_pages={entry['rows_with_exact_page']:<3} {entry['by_sitemap']}", (p["article"], p["section"]) if p else entry.get("reason", "")[:40])


if __name__ == "__main__":
    with offline_only():
        main()
