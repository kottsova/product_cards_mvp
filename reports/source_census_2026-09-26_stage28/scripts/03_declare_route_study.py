"""Stage 28 step 3 -- OFFLINE. Declares, BEFORE any request, the route study for the 15 queued Samsung categories.

Observed route (Stage 8.2, raw/samsung_step1.json there): the sitemap index `kz_ru/b2c-sitemap.xml` listed five sub-sitemaps: memory-sitemap.xml, im-sitemap.xml, assorted-sitemap.xml, vd-sitemap.xml, da-sitemap.xml.
vd and da are already read (Stages 24-25) and hold none of the 15 categories' pages. This study reads the index once more (to confirm the current list) and the three sub-sitemaps that no earlier stage
read in full. It requests NO product page and constructs NO address: a page is a `<loc>` a fetched sitemap lists.

Output: raw/route_study_declaration.json
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

from product_tool.offline_guard import offline_only  # noqa: E402


def main() -> None:
    step1 = json.loads((ROOT / "reports/source_census_2026-09-22_stage8_2/raw/samsung_step1.json").read_text(encoding="utf-8"))["step1_b2c_sitemap"]
    queued = json.loads((ROOT / "reports/source_census_2026-09-25_stage26/raw/batch3_proposal.json").read_text(encoding="utf-8"))["queued_categories"]
    remaining = {c: e["catalog_rows"] for c, e in queued.items() if "proposed" not in e}
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": "28 / route study", "brand": "Samsung", "market": "kz_ru",
        "observed_route": {"index": step1["url"], "listed_sub_sitemaps_in_stage8_2": step1["sample_links"], "evidence": "reports/source_census_2026-09-22_stage8_2/raw/samsung_step1.json"},
        "requests": {"planned": [{"n": 1, "url": step1["url"], "purpose": "confirm the current list of sub-sitemaps"}] + [{"n": n, "url": link, "purpose": "read in full; match the queued catalog articles against its <loc> entries"}
                                                                                                                               for n, link in enumerate([u for u in step1["sample_links"] if not u.endswith(("vd-sitemap.xml", "da-sitemap.xml"))], start=2)],
                     "max_real_requests": 4, "pacing_seconds": 1.5, "body_cap_bytes": 25_000_000, "product_pages": 0, "documents": 0, "images": 0,
                     "a_sub_sitemap_not_listed_by_the_index_today": "not requested"},
        "stop_rules": "401/403/429 or a confirmed challenge stops the host in <workdir>/samsung_fetch_log.json and ends the study; RequestBudget(max_total=4) refuses a fifth request before it is made",
        "url_construction": "none",
        "queued_categories": remaining,
        "after_the_study": "offline only: every queued catalog article is matched against the listed addresses; the batch is PROPOSED (one product per category, small groups), not run",
    }
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    (STAGE / "raw/route_study_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(declaration["declared_at"], [r["url"].rsplit("/", 1)[-1] for r in declaration["requests"]["planned"]], len(remaining), "queued categories")


if __name__ == "__main__":
    with offline_only():
        main()
