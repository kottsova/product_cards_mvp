"""Stage 25 step 2 -- run batch 2 exactly as raw/batch2_declaration.json declares it (<= 26 real requests, <= 3 per product, 1.5 s pacing, 40 MB document cap), through the
policy-aware session, reading every page with adapters/samsung.py. One product per category; nothing else is fetched.

Output: raw/batch2_result.json, batch2/responses/*, batch2/workdir/samsung_fetch_log.json
"""
from __future__ import annotations

import io
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.adapters import samsung  # noqa: E402
from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg_documents import BinarySafeSession, document_bytes, looks_like_pdf  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402

logging.disable(logging.CRITICAL)
TOTAL, PER_PRODUCT, CAP = 26, 3, 40_000_000
WORKDIR = STAGE / "batch2/workdir"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def card_summary(card: samsung.SamsungCard) -> dict:
    return {"url": card.url, "identity": {"level": card.identity.level, "evidence": card.identity.evidence, "jsonld_sku": card.identity.jsonld_sku, "title": card.identity.title[:140],
                                          "is_product_page": card.identity.is_product_page, "open_differences": card.identity.open_differences},
            "specs": {"items": len(card.specs), "groups": len({i.group for i in card.specs})}, "photos": {"full_size": len(card.photos.photos), "thumbnails": len(card.photos.thumbnails), "three_d": len(card.photos.three_d),
                                                                                                       "candidate_thumbnail_only": card.photos.candidate_thumbnail_only, "gap": card.photos.gap},
            "document_links": [{"href": d.href, "model_name": d.model_name, "file": d.file_name, "language_hint": d.language_hint} for d in card.documents], "gaps": card.gaps, "missing_fields": card.missing_fields}


def main() -> None:
    declaration = json.loads((STAGE / "raw/batch2_declaration.json").read_text(encoding="utf-8"))
    assert declaration["budget"]["max_real_requests_total"] == TOTAL and declaration["budget"]["document_cap_mb"] == 40
    started = now()
    assert started > declaration["declared_at"]
    WORKDIR.mkdir(parents=True, exist_ok=True)
    plain = requests.Session()
    plain.headers.update({"User-Agent": "ProductCardsSourceCensus/2.0 (bounded diagnostic probe)", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"})
    client = PolicyAwareSession(WORKDIR / "samsung_fetch_log.json", allowed_hosts=("samsung.com",), underlying=BinarySafeSession(plain), max_bytes=CAP, min_interval_seconds=1.5)
    budget = RequestBudget(max_per_row=PER_PRODUCT, max_total=TOTAL)
    steps, halted, out = [], "", {}

    def fetch(label: str, url: str):
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

    def read_document(label: str, link: samsung.DocumentLink, article: str, page_level: str) -> dict:
        record = {"href": link.href, "file": link.file_name, "language_hint_from_file_name": link.language_hint, "link_model_name": link.model_name, "state": "candidate_link"}
        response = fetch(label, link.href)
        if response is None:
            record["state"] = "candidate_link_unreachable"
            return record
        data = document_bytes(response)
        record.update({"bytes": len(data), "final_url": response.url, "truncated": bool(response.truncated)})
        if not looks_like_pdf(data) or response.truncated:
            record["state"] = "reachable_but_not_a_complete_pdf"
            return record
        import pypdf
        pages = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
        facts = samsung.assess_samsung_document(pages, article, link.model_name, page_level)
        record.update({"state": "reachable_file", "pages": len(pages), "facts": facts, "rule4_analog": samsung.rule4_analog(facts)})
        return record

    with request_budget(budget), record_responses(STAGE / "batch2/responses"):
        for category, item in declaration["products"].items():
            budget.begin_row(category)
            result = {"article": item["article"], "category": category}
            out[category] = result
            response = fetch(f"{category}: product page", item["page_url"])
            if response is None:
                result["outcome"] = "page_unreachable"
                continue
            card = samsung.parse_product_page(response.text, response.url, item["article"])
            result.update(card_summary(card))
            result["documents"] = []
            for link in samsung.order_for_request(card.documents)[:2]:
                record = read_document(f"{category}: manual", link, item["article"], card.identity.level)
                result["documents"].append(record)
                if record.get("facts", {}).get("russian_by_text"):
                    break
        extra = declaration["extra_requests"]
        budget.begin_row("Микроволновые печи")
        response = fetch("Микроволновые печи: product page", extra["microwave_product_page"])
        if response is not None:
            out["Микроволновые печи"] = {"article": "MS23K3614AK/BW", **card_summary(samsung.parse_product_page(response.text, response.url, "MS23K3614AK/BW"))}
        budget.begin_row("Смартфоны")
        response = fetch("Смартфоны: A37 buy page", extra["a37_buy_page"])
        if response is not None:
            out["Смартфоны: A37 buy page"] = {"article": "SM-A376EZAGINS", **card_summary(samsung.parse_product_page(response.text, response.url, "SM-A376EZAGINS"))}
        budget.begin_row("Стиральные машины")
        wash = json.loads((ROOT / "reports/source_census_2026-09-25_stage24/raw/batch1_result.json").read_text(encoding="utf-8"))["categories"]["Стиральные машины"]["page"]["document"]
        link = samsung.DocumentLink(wash["href"], "WD10T754CBX/LD", wash["href"].split("VPath=")[-1].split("%2F")[-1], "UZ")
        out["Стиральные машины: manual"] = read_document("Стиральные машины: the only manual", link, "WD10T754CBX/LD", "full_sku")
    result = {"started_at": started, "finished_at": now(), "requests_made": budget.total, "halted": halted, "steps": steps, "products": out}
    (STAGE / "raw/batch2_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("requests", budget.total, "halted", halted)
    for s in steps:
        print("  ", s["step"], s.get("status") or s.get("error") or s.get("skipped"), s["url"][-70:])


if __name__ == "__main__":
    main()
