"""Stage 22b -- a NEW, explicitly declared stage for the LG Russia documents route (started after Phase A ended by its own rule).

What happened in Phase A (scripts/01_docs_route_phase_a.py, raw/docs_phase_a_result.json): 2 of 8 requests were spent on the two scripts the
saved manuals page prints. The declared textual test (data-detail | manual-select | modelDetail | retrieveGp) found nothing in either text,
so the declared rule said STOP -- and the probe stopped. Read afterwards (offline), the two scripts show why the test missed: the widget reads
its endpoint as x.data("detail") (jQuery), not as the attribute text; and it calls `ajax.call(detailURL, {categoryId, subCategoryId, modelName}, "html")`
with categoryId/subCategoryId taken from a category picker, whose transport (GET or POST) lives in a THIRD script (common.min.js). That path is
therefore not usable without another script request AND values that a product page does not print. This is a defect of the Phase A test (too
narrow), recorded here; the Phase A rule was not changed.

Stage 22b uses a different, observed route and does not touch the ajax widget:
  common-support.min.js (S1, already fetched) has a handler for `.support-downloads .list>li .name a.link-text` with `li.manuals` -- a
  download list on the PRODUCT SUPPORT page. Every saved LG Russia product page prints its own support link
  /ru/support/product/lg-<full code>. These two facts are observed; nothing is constructed.

Declared BEFORE the first request (raw/docs_b_declaration.json):
  Budget: at most 6 requests (host www.lg.com and *.lge.com subdomains), pacing 1 s, separate from Phase A (2 of 8 spent there; the whole documents
      route therefore stays within the 8 declared for it).
  Products: P1 = XL7S, P2 = MS2032GAS (the Phase A choice). The support URL of each is the /ru/support/product/ link printed on that row's SAVED RU page.
  Step 1 (per product, 1 request): GET that support page. Candidates = anchors inside `.support-downloads` list items with class `manuals`.
      None in the static HTML -> stop for this product, and P2 is not tried (a JS-only list would need a new stage).
  Step 2 (per product, at most 1 request): GET the first candidate whose href is http(s) or relative (not javascript:/#), host lg.com or *.lge.com. Nothing else is fetched.
  P2 is tried only if P1's page had at least one candidate.
  Classification (never from a name or label): candidate link -> reachable file (status 200, complete = not truncated, starts with %PDF-) ->
      instruction confirmed by content (extracted text is not a regulatory document and names the expected model or code, via verify_document).
      Language = per-page classification of the extracted text (lg_documents.document_languages); the file name is never read for it.
  Stop rule: 401/403/429 or a confirmed challenge stops the host in data/lg_fetch_log.json and ends the run; a rule that says stop ends THIS stage.

Output: raw/docs_b_declaration.json, raw/docs_b_result.json, docs_probe/responses/*
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S21 = ROOT / "reports/source_census_2026-09-24_stage21"
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.document_verification import verify_document  # noqa: E402
from product_tool.adapters.lg import lg_session  # noqa: E402
from product_tool.adapters.lg_documents import BinarySafeSession, document_bytes, document_languages, looks_like_pdf  # noqa: E402
from product_tool.adapters.lg_policy import lg_log_path  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402

PRODUCTS = [("XL7S", "audio/lg-xl7s"), ("MS2032GAS", "microwaves/lg-ms2032gas")]
ALLOWED = ("lg.com", "lge.com")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def saved_page(suffix: str) -> tuple[str, str]:
    for line in (S21 / "verify/responses/index.jsonl").read_text(encoding="utf-8").splitlines() + (S21 / "probe/responses/index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["url"].endswith(suffix) and entry["saved_as"]:
            for directory in ("verify", "probe"):
                path = S21 / directory / "responses" / entry["saved_as"]
                if path.exists():
                    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                        return entry["url"], handle.read()
    raise SystemExit(f"no saved page for {suffix}")


def support_url(sku: str, suffix: str) -> str:
    url, html = saved_page(suffix)
    links = sorted({a["href"] for a in BeautifulSoup(html, "html.parser").select("a[href]") if re.search(r"/ru/support/product/lg-" + re.escape(sku), a["href"], re.I)})
    assert len(links) == 1, (sku, links)
    return urljoin(url, links[0])


def pdf_pages(data: bytes) -> list[str]:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    return [(page.extract_text() or "") for page in reader.pages]


def main() -> None:
    plan = [{"sku": sku, "support_url": support_url(sku, suffix)} for sku, suffix in PRODUCTS]
    declaration = {"declared_at": now(), "stage": "22b", "reason": "Phase A ended by its own declared rule (no request logic found by the declared textual test); a new stage is declared instead of editing that rule",
                   "budget": {"max_requests": 6, "hosts": ["www.lg.com", "*.lge.com"], "pacing_seconds": 1.0}, "products": plan,
                   "step1": "GET the support page printed on the saved RU page; candidates = anchors in .support-downloads li.manuals; none -> stop (P2 not tried)",
                   "step2": "<=1 file request per product: the first candidate with an http(s)/relative href on lg.com or *.lge.com",
                   "p2_condition": "P1's page had at least one candidate",
                   "classification": "candidate link -> reachable file (200, complete, %PDF-) -> confirmed instruction (text not regulatory, names model/code); language from extracted text per page only",
                   "stop_rule": "401/403/429 or confirmed challenge: host stopped in data/lg_fetch_log.json, run ends", "url_construction": "none",
                   "script": "reports/source_census_2026-09-24_stage22/scripts/02_docs_route_stage22b.py"}
    (STAGE / "raw/docs_b_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    client = PolicyAwareSession(lg_log_path(ROOT / "data"), allowed_hosts=ALLOWED, underlying=BinarySafeSession(lg_session()), max_bytes=25_000_000)
    budget = RequestBudget(max_per_row=6, max_total=6)
    steps, products, halted = [], [], ""

    def fetch(label: str, url: str):
        nonlocal halted
        try:
            response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            steps.append({"step": label, "url": url, "status": response.status_code, "bytes": len(response.content), "content_type": response.headers.get("Content-Type", ""), "truncated": response.truncated})
            return response
        except SourceError as exc:
            steps.append({"step": label, "url": url, "error": str(exc)})
            if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                halted = str(exc)
            return None

    with request_budget(budget), record_responses(STAGE / "docs_probe/responses"):
        budget.begin_row("docs-b")
        for index, item in enumerate(plan):
            sku = item["sku"]
            record = {"sku": sku, "support_url": item["support_url"], "candidates": [], "file": None, "verdict": "not_reached"}
            products.append(record)
            if halted:
                record["verdict"] = "halted"
                break
            page = fetch(f"support:{sku}", item["support_url"])
            if page is None:
                record["verdict"] = "support_page_unreachable"
                break
            soup = BeautifulSoup(page.text, "html.parser")
            record["support_page"] = {"title": (soup.title.string or "").strip()[:100] if soup.title else "", "has_support_downloads": bool(soup.select_one(".support-downloads")),
                                      "downloads_li_classes": [" ".join(li.get("class", [])) for li in soup.select(".support-downloads .list > li")][:20],
                                      "model_text": " ".join((soup.select_one(".support-product-area .text-block .model") or soup).get_text(" ").split())[:120] if soup.select_one(".support-product-area .text-block .model") else ""}
            for li in soup.select(".support-downloads .list > li.manuals"):
                for a in li.select("a[href]"):
                    record["candidates"].append({"text": " ".join(a.get_text(" ").split())[:120], "href": urljoin(page.url, a["href"]) if a["href"] else "", "raw_href": a["href"][:200], "li_text": " ".join(li.get_text(" ").split())[:160]})
            if not record["candidates"]:
                record["verdict"] = "no_manual_candidates_in_static_html"
                break
            usable = [c for c in record["candidates"] if re.match(r"https?://|/", c["raw_href"]) and (urlsplit(c["href"]).hostname or "").endswith(ALLOWED)]
            if not usable:
                record["verdict"] = "candidates_without_a_fetchable_href"
                continue
            record["verdict"] = "candidate_link"
            target = usable[0]["href"]
            response = fetch(f"file:{sku}", target)
            if response is None:
                record["verdict"] = "candidate_link_file_unreachable"
                continue
            data = document_bytes(response)
            record["file"] = {"url": response.url, "status": response.status_code, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "content_type": response.headers.get("Content-Type", ""),
                              "starts_with_pdf_magic": looks_like_pdf(data), "truncated": bool(response.truncated)}
            if not looks_like_pdf(data) or response.truncated:
                record["verdict"] = "reachable_but_not_a_complete_pdf"
                continue
            record["verdict"] = "reachable_file"
            try:
                pages = pdf_pages(data)
            except Exception as exc:  # noqa: BLE001 -- a parser failure is an outcome, not a crash
                record["file"]["parse_error"] = str(exc)[:200]
                continue
            text = "\n".join(pages)
            verification = verify_document(text, expected_model_tokens=[sku], expected_code=sku)
            languages = document_languages(pages)
            record["file"].update({"pages": len(pages), "text_chars": len(text), "verification": {"accepted": verification.accepted, "type": verification.document_type, "matched_model": verification.matched_model,
                                                                                                 "reason": verification.reason}, "languages": languages})
            if verification.accepted:
                record["verdict"] = "instruction_confirmed_by_content"
    result = {"finished_at": now(), "requests_made": budget.total, "halted": halted, "steps": steps, "products": products}
    (STAGE / "raw/docs_b_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
