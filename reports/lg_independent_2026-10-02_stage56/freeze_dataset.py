"""Freeze an independent Stage 56 LG catalog sample before any worker run."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CATALOG = ROOT / "data/catalog_2026-09-21.xlsx"
DATASET = HERE / "dataset.json"
POOL = ROOT / "data/stage56/catalog_pool.json"
STAGE51 = ROOT / "reports/lg_generalization_2026-09-29_stage51/dataset.json"
SELECTION = [
    ("32LB650B6LA", "Older TV; other-region discovery may be needed."),
    ("43NANO80A6B.ARUG", "TV full RU sales-code variant."),
    ("43NANO756QA_KZ", "TV regional _KZ suffix; base/family guard."),
    ("F2Y1NS5W.AGWPCOM", "Washer full regional sales code."),
    ("W1S1CVKK2HM", "Large washer-dryer / WashTower-like family case."),
    ("DC90V9V9WN", "Dryer near a different Stage 51 family variant."),
    ("GC-B399SMCL.APZQCIS", "Refrigerator full color/region variant."),
    ("GC-B509FNPW.APYQCIS", "Refrigerator full family/size/color variant."),
    ("MH6565DIS", "Microwave grill base model."),
    ("MS2535GIS", "Microwave solo base model."),
    ("A9N-PRIME", "Vacuum with hyphenated model."),
    ("VC5420NHTG.AIGQCIS", "Vacuum with full regional suffix."),
    ("S70TY.ARUSLLK", "Soundbar full regional suffix."),
    ("OL90DK.DRUSLLK", "Audio system full regional suffix."),
    ("WZ09AWN", "Air conditioner distinct from prior P12ED and AC09BK."),
]

def main():
    if DATASET.exists():
        raise SystemExit("Frozen Stage 56 dataset exists; refusing to replace it")
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    available = {x["article"].upper(): x for x in pool["rows"]}
    old51 = {x["article"].upper() for x in json.loads(STAGE51.read_text(encoding="utf-8"))["rows"]}
    with sqlite3.connect(ROOT / "data/batches.sqlite3") as connection:
        live = {str(x[0]).upper() for x in connection.execute("SELECT search_code FROM products")}
    rows=[]
    for article, reason in SELECTION:
        item=available.get(article.upper())
        if item is None or item["in_tests"] or article.upper() in old51 or article.upper() in live:
            raise ValueError(f"Not independent: {article}")
        rows.append({k:item[k] for k in ("excel_row","category","article","name")}|{"reason":reason})
    if len(rows)!=15 or len({x["article"].upper() for x in rows})!=15:
        raise ValueError("Expected 15 distinct products")
    payload={"stage":56,"frozen_at_utc":datetime.now(timezone.utc).isoformat(),
             "catalog":str(CATALOG.relative_to(ROOT)).replace("\\","/"),
             "catalog_sha256":hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
             "sampling_rule":"Real catalog rows, absent from live batches, Stage 51 and Python regression fixtures; selected before first run.",
             "rows":rows}
    encoded=(json.dumps(payload,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    DATASET.write_bytes(encoded)
    (HERE/"dataset.sha256").write_text(hashlib.sha256(encoded).hexdigest()+"  dataset.json\n",encoding="ascii")
    print("FROZEN",len(rows),hashlib.sha256(encoded).hexdigest())
    for item in rows:
        print(item["category"],"|",item["article"])

if __name__=="__main__":
    main()
