"""Stage 19 step 6 -- OFFLINE, zero requests. The five Stage 18 `needs_review` rows, from the source fragments.

Stage 18 counted conflicts (same normalized name, different values) = 1 for four rows and 3 for B5VC4AA (7 in all).
For each one this script prints the two source fragments and decides, from the fragments alone, whether the values
contradict each other or describe different things. A conflict counts as RESOLVED only when the cause is proven by
the page itself:

  * different_device_node : the two values sit in different spec blocks of the page, and the later block is proven to
                            be the microphone's by its own row ("Element = ... microphone") -- the headset driver's and the
                            microphone's values of the same name are not the same quantity (dBSPL/mW vs dBV/Pa or dBFS/Pa,
                            20 Hz-20 kHz vs 100 Hz-10 kHz);
  * not_a_specification   : the "value" comes from a price widget (<dl> under a `price` container), not from the specification table.

Anything else stays disputed. The rule change (adapters/hyperx._spec_attributes, structured_page price-widget exclusion)
is justified only for the resolved ones.

Output: raw/conflict_analysis.json
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE18 = ROOT / "reports/source_census_2026-09-24_stage18"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.hyperx import _block_label  # noqa: E402
from product_tool.adapters.structured_page import ROLE_DOM_TABLE, _in_price_widget, extract_dom_spec_table  # noqa: E402
from product_tool.normalization import normalize_fact  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

ROWS = {"4P5D4AA": {"sensitivity"}, "4P5J1AA": {"sensitivity"}, "4P5L3AA": {"sensitivity"}, "683L9AA": {"sensitivity"}, "B5VC4AA": {"sensitivity", "frequency_response", "unit_price"}}
UNIT_CLASS = [("driver_acoustic", re.compile(r"dB\s*SPL", re.I)), ("microphone_voltage", re.compile(r"dBV|dBFS", re.I)), ("frequency_range", re.compile(r"hz", re.I)), ("price", re.compile(r"\$"))]


def unit_class(value: str) -> str:
    return next((name for name, pattern in UNIT_CLASS if pattern.search(value)), "other")


def load_stage18_page(item: dict) -> str:
    if item["basis"] == "saved_official_snapshot":
        connection = sqlite3.connect(f"file:{ROOT / item['database']}?mode=ro", uri=True)
        try:
            return connection.execute("SELECT content FROM source_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()[0]
        finally:
            connection.close()
    with gzip.open(STAGE18 / item["saved_as"], "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


def price_widget_values(html: str) -> list[str]:
    """What the pre-fix extractor read as ("Unit price", value): every <dl><dt>Unit price</dt><dd>..</dd> under a price container."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for dl in soup.select("dl"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            if dt.get_text(" ", strip=True).casefold() == "unit price":
                found.append((dd.get_text(" ", strip=True), _in_price_widget(dl)))
    return found


def main() -> None:
    stage18 = {a["seller_sku"]: a for a in json.loads((STAGE18 / "raw/accepted_urls.json").read_text(encoding="utf-8"))["accepted"]}
    review = {r["seller_sku"]: r for r in json.loads((STAGE18 / "controls/new_ready_summary.json").read_text(encoding="utf-8"))["per_unit"]}
    result, resolved, disputed = [], 0, 0
    for sku, names in ROWS.items():
        html = load_stage18_page(stage18[sku])
        fields = extract_dom_spec_table(html, stage18[sku]["url"])
        blocks = defaultdict(list)
        for f in fields:
            if f.role == ROLE_DOM_TABLE and f.block:
                blocks[f.block].append(f)
        by_name = defaultdict(list)
        for f in fields:
            by_name[normalize_fact(type("R", (), {"name": f.name, "value": f.value})()).normalized_name].append(f)
        for name in sorted(names):
            if name == "unit_price":
                widgets = price_widget_values(html)
                cause = "not_a_specification" if widgets and all(in_price for _, in_price in widgets) else "unproven"
                fragments = [{"value": v, "container": "price widget" if in_price else "other"} for v, in_price in widgets]
                conflict = {"seller_sku": sku, "name": name, "fragments": fragments, "cause": cause}
            else:
                rows = by_name[name]
                distinct = {f.value for f in rows}
                labels = [_block_label(blocks[f.block]) for f in rows]
                fragments = [{"section": f.section, "block": f.block, "block_label": label, "raw_name": f.name, "value": f.value, "unit_class": unit_class(f.value)} for f, label in zip(rows, labels)]
                different_blocks = len({f.block for f in rows}) == len(rows) and len(distinct) == len(rows)
                later_is_microphone = all(label == "microphone" for label in labels[1:])
                cause = "different_device_node" if len(rows) >= 2 and different_blocks and later_is_microphone else "unproven"
                conflict = {"seller_sku": sku, "name": name, "fragments": fragments, "cause": cause,
                            "unit_classes_differ": len({fragment["unit_class"] for fragment in fragments}) == len(fragments)}
            conflict["resolved"] = conflict["cause"] != "unproven"
            resolved += conflict["resolved"]
            disputed += not conflict["resolved"]
            result.append(conflict)
    per_row = {}
    for c in result:
        per_row.setdefault(c["seller_sku"], []).append(c["resolved"])
    out = {"step": "offline, zero requests", "stage18_conflicts_total": sum(r["conflicts"] for sku, r in review.items() if sku in ROWS), "conflicts_analysed": len(result),
           "resolved": resolved, "still_disputed": disputed, "rows": len(ROWS), "rows_with_every_conflict_resolved": sum(1 for v in per_row.values() if all(v)), "conflicts": result}
    (STAGE / "raw" / "conflict_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({k: v for k, v in out.items() if k != "conflicts"})
    for c in result:
        print(" ", c["seller_sku"], c["name"], c["cause"], [f.get("value") for f in c["fragments"]])


if __name__ == "__main__":
    with offline_only():
        main()
