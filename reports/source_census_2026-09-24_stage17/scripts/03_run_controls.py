"""Stage 17 -- run the control rows through the ordinary worker.run_once() via
the coverage executor, offline (fixture transports only), and save the
checkpoints under reports/source_census_2026-09-24_stage17/controls/.

Volatile ids (uuid job ids, autoincrement product ids) are dropped from the
saved copy so the artifact is stable between runs."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from product_tool.coverage import executor  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402
import coverage_controls as controls  # noqa: E402

OUT = ROOT / "reports/source_census_2026-09-24_stage17/controls"
VOLATILE = {"job_id", "product_id"}


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


with offline_only(), tempfile.TemporaryDirectory() as tmp:
    result = controls.run_controls(Path(tmp))
OUT.mkdir(parents=True, exist_ok=True)
for name in ("main", "host_stop", "lg"):
    (OUT / f"control_checkpoint_{name}.json").write_text(json.dumps(scrub(result[name]), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
summary = {
    name: executor.summarize(result[name]) for name in ("main", "host_stop", "lg")
}
summary["network"] = {
    "hyperx_fixture_calls": result["sessions"]["hyperx_calls"],
    "negative_control_fixture_calls": result["sessions"]["negative_calls"],
    "calls_after_restart_on_a_stopped_host": result["sessions"]["restarted_session_calls"],
    "lg_fixture_calls": result["sessions"]["lg_calls"],
    "refused_requests": result["sessions"]["lg_refused"],
    "note": "Every call above was answered from memory by tests/coverage_controls.py; no socket was opened (offline_guard active).",
}
(OUT / "control_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
