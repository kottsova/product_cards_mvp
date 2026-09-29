"""Stage 20 step 2 -- the LG pilot: the ORDINARY worker.run_once() for the 12 rows fixed in step 1.

What is real here: the default adapter factories of the worker (LGAdapter, LGRUAdapter and SulpakAdapter through
PolicyAwareSession, DNS default), stages 1,2,3,4,6, one job per row, the jobs database and the export code. What is
added around it: the request budget (<=5 per row, <=60 in total, refused before the request is made), the response
recorder (so failures can be diagnosed offline) and the halt rule (a stopped host ends the pilot before the next row).

Everything is written under reports/source_census_2026-09-24_stage20/pilot/ (the pilot's own database and log; the
user's data/ directory is not touched).

Output: pilot/workdir/*, pilot/responses/*, raw/pilot_rows.json, raw/pilot_requests.json
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
PILOT = STAGE / "pilot"
sys.path.insert(0, str(ROOT))

from product_tool import jobs, worker  # noqa: E402
from product_tool.adapters.lg_policy import lg_log_path  # noqa: E402
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log  # noqa: E402
from product_tool.adapters.policy_session import RequestBudget, record_responses, request_budget  # noqa: E402
from product_tool.coverage import executor  # noqa: E402

STAGES = [1, 2, 3, 4, 6]


def snapshot(database: Path, product_id: int, job: dict) -> dict:
    sources = jobs.get_source_pages(database, product_id)
    facts = jobs.get_facts(database, product_id)
    resolved = jobs.get_resolved(database, product_id)
    photos = jobs.get_photo_candidates(database, product_id, include_excluded=True)
    documents = jobs.get_documents(database, product_id)
    events = jobs.list_events(database, job["id"])
    per_source = {}
    for s in sources:
        key = s["source_key"]
        per_source[key] = {
            "site": s["site_name"], "match_level": s["match_level"], "url": s["url"], "found_model": s["found_model"], "error": s["error"], "evidence": s["evidence"][:300],
            "facts": sum(1 for f in facts if f["source_key"] == key),
            "photos": {kind: sum(1 for p in photos if p["source_key"] == key and p["kind"] == kind) for kind in sorted({p["kind"] for p in photos if p["source_key"] == key})},
            "photos_selected": sum(1 for p in photos if p["source_key"] == key and p["selected"] and p["kind"] == "product_gallery"),
            "description_chars": len(s.get("description") or ""),
        }
    return {
        "job": {"status": job["status"], "message": job["message"], "stages": job["stages"]},
        "sources": per_source,
        "resolved": {"total": len(resolved), "by_status": {st: sum(1 for r in resolved if r["status"] == st) for st in sorted({r["status"] for r in resolved})}, "conflicts": sum(1 for r in resolved if r.get("conflict"))},
        "documents": [{"title": d["title"], "language": d["language"], "date": d["document_date"], "support_model": d["support_model"], "direct_url": d["direct_url"], "source_key": d.get("source_key", "")} for d in documents],
        "events": [{"stage": e.get("stage"), "level": e.get("level"), "message": e.get("message"), "source_url": e.get("source_url")} for e in events],
    }


def main() -> None:
    selection = json.loads((STAGE / "raw/pilot_selection.json").read_text(encoding="utf-8"))
    declaration = json.loads((STAGE / "raw/predeclaration.json").read_text(encoding="utf-8"))
    assert declaration["budget"]["max_requests_per_row"] == 5 and declaration["budget"]["max_requests_total"] == 60
    if PILOT.exists():
        shutil.rmtree(PILOT)
    workdir = PILOT / "workdir"
    workdir.mkdir(parents=True)
    database = workdir / "batches.sqlite3"
    jobs.initialize(database)
    log = lg_log_path(workdir)
    budget = RequestBudget(max_per_row=5, max_total=60)
    rows, halted, not_run = [], "", []
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assert started > declaration["declared_at"]
    with request_budget(budget), record_responses(PILOT / "responses"):
        for index, row in enumerate(selection["rows"]):
            if halted:
                not_run.append({"seller_sku": row["seller_sku"], "category": row["category"], "reason": halted})
                continue
            unit = {"catalog_row": row["catalog_row"], "brand": row["brand"], "category": row["category"], "title": row["title"], "seller_sku": row["seller_sku"]}
            product_id = executor._ensure_product(database, unit, "lg-pilot")
            job_id = jobs.enqueue(database, product_id, STAGES)
            budget.begin_row(row["seller_sku"])
            t0 = time.monotonic()
            processed = worker.run_once(database, clock=time.monotonic)
            elapsed = round(time.monotonic() - t0, 1)
            job = next(j for j in jobs.list_jobs(database, product_id) if j["id"] == job_id)
            data = snapshot(database, product_id, job)
            data.update({"index": index, "seller_sku": row["seller_sku"], "category": row["category"], "title": row["title"], "product_id": product_id, "processed": processed,
                         "seconds": elapsed, "requests_in_row": budget.row})
            rows.append(data)
            entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
            stopped = sorted(stopped_hosts_from_fetch_log(entries))
            if stopped:
                halted = f"host stopped by the policy after {row['seller_sku']}: {', '.join(stopped)}"
    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    requests_out = {"started_at": started, "finished_at": finished, "max_per_row": 5, "max_total": 60, "requests_total": budget.total, "per_row": {r["seller_sku"]: r["requests_in_row"] for r in rows},
                    "max_requests_in_one_row": max((r["requests_in_row"] for r in rows), default=0), "log": budget.log, "fetch_log": entries, "halted": halted, "rows_not_run": not_run,
                    "stopped_hosts": sorted(stopped_hosts_from_fetch_log(entries))}
    (STAGE / "raw/pilot_requests.json").write_text(json.dumps(requests_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (STAGE / "raw/pilot_rows.json").write_text(json.dumps({"rows": rows, "halted": halted, "not_run": not_run}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rows_run={len(rows)} requests_total={budget.total} max_in_row={requests_out['max_requests_in_one_row']} halted={halted!r}")
    for r in rows:
        srcs = {k: (v["match_level"], v["facts"], v["error"][:50]) for k, v in r["sources"].items()}
        print(f"  {r['seller_sku']:<16} job={r['job']['status']:<12} req={r['requests_in_row']} {r['seconds']}s docs={len(r['documents'])} {srcs}")


if __name__ == "__main__":
    main()
