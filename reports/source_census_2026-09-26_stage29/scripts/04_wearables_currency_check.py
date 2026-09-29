"""Stage 29 step 4 -- OFFLINE, zero requests. Is the watch (SM-L300NZEACIS) and the band (SM-R390NZSACIS) proposed in Stage 28 a NOVELTY (owner rule: for wearables only new models)?

Evidence used: only the official im-sitemap.xml already read in Stage 28 (route_study/responses) and the catalog. A page in a sitemap proves that the model is still sold on the site, NOT that it is new;
the newness is judged by what else the same official list contains (newer generations of the same line). The Stage 24 conclusion (Watch7 / Fit 3 are not novelties) is kept unless this changes it.

Output: raw/wearables_currency_check.json
"""
from __future__ import annotations

import gzip
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
from product_tool.coverage.catalog_units import load_catalog  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

IM = ROOT / "reports/source_census_2026-09-26_stage28/route_study/responses"
LINES = (("watch-fe", r"galaxy-watch-fe-"), ("watch5-pro", r"galaxy-watch5-pro-"), ("watch6", r"galaxy-watch6-\d"), ("watch6-classic", r"galaxy-watch6-classic-"), ("watch7", r"galaxy-watch7-"), ("ultra", r"galaxy-watch-ultra-(?!2025)"),
         ("ultra-2025", r"galaxy-watch-ultra-2025-"), ("watch8", r"galaxy-watch8-\d"), ("watch8-classic", r"galaxy-watch8-classic-"), ("watch9", r"galaxy-watch9-"), ("ultra2", r"galaxy-watch-ultra2-"), ("fit3", r"galaxy-fit3-"))


def main() -> None:
    text = next(gzip.open(IM / json.loads(line)["saved_as"], "rt", encoding="utf-8", newline="").read() for line in (IM / "index.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(line)["url"].endswith("im-sitemap.xml"))
    locs = sitemap_locs(text)
    watches = [u for u in locs if "/watches/galaxy-watch/" in u and u.rsplit("/", 2)[-2] != "galaxy-watch"]
    bands = [u for u in locs if "/watches/galaxy-fit/" in u and u.rsplit("/", 2)[-2] != "galaxy-fit"]
    listed = {name: sum(1 for u in watches + bands if re.search(pattern, u)) for name, pattern in LINES}
    catalog = {unit.seller_sku: unit for unit in load_catalog(ROOT / "data/catalog_2026-09-21_filtered.xlsx").units}
    rows = []
    for unit in catalog.values():
        if unit.category in ("Смарт-часы", "Фитнес-браслеты") and unit.brand.lower().startswith("samsung"):
            page = samsung.find_in_sitemap(locs, unit.seller_sku)
            rows.append({"catalog_row": unit.row_number, "category": unit.category, "article": unit.seller_sku, "title": unit.title, "exact_page_in_sitemap": bool(page), "page_slug": page.rsplit("/", 2)[-2] if page else ""})
    watch8_catalog = [r for r in rows if r["title"].startswith("Galaxy Watch8")]
    report = {
        "requests_made": 0, "evidence": "official kz_ru/im-sitemap.xml read in Stage 28 (route_study/responses) + the catalog; no page was requested",
        "sitemap_lines_listed_page_counts": listed,
        "watch": {"catalog_article": "SM-L300NZEACIS", "title": "Galaxy Watch7 40mm", "page_listed_in_official_sitemap": listed["watch7"] > 0,
                  "newer_generations_listed": [name for name in ("watch8", "watch8-classic", "watch9", "ultra2") if listed[name]],
                  "verdict": "not_a_novelty" if listed["watch9"] and listed["watch8"] else "undecided",
                  "reason": "the same official list carries Watch8, Watch8 Classic, Watch9 and Ultra2: Watch7 is at least two generations behind, so a page in the sitemap shows only that it is still sold",
                  "stage24_conclusion_kept": True},
        "band": {"catalog_article": "SM-R390NZSACIS", "title": "Galaxy Fit 3", "page_listed_in_official_sitemap": listed["fit3"] > 0, "lines_listed": [name for name in ("fit3",) if listed[name]],
                 "newer_generations_listed": [],
                 "verdict": "newest_listed_novelty_not_proved_owner_decision",
                 "reason": "Fit3 is the only band the official list carries and nothing newer is listed, so it is the current model of its line; the sitemap gives no release date, so 'new' is not proved by any observed official source (the Stage 24 conclusion is not overturned)",
                 "stage24_conclusion_kept": True},
        "newer_watch_rows_in_catalog": {"rows": watch8_catalog, "note": "Watch8 rows exist in the catalog but with the INS region code; the KZ site lists SKZ/CIS codes for Watch8, so none of these rows has an exact page: the variant would stay open (as for Galaxy A37)"},
        "catalog_rows": rows, "sitemap_watch_pages": len(watches), "sitemap_band_pages": len(bands), "counts": dict(Counter(r["category"] for r in rows)),
    }
    (STAGE / "raw/wearables_currency_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("sitemap_lines_listed_page_counts",)}, ensure_ascii=False))
    print(report["watch"]["verdict"], report["watch"]["newer_generations_listed"], "|", report["band"]["verdict"], report["band"]["lines_listed"])


if __name__ == "__main__":
    with offline_only():
        main()
