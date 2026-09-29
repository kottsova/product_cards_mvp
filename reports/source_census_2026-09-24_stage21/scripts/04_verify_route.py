"""Stage 21 step 4 -- the separately budgeted verification of the NEW routes, for the replay of the same 12 rows.

Declared BEFORE the first request (raw/verify_declaration.json). Budget: at most 14 requests to www.lg.com, pacing 1 s.
  Product pages (<= 11): exactly the URLs the phase-1 replay reported as needed and unrecorded (raw/replay_phase1.json): each
      is an observed URL -- a slug match in the saved LG Russia sitemap (10 pages) or in the saved LG Kazakhstan sitemap
      (24mr400-b, the D4 case). Nothing is built.
  Documents route (<= 3): the manuals link PRINTED on the saved LG Russia page of XL7S
      (https://www.lg.com/ru/support/manuals?csSalesCode=XL7S.DRUSLLK): one request; then at most 2 more, each a link printed on
      the fetched page under https://www.lg.com/ru/support/ whose URL contains 'manual' or 'download' (document order). No PDF is downloaded.
  Stop rule: 401/403/429 or a confirmed challenge stops the host in data/lg_fetch_log.json and ends the run; requests over budget are refused.

Output: raw/verify_declaration.json, raw/verify_result.json, verify/responses/*
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg import lg_session  # noqa: E402
from product_tool.adapters.lg_policy import LG_HOSTS, lg_log_path  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402

MANUALS = "https://www.lg.com/ru/support/manuals?csSalesCode=XL7S.DRUSLLK"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    phase1 = json.loads((STAGE / "raw/replay_phase1.json").read_text(encoding="utf-8"))
    pages = phase1["unrecorded"]
    assert len(pages) <= 11 and all(urlsplit(u).hostname == "www.lg.com" for u in pages)
    declaration = {"declared_at": now(), "max_requests": 14, "host": "www.lg.com", "pacing_seconds": 1.0, "product_pages": pages, "documents_route": {"first": MANUALS, "follow_ups_max": 2,
                   "follow_up_rule": "links printed on the fetched page under https://www.lg.com/ru/support/ whose URL contains 'manual' or 'download', document order; no PDF downloaded"},
                   "stop_rule": "401/403/429 or confirmed challenge: host stopped in data/lg_fetch_log.json, run ends", "url_construction": "none", "script": "reports/source_census_2026-09-24_stage21/scripts/04_verify_route.py"}
    (STAGE / "raw/verify_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    client = PolicyAwareSession(lg_log_path(ROOT / "data"), allowed_hosts=LG_HOSTS, underlying=lg_session())
    budget = RequestBudget(max_per_row=14, max_total=14)
    steps, halted = [], ""

    def fetch(label, url):
        nonlocal halted
        if halted:
            steps.append({"step": label, "url": url, "skipped": halted})
            return None
        try:
            response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            steps.append({"step": label, "url": url, "status": response.status_code, "bytes": len(response.content)})
            return response
        except SourceError as exc:
            steps.append({"step": label, "url": url, "error": str(exc)})
            if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                halted = str(exc)
            return None

    docs_analysis = {}
    with request_budget(budget), record_responses(STAGE / "verify/responses"):
        budget.begin_row("verify")
        for url in pages:
            fetch("page", url)
        manuals = fetch("docs", MANUALS)
        if manuals is not None:
            soup = BeautifulSoup(manuals.text, "html.parser")
            hrefs = [urljoin(manuals.url, a["href"]) for a in soup.select("a[href]")]
            follow = []
            for h in hrefs:
                if h.startswith("https://www.lg.com/ru/support/") and re.search(r"manual|download", h, re.I) and h not in follow and h != MANUALS and h.split("?")[0] != MANUALS.split("?")[0]:
                    follow.append(h)
            docs_analysis = {"html_bytes": len(manuals.text), "title": (soup.title.string or "").strip()[:100] if soup.title else "", "pdf_or_download_links_in_static_html": [h for h in hrefs if re.search(r"downloadFile|\.pdf|gscs-b2c", h, re.I)][:10],
                             "language_labels_in_static_html": sorted(set(re.findall(r"Русский|Russian|Қазақша|English", manuals.text)))[:6], "candidate_follow_ups": follow[:5], "script_tags": len(soup.select("script")),
                             "has_csSalesCode_input": "csSalesCode" in manuals.text}
            for h in follow[:2]:
                fetch("docs-follow", h)
    result = {"finished_at": now(), "requests_made": budget.total, "halted": halted, "steps": steps, "documents_analysis": docs_analysis}
    (STAGE / "raw/verify_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"requests_made": budget.total, "halted": halted, "steps": [(s["step"], s.get("status") or s.get("error") or s.get("skipped"), s["url"][-50:]) for s in steps], "docs": docs_analysis}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
