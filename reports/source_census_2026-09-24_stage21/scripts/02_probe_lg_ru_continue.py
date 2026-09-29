"""Stage 21 step 2 -- the remaining 2 of the 3 declared requests of the LG Russia probe.

R1 (step 1) returned a sitemap INDEX with four children: ru/sitemap.xml, ru/sitemap-cs.xml, ru/business/sitemap.xml,
ru/lg-signature/sitemap.xml. The declared R2 rule ("a child containing 'pdp' or 'product'") matches none of them, so the
declared rule says stop. Amendment, written BEFORE the next request and marked as an amendment (it was made after seeing R1):

  R2' GET https://www.lg.com/ru/sitemap.xml -- the observed child that is the RU counterpart of the KZ https://www.lg.com/kz/sitemap.xml
      which the production adapter already reads for product URLs (the other three are support-cs, business and lg-signature).
  R3  unchanged from the declaration: after a sitemap, the RU product page of the first pilot row (fixed pilot order) whose slug key equals
      the key of its full article or base model in R2's URLs; none -> the second child ru/sitemap-cs.xml is NOT fetched (it is a
      customer-service map, not a product map) -> stop.

Budget: 2 requests (3 in total with R1), host www.lg.com, pacing 1 s, stop on 401/403/429 or a confirmed challenge.

Output: raw/probe_amendment.json, raw/probe_result_2.json, probe/responses/*
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg import lg_article_key, lg_base_model, lg_session, normalize_lg_sku  # noqa: E402
from product_tool.adapters.lg_policy import LG_HOSTS, lg_log_path  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402

R2_URL = "https://www.lg.com/ru/sitemap.xml"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug_key(url: str) -> str:
    return lg_article_key(url.rstrip("/").rsplit("/", 1)[-1].removeprefix("lg-"))


def main() -> None:
    first = json.loads((STAGE / "raw/probe_result.json").read_text(encoding="utf-8"))
    assert first["requests_made"] == 1 and not first["halted"] and R2_URL in first["analysis"]["r1_sample"]
    amendment = {"amended_at": now(), "reason": "R1 returned an index whose children contain neither 'pdp' nor 'product'; the declared rule says stop", "R2_prime": R2_URL,
                 "why_this_child": "RU counterpart of kz/sitemap.xml, the product sitemap the production adapter already reads; the other children are ru/sitemap-cs.xml, ru/business/sitemap.xml, ru/lg-signature/sitemap.xml",
                 "remaining_budget": 2, "R3": "unchanged (product page of the first matching pilot row, else stop)"}
    (STAGE / "raw/probe_amendment.json").write_text(json.dumps(amendment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = json.loads((ROOT / "reports/source_census_2026-09-24_stage20/raw/pilot_selection.json").read_text(encoding="utf-8"))["rows"]
    client = PolicyAwareSession(lg_log_path(ROOT / "data"), allowed_hosts=LG_HOSTS, underlying=lg_session())
    budget = RequestBudget(max_per_row=2, max_total=2)
    steps, analysis, halted = [], {}, ""

    def fetch(label: str, url: str):
        nonlocal halted
        try:
            response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            steps.append({"step": label, "url": url, "status": response.status_code, "bytes": len(response.content), "final_url": response.url})
            return response
        except SourceError as exc:
            steps.append({"step": label, "url": url, "error": str(exc)})
            if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                halted = str(exc)
            return None

    with request_budget(budget), record_responses(STAGE / "probe/responses"):
        budget.begin_row("probe")
        r2 = fetch("R2'", R2_URL)
        if r2 is not None:
            locs = sitemap_locs(r2.text)
            ru = [u for u in locs if "/ru/" in u]
            by_slug = {}
            for url in ru:
                by_slug.setdefault(slug_key(url), url)
            matched = []
            for row in rows:
                full = normalize_lg_sku(row["seller_sku"])
                for key in (lg_article_key(full), lg_article_key(lg_base_model(full))):
                    if key in by_slug:
                        matched.append((row, by_slug[key]))
                        break
            depth = {}
            for url in ru:
                parts = [p for p in url.split("/ru/", 1)[1].split("/") if p]
                depth[len(parts)] = depth.get(len(parts), 0) + 1
            analysis["r2"] = {"kind": "urlset" if "<urlset" in r2.text[:3000] else "other", "locs_total": len(locs), "locs_ru": len(ru), "path_depth_counts": dict(sorted(depth.items())), "sample": ru[:10],
                              "product_like_samples": [u for u in ru if re.search(r"/lg-[a-z0-9-]+/?$", u, re.I)][:10],
                              "pilot_rows_matched": [(m[0]["seller_sku"], m[1]) for m in matched]}
            if matched and not halted:
                row, url = matched[0]
                r3 = fetch("R3", url)
                analysis["r3"] = {"seller_sku": row["seller_sku"], "url": url}
                if r3 is not None:
                    soup = BeautifulSoup(r3.text, "html.parser")
                    hrefs = [a["href"] for a in soup.select("a[href]")]
                    support = [h for h in hrefs if "/support/" in h][:8]
                    text = re.sub(r"\s+", "", soup.get_text(" ")).upper()
                    analysis["r3"].update({"final_url": r3.url, "html_bytes": len(r3.text), "has_h1": bool(soup.select_one("h1")), "article_on_page": normalize_lg_sku(row["seller_sku"]) in text,
                                           "support_links": support, "manual_links": [h for h in hrefs if re.search(r"manual|downloadFile|gscs-b2c", h, re.I)][:8], "specs_markup": bool(soup.select_one("#pdp_spec, #overview"))})
    result = {"finished_at": now(), "requests_made": budget.total, "requests_in_total_with_r1": 1 + budget.total, "halted": halted, "steps": steps, "analysis": analysis}
    (STAGE / "raw/probe_result_2.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1)[:4500])


if __name__ == "__main__":
    main()
