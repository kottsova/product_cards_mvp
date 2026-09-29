"""Stage 19 step 8 -- OFFLINE. Build the Stage 19 queue and measure it against Stage 18 and Stage 17.

Nothing is written into the Stage 17 or Stage 18 directories; the catalog is read-only.

Outputs: queue/*, delta_vs_stage18.json, delta_vs_stage17.json, numbers.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.coverage import planner  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

S17 = ROOT / "reports/source_census_2026-09-24_stage17/queue"
S18 = ROOT / "reports/source_census_2026-09-24_stage18/queue"


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    plan = planner.build_plan()
    written = planner.write_plan(plan, STAGE / "queue")
    assert planner.plan_bytes(plan) == planner.plan_bytes(planner.build_plan()), "queue is not reproducible"
    final = STAGE / "queue/coverage_units.jsonl"
    delta18 = planner.delta(S18 / "coverage_units.jsonl", final)
    delta17 = planner.delta(S17 / "coverage_units.jsonl", final)
    dump(STAGE / "delta_vs_stage18.json", delta18)
    dump(STAGE / "delta_vs_stage17.json", delta17)

    replay = json.loads((STAGE / "controls/all_ready_summary.json").read_text(encoding="utf-8"))
    conflicts = json.loads((STAGE / "raw/conflict_analysis.json").read_text(encoding="utf-8"))
    linkage = json.loads((STAGE / "raw/variant_linkage.json").read_text(encoding="utf-8"))
    accepted = json.loads((STAGE / "raw/accepted_variant_urls.json").read_text(encoding="utf-8"))["accepted"]
    hyperx = [u for u in plan["units"] if u["family"] == "hyperx"]
    numbers = {
        "variants_of_group_a_confirmed": {"confirmed": len(accepted), "of": linkage["rows_examined"], "offline_linked_and_url_observed": linkage["variants_linked_and_url_observed"],
                                          "live_pages_fetched": 7, "exact_variant_on_the_fetched_page": len(accepted)},
        "stage18_review_conflicts_resolved": {"conflicts_resolved": conflicts["resolved"], "of": conflicts["stage18_conflicts_total"], "rows_fully_resolved": conflicts["rows_with_every_conflict_resolved"],
                                              "of_rows": conflicts["rows"], "still_disputed": conflicts["still_disputed"]},
        "hyperx_cards": {"rows_with_url_of_record": replay["units"], "cards": replay["outcomes"].get("card", 0), "for_review": replay["outcomes"].get("review", 0),
                         "stage17_cards": 2, "stage18_cards_on_new_rows": 6, "stage18_reviews_on_new_rows": 5,
                         "hyperx_rows_total": len(hyperx), "hyperx_status_counts": dict(sorted(Counter(u["status"] for u in hyperx).items())),
                         "how": "worker.run_once() through the coverage executor on saved official pages (offline replay of real hyperx.com pages); no live worker run"},
        "ready_to_run_units": {"stage17": 580, "stage18": json.loads((S18 / "coverage_summary.json").read_text(encoding="utf-8"))["summary"]["units_by_status"]["ready_to_run"],
                               "stage19": plan["summary"]["units_by_status"]["ready_to_run"], "delta_vs_stage18": delta18["ready_to_run_gain"], "delta_vs_stage17": delta17["ready_to_run_gain"]},
        "gaps": {"rows_with_documents": len([r for r in replay["per_unit"] if r["documents"]]), "rows_without_documents": len([r for r in replay["per_unit"] if not r["documents"]]),
                 "rows_without_photos": [r["seller_sku"] for r in replay["per_unit"] if not r["photos"]],
                 "rows_without_model_specs": [r["seller_sku"] for r in replay["per_unit"] if not r["shared_model_attributes"]],
                 "hyperx_rows_still_without_url": len([u for u in hyperx if u["status"] == "adapter_url_missing"])},
    }
    dump(STAGE / "numbers.json", numbers)
    print("files:", written)
    print(json.dumps(numbers, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    with offline_only():
        main()
