"""Complete only rows stopped by Stage 51.1's declared HTTP budget."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from product_tool import jobs, worker
from product_tool.adapters import access_stop
from product_tool.adapters.policy_fetch import read_log
from product_tool.adapters.policy_session import RequestBudget, record_responses, request_budget
import run_repeat as pilot


EXTRA_BUDGET = 18


def main() -> int:
    rows = pilot.prepare()
    if not pilot.RESULT.exists():
        raise SystemExit("The capped first repeat result is missing")
    capped = HERE / "repeat_result_capped.json"
    if capped.exists():
        raise SystemExit("Budget completion already attempted")
    shutil.copy2(pilot.RESULT, capped)
    progress = json.loads(pilot.PROGRESS.read_text(encoding="utf-8"))
    previous_total = progress["budget_total"]
    selected = []
    for row in rows:
        pages = jobs.get_source_pages(pilot.DB, row["id"])
        if any(page["source_key"] in {"lg_kz", "lg_ru"} and
               "policy_budget_exhausted" in page["error"] for page in pages):
            selected.append(row)
    if not selected or len(selected) > 3:
        raise SystemExit(f"Expected at most 3 budget-limited rows, found {len(selected)}")
    budget = RequestBudget(max_per_row=pilot.MAX_PER_ROW,
                           max_total=previous_total + EXTRA_BUDGET)
    budget.total, budget.log = previous_total, progress["budget_log"]
    for row in selected:
        jobs.enqueue(pilot.DB, row["id"], pilot.STAGES)
    halted = ""
    with request_budget(budget), record_responses(pilot.PILOT / "responses"):
        for row in selected:
            budget.begin_row(row["search_code"])
            if not worker.run_once(pilot.DB):
                raise RuntimeError(f"Worker could not claim {row['search_code']}")
            job = jobs.list_jobs(pilot.DB, row["id"])[0]
            print(row["search_code"], job["status"], "http_budget", budget.total, flush=True)
            active = access_stop.active_stops(read_log(pilot.PILOT / "lg_fetch_log.json"))
            if "www.lg.com" in active:
                halted = "www.lg.com active stop after this row"
                print(halted, flush=True)
                break
    result = pilot.summarize(rows, budget, halted=halted)
    pilot.RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    pilot.PROGRESS.write_text(json.dumps({"budget_total": budget.total, "budget_log": budget.log},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
    return 3 if halted else 0


if __name__ == "__main__":
    raise SystemExit(main())
