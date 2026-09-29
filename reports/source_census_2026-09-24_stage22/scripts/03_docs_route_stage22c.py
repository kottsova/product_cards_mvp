"""Stage 22c -- a NEW declared step after Stage 22b ended by its own declared rule.

What 22b showed (raw/docs_b_result.json, 4 of 6 requests used; 22b's step 2 allowed one file per product and both are spent):
  * the static support page /ru/support/product/lg-<full code> lists manuals: li.manuals with a type text, a language LABEL, a date, a size and an
    href on gscs-b2c.lge.com -- route established for both products (3 candidates each);
  * XL7S candidate #1 ("Краткое руководство", label "English,Русский") is a complete PDF whose text is a multi-language quick guide;
  * MS2032GAS candidate #1 ("Краткое руководство", label "Русский") is a ZIP (an online-manual package, bytes start with PK), not a PDF.
The 22b choice "first candidate" turned out to pick a quick guide / a package. 22c chooses differently and says so here, before any request.

Declared BEFORE the first request (raw/docs_c_declaration.json):
  Budget: at most 2 requests to a *.lge.com host (the documents route stays within its declared 8: Phase A 2 + 22b 4 + 22c 2), pacing 1 s.
  Requests, no others:
    C1  MS2032GAS: the candidate on its saved support page (raw/docs_b_result.json) whose printed type text is "Руководства пользователя".
    C2  XL7S:     the candidate whose printed type text is "Руководства пользователя" and whose printed label is "Русский".
  The printed type text and label only CHOOSE which printed link is fetched; they confirm nothing. Classification is by content only
      (lg_documents.assess_document: complete PDF -> extracted text -> not a conformity declaration, names the model, instruction wording;
      language = chunk-level classification of the extracted text; Russian INSTRUCTION needs >= 2500 Russian letters and >= 2 instruction words).
  If C1 is not a complete PDF, it is recorded as such and nothing else is fetched.
  Stop rule: 401/403/429 or a confirmed challenge stops the host in data/lg_fetch_log.json and ends the run.

Output: raw/docs_c_declaration.json, raw/docs_c_result.json, docs_probe/responses/*
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg import lg_session  # noqa: E402
from product_tool.adapters.lg_documents import BinarySafeSession, assess_document, document_bytes, looks_like_pdf  # noqa: E402
from product_tool.adapters.lg_policy import lg_log_path  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402

logging.disable(logging.CRITICAL)  # pypdf warns about fonts it cannot decode; text extraction is what is asserted


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def choose(candidates: list[dict], label: str | None) -> dict | None:
    for item in candidates:
        if item["li_text"].startswith("Руководства пользователя") and (label is None or item["text"] == label):
            return item
    return None


def main() -> None:
    b = json.loads((STAGE / "raw/docs_b_result.json").read_text(encoding="utf-8"))
    by_sku = {p["sku"]: p for p in b["products"]}
    plan = [("C1", "MS2032GAS", choose(by_sku["MS2032GAS"]["candidates"], None)), ("C2", "XL7S", choose(by_sku["XL7S"]["candidates"], "Русский"))]
    assert all(item for _, _, item in plan)
    declaration = {"declared_at": now(), "stage": "22c", "budget": {"max_requests": 2, "hosts": ["*.lge.com"], "pacing_seconds": 1.0},
                   "requests": [{"id": i, "sku": sku, "href": item["href"], "printed": item["li_text"]} for i, sku, item in plan],
                   "selection": "printed type text 'Руководства пользователя' (+ label 'Русский' for C2) chooses the link; confirms nothing",
                   "classification": "by content only: complete PDF -> text -> not regulatory, names the model, instruction wording; language chunk-level from text",
                   "stop_rule": "401/403/429 or confirmed challenge: host stopped, run ends", "url_construction": "none", "script": "reports/source_census_2026-09-24_stage22/scripts/03_docs_route_stage22c.py"}
    (STAGE / "raw/docs_c_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    client = PolicyAwareSession(lg_log_path(ROOT / "data"), allowed_hosts=("lg.com", "lge.com"), underlying=BinarySafeSession(lg_session()), max_bytes=25_000_000)
    budget = RequestBudget(max_per_row=2, max_total=2)
    results, halted = [], ""
    import pypdf
    with request_budget(budget), record_responses(STAGE / "docs_probe/responses"):
        budget.begin_row("docs-c")
        for ident, sku, item in plan:
            record = {"id": ident, "sku": sku, "href": item["href"], "printed": item["li_text"]}
            results.append(record)
            if halted:
                record["verdict"] = "halted"
                continue
            try:
                response = fetch_with_retry(client, item["href"], deadline=1e12, clock=lambda: 0.0)
            except SourceError as exc:
                record.update({"verdict": "candidate_link_file_unreachable", "error": str(exc)})
                if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                    halted = str(exc)
                continue
            data = document_bytes(response)
            record["file"] = {"url": response.url, "status": response.status_code, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "content_type": response.headers.get("Content-Type", ""),
                              "starts_with_pdf_magic": looks_like_pdf(data), "truncated": bool(response.truncated)}
            if not looks_like_pdf(data) or response.truncated:
                record["verdict"] = "reachable_but_not_a_complete_pdf"
                continue
            record["verdict"] = "reachable_file"
            try:
                pages = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
            except Exception as exc:  # noqa: BLE001
                record["file"]["parse_error"] = str(exc)[:200]
                continue
            assessment = assess_document(pages, [sku])
            record["file"]["pages"] = len(pages)
            record["assessment"] = assessment
            record["verdict"] = "instruction_confirmed_by_content" if assessment["accepted"] else "reachable_file_not_confirmed_as_instruction"
    result = {"finished_at": now(), "requests_made": budget.total, "halted": halted, "results": results}
    (STAGE / "raw/docs_c_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1)[:5000])


if __name__ == "__main__":
    main()
