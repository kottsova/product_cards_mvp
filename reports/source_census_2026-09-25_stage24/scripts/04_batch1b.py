"""Stage 24 step 4 -- batch 1b: a declared CORRECTION and one follow-up, after reading the batch 1 responses (offline). Declares first (raw/batch1b_declaration.json), then runs.

What batch 1 showed (offline reading of batch1/responses):
  * smartphones: the declared rule (SKZ-coded catalog rows only, models a36/a56/a26/s25) ended on the Galaxy S25 Ultra FAMILY page, which is the previous generation: the same official
    galaxy-a hub prints the 2026 Galaxy A37 with a KZ product page (.../galaxy-a37-5g-awesome-graygreen-256gb-sm-a376edggskz/), and the catalog has A37 rows (region code INS, not SKZ).
    The category's card is therefore corrected to A37; the S25 Ultra fetch stays recorded as evidence of the family-page template. This is a second product in one category and is disclosed as such.
  * vacuum cleaners: the first manual link was Kazakh (file name token _KK_); the same page prints a Russian one (_RU_). The language is read from the content, the file name only orders the request.
Budget (whole 1b): at most 3 real requests, host www.samsung.com / *.samsung.com, pacing 1.5 s, same stop rule; no other URL.
  1. GET the A37 product page printed on the official galaxy-a hub;
  2. GET the vacuum cleaner's Russian manual (the link printed on its product page whose file name has _RU_);
  3. only if the A37 page prints a manual link (CDCttType=UM): its file whose name has _RU_ (or, if none, none).

Output: raw/batch1b_declaration.json, raw/batch1b_result.json, batch1b/responses/*
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg_documents import BinarySafeSession, assess_document, document_bytes, looks_like_pdf  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402

spec = importlib.util.spec_from_file_location("batch1", HERE / "03_run_batch1.py")
batch1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch1)

A37_URL = "https://www.samsung.com/kz_ru/smartphones/galaxy-a/galaxy-a37-5g-awesome-graygreen-256gb-sm-a376edggskz/"
WORKDIR = STAGE / "batch1b/workdir"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    result1 = json.loads((STAGE / "raw/batch1_result.json").read_text(encoding="utf-8"))
    vac = result1["categories"]["Пылесосы"]["page"]
    ru_link = next(h for h, _ in vac["document"]["candidates"] if re.search(r"_RU_", h))
    hub_text = "".join(json.loads(l)["url"] for l in (STAGE / "batch1/responses/index.jsonl").read_text(encoding="utf-8").splitlines() if "galaxy-a/" in l)
    declaration = {"declared_at": now(), "stage": "24 / batch 1b", "budget": {"max_real_requests": 3, "pacing_seconds": 1.5, "hosts": ["www.samsung.com", "*.samsung.com"]},
                   "requests": {"1_a37_product_page": A37_URL, "2_vacuum_russian_manual": ru_link, "3_a37_manual": "only if the A37 page prints a UM link; the file whose name has _RU_"},
                   "origin": {"a37_url": "printed on the official galaxy-a hub fetched in batch 1 (raw/batch1_result.json, batch1/responses)", "vacuum_ru": "printed on the vacuum cleaner's official product page fetched in batch 1"},
                   "reason": __doc__.split("Budget")[0], "stop_rule": "401/403/429 or confirmed challenge: host stopped in batch1b/workdir/samsung_fetch_log.json, run ends", "url_construction": "none"}
    (STAGE / "raw/batch1b_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    plain = requests.Session()
    plain.headers.update({"User-Agent": "ProductCardsSourceCensus/2.0 (bounded diagnostic probe)", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"})
    WORKDIR.mkdir(parents=True, exist_ok=True)
    client = PolicyAwareSession(WORKDIR / "samsung_fetch_log.json", allowed_hosts=("samsung.com",), underlying=BinarySafeSession(plain), max_bytes=25_000_000, min_interval_seconds=1.5)
    budget = RequestBudget(max_per_row=3, max_total=3)
    steps, halted, out = [], "", {}

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

    def pdf_record(response, tokens):
        data = document_bytes(response)
        record = {"bytes": len(data), "final_url": response.url, "truncated": bool(response.truncated)}
        if not looks_like_pdf(data) or response.truncated:
            record["state"] = "reachable_but_not_a_complete_pdf"
            return record
        import logging
        import pypdf
        logging.disable(logging.CRITICAL)
        texts = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
        a = assess_document(texts, tokens)
        langs = a["languages"]
        record.update({"pages": len(texts), "state": "instruction_confirmed_by_content" if a["accepted"] else "reachable_file_not_confirmed_as_instruction",
                       "assessment": {"kind": a["kind"], "model_evidence": a["model_evidence"], "names_model": a["names_model"], "model_masks": a["model_masks"], "conflicting_models": a["conflicting_models"],
                                      "languages": langs["present"], "letters_by_language": langs["letters_by_language"], "russian_instruction": langs["russian_instruction"]}})
        return record

    with request_budget(budget), record_responses(STAGE / "batch1b/responses"):
        budget.begin_row("1b")
        page = fetch("Смартфоны: A37 product page", A37_URL)
        if page is not None:
            info = batch1.analyze_page(page.text, page.url, "SM-A376EZAGINS")
            out["a37"] = info
            out["a37_catalog_rows"] = "SM-A376ELVDINS, SM-A376ELVGINS, SM-A376EZADINS, SM-A376EZAGINS, SM-A376EZWGINS (region code INS)"
        vac_response = fetch("Пылесосы: Russian manual", ru_link)
        if vac_response is not None:
            model_name = re.search(r"ModelName=([A-Za-z0-9%]+)", ru_link)
            out["vacuum_ru"] = pdf_record(vac_response, ["VC18M21D0VG", "SC18M21D0VG", (model_name.group(1) if model_name else "")])
            out["vacuum_ru"]["model_name_printed_by_the_page_link"] = model_name.group(1) if model_name else ""
        if page is not None and out.get("a37", {}).get("pdf_like_links"):
            links = [h for h, _ in out["a37"]["pdf_like_links"] if "CDCttType=UM" in h and re.search(r"_RU_", h)]
            out["a37_manual_candidates"] = [h for h, _ in out["a37"]["pdf_like_links"]]
            if links:
                r = fetch("Смартфоны: A37 Russian manual", links[0])
                if r is not None:
                    out["a37_manual"] = pdf_record(r, ["SM-A376", "A376"])
    result = {"started_at": declaration["declared_at"], "finished_at": now(), "requests_made": budget.total, "halted": halted, "steps": steps, "result": out}
    (STAGE / "raw/batch1b_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("requests", budget.total, "halted", halted)
    for s in steps:
        print("  ", s["step"], s.get("status") or s.get("error") or s.get("skipped"), s["url"][-80:])


if __name__ == "__main__":
    main()
