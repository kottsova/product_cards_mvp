"""The two selected Bosch Home rows in the ordinary queued worker path."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Callable

from . import bosch_readiness, card_evidence, jobs
from .adapters.bosch_home import MANIFEST, BoschHomeAdapter, selected_page
from .adapters.policy_session import RequestBudget, request_budget

PLANNER = Path(__file__).resolve().parent / "config" / "coverage_planner.v1.json"


def is_selected(category: str, code: str) -> bool:
    code = (code or "").strip().upper()
    if selected_page(code, category) is None:
        return False
    config = json.loads(PLANNER.read_text(encoding="utf-8"))
    entries = config.get("selected_products", {}).get("bosch_home", {}).get("products", [])
    return any(e["category"].strip().casefold() == (category or "").strip().casefold()
               and e["seller_sku"].strip().upper() == code for e in entries)


def run_job(database: Path, job_id: str, product_id: int, product: dict, *, stages: list[int],
            adapter_factory: Callable[[], BoschHomeAdapter] | None = None,
            clock: Callable[[], float] = time.monotonic) -> None:
    code = (product.get("search_code") or "").strip().upper()
    category = product.get("category", "")
    # Check before constructing a client, including when an old queued job
    # bypassed the current enqueue gate.
    if not is_selected(category, code):
        jobs.finish(database, job_id, "needs_review", "Bosch Home: row not selected for the two-category batch; no source request made.")
        return
    adapter = (adapter_factory or (lambda: BoschHomeAdapter(clock=clock,
               fetch_log_path=database.parent / "bosch_home_fetch_log.json")))()
    budget = RequestBudget(max_per_row=1, max_total=1)
    budget.begin_row(str(product_id))
    with request_budget(budget):
        document = adapter.find_source(code, category=category, deadline=clock() + 20.0)
    jobs.save_source_document(database, product_id, document,
                              update_description=2 in stages,
                              update_attributes=3 in stages,
                              update_photos=4 in stages)
    report = adapter.reports.get(code, {})
    evidence = {**report, "manual_verified": False, "manual_family": "",
                "manual_russian_by_text": False, "manual_exact_code_in_pdf": False,
                "other_manuals_unverified": []}
    if 4 in stages and document.photos and not document.error:
        jobs.set_photo_selection(database, product_id, [], mode="source", source_key=adapter.source_key)
    jobs.progress(database, job_id, 1,
                  f"Bosch Home KZ: {document.match_level}; {document.error or document.evidence}",
                  level="warning" if document.error else "info", source_url=document.url)
    if 3 in stages:
        jobs.resolve_product(database, product_id)
        jobs.progress(database, job_id, 3, f"Bosch KZ specifications: {len(document.attributes)} fields.", source_url=document.url)
    if 6 in stages:
        manuals = adapter.find_documents(document, code)
        jobs.save_documents(database, product_id, adapter.source_key, manuals)
        config = json.loads(MANIFEST.read_text(encoding="utf-8"))["pages"].get(code, {})
        verified = config.get("manual", {})
        evidence.update({"manual_verified": bool(manuals),
                         "manual_family": verified.get("family", "") if manuals else "",
                         "manual_russian_by_text": bool(verified.get("russian_by_text")) if manuals else False,
                         "manual_exact_code_in_pdf": bool(verified.get("exact_code_in_pdf")) if manuals else False,
                         "manual_verified_sha256": verified.get("sha256", "") if manuals else "",
                         "other_manuals_unverified": [u for u in report.get("manual_links", [])
                                                      if u != verified.get("url")]})
        jobs.progress(database, job_id, 6,
                      f"Bosch KZ family manual: {verified.get('family', '') if manuals else 'none verified'}; exact catalog code absent from PDF; other links unverified.",
                      level="info" if manuals else "warning", source_url=document.url)
    card_evidence.save(database, product_id, "bosch_home", evidence)
    readiness = bosch_readiness.card_readiness(database, product_id)
    jobs.progress(database, job_id, max(stages),
                  f"Bosch card readiness: {readiness['verdict']}; revision {readiness['revision_status']}; gaps {', '.join(readiness['blocking_gaps']) or 'none'}.",
                  level="info" if readiness["verdict"] == "export_ready" else "warning")
    if document.error:
        status = "needs_review" if document.match_level == "mismatch" else "error"
    elif document.match_level == "full_sku" and not readiness["real_conflicts"]:
        status = "done"
    else:
        status = "needs_review"
    jobs.finish(database, job_id, status,
                f"Bosch Home KZ model {code}: {document.evidence or document.error} Job {status}; card {readiness['verdict']}; E-Nr revision unknown.")
