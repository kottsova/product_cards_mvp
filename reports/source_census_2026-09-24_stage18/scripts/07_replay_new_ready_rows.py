"""Stage 18 step 7 -- OFFLINE. Hand every row that got a URL of record in this stage to the ordinary worker.run_once()
through the coverage executor, with the saved official page as the only transport, and record what came out.

This is how "cards actually obtained" is counted: a card is a job that run_once() finished as `done`. The pages are
the copies saved by step 3 (or the Stage 5.1 snapshot), so no request is made here; the number says what the working
adapter produces from those real pages, not that a live worker run was made.

Output: controls/new_ready_checkpoint.json, controls/new_ready_summary.json
"""
from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.adapters.hyperx import HyperXAdapter, KNOWN_URLS  # noqa: E402
from product_tool.census.endpoint_probe import ProbePolicy  # noqa: E402
from product_tool.coverage import executor, planner  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402
from tests.coverage_controls import FixtureSession, NoDealer  # noqa: E402


def saved_pages() -> dict[str, str]:
    accepted = json.loads((STAGE / "raw" / "accepted_urls.json").read_text(encoding="utf-8"))["accepted"]
    pages = {}
    for item in accepted:
        if item["basis"] == "saved_official_snapshot":
            connection = sqlite3.connect(f"file:{ROOT / item['database']}?mode=ro", uri=True)
            try:
                pages[item["url"]] = connection.execute("SELECT content FROM source_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()[0]
            finally:
                connection.close()
        else:
            with gzip.open(STAGE / item["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                pages[item["url"]] = handle.read()
    return pages


def replay(out: Path, plan_units: list[dict] | None = None) -> tuple[dict, Path]:
    """Run every accepted row through executor.run_units() in `out`; return (summary, checkpoint path)."""
    if plan_units is None:
        plan_units = planner.build_plan()["units"]
    accepted = json.loads((STAGE / "raw" / "accepted_urls.json").read_text(encoding="utf-8"))["accepted"]
    wanted = {item["seller_sku"] for item in accepted}
    units = sorted((u for u in plan_units if u["family"] == "hyperx" and u["seller_sku"].upper() in wanted), key=lambda u: u["seller_sku"])
    assert len(units) == len(wanted), (len(units), len(wanted))
    assert all(u["status"] == "ready_to_run" and u["exact_url"] == KNOWN_URLS[u["seller_sku"].upper()] for u in units)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    session = FixtureSession({url: (200, html) for url, html in saved_pages().items()})
    clock = lambda: 0.0  # noqa: E731
    log = out / "hyperx_fetch_log.json"
    factories = executor.RunFactories(
        session=session, hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=clock, fetch_log_path=log, policy=ProbePolicy(min_interval_seconds=0.0)),  # fixtures need no politeness delay
        dns_adapter_factory=lambda: NoDealer(), fetch_log_paths=(log,),
    )
    checkpoint_path = out / "checkpoint.json"
    checkpoint = executor.run_units(units, workdir=out, checkpoint_path=checkpoint_path, factories=factories, clock=clock)
    calls_after_first = list(session.calls)
    executor.run_units(units, workdir=out, checkpoint_path=checkpoint_path, factories=factories, clock=clock)
    summary = {
        "step": "offline replay of saved official pages through worker.run_once(); zero requests",
        "units": len(units), **executor.summarize(checkpoint),
        "resume_pass_new_calls": len(session.calls) - len(calls_after_first),
        "requests_to_fixture_transport": len(calls_after_first), "refused_requests": session.refused,
        "per_unit": [
            {"seller_sku": e["seller_sku"], "category": e["category"], "outcome": e["outcome"], "stop_code": e.get("stop_code", ""),
             "job_status": e.get("job_status", ""),
             "hyperx_match_level": next((s["match_level"] for s in e.get("card", {}).get("sources", []) if s["source_key"] == "hyperx"), ""), "facts": e.get("card", {}).get("facts"),
             "photos": e.get("card", {}).get("photos"), "documents": e.get("card", {}).get("documents"), "gaps": e.get("card", {}).get("gaps"),
             "conflicts": e.get("card", {}).get("conflicts"), "url": (e.get("card", {}).get("evidence_urls") or [""])[0]}
            for e in sorted(checkpoint["units"].values(), key=lambda e: e["seller_sku"])
        ],
    }
    return summary, checkpoint_path


def main() -> None:
    summary, checkpoint_path = replay(STAGE / "controls" / "new_ready_replay")
    (STAGE / "controls" / "new_ready_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy(checkpoint_path, STAGE / "controls" / "new_ready_checkpoint.json")
    print({k: v for k, v in summary.items() if k != "per_unit"})
    for row in summary["per_unit"]:
        print(" ", row["seller_sku"], row["outcome"], row["stop_code"], row["hyperx_match_level"], "facts", row["facts"], "photos", row["photos"], "docs", row["documents"], row["gaps"])


if __name__ == "__main__":
    with offline_only():
        main()
