"""Stage 17 -- which test commands really run with the network guard on.

Two kinds of evidence, both offline:
  * probes: load the tests exactly the way each command does, WITHOUT running
    them, then report whether real HTTP/DNS is already blocked;
  * full runs: the three documented commands, with their test counts.

Writes reports/source_census_2026-09-24_stage17/guard_matrix.json."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "reports/source_census_2026-09-24_stage17/guard_matrix.json"
PY = sys.executable

PROBE = r'''
import sys, unittest
sys.path.insert(0, ".")
from product_tool.offline_guard import guard_state
mode = sys.argv[1]
loader = unittest.TestLoader()
if mode == "legacy_full_discovery":      # python -m unittest discover -s tests
    loader.discover("tests", pattern="test_*.py")
elif mode == "legacy_narrowed_pattern":  # python -m unittest discover -s tests -p test_hyperx_adapter.py
    loader.discover("tests", pattern="test_hyperx_adapter.py")
elif mode == "top_level_dir_narrowed":   # python -m unittest discover -s tests -t . -p test_hyperx_adapter.py
    loader.discover("tests", pattern="test_hyperx_adapter.py", top_level_dir=".")
elif mode == "single_module":            # python -m unittest tests.test_hyperx_adapter
    loader.loadTestsFromName("tests.test_hyperx_adapter")
elif mode == "runner_module":            # python -m tests (activation happens on import of tests/__main__)
    sys.argv = ["tests"]
    import tests.__main__  # noqa: F401
print(mode, guard_state(), "package_imported=", "tests" in sys.modules)
'''

MODES = {
    "legacy_full_discovery": "python -m unittest discover -s tests",
    "legacy_narrowed_pattern": "python -m unittest discover -s tests -p test_hyperx_adapter.py",
    "top_level_dir_narrowed": "python -m unittest discover -s tests -t . -p test_hyperx_adapter.py",
    "single_module": "python -m unittest tests.test_hyperx_adapter",
    "runner_module": "python -m tests",
}
probes = {}
for mode, command in MODES.items():
    proc = subprocess.run([PY, "-c", PROBE, mode], cwd=ROOT, capture_output=True, text=True, timeout=300)
    line = proc.stdout.strip().splitlines()[-1]
    match = re.search(r"\{.*\}", line)
    state = eval(match.group(0)) if match else {}
    probes[mode] = {"command": command, "guard_on_before_any_test_runs": bool(state.get("http_blocked") and state.get("dns_blocked")),
                    "state": state, "package_imported": "package_imported= True" in line, "returncode": proc.returncode}

runs = {}
for name, args in {
    "python -m tests": ["-m", "tests", "-q"],
    "python -m unittest discover -s tests -t . -q": ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"],
    "python -m unittest discover -s tests -q": ["-m", "unittest", "discover", "-s", "tests", "-q"],
}.items():
    proc = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, timeout=900)
    tail = proc.stderr.strip().splitlines()[-3:]
    runs[name] = {"returncode": proc.returncode, "summary": tail}

result = {
    "probes": probes,
    "full_runs": runs,
    "guaranteed_regardless_of_module_order_or_file_selection": [c["command"] for c in probes.values() if c["guard_on_before_any_test_runs"] and c["package_imported"]],
    "not_guaranteed": [c["command"] for c in probes.values() if not c["guard_on_before_any_test_runs"]],
    "held_only_by_import_order": [c["command"] for c in probes.values() if c["guard_on_before_any_test_runs"] and not c["package_imported"]],
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
