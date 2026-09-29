"""Stage 17 -- refresh tests/_pipeline_migration.py::PINNED_SHA256 for every
file the documented migration authorizes, and add pins for files newly
authorized this stage. Offline; reads repo files, rewrites only that dict.

Usage:  python reports/source_census_2026-09-24_stage17/scripts/01_repin_migration_hashes.py
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))
import importlib

import _pipeline_migration as mig  # noqa: E402

importlib.reload(mig)
target = ROOT / "tests/_pipeline_migration.py"
text = target.read_text(encoding="utf-8")

start = text.index("PINNED_SHA256: dict[str, str] = {")
end = text.index("\n}\n", start) + 3
paths = list(mig.ALL_AUTHORIZED_CHANGES)  # every authorized path gets a pin
lines = ["PINNED_SHA256: dict[str, str] = {"]
changed = []
for path in paths:
    digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if mig.PINNED_SHA256.get(path) != digest:
        changed.append(path)
    lines.append(f'    "{path}": "{digest}",')
lines.append("}\n")
target.write_text(text[:start] + "\n".join(lines) + text[end:], encoding="utf-8")
# same-size rewrite within one second can leave a stale .pyc that still validates
for stale in (ROOT / "tests/__pycache__").glob("_pipeline_migration*.pyc"):
    stale.unlink()
print("re-pinned", len(changed), "of", len(paths))
for path in changed:
    print("  ", path)
