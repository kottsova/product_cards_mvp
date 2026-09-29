"""Stage 28 step 9 -- OFFLINE, zero requests. The ordinary path (Excel upload -> confirmed batch -> one search job per product -> worker.run_once() -> export through the web route) over the saved
responses, for all 15 selected Samsung cards, with the Stage 27 owner rules, the recorded microwave and dishwasher evidence and the Stage 28 device split; plus the planner's view of Samsung and the checks of the two rules that
need an experiment (a person confirming photos; the dealer path).

Output: raw/all15_result.json, raw/replay_calls.json, export/samsung_all15_export.xlsx
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import _samsung_replay as R  # noqa: E402
from product_tool import card_evidence, jobs, samsung_readiness  # noqa: E402
from product_tool.coverage import planner  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("run4", ROOT / "reports/source_census_2026-09-25_stage27/scripts/02_run_batch4.py")   # its card_record() reads what run_once() stored
run4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run4)


def main() -> None:
    cards = list(R.CARDS) + list(R.CARDS4)
    with tempfile.TemporaryDirectory() as tmp:
        result = R.run_products(Path(tmp), cards=cards)
        records = []
        for o in result["outcomes"]:
            record = run4.card_record(result["database"], o)
            record["device_split"] = (card_evidence.load(result["database"], o["product_id"], "samsung_page") or {}).get("device_split")
            records.append(record)
        (STAGE / "raw/all15_result.json").write_text(json.dumps({"cards": records}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        replay = result["replay"]
        (STAGE / "raw/replay_calls.json").write_text(json.dumps({"served": [c for c in replay.calls if c not in replay.refused], "refused": replay.refused, "dealer_session_calls": result["dealer_session"].calls}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (STAGE / "export").mkdir(exist_ok=True)
        (STAGE / "export/samsung_all15_export.xlsx").write_bytes(result["export"])
    plan = planner.build_plan()
    samsung = [u for u in plan["units"] if u["family"] == "samsung"]
    (STAGE / "raw/planner_samsung.json").write_text(json.dumps({
        "samsung_units": len(samsung), "by_status_and_reason": {f"{s}/{r}": n for (s, r), n in sorted(Counter((u["status"], u["reason"]) for u in samsung).items())},
        "ready": sorted(({"category": u["category"], "seller_sku": u["seller_sku"], "catalog_row": u["catalog_row"]} for u in samsung if u["status"] == "ready_to_run"), key=lambda x: x["category"]),
        "working_adapters": plan["meta"]["working_adapters"], "all_units_by_status": plan["summary"]["units_by_status"]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for card in records:
        r = card["readiness"]
        print(f"{card['category']:<22} job={card['job_status']:<13} {r['verdict']:<24} {r['page_match_level']:<18} photos={r['official_photos_selected']}/{r['official_photos']:<3} basis={r['instruction']['acceptance_basis']} gaps={r['gaps']}")
    print(Counter(c["readiness"]["verdict"] for c in records), Counter(c["job_status"] for c in records))


if __name__ == "__main__":
    with offline_only():
        main()
