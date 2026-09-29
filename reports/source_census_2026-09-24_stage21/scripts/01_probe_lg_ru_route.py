"""Stage 21 step 1 -- the bounded probe of the LG Russia route (D1/D5). At most 3 requests to www.lg.com.

Question: does an OBSERVED official route to LG Russia product pages / documents exist? "Observed" = a URL that already
appears in a saved official response. The only saved starting point is Stage 7's snapshot of https://www.lg.com/sitemap.xml
(fetched 2026-09-22), whose <loc> list contains https://www.lg.com/ru/index.xml. Nothing is built from a pattern.

Declared BEFORE the first request (raw/probe_declaration.json):
  R1  GET https://www.lg.com/ru/index.xml                     (a <loc> of the saved lg.com sitemap index)
  R2  if R1 is a sitemap index: the first child whose URL contains "pdp" or "product" (document order); none -> stop.
      if R1 is a urlset: the RU product URL of the first pilot row (fixed pilot order) whose slug matches; none -> stop.
  R3  if R2 was a sitemap: the RU product page of the first pilot row (fixed order) whose slug key equals the key of its full
      article or base model in R2's URLs; none -> the second pdp/product child sitemap; none -> stop.
      if R2 was a product page: the first support/manual link PRINTED on that page under www.lg.com; none -> stop.
  Stop rule: 401/403/429 or a confirmed challenge stops the host in data/lg_fetch_log.json and the probe. Budget 3; pacing 1 s.
  Every URL comes from content fetched earlier in the probe or from the saved Stage 7 snapshot.

Output: raw/probe_declaration.json, raw/probe_result.json, probe/responses/*
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE20 = ROOT / "reports/source_census_2026-09-24_stage20"
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg import lg_article_key, lg_base_model, normalize_lg_sku  # noqa: E402
from product_tool.adapters.lg_policy import LG_HOSTS, lg_log_path  # noqa: E402
from product_tool.adapters.lg import lg_session  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402

START = "https://www.lg.com/ru/index.xml"
STAGE7_DB = ROOT / "reports/source_census_2026-09-22_stage7/source_snapshots.sqlite3"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug_key(url: str) -> str:
    return lg_article_key(url.rstrip("/").rsplit("/", 1)[-1].removeprefix("lg-"))


def pilot_rows() -> list[dict]:
    return json.loads((STAGE20 / "raw/pilot_selection.json").read_text(encoding="utf-8"))["rows"]


def main() -> None:
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(f"file:{STAGE7_DB}?mode=ro", uri=True)
    try:
        snapshot_id, fetched_at, content = connection.execute("SELECT id, fetched_at, content FROM source_snapshots WHERE source_url='https://www.lg.com/sitemap.xml'").fetchone()
    finally:
        connection.close()
    saved_locs = sitemap_locs(content)
    assert START in saved_locs, "the starting URL is not in the saved snapshot"
    declaration = {
        "declared_at": now(), "budget": {"max_requests": 3, "host": "www.lg.com", "pacing_seconds": 1.0},
        "observed_origin": {"file": "reports/source_census_2026-09-22_stage7/source_snapshots.sqlite3", "snapshot_id": snapshot_id, "url": "https://www.lg.com/sitemap.xml", "fetched_at": fetched_at,
                            "loc_used": START, "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()},
        "rules": {"R1": START, "R2": "sitemap index -> first child containing 'pdp' or 'product'; urlset -> RU product URL of the first matching pilot row; none -> stop",
                  "R3": "after a sitemap: RU product page of the first matching pilot row, else second pdp/product child, else stop; after a product page: the first support/manual link printed on it under www.lg.com, else stop"},
        "stop_rule": "401/403/429 or confirmed challenge: host stopped in data/lg_fetch_log.json, probe ends", "url_construction": "none",
        "script": "reports/source_census_2026-09-24_stage21/scripts/01_probe_lg_ru_route.py",
    }
    (STAGE / "raw/probe_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log = lg_log_path(ROOT / "data")
    client = PolicyAwareSession(log, allowed_hosts=LG_HOSTS, underlying=lg_session())
    budget = RequestBudget(max_per_row=3, max_total=3)
    steps, halted = [], ""
    rows = pilot_rows()

    def fetch(label: str, url: str):
        nonlocal halted
        try:
            response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            steps.append({"step": label, "url": url, "status": response.status_code, "bytes": len(response.content), "final_url": response.url})
            return response
        except SourceError as exc:
            steps.append({"step": label, "url": url, "error": str(exc)})
            if "policy_host_stopped" in str(exc) or "HTTP 403" in str(exc) or "HTTP 429" in str(exc) or "challenge" in str(exc):
                halted = str(exc)
            return None

    def match_rows(urls: list[str]) -> list[tuple[dict, str]]:
        by_slug = {}
        for url in urls:
            by_slug.setdefault(slug_key(url), url)
        found = []
        for row in rows:
            full = normalize_lg_sku(row["seller_sku"])
            for key in (lg_article_key(full), lg_article_key(lg_base_model(full))):
                if key in by_slug:
                    found.append((row, by_slug[key]))
                    break
        return found

    with request_budget(budget), record_responses(STAGE / "probe/responses"):
        budget.begin_row("probe")
        r1 = fetch("R1", START)
        analysis = {"r1_kind": "", "r2": None, "r3": None}
        if r1 is not None:
            text = r1.text
            kind = "sitemapindex" if "<sitemapindex" in text[:2000] else "urlset" if "<urlset" in text[:2000] else "other"
            analysis["r1_kind"] = kind
            locs = sitemap_locs(text)
            analysis["r1_locs"] = len(locs)
            analysis["r1_sample"] = locs[:6]
            children = [u for u in locs if re.search(r"pdp|product", u, re.I)] if kind == "sitemapindex" else []
            if kind == "sitemapindex" and children and not halted:
                r2 = fetch("R2", children[0])
                analysis["r2"] = {"kind": "sitemap", "url": children[0], "pdp_children_in_r1": len(children)}
                if r2 is not None:
                    urls = [u for u in sitemap_locs(r2.text) if "/ru/" in u]
                    matches = match_rows(urls)
                    analysis["r2"].update({"locs": len(urls), "sample": urls[:6], "pilot_rows_matched": [m[0]["seller_sku"] for m in matches]})
                    if matches and not halted:
                        row, url = matches[0]
                        r3 = fetch("R3", url)
                        analysis["r3"] = {"kind": "product_page", "seller_sku": row["seller_sku"], "url": url}
                        if r3 is not None:
                            soup = BeautifulSoup(r3.text, "html.parser")
                            links = [a["href"] for a in soup.select("a[href]") if "lg.com" in a["href"] or a["href"].startswith("/")]
                            support = [h for h in links if re.search(r"/support/", h) and re.search(r"manual|product|model", h, re.I)]
                            analysis["r3"].update({"title": (soup.title.string or "").strip()[:100] if soup.title else "", "has_h1": bool(soup.select_one("h1")), "support_links": support[:5],
                                                   "article_on_page": normalize_lg_sku(row["seller_sku"]) in re.sub(r"\s+", "", soup.get_text(" ")).upper(), "html_bytes": len(r3.text)})
                    elif not matches and len(children) > 1 and not halted:
                        r3 = fetch("R3", children[1])
                        analysis["r3"] = {"kind": "sitemap", "url": children[1]}
                        if r3 is not None:
                            urls3 = [u for u in sitemap_locs(r3.text) if "/ru/" in u]
                            analysis["r3"].update({"locs": len(urls3), "sample": urls3[:6], "pilot_rows_matched": [m[0]["seller_sku"] for m in match_rows(urls3)]})
            elif kind == "urlset":
                urls = [u for u in locs if "/ru/" in u]
                matches = match_rows(urls)
                analysis["r2"] = {"kind": "urlset_direct", "locs": len(urls), "pilot_rows_matched": [m[0]["seller_sku"] for m in matches]}
    result = {"finished_at": now(), "requests_made": budget.total, "halted": halted, "steps": steps, "analysis": analysis, "fetch_log_entries": len(json.loads(log.read_text(encoding="utf-8"))) if log.exists() else 0}
    (STAGE / "raw/probe_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"requests_made": budget.total, "halted": halted, "steps": steps, "analysis": {k: v for k, v in analysis.items() if k != "r1_sample"}}, ensure_ascii=False, indent=1)[:3500])


if __name__ == "__main__":
    main()
