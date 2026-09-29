"""Stage 18 step 8 -- OFFLINE. Build the final queue and measure it against Stage 17 in three separate deltas.

  delta_a_evidence_and_identity.json : Stage 17 queue -> corrected planner, still with the Stage 17 URL map
                                       (queue_a_evidence_scope, built before any URL work)
  delta_b_confirmed_urls.json        : queue_a_evidence_scope -> final queue (only the URLs of record added in this stage)
  delta_total_vs_stage17.json        : Stage 17 queue -> final queue
  four_numbers.json                  : the four figures the stage reports, kept apart

Nothing is written into the Stage 17 directory; the catalog is read-only.
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

STAGE17_UNITS = ROOT / "reports/source_census_2026-09-24_stage17/queue/coverage_units.jsonl"
STAGE17_SUMMARY = ROOT / "reports/source_census_2026-09-24_stage17/queue/coverage_summary.json"


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    plan = planner.build_plan()
    written = planner.write_plan(plan, STAGE / "queue")
    assert planner.plan_bytes(plan) == planner.plan_bytes(planner.build_plan()), "queue is not reproducible"

    queue_a = STAGE / "queue_a_evidence_scope" / "coverage_units.jsonl"
    final = STAGE / "queue" / "coverage_units.jsonl"
    delta_a = planner.delta(STAGE17_UNITS, queue_a)
    delta_b = planner.delta(queue_a, final)
    delta_total = planner.delta(STAGE17_UNITS, final)
    dump(STAGE / "delta_a_evidence_and_identity.json", delta_a)
    dump(STAGE / "delta_b_confirmed_urls.json", delta_b)
    dump(STAGE / "delta_total_vs_stage17.json", delta_total)

    replay = json.loads((STAGE / "controls" / "new_ready_summary.json").read_text(encoding="utf-8"))
    accepted = json.loads((STAGE / "raw" / "accepted_urls.json").read_text(encoding="utf-8"))["accepted"]
    old = json.loads(STAGE17_SUMMARY.read_text(encoding="utf-8"))["summary"]
    new = plan["summary"]
    causes = delta_a["moves_by_cause"]
    four = {
        "note": "Four different quantities; none is derived from another.",
        "1_status_changed_because_evidence_was_overstated": {
            "units": causes["evidence_scope_corrected"]["units"], "moves": causes["evidence_scope_corrected"]["moves"],
            "plus_units_changed_by_the_identity_rule_fix": {"units": causes["identity_rule_corrected"]["units"], "moves": causes["identity_rule_corrected"]["moves"]},
            "measured": "Stage 17 queue -> queue_a_evidence_scope (same URL map)",
        },
        "2_units_that_got_a_really_confirmed_url": {
            "units": len(accepted), "by_basis": dict(Counter(item["basis"] for item in accepted)),
            "rows_examined_by_the_wave_without_a_url": json.loads((STAGE / "raw" / "url_findings.json").read_text(encoding="utf-8"))["not_accepted"],
            "measured": "queue_a_evidence_scope -> final queue (moves_by_cause.exact_url_confirmed)",
        },
        "3_units_that_can_be_launched_now": {
            "ready_to_run_units": new["units_by_status"]["ready_to_run"], "stage17_ready_to_run_units": old["units_by_status"]["ready_to_run"],
            "gain_vs_stage17": delta_total["ready_to_run_gain"], "by_url_basis": new["ready_units_by_url_basis"],
            "ready_pairs": new["pairs_by_status"]["ready_to_run"], "partially_ready_pairs": new["pairs_partially_ready"],
            "meaning": "may be passed to worker.run_once(); says nothing about whether a card will come out",
        },
        "4_cards_actually_obtained": {
            "from_the_11_new_rows": replay["outcomes"], "cards": replay["outcomes"].get("card", 0), "for_review": replay["outcomes"].get("review", 0),
            "how": "worker.run_once() through the coverage executor on the saved official pages (offline replay); no live worker run was made",
            "not_counted": "the Stage 17 control cards (9A273AA, A1KY6AA, one LG row) are Stage 17 results",
        },
    }
    dump(STAGE / "four_numbers.json", four)
    print("files:", written)
    print(json.dumps({k: v for k, v in four.items() if k != "note"}, ensure_ascii=False, indent=1)[:3500])


if __name__ == "__main__":
    with offline_only():
        main()
