"""Offline ordinary upload -> jobs -> worker -> Excel export for two Stage 31 catalog rows."""
from __future__ import annotations
import gzip
import importlib.util
import json
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
logging.disable(logging.CRITICAL)

import _samsung_replay as R
from product_tool import jobs
from product_tool.offline_guard import offline_only

spec=importlib.util.spec_from_file_location("run4",ROOT/"reports/source_census_2026-09-25_stage27/scripts/02_run_batch4.py")
run4=importlib.util.module_from_spec(spec)
spec.loader.exec_module(run4)

def main():
    declaration=json.loads((STAGE/"raw/route_declaration.json").read_text(encoding="utf-8"))
    directory=STAGE/"route_check/responses"
    pages={}
    for line in (directory/"index.jsonl").read_text(encoding="utf-8").splitlines():
        item=json.loads(line)
        if item["saved_as"]:
            with gzip.open(directory/item["saved_as"],"rt",encoding="utf-8",newline="") as handle:
                pages[item["url"]]=(item["status"],handle.read())
    cards=[(declaration["products"][sku]["category"],sku) for sku in ("EP-T4511XBEGEU","EP-DA705BBRGRU")]
    with offline_only(),TemporaryDirectory() as tmp:
        replay=R.Replay(extra_pages=pages)
        batch=R.run_products(Path(tmp),cards=cards,replay=replay)
        records=[]
        for outcome in batch["outcomes"]:
            record=run4.card_record(batch["database"],outcome)
            record["official_facts"]=[{"name":f["raw_name"],"value":f["raw_value"],"source_key":f["source_key"]} for f in jobs.get_facts(batch["database"],outcome["product_id"]) if f["source_key"]=="samsung"]
            records.append(record)
        (STAGE/"raw/offline_two_result.json").write_text(json.dumps({"cards":records},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (STAGE/"raw/offline_replay_calls.json").write_text(json.dumps({"calls":replay.calls,"refused":replay.refused,"dealer_calls":batch["dealer_session"].calls},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (STAGE/"export").mkdir(exist_ok=True)
        (STAGE/"export/samsung_two_export.xlsx").write_bytes(batch["export"])
        assert not replay.refused and not batch["dealer_session"].calls
        print(json.dumps({"cards":[{"article":x["article"],"job":x["job_status"],"readiness":x["readiness"]["verdict"],"page_match":x["readiness"]["page_match_level"],"facts":x["facts"]["samsung"],"photos":x["photos"],"documents":len(x["documents"]),"gaps":x["readiness"]["gaps"]} for x in records],"replay_calls":len(replay.calls),"export_bytes":len(batch["export"])},ensure_ascii=True,indent=2))

if __name__=="__main__":
    main()
