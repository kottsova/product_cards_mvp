"""Stage 22 step 1 -- LG Russia documents route, PHASE A: read the script (D1/D5 remainder of Stage 21).

Everything below is written to raw/docs_declaration.json BEFORE the first request. The rules are fixed for the whole probe;
if a rule says stop, the probe stops and a NEW, explicitly declared stage begins (the rule is never edited mid-probe).

Origin of every address (observed): the saved LG Russia manuals page (reports/source_census_2026-09-24_stage21/verify/responses,
url https://www.lg.com/ru/support/manuals?csSalesCode=XL7S.DRUSLLK) prints <script src> for
  S1 /lg5-common-gp/js/common-support.min.js                          (the address named in Stage 21)
  S2 /lg5-common-gp/js/support/select-product-category.min.js         (printed on the same page; the page's data-detail
                                                                       attribute "/ru/support/manual-select-category-result" is
                                                                       the endpoint of that widget)
Budget (whole probe, phases A+B+C): at most 8 requests to www.lg.com / *.lge.com, pacing 1 s.
  Phase A (this script): S1 (1). S2 (1) ONLY if the text of S1 contains none of: data-detail, manual-select, modelDetail, retrieveGp.
      If S2 is also without any of them -> stop.
  Phase B (a later script, run only after a Phase-B declaration written before its first request, and only if Phase A found the request logic):
      document-list requests <= 2 per product, products <= 2: P1 = XL7S (RU page full_sku, saved manuals link XL7S.DRUSLLK);
      P2 = the next pilot row in the fixed pilot order whose saved RU page is full_sku, in a different category (MS2032GAS).
      P2 is tried only if P1 returned a document list naming its model.
      Request derivation: GET only (a POST or any request the client cannot make as GET -> stop); URL = the literal the script itself requests;
      parameters = the names the script sends, values only from the product's saved page; nothing else is added.
  Phase C (document file): at most 1 file request per product, only for a href printed in that product's document-list response, host lg.com or a
      *.lge.com subdomain (anything else -> not fetched, recorded as a candidate). Complete file only (not truncated, starts with %PDF-).
  Classification of a document: candidate link (printed href) -> reachable file (complete bytes, %PDF-) -> instruction confirmed by content (text
      extracted from the PDF names the expected model AND is not a regulatory document). Language is read from the extracted TEXT only, never from
      a file name, a URL or a label on the page.
Stop rule: 401/403/429 or a confirmed challenge stops the host in data/lg_fetch_log.json and ends the probe; over-budget requests are refused.
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
sys.path.insert(0, str(ROOT))

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg import lg_session  # noqa: E402
from product_tool.adapters.lg_policy import LG_HOSTS, lg_log_path  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402

S1 = "https://www.lg.com/lg5-common-gp/js/common-support.min.js"
S2 = "https://www.lg.com/lg5-common-gp/js/support/select-product-category.min.js"
LOGIC = re.compile(r"data-detail|manual-select|modelDetail|retrieveGp")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    declaration = {"declared_at": now(), "budget": {"max_requests_all_phases": 8, "host": "www.lg.com", "pacing_seconds": 1.0, "phase_a_max": 2},
                   "origin": "reports/source_census_2026-09-24_stage21/verify/responses (manuals page for XL7S.DRUSLLK, <script src> list)", "S1": S1, "S2": S2,
                   "S2_condition": "S1 text has none of: data-detail, manual-select, modelDetail, retrieveGp",
                   "phase_b": "GET only; URL literal from the script; parameters named by the script with values only from the product's saved page; <=2 list requests per product; products XL7S then MS2032GAS (only if XL7S returned a list naming its model)",
                   "phase_c": "<=1 file request per product; only a href printed in that product's list response; host lg.com or *.lge.com; complete + %PDF- required",
                   "classification": "candidate link -> reachable file -> instruction confirmed by content; language from extracted text only",
                   "stop_rule": "401/403/429 or confirmed challenge: host stopped in data/lg_fetch_log.json, probe ends; a stop by rule starts a new declared stage", "url_construction": "none",
                   "script": "reports/source_census_2026-09-24_stage22/scripts/01_docs_route_phase_a.py"}
    (STAGE / "raw/docs_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    client = PolicyAwareSession(lg_log_path(ROOT / "data"), allowed_hosts=LG_HOSTS, underlying=lg_session())
    budget = RequestBudget(max_per_row=2, max_total=2)
    steps, halted, texts = [], "", {}

    def fetch(label: str, url: str):
        nonlocal halted
        try:
            response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            steps.append({"step": label, "url": url, "status": response.status_code, "bytes": len(response.content)})
            return response
        except SourceError as exc:
            steps.append({"step": label, "url": url, "error": str(exc)})
            if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                halted = str(exc)
            return None

    outcome = "stop"
    with request_budget(budget), record_responses(STAGE / "docs_probe/responses"):
        budget.begin_row("docs-phase-a")
        r1 = fetch("S1", S1)
        if r1 is not None:
            texts["S1"] = r1.text
            if LOGIC.search(r1.text):
                outcome = "request_logic_in_S1"
            elif not halted:
                r2 = fetch("S2", S2)
                if r2 is not None:
                    texts["S2"] = r2.text
                    outcome = "request_logic_in_S2" if LOGIC.search(r2.text) else "stop_no_request_logic_in_S1_or_S2"
    result = {"finished_at": now(), "requests_made": budget.total, "halted": halted, "outcome": outcome, "steps": steps,
              "logic_hits": {k: sorted(set(LOGIC.findall(v))) for k, v in texts.items()}}
    (STAGE / "raw/docs_phase_a_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
