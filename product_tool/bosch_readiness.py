"""Bosch Home KZ card readiness, separate from the search job status."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from . import card_evidence, jobs

KEY = "bosch_home"


def card_readiness(database: Path, product_id: int) -> dict[str, Any]:
    pages = [p for p in jobs.get_source_pages(database, product_id) if p["source_key"] == KEY]
    page = pages[0] if pages else None
    facts = [f for f in jobs.get_facts(database, product_id) if f["source_key"] == KEY]
    photos = [p for p in jobs.get_photo_candidates(database, product_id, include_excluded=False)
              if p["source_key"] == KEY and p["kind"] == "product_gallery"]
    selected = [p for p in photos if p["selected"]]
    manuals = [d for d in jobs.get_documents(database, product_id) if d["source_key"] == KEY]
    evidence = card_evidence.load(database, product_id, "bosch_home") or {}
    blocking = []
    advisory = []
    if not page or page["error"] or page["match_level"] != "full_sku" or not evidence.get("model_confirmed"):
        blocking.append("model_not_confirmed")
    if not facts:
        blocking.append("official_specifications_missing")
    if not selected:
        blocking.append("model_bound_photo_missing")
    if not manuals or not evidence.get("manual_verified"):
        blocking.append("verified_russian_manual_missing")
    if evidence.get("revision_status") == "unknown":
        advisory.append("enr_revision_unknown")
    if manuals and not evidence.get("manual_exact_code_in_pdf"):
        advisory.append("manual_names_family_only")
    conflicts = jobs.result_counts(database, product_id)["conflicts"]
    if conflicts:
        blocking.append("attribute_conflict")
    verdict = "not_ready" if any(x in blocking for x in ("model_not_confirmed", "official_specifications_missing", "model_bound_photo_missing")) else "export_ready_with_gaps" if blocking else "export_ready"
    return {"verdict": verdict, "blocking_gaps": blocking, "advisory_gaps": advisory,
            "model_confirmed": bool(evidence.get("model_confirmed")),
            "catalog_revision": evidence.get("catalog_revision"),
            "page_enr": evidence.get("page_enr"),
            "revision_status": evidence.get("revision_status", "unknown"),
            "gtin": evidence.get("gtin"), "official_facts": len(facts),
            "official_photos": len(photos), "official_photos_selected": len(selected),
            "manuals_saved": len(manuals), "manual_family": evidence.get("manual_family", ""),
            "manual_russian_by_text": bool(evidence.get("manual_russian_by_text")),
            "manual_exact_code_in_pdf": bool(evidence.get("manual_exact_code_in_pdf")),
            "manual_links_on_page": evidence.get("manual_links", []),
            "other_manuals_unverified": evidence.get("other_manuals_unverified", []),
            "real_conflicts": conflicts}
