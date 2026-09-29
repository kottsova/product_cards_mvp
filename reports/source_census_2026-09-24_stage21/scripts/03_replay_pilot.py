"""Stage 21 step 3 -- OFFLINE replay of the SAME 12 pilot rows through the ordinary worker.run_once() with the fixed code, on SAVED responses.

Transport = the responses saved by the Stage 20 pilot (pilot/responses), by the Stage 21 route probe (probe/responses) and, in
phase 2, by the separately budgeted route verification (verify/responses). A URL that no saved response covers is NOT fetched:
it is refused, listed in `unrecorded`, and the row records the refusal. Phase 1 therefore tells exactly which observed URLs
the new route would need; nothing is requested here.

Usage: 03_replay_pilot.py PHASE  (PHASE = phase1 | phase2)
Output: raw/replay_<phase>.json (+ the databases under replay/<phase>/)
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE20 = ROOT / "reports/source_census_2026-09-24_stage20"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from product_tool import jobs, readiness, worker  # noqa: E402
from product_tool.adapters.dns import DnsAdapter  # noqa: E402
from product_tool.adapters.lg import LGAdapter, LGRUAdapter  # noqa: E402
from product_tool.adapters.sulpak import SulpakAdapter  # noqa: E402
from product_tool.coverage import executor  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402
from coverage_controls import FixtureResponse  # noqa: E402

STAGES = [1, 2, 3, 4, 6]


def load_responses(*directories: Path) -> dict[str, tuple[int, str]]:
    pages: dict[str, tuple[int, str]] = {}
    for directory in directories:
        index = directory / "index.jsonl"
        if not index.exists():
            continue
        for line in index.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            body = ""
            if entry["saved_as"]:
                with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                    body = handle.read()
            pages[entry["url"]] = (entry["status"], body)
    return pages


class RecordedTransport:
    def __init__(self, pages):
        self.pages, self.calls, self.unrecorded, self.headers = pages, [], [], {}

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            if url not in self.unrecorded:
                self.unrecorded.append(url)
            raise requests.ConnectionError(f"not recorded: {url}")
        status, text = self.pages[url]
        return FixtureResponse(url, text, status)


class Refusing:
    headers: dict = {}

    def get(self, url, **kw):
        raise requests.ConnectionError("dealer: no request in a replay")


def run(phase: str) -> dict:
    selection = json.loads((STAGE20 / "raw/pilot_selection.json").read_text(encoding="utf-8"))
    dirs = [STAGE20 / "pilot/responses", STAGE / "probe/responses"] + ([STAGE / "verify/responses"] if phase == "phase2" else [])
    transport = RecordedTransport(load_responses(*dirs))
    out = STAGE / "replay" / phase
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    database = out / "batches.sqlite3"
    jobs.initialize(database)
    rows = []
    for index, row in enumerate(selection["rows"]):
        unit = {"catalog_row": row["catalog_row"], "brand": row["brand"], "category": row["category"], "title": row["title"], "seller_sku": row["seller_sku"]}
        product_id = executor._ensure_product(database, unit, "lg-replay")
        job_id = jobs.enqueue(database, product_id, STAGES)
        before = len(transport.unrecorded)
        worker.run_once(database, lambda: (LGAdapter(transport, clock=lambda: 0.0), LGRUAdapter(transport, clock=lambda: 0.0), SulpakAdapter(transport, clock=lambda: 0.0)),
                        clock=lambda: 0.0, dns_adapter_factory=lambda: DnsAdapter(Refusing(), clock=lambda: 0.0))
        job = next(j for j in jobs.list_jobs(database, product_id) if j["id"] == job_id)
        sources = jobs.get_source_pages(database, product_id)
        facts = jobs.get_facts(database, product_id)
        photos = jobs.get_photo_candidates(database, product_id, include_excluded=True)
        resolved = jobs.get_resolved(database, product_id)
        card = readiness.card_readiness(database, product_id)
        conflicts = []
        for r in resolved:
            if r["conflict"]:
                names = sorted({f["raw_name"] for f in facts if f["normalized_name"] == r["normalized_name"]})
                srcs = sorted({f["source_key"] for f in facts if f["normalized_name"] == r["normalized_name"]})
                values = sorted({f["normalized_value"] for f in facts if f["normalized_name"] == r["normalized_name"]})
                conflicts.append({"normalized_name": r["normalized_name"], "sources": srcs, "raw_names": names, "values": values})
        per_source = {s["source_key"]: {"match_level": s["match_level"], "url": s["url"], "error": s["error"], "facts": sum(1 for f in facts if f["source_key"] == s["source_key"]),
                                        "gallery_selected": sum(1 for p in photos if p["source_key"] == s["source_key"] and p["kind"] == "product_gallery" and p["selected"])} for s in sources}
        rows.append({"index": index, "seller_sku": row["seller_sku"], "category": row["category"], "job_status": job["status"], "job_message": job["message"], "sources": per_source, "readiness": card,
                     "real_conflicts": conflicts, "resolved_total": len(resolved), "unrecorded_urls_for_row": transport.unrecorded[before:], "documents": len(jobs.get_documents(database, product_id))})
    result = {"phase": phase, "rows": rows, "unrecorded": transport.unrecorded, "requests_made": 0, "transport_calls": len(transport.calls)}
    (STAGE / f"raw/replay_{phase}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "phase1"
    result = run(phase)
    print(phase, "unrecorded:", len(result["unrecorded"]))
    for u in result["unrecorded"]:
        print("   ", u)
    for r in result["rows"]:
        s = r["sources"]
        print(f"  {r['seller_sku']:<15} {r['job_status']:<12} {r['readiness']['verdict']:<22} kz={s.get('lg_kz', {}).get('match_level')}/{s.get('lg_kz', {}).get('facts')} ru={s.get('lg_ru', {}).get('match_level')}/{s.get('lg_ru', {}).get('facts')} conflicts={len(r['real_conflicts'])} gaps={r['readiness']['gaps']}")


if __name__ == "__main__":
    with offline_only():
        main()
