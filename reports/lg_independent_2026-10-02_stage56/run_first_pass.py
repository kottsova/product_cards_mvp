"""First untouched production run for the frozen Stage 56 sample."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from product_tool import jobs, storage, worker
from product_tool.identity import ProductIdentity

HERE=Path(__file__).resolve().parent
DATASET=HERE/"dataset.json"
DB=ROOT/"data/stage56/stage56.sqlite3"
LOG=DB.parent/"lg_fetch_log.json"
MANIFEST=HERE/"first_pass_manifest.json"
PROGRESS=HERE/"first_pass_progress.jsonl"
STAGES=[1,2,3,4,6]

def main():
    expected=(HERE/"dataset.sha256").read_text(encoding="ascii").split()[0]
    actual=hashlib.sha256(DATASET.read_bytes()).hexdigest()
    if actual!=expected:
        raise SystemExit("Frozen dataset hash changed")
    if DB.exists() or MANIFEST.exists() or PROGRESS.exists():
        raise SystemExit("First pass already initialized; refusing to replace it")
    dataset=json.loads(DATASET.read_text(encoding="utf-8"))
    DB.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/"data/lg_fetch_log.json",LOG)
    jobs.initialize(DB)
    batch="stage56_independent_frozen"
    with storage._connection(DB) as connection:
        connection.execute("INSERT INTO batches VALUES (?,?,?,?,?)",
                           (batch,"catalog_2026-09-21.xlsx","frozen LG sample","{}",storage._now()))
        for n,item in enumerate(dataset["rows"],2):
            product={"brand":"LG","category":item["category"],"search_code":item["article"],
                     "name":item["name"],"alternate_code":""}
            connection.execute(
                "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,"
                "needs_confirmation,issues_json,original_values_json,identity_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (batch,n,product["name"],"LG",product["search_code"],"",product["category"],0,
                 "[]",json.dumps(product,ensure_ascii=False),
                 json.dumps(ProductIdentity.from_product(product).to_dict(),ensure_ascii=False))
            )
        rows=[dict(x) for x in connection.execute(
            "SELECT id,row_number,search_code,category FROM products WHERE batch_id=? ORDER BY row_number",(batch,))]
    for item in rows:
        item["job_id"]=jobs.enqueue(DB,item["id"],STAGES)
    MANIFEST.write_text(json.dumps(
        {"dataset_sha256":actual,"database":str(DB.relative_to(ROOT)).replace("\\","/"),
         "batch_id":batch,"rows":rows,"stages":STAGES,"production_worker":"product_tool.worker.run_once",
         "custom_request_budget":None},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FROZEN_RUN",actual,len(rows),flush=True)
    for item in rows:
        if not worker.run_once(DB):
            raise RuntimeError("Queued job missing")
        job=jobs.list_jobs(DB,item["id"])[0]
        entry={"article":item["search_code"],"product_id":item["id"],
               "job_id":job["id"],"status":job["status"],"message":job["message"]}
        with PROGRESS.open("a",encoding="utf-8") as handle:
            handle.write(json.dumps(entry,ensure_ascii=False)+"\n")
        print("DONE",item["row_number"]-1,item["search_code"],job["status"],flush=True)
    print("FIRST_PASS_COMPLETE",flush=True)

if __name__=="__main__":
    main()
