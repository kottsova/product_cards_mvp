"""Stage 37 offline UI to Excel replay. `tests` blocks all real HTTP/DNS."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from product_tool import jobs, lg_batch, worker  # noqa: E402
from tests.coverage_controls import NoDealer  # noqa: E402
from tests.test_stage37_lg_batch import LgBatchTests, Replay  # noqa: E402
from product_tool.adapters.lg_policy import default_lg_adapters  # noqa: E402

OUT = Path(__file__).resolve().parents[1]


def main():
    case = LgBatchTests("test_batch_selection_queue_replay_cards_and_excel")
    case.setUp()
    try:
        batch, ids = case.upload()
        chosen = [ids["XL7S"], ids["MS2032GAS"]]
        before = case.client.get(f"/batches/{batch['id']}")
        assert before.status_code == 200
        response = case.client.post(f"/batches/{batch['id']}/lg-search", data={
            "product_ids": [str(pid) for pid in chosen],
            "stages": [str(stage) for stage in lg_batch.DEFAULT_STAGES],
        }, follow_redirects=False)
        assert response.status_code == 303
        replay = Replay()
        adapter_runs = []
        def adapters():
            item = default_lg_adapters(case.root, underlying_lg=replay, min_interval_seconds=0)
            adapter_runs.append(item)
            return item
        times = {}
        for code in ("XL7S", "MS2032GAS"):
            started = time.perf_counter()
            assert worker.run_once(case.database, adapters, dns_adapter_factory=NoDealer)
            times[code] = round(time.perf_counter() - started, 3)
        result = {}
        for code in ("XL7S", "MS2032GAS", "CK43", "XL7S.OTHER"):
            pid = ids[code]
            history = jobs.list_jobs(case.database, pid)
            summary = lg_batch.card_summary(case.database, pid, history[0] if history else None)
            photos = jobs.get_photo_candidates(case.database, pid, include_excluded=False)
            result[code] = {
                "job_status": history[0]["status"] if history else "not_started",
                "card_readiness": summary["verdict"],
                "reasons": summary["reasons"],
                "facts": len(jobs.get_facts(case.database, pid)),
                "selected_photos": sum(1 for photo in photos if photo["selected"]),
                "documents": [{"title": doc["title"], "language": doc["language"]} for doc in jobs.get_documents(case.database, pid)],
                "instruction_events": [e["message"] for e in jobs.list_events(case.database, history[0]["id"]) if e["stage"] == 6] if history else [],
                "product_page_http": case.client.get(f"/products/{pid}").status_code,
            }
        excel = case.client.get(f"/batches/{batch['id']}/export.xlsx")
        excel.raise_for_status()
        (OUT / "offline_lg_export.xlsx").write_bytes(excel.content)
        summary = {
            "network": "saved responses only; tests package blocks HTTP/DNS",
            "chosen": ["XL7S", "MS2032GAS"],
            "saved_response_calls": len(replay.calls),
            "worker_seconds": times,
            "document_reports": {code: adapter_runs[i][1].reports for i, code in enumerate(("XL7S", "MS2032GAS"))},
            "batch_counts": lg_batch.batch_rows(case.database, batch["products"], set(chosen))[1],
            "products": result,
            "excel_bytes": len(excel.content),
        }
        (OUT / "offline_replay_result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"chosen": summary["chosen"], "seconds": times,
                          "status": {code: (v["job_status"], v["card_readiness"]) for code, v in result.items()}}, ensure_ascii=True))
    finally:
        case.doCleanups()


if __name__ == "__main__":
    main()
