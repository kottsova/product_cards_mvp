"""One visible, user-assisted LG access check on an observed support URL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from product_tool.census.attended_support import AttendedBudget, capture


URL = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"
PROFILE = ROOT / "data" / "browser_profiles" / "lg_support"
OUTPUT = ROOT / "data" / "attended_capture" / "stage51_1_preflight"
LOG = ROOT / "data" / "lg_fetch_log.json"
BUDGET = AttendedBudget(max_navigations=2, max_resources=100,
                        max_wait_seconds=180, max_response_bytes=1_500_000,
                        max_dom_bytes=3_000_000, max_saved_responses=8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true")
    args = parser.parse_args()
    if not args.attended:
        parser.error("Visible, user-assisted Chrome requires --attended")
    if OUTPUT.exists():
        parser.error("Preflight capture already exists; refusing automatic repeat")
    result = capture(URL, OUTPUT, PROFILE, fetch_log_path=LOG,
                     budget=BUDGET, announce=lambda message: print(message, flush=True))
    print(json.dumps({"outcome": result["outcome"],
                      "challenge_seen": result.get("challenge_seen"),
                      "counts": result.get("counts"),
                      "challenge_stop_resolved": result.get("challenge_stop_resolved", False)},
                     ensure_ascii=False), flush=True)
    return 0 if result["outcome"] == "captured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
