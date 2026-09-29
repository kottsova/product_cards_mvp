"""Fetch only the two observed KZ routes, plus a blender product URL if printed there."""
from __future__ import annotations

import gzip
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.CRITICAL)

from product_tool.adapters.common import SourceError, fetch_with_retry
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import (
    PolicyAwareSession, RequestBudget, record_responses, request_budget,
)


def stopped(log: Path) -> list[str]:
    if not log.exists():
        return []
    return sorted(stopped_hosts_from_fetch_log(
        x for x in json.loads(log.read_text(encoding="utf-8")) if isinstance(x, dict)
    ))


def main() -> None:
    declaration = json.loads((STAGE / "raw/declaration.json").read_text(encoding="utf-8"))
    assert declaration["budget"]["max_product_and_category_gets"] == 3
    assert declaration["budget"]["max_real_requests_total"] == 4
    routes = json.loads((STAGE / "raw/route_provenance.json").read_text(encoding="utf-8"))
    saved = STAGE / "route_check/responses"
    assert not saved.exists(), "Never repeat the same network probe"
    log = STAGE / "route_check/workdir/bosch_fetch_log.json"
    plain = requests.Session()
    plain.headers.update({
        "User-Agent": "ProductCardsSourceCensus/2.0 (bounded diagnostic probe)",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    })
    client = PolicyAwareSession(
        log, allowed_hosts=("www.bosch-home.com",), underlying=plain,
        max_bytes=declaration["budget"]["page_cap_bytes"],
        min_interval_seconds=declaration["budget"]["pacing_seconds"],
    )
    budget = RequestBudget(max_per_row=3, max_total=3)
    budget.begin_row("bosch_kz_two_products")
    result: dict = {"steps": [], "blender_product_url_observed": None}

    def fetch(url: str, kind: str):
        step = {"kind": kind, "url": url}
        try:
            with record_responses(saved), request_budget(budget):
                response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            step.update({"status": response.status_code, "final_url": response.url,
                         "bytes": len(response.content), "truncated": response.truncated})
        except SourceError as exc:
            step["error"] = str(exc)[:500]
            response = None
        result["steps"].append(step)
        return response

    kettle_url = routes["TWK7203"]["observed_url"]
    kettle = fetch(kettle_url, "kettle_product")
    if kettle is not None and not stopped(log):
        category_url = routes["MMB2111M"]["observed_category_url"]
        category = fetch(category_url, "blender_category")
        if category is not None and not stopped(log):
            soup = BeautifulSoup(category.content, "html.parser")
            candidates = sorted({
                urljoin(category.url, a.get("href", ""))
                for a in soup.select("a[href]")
                if re.search(r"(?<![A-Z0-9])MMB2111M(?![A-Z0-9])", a.get("href", ""), re.I)
            })
            exact = [u for u in candidates if urlparse(u).hostname == "www.bosch-home.com"
                     and urlparse(u).path.startswith("/kz/ru/product/")
                     and urlparse(u).path.rstrip("/").upper().endswith("/MMB2111M")]
            result["blender_candidates"] = candidates
            if len(exact) == 1:
                result["blender_product_url_observed"] = exact[0]
                fetch(exact[0], "blender_product")
    result["budget_spent"] = budget.total
    result["stopped_hosts"] = stopped(log)
    (STAGE / "raw/limited_pages_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
