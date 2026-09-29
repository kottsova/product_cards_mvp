"""Run the frozen LG pilot through the unchanged production worker in isolation."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from product_tool import jobs, readiness, storage, worker
from product_tool.adapters.policy_fetch import read_log, stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import RequestBudget, request_budget
from product_tool.identity import ProductIdentity


ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(__file__).resolve().parent
PILOT = ROOT / "data" / "stage51_pilot"
DB = PILOT / "stage51.sqlite3"
RESULT = STAGE / "first_pass.json"
DATASET = json.loads((STAGE / "dataset.json").read_text(encoding="utf-8"))
STAGES = [1, 2, 3, 4, 6]


def prepare() -> list[dict]:
    if DB.exists() or RESULT.exists():
        raise SystemExit("First pass already exists; refusing to replace it")
    PILOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data" / "lg_fetch_log.json", PILOT / "lg_fetch_log.json")
    stopped = stopped_hosts_from_fetch_log(read_log(PILOT / "lg_fetch_log.json"))
    if not {"www.lg.com", "www.sulpak.kz"}.issubset(stopped):
        raise SystemExit(f"Expected host stops not present: {sorted(stopped)}")
    jobs.initialize(DB)
    batch = "stage51_frozen_pilot"
    with storage._connection(DB) as connection:
        connection.execute("INSERT INTO batches VALUES (?, ?, ?, ?, ?)",
                           (batch, "stage51_fixture.json", "frozen", "{}", storage._now()))
        for n, item in enumerate(DATASET["rows"], 2):
            product = {"brand": "LG", "category": item["category"],
                       "search_code": item["article"], "name": item["catalog_name"],
                       "alternate_code": ""}
            connection.execute(
                "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,"
                "needs_confirmation,issues_json,original_values_json,identity_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (batch, n, product["name"], "LG", product["search_code"], "",
                 product["category"], 0, "[]", json.dumps(product, ensure_ascii=False),
                 json.dumps(ProductIdentity.from_product(product).to_dict(), ensure_ascii=False)),
            )
        rows = [dict(row) for row in connection.execute(
            "SELECT id,search_code,category FROM products WHERE batch_id=? ORDER BY row_number", (batch,))]
    for item in rows:
        item["job_id"] = jobs.enqueue(DB, item["id"], STAGES)
    return rows


def main() -> None:
    rows = prepare()
    budget = RequestBudget(max_per_row=2, max_total=3)
    with request_budget(budget):
        for item in rows:
            budget.begin_row(item["search_code"])
            if not worker.run_once(DB):
                raise RuntimeError(f"Queued job did not run: {item['search_code']}")
            job = jobs.list_jobs(DB, item["id"])[0]
            print(item["search_code"], job["status"], flush=True)
    summary = []
    for item in rows:
        product_id = item["id"]
        pages = jobs.get_source_pages(DB, product_id)
        photos = jobs.get_photo_candidates(DB, product_id)
        state = readiness.card_readiness(DB, product_id)
        job = jobs.list_jobs(DB, product_id)[0]
        summary.append({
            "article": item["search_code"], "category": item["category"],
            "job_id": item["job_id"], "job_status": job["status"],
            "job_message": job["message"], "readiness": state,
            "sources": [{k: p[k] for k in ("source_key", "url", "match_level", "error", "evidence")}
                        for p in pages],
            "raw_facts": len(jobs.get_facts(DB, product_id)),
            "confirmed_specs": sum(x["status"] == "confirmed" for x in jobs.get_resolved(DB, product_id)),
            "photos_found": len(photos),
            "photos_confirmed": sum(bool(p["selected"]) for p in photos),
            "documents": [{k: d[k] for k in ("title", "language", "direct_url", "source_url")}
                          for d in jobs.get_documents(DB, product_id)],
        })
    with storage._connection(DB) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        product_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        job_count = connection.execute("SELECT COUNT(*) FROM search_jobs").fetchone()[0]
    result = {"frozen_dataset": "dataset.json", "rows": summary,
              "policy_budget_total": budget.total, "policy_budget_log": budget.log,
              "sqlite_integrity": integrity, "foreign_key_violations": fk,
              "product_count": product_count, "job_count": job_count,
              "stopped_hosts": sorted(stopped_hosts_from_fetch_log(read_log(PILOT / "lg_fetch_log.json")))}
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("First pass saved:", RESULT, "official/Sulpak requests:", budget.total)


if __name__ == "__main__":
    main()



