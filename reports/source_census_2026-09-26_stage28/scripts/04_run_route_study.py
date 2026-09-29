"""Stage 28 step 4 -- REAL REQUESTS, exactly as raw/route_study_declaration.json declares: the sitemap index and the three sub-sitemaps no earlier stage read in full (<= 4 requests, 1.5 s pacing,
25 MB body cap), through the ordinary access protection. No product page, no document, no image. Every response is recorded (route_study/responses) for offline replay.

Output: raw/route_study_result.json, route_study/responses/*, route_study/workdir/samsung_fetch_log.json
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

logging.disable(logging.CRITICAL)

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402
from product_tool.adapters.samsung_source import PAGE_HOSTS, USER_AGENT  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402

import requests  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    declaration = json.loads((STAGE / "raw/route_study_declaration.json").read_text(encoding="utf-8"))
    started = now()
    assert started > declaration["declared_at"], "declare first"
    workdir = STAGE / "route_study/workdir"
    assert not workdir.exists(), "this study runs once"
    workdir.mkdir(parents=True)
    plain = requests.Session()
    plain.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"})
    client = PolicyAwareSession(workdir / "samsung_fetch_log.json", allowed_hosts=PAGE_HOSTS, underlying=plain, max_bytes=declaration["requests"]["body_cap_bytes"], min_interval_seconds=1.5)
    budget = RequestBudget(max_per_row=4, max_total=4)
    budget.begin_row("route_study")
    steps, listed, halted = [], {}, ""
    with record_responses(STAGE / "route_study/responses"), request_budget(budget):
        index_url = declaration["requests"]["planned"][0]["url"]
        try:
            index = fetch_with_retry(client, index_url, deadline=1e12, clock=lambda: 0.0)
            listed_now = sitemap_locs(index.text)
            steps.append({"url": index_url, "status": index.status_code, "locs": listed_now, "bytes": len(index.content), "truncated": bool(index.truncated)})
        except SourceError as exc:
            steps.append({"url": index_url, "error": str(exc)[:200]})
            listed_now, halted = [], str(exc)[:200]
        wanted = [r["url"] for r in declaration["requests"]["planned"][1:]]
        for url in wanted:
            if halted:
                steps.append({"url": url, "skipped": halted})
                continue
            if listed_now and url not in listed_now:
                steps.append({"url": url, "skipped": "no longer listed by the index"})
                continue
            try:
                response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
                locs = sitemap_locs(response.text)
                listed[url] = locs
                steps.append({"url": url, "status": response.status_code, "bytes": len(response.content), "truncated": bool(response.truncated), "locs": len(locs)})
            except SourceError as exc:
                steps.append({"url": url, "error": str(exc)[:200]})
                if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                    halted = str(exc)[:200]
    log = workdir / "samsung_fetch_log.json"
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    result = {"declared_at": declaration["declared_at"], "started_at": started, "finished_at": now(), "budget": {"max": 4, "spent": budget.total, "log": budget.log}, "stopped_hosts": sorted(stopped_hosts_from_fetch_log(e for e in entries if isinstance(e, dict))),
              "fetch_log": entries, "steps": [{k: (len(v) if k == "locs" and isinstance(v, list) else v) for k, v in step.items()} for step in steps], "index_listed_now": listed_now, "halted": halted}
    (STAGE / "raw/route_study_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("requests:", budget.total, "of 4 | stopped:", result["stopped_hosts"], "|", [(s["url"].rsplit("/", 1)[-1], s.get("status"), s.get("locs")) for s in result["steps"]])


if __name__ == "__main__":
    main()
