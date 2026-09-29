"""Read-only Stage 31 integrity check; writes only this stage's result."""
from __future__ import annotations
import gzip
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
import _pipeline_migration as mig
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    declaration=json.loads((STAGE/"raw/route_declaration.json").read_text(encoding="utf-8"))
    started=datetime.fromisoformat(declaration["declared_at"]).timestamp()
    catalog=ROOT/"data/catalog_2026-09-21_filtered.xlsx"
    registry=ROOT/"product_tool/config/source_catalog.v2.json"
    pins={path:mig.check_migrated_file(path,sha(ROOT/path))[0] for path in mig.ALL_AUTHORIZED_CHANGES}
    prior=[p for p in (ROOT/"reports").glob("source_census_*") if p!=STAGE]
    modified=sorted(p.relative_to(ROOT).as_posix() for directory in prior for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.stat().st_mtime>started)
    records=[json.loads(line) for line in (STAGE/"route_check/responses/index.jsonl").read_text(encoding="utf-8").splitlines()]
    response_hashes={}
    for item in records:
        if item["saved_as"]:
            with gzip.open(STAGE/"route_check/responses"/item["saved_as"],"rt",encoding="utf-8",newline="") as handle:
                response_hashes[item["url"]]=hashlib.sha256(handle.read().encode("utf-8")).hexdigest()==item["sha256"]
    route=json.loads((STAGE/"raw/route_check_result.json").read_text(encoding="utf-8"))
    config=json.loads((ROOT/"product_tool/config/coverage_planner.v1.json").read_text(encoding="utf-8"))
    selected=config["selected_products"]["samsung"]["products"]
    log=STAGE/"route_check/workdir/samsung_fetch_log.json"
    entries=json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    result={
        "catalog_unchanged":sha(catalog)==declaration["catalog_sha256_before"],
        "catalog_matches_known_pin":sha(catalog)=="99789238cde44dd2a5ec776f504944d9d91ab5698770cff8126f353212e107ba",
        "source_registry_unchanged":sha(registry)==declaration["registry_sha256_before"],
        "source_registry_pin_ok":pins["product_tool/config/source_catalog.v2.json"],
        "protected_pins_ok":all(pins.values()),
        "failed_protected_pins":sorted(p for p,ok in pins.items() if not ok),
        "prior_report_files_modified_since_declaration":modified,
        "local_database_modified_since_declaration":(ROOT/"data/batches.sqlite3").stat().st_mtime>started,
        "root_samsung_fetch_log_exists":(ROOT/"data/samsung_fetch_log.json").exists(),
        "stage31_stopped_hosts":sorted(stopped_hosts_from_fetch_log(x for x in entries if isinstance(x,dict))),
        "requests_spent":route["budget"]["spent"],
        "requests_within_declared_budget":route["budget"]["spent"]<=declaration["budget"]["max_real_requests_total"],
        "recorded_response_hashes_ok":all(response_hashes.values()) and len(response_hashes)==5,
        "selected_samsung_products":len(selected),
        "selected_samsung_categories":len({x["category"] for x in selected}),
        "cable_selected":any(x["seller_sku"]=="EP-DA705BBRGRU" for x in selected),
        "charger_unselected":all(x["seller_sku"]!="EP-T4511XBEGEU" for x in selected),
    }
    (STAGE/"protected_hashes_check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True,indent=2))
    assert result["catalog_unchanged"] and result["catalog_matches_known_pin"] and result["source_registry_unchanged"] and result["protected_pins_ok"]
    assert not modified and not result["local_database_modified_since_declaration"] and not result["stage31_stopped_hosts"]
    assert result["requests_within_declared_budget"] and result["recorded_response_hashes_ok"]
    assert result["selected_samsung_products"]==result["selected_samsung_categories"]==20
    assert result["cable_selected"] and result["charger_unselected"]

if __name__=="__main__":
    main()
