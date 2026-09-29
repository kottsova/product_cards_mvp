"""Repeat the frozen Stage 51 LG pilot through the ordinary production worker."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from product_tool import jobs, readiness, storage, worker
from product_tool.adapters import access_stop
from product_tool.adapters.policy_fetch import append_log_entry, read_log
from product_tool.adapters.policy_session import RequestBudget, record_responses, request_budget
from product_tool.identity import ProductIdentity


HERE = Path(__file__).resolve().parent
STAGE51 = HERE.parent / "lg_generalization_2026-09-29_stage51"
DATASET = json.loads((STAGE51 / "dataset.json").read_text(encoding="utf-8"))
PRIOR = json.loads((STAGE51 / "first_pass.json").read_text(encoding="utf-8"))
PILOT = ROOT / "data" / "stage51_1_pilot"
DB = PILOT / "stage51_1.sqlite3"
RESULT = HERE / "repeat_result.json"
PROGRESS = PILOT / "progress.json"
STAGES = [1, 2, 3, 4, 6]
MAX_PER_ROW = 6
MAX_TOTAL = 60


def prepare() -> list[dict]:
    catalog = ROOT / "data" / "catalog_2026-09-21.xlsx"
    if hashlib.sha256(catalog.read_bytes()).hexdigest() != DATASET["catalog_sha256"]:
        raise SystemExit("Catalog bytes changed since dataset was frozen")
    if DB.exists():
        with storage._connection(DB) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT id,search_code,category FROM products ORDER BY row_number")]
    PILOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data" / "lg_fetch_log.json", PILOT / "lg_fetch_log.json")
    active = access_stop.active_stops(read_log(PILOT / "lg_fetch_log.json"))
    if "www.lg.com" in active:
        raise SystemExit(f"Official LG host still has active stop: {active['www.lg.com']}")
    # The Stage 51 first pass observed a real DNS 401. Preserve that
    # observation in this isolated pilot, so it is not probed a second time.
    observed_at = datetime.fromtimestamp((STAGE51 / "first_pass.json").stat().st_mtime,
                                         tz=timezone.utc).isoformat()
    for row in PRIOR["rows"]:
        for source in row["sources"]:
            if source["source_key"] != "dns" or not source["url"]:
                continue
            match = re.search(r"HTTP (401|403|429)", source["error"])
            if match:
                append_log_entry(PILOT / "dns_fetch_log.json", {
                    "url": source["url"], "final_url": source["url"],
                    "status_code": int(match.group(1)), "checked_at": observed_at,
                    "access_status": "captcha_or_blocked", "protection_status": "ordinary_page",
                    "source_session": "stage51_first_pass",
                })
    jobs.initialize(DB)
    with storage._connection(DB) as connection:
        connection.execute("INSERT INTO batches VALUES (?, ?, ?, ?, ?)",
                           ("stage51_1_pilot", "stage51_dataset.json", "frozen", "{}", storage._now()))
        for n, item in enumerate(DATASET["rows"], 2):
            product = {"brand": "LG", "category": item["category"], "name": item["catalog_name"],
                       "search_code": item["article"], "alternate_code": ""}
            connection.execute(
                "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,"
                "needs_confirmation,issues_json,original_values_json,identity_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("stage51_1_pilot", n, product["name"], "LG", product["search_code"], "",
                 product["category"], 0, "[]", json.dumps(product, ensure_ascii=False),
                 json.dumps(ProductIdentity.from_product(product).to_dict(), ensure_ascii=False)),
            )
        rows = [dict(row) for row in connection.execute(
            "SELECT id,search_code,category FROM products ORDER BY row_number")]
    for row in rows:
        jobs.enqueue(DB, row["id"], STAGES)
    return rows


def summarize(rows: list[dict], budget: RequestBudget, *, halted: str = "") -> dict:
    items = []
    for row in rows:
        product_id = row["id"]
        job = jobs.list_jobs(DB, product_id)[0]
        pages = jobs.get_source_pages(DB, product_id)
        photos = jobs.get_photo_candidates(DB, product_id)
        resolved = jobs.get_resolved(DB, product_id)
        state = readiness.card_readiness(DB, product_id)
        items.append({
            "article": row["search_code"], "category": row["category"],
            "job_id": job["id"], "job_status": job["status"], "job_message": job["message"],
            "readiness": state,
            "sources": [{key: page[key] for key in ("source_key", "url", "match_level", "error", "evidence")}
                        for page in pages],
            "raw_facts": len(jobs.get_facts(DB, product_id)),
            "confirmed_specs": sum(x["status"] in {"full_sku_lg", "supplier_confirmed"} for x in resolved),
            "photos_found": len(photos),
            "photos_selected": sum(bool(p["selected"]) for p in photos),
            "photos_confirmed": state["official_gallery_from_exact_pages"],
            "documents": [{key: d[key] for key in ("title", "language", "direct_url", "source_url")}
                          for d in jobs.get_documents(DB, product_id)],
        })
    with storage._connection(DB) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("products", "search_jobs")}
    return {"dataset_sha256": hashlib.sha256((STAGE51 / "dataset.json").read_bytes()).hexdigest(),
            "halted": halted, "rows": items, "budget_total": budget.total,
            "budget_log": budget.log, "sqlite_integrity": integrity,
            "foreign_key_violations": fk, "counts": counts,
            "active_lg_stops": access_stop.active_stops(read_log(PILOT / "lg_fetch_log.json")),
            "active_dns_stops": access_stop.active_stops(read_log(PILOT / "dns_fetch_log.json"))}


def main() -> int:
    rows = prepare()
    previous = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
    budget = RequestBudget(max_per_row=MAX_PER_ROW, max_total=MAX_TOTAL)
    budget.total = previous.get("budget_total", 0)
    budget.log = previous.get("budget_log", [])
    halted = ""
    with request_budget(budget), record_responses(PILOT / "responses"):
        for row in rows:
            current = jobs.list_jobs(DB, row["id"])[0]
            if current["status"] != "queued":
                continue
            budget.begin_row(row["search_code"])
            if not worker.run_once(DB):
                raise RuntimeError(f"Worker could not claim {row['search_code']}")
            job = jobs.list_jobs(DB, row["id"])[0]
            print(row["search_code"], job["status"], "http_budget", budget.total, flush=True)
            PROGRESS.write_text(json.dumps({"budget_total": budget.total, "budget_log": budget.log},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
            active = access_stop.active_stops(read_log(PILOT / "lg_fetch_log.json"))
            if "www.lg.com" in active:
                halted = "www.lg.com active stop after this row"
                print(halted, flush=True)
                break
    result = summarize(rows, budget, halted=halted)
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 3 if halted else 0


if __name__ == "__main__":
    raise SystemExit(main())
