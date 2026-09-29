"""Stage 18 step 1 -- OFFLINE. Which of the 38 adapter_url_missing HyperX rows already have an
observed official product link? Reads only files in the repository; makes no request.

Input : queue_a_evidence_scope/coverage_units.jsonl (corrected planner, before any URL work)
        product links saved on official hyperx.com pages by Stage 11 / 11.1 (category pages, product pages)
Output: raw/offline_candidates.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hx_matching  # noqa: E402

ROOT = HERE.parents[2]
STAGE = HERE.parent
SAVED_PAGES = [
    "reports/source_census_2026-09-23_stage11/raw/hyperx_quadcast_2s_product_page.html.txt",
    "reports/source_census_2026-09-23_stage11_1/raw/hyperx_category_gaming-keyboards.html.txt",
    "reports/source_census_2026-09-23_stage11_1/raw/hyperx_category_gaming-mice.html.txt",
    "reports/source_census_2026-09-23_stage11_1/raw/hyperx_keyboard_product_page.html.txt",
    "reports/source_census_2026-09-23_stage11_1/raw/hyperx_mouse_product_page.html.txt",
]
LINK = re.compile(r'href="(?:https://hyperx\.com)?(/products/[^"#?\s]+)')


def missing_rows() -> list[dict]:
    rows = [json.loads(line) for line in (STAGE / "queue_a_evidence_scope" / "coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    return sorted((r for r in rows if r["status"] == "adapter_url_missing" and r["family"] == "hyperx"), key=lambda r: (r["category"], r["seller_sku"]))


def saved_links() -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for rel in SAVED_PAGES:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for path in sorted(set(LINK.findall(text))):
            if path.endswith(".oembed"):
                continue
            seen.setdefault(path, []).append(rel)
    return seen


def main() -> None:
    rows = missing_rows()
    links = saved_links()
    slugs = [hx_matching.slug_of(path) for path in links]
    by_slug = {hx_matching.slug_of(path): path for path in links}
    out = []
    for row in rows:
        flagged = "title_names_other_manufacturer" in row["flags"]
        found = [] if flagged else hx_matching.candidates(row["title"], slugs)
        out.append({
            "seller_sku": row["seller_sku"], "category": row["category"], "title": row["title"],
            "skipped": "title_names_other_manufacturer (Kingston memory module)" if flagged else "",
            "candidates": [{"path": by_slug[s], "found_on": links[by_slug[s]]} for s in found],
        })
    with_candidate = sum(1 for item in out if item["candidates"])
    result = {
        "step": "offline, zero requests", "rows": len(rows), "rows_with_an_observed_candidate_link": with_candidate,
        "saved_pages_read": SAVED_PAGES, "distinct_product_links_seen": len(links),
        "note": "A candidate is not a URL of record: the page's own sku must equal the catalog code first.",
        "items": out,
    }
    (STAGE / "raw" / "offline_candidates.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rows={len(rows)} with_candidate={with_candidate} distinct_links={len(links)}")
    for item in out:
        names = ", ".join(c["path"] for c in item["candidates"]) or ("-- " + item["skipped"] if item["skipped"] else "-")
        print(f"{item['seller_sku']:<14} {item['title'][:52]:<52} {names}")


if __name__ == "__main__":
    main()
