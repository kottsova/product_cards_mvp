"""Stage 30 step 1 -- OFFLINE, zero requests. The ordinary path (Excel upload -> confirmed batch -> one search job per product -> worker.run_once() -> export through the web route) over the saved
responses, for all 19 checked Samsung cards (Stages 24-29), with the Stage 30 rules: the brief-guide decision, the page's own product-data code as variant evidence, and the dealer link request that
stays open until a full Russian instruction is confirmed.

Output: raw/all19_result.json, raw/replay_calls.json, export/samsung_all19_export.xlsx
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
from product_tool import card_evidence  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("run4", ROOT / "reports/source_census_2026-09-25_stage27/scripts/02_run_batch4.py")   # its card_record() reads what run_once() stored
run4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run4)

MEMORY = (("Внутренние SSD-накопители", "MZ-77E500BW"), ("Flash-накопители", "MUF-64BE3/APC"), ("Внешние SSD-накопители", "MU-PC1T0H/WW"), ("Карты памяти", "MB-MC64HARU"))


def main() -> None:
    cards = list(R.CARDS) + list(R.CARDS4) + list(MEMORY)
    with tempfile.TemporaryDirectory() as tmp:
        result = R.run_products(Path(tmp), cards=cards)
        records = []
        for o in result["outcomes"]:
            record = run4.card_record(result["database"], o)
            record["device_split"] = (card_evidence.load(result["database"], o["product_id"], "samsung_page") or {}).get("device_split")
            record["dealer_request"] = (card_evidence.load(result["database"], o["product_id"], "dealer") or {})
            records.append(record)
        (STAGE / "raw/all19_result.json").write_text(json.dumps({"cards": records}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        replay = result["replay"]
        (STAGE / "raw/replay_calls.json").write_text(json.dumps({"served": [c for c in replay.calls if c not in replay.refused], "refused": replay.refused, "dealer_session_calls": result["dealer_session"].calls}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (STAGE / "export/samsung_all19_export.xlsx").write_bytes(result["export"])
    for card in records:
        r = card["readiness"]
        print(f"{card['category']:<26} job={card['job_status']:<13} {r['verdict']:<24} {r['page_match_level']:<18} photos={r['official_photos_selected']}/{r['official_photos']:<3} basis={r['instruction']['acceptance_basis']} gaps={r['gaps']}")
    print(Counter(c["readiness"]["verdict"] for c in records), Counter(c["job_status"] for c in records), "dealer calls:", result["dealer_session"].calls, "refused:", len(replay.refused))


if __name__ == "__main__":
    with offline_only():
        main()
