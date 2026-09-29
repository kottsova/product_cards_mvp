"""python -m product_tool.coverage {plan,delta} -- offline, network-blocked."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..offline_guard import offline_only
from . import planner


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m product_tool.coverage", description="Offline catalog coverage queue")
    sub = parser.add_subparsers(dest="command", required=True)
    plan_cmd = sub.add_parser("plan", help="classify the read-only catalog and write the queue files")
    plan_cmd.add_argument("--catalog", default=planner.DEFAULT_CATALOG)
    plan_cmd.add_argument("--out", type=Path, required=True, help="directory for the generated queue files")
    plan_cmd.add_argument("--print-summary", action="store_true")
    delta_cmd = sub.add_parser("delta", help="compare two coverage_units.jsonl files")
    delta_cmd.add_argument("--before", type=Path, required=True)
    delta_cmd.add_argument("--after", type=Path, required=True)
    args = parser.parse_args(argv)
    with offline_only():  # a planner run can never reach the network, by construction
        if args.command == "plan":
            plan = planner.build_plan(args.catalog)
            written = planner.write_plan(plan, args.out)
            print(f"wrote {len(written)} files to {args.out}: {', '.join(written)}")
            if args.print_summary:
                print(json.dumps(plan["summary"], ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(json.dumps(planner.delta(args.before, args.after), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
