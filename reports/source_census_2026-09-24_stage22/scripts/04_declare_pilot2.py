"""Stage 22 step 4 -- OFFLINE, zero requests. Fixes, BEFORE any request of the second pilot, the sample, the selection rule, the budget,
the stop rules and what is measured.

Sample = the 12 rows of the first pilot (unchanged, Stage 20 selection) + 12 NEW rows chosen by this rule (deterministic; nothing about a row's
expected result other than sitemap reachability is used):
  universe  = the Stage 19 queue units with family "lg" and status "ready_to_run" (578) minus the 12 first-pilot rows;
  reach     = from the SAVED sitemaps (LG Kazakhstan: Stage 20 pilot responses; LG Russia: Stage 21 probe responses), whether a product URL whose slug equals the
              key of the full article or of its base model exists (the production lookup rule after D4);
  groups, taken in this order, each with a quota:
     A  not in the KZ sitemap, in the RU sitemap ........ 5   (the "not in KZ" requirement: at least five)
     B  the article has a dot (regional suffix), reachable in KZ or RU, not yet chosen ... 3
     C  in neither sitemap ............................... 1   (an honest miss)
     D  reachable in both, no dot in the article .......... 3
  inside a group each pick is: among the group's remaining units, those whose category has the FEWEST picks so far in the new set; of those, the smallest
  SHA-256 of the upper-cased seller article. Categories therefore spread as widely as the groups allow.

Output: raw/pilot2_selection.json, raw/pilot2_declaration.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE20 = ROOT / "reports/source_census_2026-09-24_stage20"
STAGE21 = ROOT / "reports/source_census_2026-09-24_stage21"
QUEUE = ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.lg import _slug_key, lg_article_key, lg_base_model, lg_is_product_url, normalize_lg_sku  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

QUOTAS = [("A", 5), ("B", 3), ("C", 1), ("D", 3)]


def saved_text(directory: Path, suffix: str) -> str:
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["url"].endswith(suffix) and entry["saved_as"]:
            with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                return handle.read()
    raise SystemExit(f"no saved {suffix}")


def digest(unit) -> str:
    return hashlib.sha256(unit["seller_sku"].upper().encode("utf-8")).hexdigest()


def main() -> None:
    kz_slugs = {_slug_key(u) for u in sitemap_locs(saved_text(STAGE20 / "pilot/responses", "/kz/sitemap.xml")) if lg_is_product_url(u)}
    ru_slugs = {lg_article_key(u.rstrip("/").rsplit("/", 1)[-1].removeprefix("lg-")) for u in sitemap_locs(saved_text(STAGE21 / "probe/responses", "/ru/sitemap.xml")) if "/ru/" in u and "/support/" not in u}
    first = json.loads((STAGE20 / "raw/pilot_selection.json").read_text(encoding="utf-8"))
    first_skus = {r["seller_sku"].upper() for r in first["rows"]}
    units = [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line]
    ready = [u for u in units if u["family"] == "lg" and u["status"] == "ready_to_run"]
    assert len(ready) == 578
    universe = [u for u in ready if u["seller_sku"].upper() not in first_skus]
    for u in universe:
        full = normalize_lg_sku(u["seller_sku"])
        keys = {lg_article_key(full), lg_article_key(lg_base_model(full))}
        u["_kz"], u["_ru"], u["_dot"] = bool(keys & kz_slugs), bool(keys & ru_slugs), "." in u["seller_sku"]
    groups = {"A": lambda u: not u["_kz"] and u["_ru"], "B": lambda u: u["_dot"] and (u["_kz"] or u["_ru"]), "C": lambda u: not u["_kz"] and not u["_ru"], "D": lambda u: u["_kz"] and u["_ru"] and not u["_dot"]}
    chosen, taken, per_category = [], set(), Counter()
    for group, quota in QUOTAS:
        for _ in range(quota):
            pool = [u for u in universe if groups[group](u) and u["seller_sku"] not in taken]
            fewest = min(per_category[u["category"]] for u in pool)
            pick = min((u for u in pool if per_category[u["category"]] == fewest), key=digest)
            taken.add(pick["seller_sku"])
            per_category[pick["category"]] += 1
            chosen.append({"group": group, "category": pick["category"], "seller_sku": pick["seller_sku"], "catalog_row": pick["catalog_row"], "brand": pick["brand"], "title": pick["title"],
                           "unit_id": pick["unit_id"], "sha256_of_article": digest(pick), "in_kz_sitemap": pick["_kz"], "in_ru_sitemap": pick["_ru"], "article_has_dot": pick["_dot"], "group_pool_size": len(pool)})
    rows = [dict(r, group="first_pilot") for r in first["rows"]] + chosen
    assert len(chosen) == 12 and len({r["seller_sku"] for r in rows}) == 24
    not_in_kz_new = sum(1 for c in chosen if not c["in_kz_sitemap"])
    selection = {"rule": __doc__.split("Output:")[0], "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(), "new_rows": chosen, "first_pilot_rows": first["rows"],
                 "rows": [{k: r[k] for k in ("group", "category", "seller_sku", "catalog_row", "brand", "title")} for r in rows],
                 "new_rows_not_in_kz_sitemap": not_in_kz_new, "new_rows_with_dot": sum(1 for c in chosen if c["article_has_dot"]), "new_categories": sorted({c["category"] for c in chosen}),
                 "universe_group_sizes": {g: sum(1 for u in universe if fn(u)) for g, fn in groups.items()}}
    assert not_in_kz_new >= 5
    (STAGE / "raw/pilot2_selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample": {"first_pilot_rows": 12, "new_rows": 12, "total": 24, "new_rows_not_in_kz_sitemap": not_in_kz_new, "order": "the 12 first-pilot rows in their Stage 20 order, then the 12 new rows in group order"},
        "budget": {"max_real_requests_per_row": 12, "max_real_requests_total": 180, "pacing_seconds": 1.0,
                   "counted": "every REAL request of the LG adapters (pages, sitemaps not held, support pages, document files); a response served from a saved file is not a request and is listed as replayed",
                   "expected": "first-pilot rows: LG pages replayed from Stage 20/21/22 saved responses, so only their support pages and document files are new (<= 3 per row); new rows: KZ/RU pages + support page + <= 2 files",
                   "refusal": "a real request over the per-row or total cap is refused before it is made and the row records it"},
        "hosts_allowed": ["www.lg.com", "lg.com", "*.lge.com (document files, printed on the support page)", "www.sulpak.kz", "sulpak.kz"],
        "addresses": "only URLs that come from a saved or fetched official page or sitemap (sitemap slug match, the /ru/support/product/ link printed on the RU page, an href printed on that support page); nothing is constructed",
        "stop_rule": "401/403/429 or a confirmed challenge (any HTTP status) stops that host in the pilot's persisted log; a stopped lg.com ends the pilot before the next row and lists rows not run; a stopped document host only ends document requests",
        "workflow": "the ordinary worker.run_once(database) with the default adapters (LGAdapter, LGRUDocumentAdapter, SulpakAdapter through PolicyAwareSession), stages 1,2,3,4,6, one job per row; dealers make no request for a row that has no known URL",
        "measured_per_row": ["job status and message", "card readiness verdict and gaps", "variant accuracy: match level per region (full_sku / base_model / mismatch) and the url",
                             "specification facts per source; real conflicts with raw names and values", "photos: gallery selected per source, from exact pages",
                             "instruction: candidate links, files reached, confirmed by content, language from the text, model named in the text", "requests made and replayed"],
        "instruction_states": ["candidate_link", "reachable_file", "instruction_confirmed_by_content"],
        "not_done_here": "the full run of the 578 rows",
    }
    (STAGE / "raw/pilot2_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("group sizes:", selection["universe_group_sizes"])
    for c in chosen:
        print(f"  {c['group']} {c['category']:<26} {c['seller_sku']:<22} kz={c['in_kz_sitemap']!s:<5} ru={c['in_ru_sitemap']!s:<5} dot={c['article_has_dot']}")
    print("new rows not in KZ sitemap:", not_in_kz_new)


if __name__ == "__main__":
    with offline_only():
        main()
