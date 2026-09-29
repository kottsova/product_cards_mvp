"""Stage 22 step 5 -- the second LG pilot: the ORDINARY worker.run_once() for the 24 rows fixed in step 4.

Real: the default adapters of the worker (LGAdapter, LGRUDocumentAdapter, SulpakAdapter through PolicyAwareSession with a persisted log), stages
1,2,3,4,6, one job per row, the jobs database, the readiness code. Added around it: a ledger that lets a SAVED response stand in for a request the
project already made (Stage 20 pilot, Stage 21 probe/verification, Stage 22 documents probe) and counts every REAL request against the declared caps
(<= 12 per row, <= 180 in total, 1 s between real requests); a request over a cap is refused before it is made. A stopped lg.com ends the pilot.

Output: pilot2/workdir/* (its own database and fetch log), pilot2/responses/*, raw/pilot2_rows.json, raw/pilot2_requests.json
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
REPLAY = "--replay" in sys.argv  # OFFLINE re-run on the responses the live run saved (pilot2/responses): no request is possible; outputs go to pilot2_replay*
DRY = "--dry" in sys.argv or REPLAY  # every real request is refused (no network)
TAG = "pilot2_replay" if REPLAY else "pilot2_dry" if DRY else "pilot2"
PILOT = STAGE / TAG
sys.path.insert(0, str(ROOT))

from product_tool import jobs, readiness, worker  # noqa: E402
from product_tool.adapters.lg import lg_session  # noqa: E402
from product_tool.adapters.lg_policy import default_lg_adapters, lg_log_path  # noqa: E402
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log  # noqa: E402
from product_tool.adapters.policy_session import record_responses  # noqa: E402
from product_tool.coverage import executor  # noqa: E402

STAGES = [1, 2, 3, 4, 6]
PER_ROW, TOTAL, PACING = 12, 180, 1.0
RECORDED_DIRS = [ROOT / "reports/source_census_2026-09-24_stage20/pilot/responses", STAGE.parent / "source_census_2026-09-24_stage21/probe/responses",
                 STAGE.parent / "source_census_2026-09-24_stage21/verify/responses", STAGE / "docs_probe/responses"] + ([STAGE / "pilot2/responses"] if REPLAY else [])


def load_recorded() -> dict[str, tuple[int, str]]:
    pages = {}
    for directory in RECORDED_DIRS:
        for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["saved_as"]:
                with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                    pages[entry["url"]] = (entry["status"], handle.read())
    return pages


class Ledger:
    def __init__(self):
        self.row, self.row_real, self.total_real, self.last_real = "", 0, 0, 0.0
        self.events: list[dict] = []
        self.refusals: list[dict] = []

    def begin_row(self, sku: str) -> None:
        self.row, self.row_real = sku, 0


class RecordedResponse:
    def __init__(self, url, data: bytes, content_type: str, status: int):
        self.url, self.status_code, self._data = url, status, data
        self.headers = {"Content-Type": content_type}
        self.history, self.encoding = (), "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self._data,))

    def close(self):
        pass


class NoNetwork:
    headers: dict = {"User-Agent": "dry"}

    def get(self, url, **kwargs):
        raise requests.ConnectionError("[dry run: no network]")


class Underlying:
    """A saved response stands in for a request already made; anything else is a REAL request, counted and capped."""

    def __init__(self, recorded, real, ledger):
        self.recorded, self.real, self.ledger = recorded, real, ledger

    @property
    def headers(self):
        return self.real.headers

    def get(self, url, **kwargs):
        ledger = self.ledger
        if url in self.recorded:
            status, text = self.recorded[url]
            binary = "lge.com" in url
            data = text.encode("latin-1") if binary else text.encode("utf-8")
            content_type = ("application/pdf" if text.startswith("%PDF-") else "application/octet-stream") if binary else "text/html;charset=UTF-8"
            ledger.events.append({"row": ledger.row, "url": url, "kind": "replayed", "status": status})
            return RecordedResponse(url, data, content_type, status)
        if ledger.row_real >= PER_ROW or ledger.total_real >= TOTAL:
            ledger.refusals.append({"row": ledger.row, "url": url, "reason": "per-row cap" if ledger.row_real >= PER_ROW else "total cap"})
            raise requests.ConnectionError("[declared request cap reached]")
        wait = PACING - (time.monotonic() - ledger.last_real)
        if wait > 0:
            time.sleep(wait)
        ledger.row_real += 1
        ledger.total_real += 1
        try:
            response = self.real.get(url, **kwargs)
        finally:
            ledger.last_real = time.monotonic()
        ledger.events.append({"row": ledger.row, "url": url, "kind": "real", "status": response.status_code, "content_type": response.headers.get("Content-Type", "")})
        return response


def snapshot(database: Path, product_id: int, job: dict, ru_adapter) -> dict:
    sources = jobs.get_source_pages(database, product_id)
    facts = jobs.get_facts(database, product_id)
    resolved = jobs.get_resolved(database, product_id)
    photos = jobs.get_photo_candidates(database, product_id, include_excluded=True)
    card = readiness.card_readiness(database, product_id)
    conflicts = []
    for r in resolved:
        if r["conflict"]:
            conflicts.append({"normalized_name": r["normalized_name"], "raw_names": sorted({f["raw_name"] for f in facts if f["normalized_name"] == r["normalized_name"]}),
                              "sources": sorted({f["source_key"] for f in facts if f["normalized_name"] == r["normalized_name"]}),
                              "values": sorted({f["normalized_value"] for f in facts if f["normalized_name"] == r["normalized_name"]})})
    per_source = {s["source_key"]: {"match_level": s["match_level"], "url": s["url"], "found_model": s["found_model"], "error": s["error"], "evidence": s["evidence"][:200],
                                    "facts": sum(1 for f in facts if f["source_key"] == s["source_key"]),
                                    "gallery_selected": sum(1 for p in photos if p["source_key"] == s["source_key"] and p["kind"] == "product_gallery" and p["selected"])} for s in sources}
    documents = [{"title": d["title"], "language": d["language"], "date": d["document_date"], "support_model": d["support_model"], "direct_url": d["direct_url"]} for d in jobs.get_documents(database, product_id)]
    doc_report = ru_adapter.reports[-1] if ru_adapter is not None and ru_adapter.reports else None
    events = [{"stage": e.get("stage"), "level": e.get("level"), "message": e.get("message")} for e in jobs.list_events(database, job["id"])]
    return {"job": {"status": job["status"], "message": job["message"]}, "readiness": card, "sources": per_source, "resolved_total": len(resolved), "real_conflicts": conflicts,
            "documents_saved": documents, "documents_report": doc_report, "events": events}


def main() -> None:
    selection = json.loads((STAGE / "raw/pilot2_selection.json").read_text(encoding="utf-8"))
    declaration = json.loads((STAGE / "raw/pilot2_declaration.json").read_text(encoding="utf-8"))
    assert declaration["budget"]["max_real_requests_per_row"] == PER_ROW and declaration["budget"]["max_real_requests_total"] == TOTAL
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assert started > declaration["declared_at"]
    if REPLAY:
        assert (STAGE / "raw/pilot2_rows.json").exists(), "the live run must exist before its replay"
    if PILOT.exists():
        shutil.rmtree(PILOT)
    workdir = PILOT / "workdir"
    workdir.mkdir(parents=True)
    database = workdir / "batches.sqlite3"
    jobs.initialize(database)
    log = lg_log_path(workdir)
    recorded = load_recorded()
    ledger = Ledger()
    holder: dict = {}

    def factory():
        adapters = default_lg_adapters(workdir, clock=time.monotonic, underlying_lg=Underlying(recorded, NoNetwork() if DRY else lg_session(), ledger), underlying_sulpak=Underlying(recorded, NoNetwork() if DRY else requests.Session(), ledger), min_interval_seconds=0.0)
        holder["ru"] = adapters[1]
        return adapters

    rows, halted, not_run = [], "", []
    from contextlib import nullcontext
    with (nullcontext() if DRY else record_responses(PILOT / "responses")):
        for index, row in enumerate(selection["rows"]):
            if halted:
                not_run.append({"seller_sku": row["seller_sku"], "category": row["category"], "reason": halted})
                continue
            unit = {"catalog_row": row["catalog_row"], "brand": row["brand"], "category": row["category"], "title": row["title"], "seller_sku": row["seller_sku"]}
            product_id = executor._ensure_product(database, unit, "lg-pilot2")
            job_id = jobs.enqueue(database, product_id, STAGES)
            ledger.begin_row(row["seller_sku"])
            holder["ru"] = None
            t0 = time.monotonic()
            worker.run_once(database, factory, clock=time.monotonic)
            elapsed = round(time.monotonic() - t0, 1)
            job = next(j for j in jobs.list_jobs(database, product_id) if j["id"] == job_id)
            data = snapshot(database, product_id, job, holder["ru"])
            data.update({"index": index, "seller_sku": row["seller_sku"], "category": row["category"], "group": row["group"], "seconds": elapsed, "real_requests": ledger.row_real,
                         "replayed": sum(1 for e in ledger.events if e["row"] == row["seller_sku"] and e["kind"] == "replayed")})
            rows.append(data)
            entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
            stopped = sorted(stopped_hosts_from_fetch_log(entries))
            if any(h in ("www.lg.com", "lg.com") for h in stopped):
                halted = f"lg.com stopped by the policy after {row['seller_sku']}: {', '.join(stopped)}"
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    out = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "caps": {"per_row": PER_ROW, "total": TOTAL, "pacing_seconds": PACING},
           "real_requests_total": ledger.total_real, "real_per_row": {r["seller_sku"]: r["real_requests"] for r in rows}, "max_real_in_one_row": max((r["real_requests"] for r in rows), default=0),
           "events": ledger.events, "refusals": ledger.refusals, "halted": halted, "rows_not_run": not_run, "stopped_hosts": sorted(stopped_hosts_from_fetch_log(entries))}
    (STAGE / f"raw/{TAG}_requests.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (STAGE / f"raw/{TAG}_rows.json").write_text(json.dumps({"rows": rows, "halted": halted, "not_run": not_run}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rows_run={len(rows)} real_requests={ledger.total_real} max_in_row={out['max_real_in_one_row']} refusals={len(ledger.refusals)} halted={halted!r} stopped={out['stopped_hosts']}")
    for r in rows:
        s = r["sources"]
        print(f"  {r['seller_sku']:<22} {r['job']['status']:<12} {r['readiness']['verdict']:<22} kz={s.get('lg_kz', {}).get('match_level')} ru={s.get('lg_ru', {}).get('match_level')} req={r['real_requests']:>2} "
              f"conf={len(r['real_conflicts'])} docs={len(r['documents_saved'])} {r['readiness']['gaps']}")


if __name__ == "__main__":
    main()
