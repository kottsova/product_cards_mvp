"""Stage 26 step 1 -- OFFLINE, zero requests. The eleven cards checked in Stages 24-25 (one per category) go through the ordinary worker.run_once() with the Samsung adapter, on the SAVED
responses (tests/_samsung_replay.py serves the saved pages and sitemaps; the document texts saved after Stages 24-25 stand in for the pruned PDFs; the dealer's session refuses every call).

Everything is read back from what run_once() stored: source rows, facts, resolved values, photo candidates, documents, evidence, reviews, job status and events, readiness, and the export workbook.
The database lives in a temporary directory and is discarded; the project's own data/ is not touched.

Output: raw/run_result.json, raw/replay_calls.json, raw/stop_and_dealer_checks.json, export/samsung_offline_export.xlsx
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import _samsung_replay as R  # noqa: E402
from product_tool import card_evidence, exporter, jobs, samsung_readiness  # noqa: E402
from product_tool.adapters.common import RawAttribute, SourceDocument  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

logging.disable(logging.CRITICAL)


def card_record(database: Path, outcome: dict) -> dict:
    pid = outcome["product_id"]
    pages = jobs.get_source_pages(database, pid)
    sources = {s["source_key"]: {k: s[k] for k in ("site_name", "url", "found_model", "match_level", "evidence", "error")} for s in pages}
    facts = jobs.get_facts(database, pid)
    resolved = jobs.get_resolved(database, pid)
    photos = jobs.get_photo_candidates(database, pid, include_excluded=True)
    gallery = [p for p in photos if p["source_key"] == "samsung" and p["kind"] == "product_gallery"]
    excluded = [p for p in photos if p["source_key"] == "samsung" and p["kind"] == "excluded"]
    page = card_evidence.load(database, pid, "samsung_page") or {}
    documents = card_evidence.load(database, pid, "samsung_documents") or {}
    return {
        "category": outcome["category"], "article": outcome["article"], "job_status": outcome["status"], "job_message": outcome["message"],
        "events": [{"stage": e["stage"], "level": e["level"], "message": e["message"]} for e in jobs.list_events(database, outcome["job_id"])],
        "sources": sources, "identification_status": jobs.identification_status(pages),
        "facts": {"samsung": sum(1 for f in facts if f["source_key"] == "samsung"), "dns": sum(1 for f in facts if f["source_key"] == "dns")},
        "resolved": {"total": len(resolved), "conflicts": sum(1 for r in resolved if r["conflict"]), "by_status": {s: sum(1 for r in resolved if r["status"] == s) for s in sorted({r["status"] for r in resolved})}},
        "photos": {"gallery_found": len(gallery), "gallery_selected": sum(1 for p in gallery if p["selected"]), "thumbnails_excluded": sum(1 for p in excluded if p["excluded_reason"] == "thumbnail"),
                   "three_d_excluded": sum(1 for p in excluded if p["excluded_reason"] == "3d_model"), "from": (page.get("photos") or {}).get("from", "")},
        "documents": [{k: d[k] for k in ("title", "language", "direct_url", "source_url", "product_model", "support_model")} for d in jobs.get_documents(database, pid)],
        "document_files_assessed": [{"file": e.get("file"), "state": e.get("state"), "link_model_name": e.get("link_model_name"), "facts": e.get("facts")} for e in documents.get("documents", [])],
        "page_evidence": {"route": page.get("route"), "identity": page.get("identity"), "specs": page.get("specs"), "photos": page.get("photos"), "gaps": page.get("gaps")},
        "readiness": samsung_readiness.card_readiness(database, pid), "open_reviews": card_evidence.open_reviews(database, pid), "requests": card_evidence.load(database, pid, "samsung_requests") or {},
    }


def dealer_double(level: str, official: dict):
    class Dealer:
        source_key, site_name, document_urls = "dns", "DNS", {}

        def find_source(self, code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
            return SourceDocument("dns", "DNS", "https://www.dns-shop.ru/product/verified-example/", found_model=code, match_level=level, evidence="synthetic dealer double for this check",
                                  attributes=[RawAttribute("Особенность только у дилера", "да, есть"), RawAttribute(official["raw_name"], official["raw_value"] + " и ещё что-то")])

        def find_documents(self, code, *, model_tokens=None, deadline):
            return [], "нет"

    return Dealer


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run = R.run_products(Path(tmp) / "main")
        database = run["database"]
        cards = [card_record(database, o) for o in run["outcomes"]]
        (STAGE / "raw/run_result.json").write_text(json.dumps({"cards": cards}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        replay = run["replay"]
        (STAGE / "raw/replay_calls.json").write_text(json.dumps({"served": [c for c in replay.calls if c not in replay.refused], "refused": replay.refused, "dealer_session_calls": run["dealer_session"].calls}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (STAGE / "export/samsung_offline_export.xlsx").write_bytes(exporter.export_batch(database, "samsung-offline"))

        # a 403 stops the host, and the stop outlives the run
        stop = R.run_products(Path(tmp) / "stop", cards=[("Телевизоры", "QE48S85HAEXCE")], blocked_hosts=("www.samsung.com",))
        again = R.run_products(Path(tmp) / "stop", cards=[("Телевизоры", "QE48S85HAEXCE")], replay=R.Replay())
        stop_log = json.loads((Path(tmp) / "stop/samsung_fetch_log.json").read_text(encoding="utf-8"))
        checks = {"stop": {"first_run": {"status": stop["outcomes"][0]["status"], "requests_to_transport": len(stop["replay"].calls), "log_status_codes": [e["status_code"] for e in stop_log]},
                           "second_run_same_directory": {"status": again["outcomes"][0]["status"], "requests_to_transport": len(again["replay"].calls),
                                                         "halted": (card_evidence.load(again["database"], again["outcomes"][0]["product_id"], "samsung_page") or {}).get("halted")}}}

        # a dealer on an exact model AND variant: one added field with its own source, one difference sent to review; a dealer that is not an exact match adds nothing
        probe = R.run_products(Path(tmp) / "probe", cards=[("Телевизоры", "QE48S85HAEXCE")])
        official = next(f for f in jobs.get_facts(probe["database"], probe["outcomes"][0]["product_id"]) if f["source_key"] == "samsung" and f["raw_value"].strip())
        for label, level in (("dealer_exact_model_and_code", "model_and_code_confirmed"), ("dealer_not_exact", "model_confirmed")):
            result = R.run_products(Path(tmp) / label, cards=[("Телевизоры", "QE48S85HAEXCE")], dealer_factory=dealer_double(level, official))
            pid = result["outcomes"][0]["product_id"]
            resolved = {r["normalized_name"]: r for r in jobs.get_resolved(result["database"], pid)}
            checks[label] = {"job_status": result["outcomes"][0]["status"], "dealer": card_evidence.load(result["database"], pid, "dealer"), "open_reviews": [r["review_type"] for r in card_evidence.open_reviews(result["database"], pid)],
                             "official_field_after_run": {"field": official["normalized_name"], "value": resolved[official["normalized_name"]]["selected_value"], "source": resolved[official["normalized_name"]]["selected_source"]},
                             "dealer_fact_rows": sum(1 for f in jobs.get_facts(result["database"], pid) if f["source_key"] == "dns"),
                             "dealer_only_field": {k: resolved[k]["selected_source"] + "/" + resolved[k]["status"] for k in resolved if k.startswith("особенность")}}
        (STAGE / "raw/stop_and_dealer_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for card in cards:
        r = card["readiness"]
        print(f"{card['category']:<20} job={card['job_status']:<13} {r['verdict']:<24} {r['page_match_level']:<18} facts={card['facts']['samsung']:<4} photos={card['photos']['gallery_selected']}/{card['photos']['gallery_found']:<3} gaps={r['gaps']}")
    print(json.dumps(checks["stop"], ensure_ascii=False))


if __name__ == "__main__":
    with offline_only():
        main()
