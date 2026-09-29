"""Stage 28 step 1 -- OFFLINE. Declares, BEFORE any request, the one limited attempt to obtain the dishwasher's candidate Russian instruction that Stage 27 could not read (the file exceeded the
40 MB cap). Owner permission (Stage 28): one attempt, ceiling 60 MB, a declared budget of actual HTTP requests, the already known link, the ordinary access protection.

Output: raw/dishwasher_declaration.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S27 = ROOT / "reports/source_census_2026-09-25_stage27"
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402


def main() -> None:
    result = json.loads((S27 / "raw/batch4_result.json").read_text(encoding="utf-8"))
    card = next(c for c in result["cards"] if c["article"] == "DW60M5050BB/WT")
    href = next(e["url"] for e in result["budget"]["log"] if e["row"] == "1" and "RU_UK_KK_UZ_R.pdf" in e["url"])
    truncated = next(e for e in card["document_files_assessed"] if e["state"] == "reachable_but_not_a_complete_pdf")
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": "28 / dishwasher candidate Russian instruction", "brand": "Samsung", "article": "DW60M5050BB/WT",
        "candidate": {"href": href, "file_name": truncated["file"], "why_a_candidate": "the file name of the link the official product page prints says RU_UK_KK_UZ; a name proves nothing about the text, so it is only a CANDIDATE until its text is read",
                      "stage27_outcome": "the download reached the 40 MB cap: not a complete PDF, nothing read"},
        "budget": {"max_real_http_requests": 2, "intended": 1, "why_two": "fetch_with_retry repeats a request once after a network error or a 429/5xx answer; a third request is refused by the budget before it is made",
                   "document_ceiling_bytes": 60_000_000, "pacing_seconds": 1.5, "hosts": ["org.downloadcenter.samsung.com", "downloadcenter.samsung.com (the redirect target)"], "product_page_requests": 0, "other_files": 0, "images": 0},
        "protection": "PolicyAwareSession: allowed hosts, redirect-chain check, persisted stop log <workdir>/samsung_fetch_log.json, RequestBudget(max_total=2); a 401/403/429 or a confirmed challenge stops the host and ends the attempt",
        "url_construction": "none: the link is the one the official page printed in Stage 27",
        "outcomes_and_statuses": {"file complete and readable": "assessed by its own text (language, tie to the page, model named) with the Stage 27 owner rules; saved as a document", "file over the ceiling, an error, a stop, or unreadable text":
                                  "status 'кандидат на русскую инструкцию не проверен' -- never 'русской инструкции нет'; the English file of Stage 27 does not stand in for it"},
        "not_done": "no other file, no other product, no page request",
    }
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    (STAGE / "raw/dishwasher_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(declaration["declared_at"], href[-60:])


if __name__ == "__main__":
    with offline_only():
        main()
