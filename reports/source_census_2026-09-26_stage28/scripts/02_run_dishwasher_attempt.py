"""Stage 28 step 2 -- REAL REQUEST(S), exactly as raw/dishwasher_declaration.json declares: the one candidate Russian instruction file of DW60M5050BB/WT, ceiling 60 MB, at most 2 actual HTTP
requests (1 intended), through the ordinary access protection. The product page is read from the SAVED Stage 27 response (no request). The response is recorded, then reduced to its text in step 3.

Output: raw/dishwasher_result.json, dishwasher/responses/*, dishwasher/workdir/samsung_fetch_log.json
"""
from __future__ import annotations

import gzip
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S27 = ROOT / "reports/source_census_2026-09-25_stage27"
sys.path.insert(0, str(ROOT))

logging.disable(logging.CRITICAL)

from product_tool.adapters.common import SourceDocument  # noqa: E402
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log  # noqa: E402
from product_tool.adapters.policy_session import RequestBudget, record_responses, request_budget  # noqa: E402
from product_tool.adapters.samsung_source import default_samsung_adapter, match_level_of  # noqa: E402
from product_tool.adapters.samsung import extract_identity  # noqa: E402

ARTICLE = "DW60M5050BB/WT"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    declaration = json.loads((STAGE / "raw/dishwasher_declaration.json").read_text(encoding="utf-8"))
    started = now()
    assert started > declaration["declared_at"], "declare first"
    workdir = STAGE / "dishwasher/workdir"
    assert not workdir.exists(), "this attempt runs once"
    workdir.mkdir(parents=True)
    # the product page: the SAVED Stage 27 response, no request
    directory = S27 / "batch4/responses"
    page_url = next(json.loads(l)["url"] for l in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines() if "dw60m5050bb-wt/" in json.loads(l)["url"] and json.loads(l)["saved_as"])
    entry = next(json.loads(l) for l in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(l)["url"] == page_url)
    html = gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8").read()
    identity = extract_identity(html, page_url, ARTICLE)
    document = SourceDocument("samsung", "Samsung Казахстан", page_url, found_model=ARTICLE, match_level=match_level_of(identity), html=html)
    adapter = default_samsung_adapter(workdir, document_max_bytes=declaration["budget"]["document_ceiling_bytes"])
    budget = RequestBudget(max_per_row=2, max_total=2)
    budget.begin_row("dishwasher")
    with record_responses(STAGE / "dishwasher/responses"), request_budget(budget):
        documents, reason = adapter.find_documents(document, ARTICLE, deadline=time.monotonic() + 300, only_hrefs=[declaration["candidate"]["href"]])
    log = workdir / "samsung_fetch_log.json"
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    report = adapter.reports[ARTICLE]
    result = {"declared_at": declaration["declared_at"], "started_at": started, "finished_at": now(), "budget": {"max": 2, "spent": budget.total, "log": budget.log}, "stopped_hosts": sorted(stopped_hosts_from_fetch_log(e for e in entries if isinstance(e, dict))),
              "fetch_log": entries, "steps": report["steps"], "documents_saved": [d.__dict__ for d in documents], "reason": reason, "files": report["documents"], "page_model_data": report.get("page_model_data"),
              "outcome": "obtained_and_assessed" if any(f.get("facts") for f in report["documents"]) else "candidate_not_verified"}
    (STAGE / "raw/dishwasher_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(result["outcome"], "requests:", budget.total, "stopped:", result["stopped_hosts"])
    for f in report["documents"]:
        facts = f.get("facts") or {}
        print(f["state"], f.get("bytes"), "ru", facts.get("russian_by_text"), "tie", facts.get("tied_by_official_page"), "cat", (facts.get("names_catalog_model") or {}), "acc", (facts.get("acceptance") or {}).get("basis"), "pages", facts.get("pages"))


if __name__ == "__main__":
    main()
