"""Stage 21 step 5 -- OFFLINE, zero requests. How many of the 578 ready LG rows can each observed official route reach?

Sources: the LG KZ sitemap saved by the Stage 20 pilot, the LG RU product sitemap saved by the Stage 21 probe.
'Reachable' = a sitemap product URL whose slug key equals the key of the full article or of its base model (the production
lookup rule after D4). Whether the page then SHOWS the full article (full_sku, i.e. an exact variant) is decided on the page
and is NOT known here -- so this is an upper bound for exact matches, a lower bound for nothing.

Output: raw/estimate_578_stage21.json
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE20 = ROOT / "reports/source_census_2026-09-24_stage20"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.lg import _slug_key, lg_article_key, lg_base_model, lg_is_product_url, normalize_lg_sku  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402


def saved(directory: Path, suffix: str) -> str:
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["url"].endswith(suffix) and entry["saved_as"]:
            with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                return handle.read()
    raise SystemExit(f"no saved response for {suffix} in {directory}")


def ru_slug(url: str) -> str:
    return lg_article_key(url.rstrip("/").rsplit("/", 1)[-1].removeprefix("lg-"))


def main() -> None:
    kz_urls = [u for u in sitemap_locs(saved(STAGE20 / "pilot/responses", "/kz/sitemap.xml")) if lg_is_product_url(u)]
    ru_urls = [u for u in sitemap_locs(saved(STAGE / "probe/responses", "/ru/sitemap.xml")) if "/ru/" in u and "/support/" not in u]
    kz, ru = defaultdict(list), defaultdict(list)
    for url in kz_urls:
        kz[_slug_key(url)].append(url)
    for url in ru_urls:
        ru[ru_slug(url)].append(url)
    queue = [json.loads(line) for line in (ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    ready = [u for u in queue if u["family"] == "lg" and u["status"] == "ready_to_run"]
    pilot = {r["seller_sku"] for r in json.loads((STAGE20 / "raw/pilot_selection.json").read_text(encoding="utf-8"))["rows"]}
    rows, cats = [], defaultdict(Counter)
    for unit in ready:
        full = normalize_lg_sku(unit["seller_sku"])
        keys = {lg_article_key(full), lg_article_key(lg_base_model(full))}
        in_kz, in_ru = any(kz.get(k) for k in keys), any(ru.get(k) for k in keys)
        exact_slug_kz, exact_slug_ru = bool(kz.get(lg_article_key(full))), bool(ru.get(lg_article_key(full)))
        rows.append((unit, in_kz, in_ru, exact_slug_kz, exact_slug_ru))
        cat = cats[unit["category"]]
        cat["total"] += 1
        cat["kz"] += in_kz
        cat["ru"] += in_ru
        cat["either"] += in_kz or in_ru
        cat["neither"] += not (in_kz or in_ru)
    result = {
        "sources": {"kz_sitemap_product_urls": len(kz_urls), "ru_sitemap_urls_without_support": len(ru_urls)},
        "ready_rows": len(ready),
        "reachable_kz": sum(1 for r in rows if r[1]), "reachable_ru": sum(1 for r in rows if r[2]),
        "reachable_either": sum(1 for r in rows if r[1] or r[2]), "reachable_both": sum(1 for r in rows if r[1] and r[2]),
        "reachable_neither": sum(1 for r in rows if not (r[1] or r[2])),
        "ru_only_gain_over_kz": sum(1 for r in rows if r[2] and not r[1]),
        "slug_equals_full_article_kz": sum(1 for r in rows if r[3]), "slug_equals_full_article_ru": sum(1 for r in rows if r[4]),
        "pilot_rows_neither": sorted(u["seller_sku"] for u, k, r, *_ in rows if u["seller_sku"] in pilot and not (k or r)),
        "by_category": {c: dict(v) for c, v in sorted(cats.items())},
        "neither_examples": [u["seller_sku"] for u, k, r, *_ in rows if not (k or r)][:20],
        "note": "Upper bound for page reach only. A base-code hit is never an exact variant: the page must show the full article. Documents (instructions) are not estimated: that route is not established.",
    }
    (STAGE / "raw/estimate_578_stage21.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("by_category", "neither_examples")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    with offline_only():
        main()
