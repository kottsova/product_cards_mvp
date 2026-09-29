"""Stage 27 step 2 -- REAL REQUESTS, exactly as raw/batch4_declaration.json declares them (<= 14 requests in all, <= 7 per product, 1.5 s pacing, 40 MB document cap, three Samsung hosts).

The ORDINARY path: an Excel book with the four catalog rows is uploaded to the web app, the draft is confirmed into a batch, one search job per product is created by the product's own POST
(stages 1, 2, 3, 4, 6), worker.run_once() processes the queue with the DEFAULT Samsung adapter (PolicyAwareSession: allowed hosts, redirect check, persisted stop log, request budget), and the
batch is exported through the web route. Every real response is recorded (batch4/responses) for offline replay.

Stop rule: after every job the persisted log is re-read; if any host is stopped, no further job is started.

Output: raw/batch4_result.json, export/samsung_batch4_export.xlsx, batch4/responses/*, batch4/workdir/* (database, samsung_fetch_log.json)
"""
from __future__ import annotations

import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

logging.disable(logging.CRITICAL)

import _samsung_replay as R  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from product_tool import card_evidence, jobs, samsung_pipeline, samsung_readiness, storage, worker  # noqa: E402
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log  # noqa: E402
from product_tool.adapters.policy_session import record_responses  # noqa: E402
from product_tool.web import create_app  # noqa: E402

WORKDIR = STAGE / "batch4/workdir"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stopped(log: Path) -> list[str]:
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    return sorted(stopped_hosts_from_fetch_log(e for e in entries if isinstance(e, dict)))


def card_record(database: Path, outcome: dict) -> dict:
    pid = outcome["product_id"]
    pages = jobs.get_source_pages(database, pid)
    facts = jobs.get_facts(database, pid)
    resolved = jobs.get_resolved(database, pid)
    photos = jobs.get_photo_candidates(database, pid, include_excluded=True)
    gallery = [p for p in photos if p["source_key"] == "samsung" and p["kind"] == "product_gallery"]
    excluded = [p for p in photos if p["source_key"] == "samsung" and p["kind"] == "excluded"]
    page = card_evidence.load(database, pid, "samsung_page") or {}
    documents = card_evidence.load(database, pid, "samsung_documents") or {}
    return {
        "category": outcome["category"], "article": outcome["article"], "job_status": outcome["status"], "job_message": outcome["message"],
        "events": [{"stage": e["stage"], "level": e["level"], "message": e["message"]} for e in jobs.list_events(database, outcome["job_id"])],
        "sources": {s["source_key"]: {k: s[k] for k in ("site_name", "url", "found_model", "match_level", "evidence", "error")} for s in pages}, "identification_status": jobs.identification_status(pages),
        "facts": {"samsung": sum(1 for f in facts if f["source_key"] == "samsung"), "dns": sum(1 for f in facts if f["source_key"] == "dns")},
        "resolved": {"total": len(resolved), "conflicts": sum(1 for r in resolved if r["conflict"]), "by_status": {s: sum(1 for r in resolved if r["status"] == s) for s in sorted({r["status"] for r in resolved})}},
        "photos": {"gallery_found": len(gallery), "gallery_selected": sum(1 for p in gallery if p["selected"]), "thumbnails_excluded": sum(1 for p in excluded if p["excluded_reason"] == "thumbnail"),
                   "three_d_excluded": sum(1 for p in excluded if p["excluded_reason"] == "3d_model"), "bound_by_asset_path": len((page.get("photos") or {}).get("bound_by_asset_path") or []), "from": (page.get("photos") or {}).get("from", "")},
        "documents": [{k: d[k] for k in ("title", "language", "direct_url", "source_url", "product_model", "support_model")} for d in jobs.get_documents(database, pid)],
        "document_files_assessed": [{"file": e.get("file"), "state": e.get("state"), "link_model_name": e.get("link_model_name"), "final_url": e.get("final_url"), "bytes": e.get("bytes"), "facts": e.get("facts")} for e in documents.get("documents", [])],
        "page_model_data": documents.get("page_model_data"), "page_evidence": {"route": page.get("route"), "identity": page.get("identity"), "specs": page.get("specs"), "photos": page.get("photos"), "gaps": page.get("gaps"), "steps": page.get("steps")},
        "readiness": samsung_readiness.card_readiness(database, pid), "open_reviews": card_evidence.open_reviews(database, pid), "requests": card_evidence.load(database, pid, "samsung_requests") or {},
    }


def main() -> None:
    declaration = json.loads((STAGE / "raw/batch4_declaration.json").read_text(encoding="utf-8"))
    started = now()
    assert started > declaration["declared_at"], "the budget must be declared before the first request"
    assert declaration["budget"]["max_real_requests_total"] == 14 and declaration["budget"]["max_real_requests_per_product"] == 7
    assert not WORKDIR.exists(), "batch4/workdir already exists: this batch runs once"
    WORKDIR.mkdir(parents=True)
    (STAGE / "export").mkdir(exist_ok=True)
    database = WORKDIR / "batches.sqlite3"
    cards = [(category, item["article"]) for category, item in declaration["products"].items()]
    units = R.catalog_units({article for _, article in cards})
    rows = [["Предмет", "Бренд", "Наименование", "Артикул продавца", "Модель"]] + [[units[a]["category"], units[a]["brand"], units[a]["title"], a, ""] for _, a in cards]
    log = WORKDIR / "samsung_fetch_log.json"
    started_jobs, not_started, halted = [], [], []
    with record_responses(STAGE / "batch4/responses"), samsung_pipeline.batch_budget(declaration["budget"]["max_real_requests_total"]) as budget, TestClient(create_app(WORKDIR)) as client:
        uploaded = client.post("/upload", files={"file": ("samsung_batch4.xlsx", R.workbook_of(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, follow_redirects=False)
        draft_path = uploaded.headers["location"]
        form = {}
        for number, (_, article) in enumerate(cards, start=2):
            form.update({f"brand_{number}": units[article]["brand"], f"search_code_{number}": article, f"alternate_code_{number}": "", f"category_{number}": units[article]["category"]})
        confirmed = client.post(f"{draft_path}/confirm", data=form, follow_redirects=False)
        batch_id = confirmed.headers["location"].rsplit("/", 1)[-1]
        products = {p["search_code"]: p for p in storage.get_batch(database, batch_id)["products"]}
        for _, article in cards:
            assert client.post(f"/products/{products[article]['id']}/search", data={"stages": ["1", "2", "3", "4", "6"]}, follow_redirects=False).status_code == 303
        while True:
            if stopped(log):
                halted = stopped(log)
                break
            processed = worker.run_once(database, clock=time.monotonic)
            if not processed:
                break
            started_jobs.append(now())
        if halted:
            not_started = [a for _, a in cards if jobs.list_jobs(database, products[a]["id"])[0]["status"] in ("queued", "running")]
        exported = client.get(f"/batches/{batch_id}/export.xlsx")
        (STAGE / "export/samsung_batch4_export.xlsx").write_bytes(exported.content)
    outcomes = []
    for category, article in cards:
        product_id = products[article]["id"]
        job = jobs.list_jobs(database, product_id)[0]
        outcomes.append({"category": category, "article": article, "product_id": product_id, "job_id": job["id"], "status": job["status"], "message": job["message"]})
    result = {"declared_at": declaration["declared_at"], "started_at": started, "finished_at": now(), "batch_id": batch_id, "budget": {"max_total": budget.max_total, "spent_total": budget.total, "max_per_row": budget.max_per_row, "log": budget.log},
              "stopped_hosts_after_run": stopped(log), "halted_before_finishing": halted, "not_started": not_started, "fetch_log_entries": json.loads(log.read_text(encoding="utf-8")) if log.exists() else [],
              "cards": [card_record(database, o) for o in outcomes]}
    (STAGE / "raw/batch4_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for card in result["cards"]:
        r = card["readiness"]
        print(f"{card['category']:<22} job={card['job_status']:<13} {r['verdict']:<24} {r['page_match_level']:<18} facts={card['facts']['samsung']:<4} photos={card['photos']['gallery_selected']}/{card['photos']['gallery_found']:<3} gaps={r['gaps']}")
    print("requests spent:", budget.total, "of", budget.max_total, "| stopped hosts:", result["stopped_hosts_after_run"], "| not started:", not_started)


if __name__ == "__main__":
    main()
