"""Stage 28 step 8 -- OFFLINE, zero requests. PROPOSES the next small Samsung groups from raw/route_match.json: one product per category, the categories that now have an observed official route, split
into small groups. Nothing is requested and nothing is declared as run; a group is run only on the owner's word, with its budget declared first.

Output: raw/batch5_proposal.json
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

from product_tool.adapters.samsung_source import route_for  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

GROUPS = {"5A (memory storage)": ["Внутренние SSD-накопители", "Flash-накопители", "Внешние SSD-накопители", "Карты памяти"], "5B (accessories and wearables)": ["Кабели", "Смарт-часы", "Фитнес-браслеты"]}
CAP_PER_ROW, DOCS_PER_PRODUCT = 7, 2


def main() -> None:
    match = json.loads((STAGE / "raw/route_match.json").read_text(encoding="utf-8"))["categories"]
    groups = {}
    for name, categories in GROUPS.items():
        products = {c: match[c]["proposed"] for c in categories}
        sitemaps = sorted({p["sitemap"] for p in products.values()})
        n = len(products)
        groups[name] = {
            "products": {c: {"article": p["article"], "title": p["title"], "catalog_row": p["catalog_row"], "page_url": p["page_url"], "sitemap": p["sitemap"], "route_in_adapter": [a.rsplit("/", 1)[-1] for a in route_for(p["article"], c)[1]]} for c, p in products.items()},
            "request_budget": {"sitemaps": f"{len(sitemaps)} ({', '.join(sitemaps)}): read once for the group", "product_pages": n, "instruction_files": f"at most {n * DOCS_PER_PRODUCT}", "per_row_cap": CAP_PER_ROW,
                               "total_cap": len(sitemaps) + n + n * DOCS_PER_PRODUCT, "pacing_seconds": 1.5, "document_cap_mb": 40},
            "stop_rules": "401/403/429 or a confirmed challenge stops the host and ends the group; no page or file is asked for except one a sitemap lists / a page prints",
            "dealer_requests": 0,
            "known_risk": "the page templates of these sections have not been read yet: if a page has no specification table or gallery in the static HTML, the card reports the gap (nothing is guessed) and the group stops being 'ready' for that category",
        }
    left = {c: e["reason"] for c, e in match.items() if "proposed" not in e}
    out = {"proposed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "PROPOSAL -- nothing has been requested", "rule": "one product per category; the smallest SHA-256 of the article among rows with an exact page listed in an observed sitemap",
           "recommended_order": list(groups), "groups": groups, "categories_still_without_a_route": left}
    (STAGE / "raw/batch5_proposal.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, g in groups.items():
        print(name, {c: p["article"] for c, p in g["products"].items()}, g["request_budget"]["total_cap"])
    print(len(left), "categories without a route:", ", ".join(left))


if __name__ == "__main__":
    with offline_only():
        main()
