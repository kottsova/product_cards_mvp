"""Stage 17 -- build the offline coverage queue from the read-only catalog.

    python reports/source_census_2026-09-24_stage17/scripts/02_generate_queue.py

Writes reports/source_census_2026-09-24_stage17/queue/*. No network (the CLI
path runs under product_tool.offline_guard.offline_only)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from product_tool.coverage.__main__ import main  # noqa: E402

raise SystemExit(main(["plan", "--out", str(ROOT / "reports/source_census_2026-09-24_stage17/queue")]))
