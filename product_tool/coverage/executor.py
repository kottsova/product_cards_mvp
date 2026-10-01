"""Hand queue units to the ordinary worker.run_once() and keep a checkpoint.

The executor adds no pipeline logic of its own: a unit becomes a product row
in a jobs database (same tables the web importer fills), a job is enqueued
with the ordinary `jobs.enqueue`, and `worker.run_once()` does the work with
the adapter factories the caller supplies. What this module contributes is
the safety around it:

  * a unit whose plan status is not runnable is *not* handed to run_once();
    the checkpoint records the exact stop reason instead;
  * before every unit the persisted fetch logs are re-read, so a host stopped
    by an earlier unit (or an earlier process) is honoured across restarts;
  * default transports refuse every request (`RefusingSession`) and record the
    URL they refused, so a unit that would need a fixture stops with a reason
    instead of touching the network;
  * one atomic checkpoint file; a rerun over it skips finished units and makes
    no call for them.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import requests

from .. import jobs, worker
from ..adapters.dns import DnsAdapter
from ..adapters.hyperx import HyperXAdapter, parse_attribute_scope
from ..adapters.lg import LGAdapter, LGRUAdapter
from ..adapters.sulpak import SulpakAdapter
from ..adapters.policy_fetch import stopped_hosts_from_fetch_log
from ..adapters.samsung_source import default_samsung_adapter
from ..identity import ProductIdentity
from .classify import ADDRESSABLE_STATUSES_FOR_RUN, READY, URL_MISSING
from .facts import host_matches

CHECKPOINT_VERSION = 1
DEFAULT_STAGES = (1, 2, 3, 4, 6)
TERMINAL_JOB_STATES = frozenset({"done", "needs_review", "not_found", "error"})


class RefusingSession:
    """A transport that never talks to anything. Every `get` is recorded and
    refused with a requests-style error, which every adapter already maps to
    an ordinary 'source unavailable' outcome."""

    def __init__(self):
        self.refused: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url, **kwargs):
        self.refused.append(url)
        raise requests.ConnectionError(f"offline coverage run: no fixture transport for {url}")


@dataclass
class RunFactories:
    """What run_once() is given. Defaults are offline-safe (refusing session);
    a control run swaps in fixture sessions."""
    session: RefusingSession = field(default_factory=RefusingSession)
    adapter_factory: Callable | None = None
    hyperx_adapter_factory: Callable | None = None
    samsung_adapter_factory: Callable | None = None
    dns_adapter_factory: Callable | None = None
    fetch_log_paths: tuple[Path, ...] = ()

    def resolve(self, workdir: Path, clock: Callable[[], float]) -> dict:
        log = workdir / "hyperx_fetch_log.json"
        session = self.session
        return {
            "adapter_factory": self.adapter_factory or (lambda: (LGAdapter(session, clock=clock), LGRUAdapter(session, clock=clock), SulpakAdapter(session, clock=clock))),
            "hyperx_adapter_factory": self.hyperx_adapter_factory or (lambda: HyperXAdapter(session, clock=clock, fetch_log_path=log)),
            "samsung_adapter_factory": self.samsung_adapter_factory or (lambda: default_samsung_adapter(workdir, clock=clock, underlying=session, min_interval_seconds=0.0)),
            "dns_adapter_factory": self.dns_adapter_factory or (lambda: DnsAdapter(session, clock=clock)),
        }

    def logs(self, workdir: Path) -> tuple[Path, ...]:
        return self.fetch_log_paths or (workdir / "hyperx_fetch_log.json", workdir / "samsung_fetch_log.json")


# -------------------------------------------------------------- checkpoint


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"version": CHECKPOINT_VERSION, "units": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != CHECKPOINT_VERSION:
        raise ValueError(f"Unsupported checkpoint version in {path}")
    return data


def save_checkpoint(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------- database


def _ensure_product(database: Path, unit: dict, batch_id: str) -> int:
    connection = sqlite3.connect(database, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT OR IGNORE INTO batches (id, filename, sheet_name, mapping_json, confirmed_at) VALUES (?, ?, ?, '{}', 'coverage-queue')",
            (batch_id, "coverage-queue", "Товары"),
        )
        row = connection.execute("SELECT id FROM products WHERE batch_id=? AND row_number=?", (batch_id, unit["catalog_row"])).fetchone()
        if row:
            connection.commit()
            return int(row["id"])
        product = {"brand": unit["brand"], "category": unit["category"], "name": unit["title"], "search_code": unit["seller_sku"], "alternate_code": ""}
        cursor = connection.execute(
            "INSERT INTO products (batch_id, row_number, name, brand, search_code, alternate_code, category, needs_confirmation, "
            "issues_json, original_values_json, identity_json) VALUES (?, ?, ?, ?, ?, '', ?, 0, '[]', '{}', ?)",
            (batch_id, unit["catalog_row"], unit["title"], unit["brand"], unit["seller_sku"], unit["category"],
             json.dumps(ProductIdentity.from_product(product).to_dict(), ensure_ascii=False)),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


_OFFICIAL_KEYS = frozenset({"hyperx", "lg_kz", "lg_ru", "lg_global", "samsung"})
_EVIDENCE_LEVELS = frozenset({"exact_variant", "full_sku", "code_in_page_text", "base_model", "base_code_confirmed", "model_and_code_confirmed"})


def _has_evidence(sources: list[dict]) -> bool:
    """A page was actually read and matched at some level (as opposed to nothing found)."""
    return any(item["match_level"] in _EVIDENCE_LEVELS and not item["error"] for item in sources)



def _stop_code(job: dict, sources: list[dict], conflicts: int = 0) -> str:
    """The most specific reason a finished job did not produce an accepted card."""
    official = [item for item in sources if item["source_key"] in _OFFICIAL_KEYS]
    levels = {(item["source_key"], item["match_level"]) for item in sources}
    if job["status"] == "needs_review":
        if not _has_evidence(sources) and any("no fixture transport" in item["error"] for item in official):
            return "offline_no_fixture_transport"
        if any(item["match_level"] in {"base_code_confirmed", "base_model"} for item in official):
            return "identity_base_code_only"
        if any(item["match_level"] == "mismatch" for item in official) and not any(item["match_level"] in {"exact_variant", "full_sku"} for item in official):
            return "identity_mismatch"
        if conflicts:
            return "attribute_conflict"
        if any(key in {"lg_kz", "lg_ru", "lg_global"} and level == "full_sku" for key, level in levels):
            return "official_full_sku_awaiting_supplier_confirmation"
        if ("dns", "model_and_code_confirmed") in levels:
            return "dealer_only_needs_human_review"
        return "job_needs_review"
    for item in sorted(official, key=lambda i: i["source_key"]):
        if item["match_level"] == "official_url_needed":
            return "official_url_needed"
        if item["match_level"] == "blocked":
            return "host_blocked"
        if item["error"] and "no fixture transport" in item["error"]:
            return "offline_no_fixture_transport"
    if any(item["error"] for item in official):
        return "official_source_error"
    return "job_" + job["status"]


def _card(database: Path, product_id: int, job: dict) -> dict:
    sources = jobs.get_source_pages(database, product_id)
    counts = jobs.result_counts(database, product_id)
    photos = jobs.get_photo_candidates(database, product_id, include_excluded=False)
    photos_all = jobs.get_photo_candidates(database, product_id, include_excluded=True)
    documents = jobs.get_documents(database, product_id)
    facts = jobs.get_facts(database, product_id)
    resolved = jobs.get_resolved(database, product_id)
    return {
        "job_status": job["status"], "job_message": job["message"],
        "identity": jobs.identification_status(sources) if sources else "",
        "sources": [
            {"source_key": s["source_key"], "match_level": s["match_level"], "url": s["url"], "error": s["error"], "evidence": s["evidence"]}
            for s in sources
        ],
        "facts": len(facts), "resolved_attributes": len(resolved), "photos": len(photos), "photos_excluded": len(photos_all) - len(photos),
        "photos_by_kind": dict(sorted(Counter(p["kind"] for p in photos).items())), "documents": len(documents),
        # Which attributes belong to the selected variant and which are shared by the whole model (adapters that say so).
        "attribute_scope": next((parse_attribute_scope(s["evidence"]) for s in sources if s["source_key"] == "hyperx"), {"variant": [], "model": []}),
        "conflict_names": sorted(r["normalized_name"] for r in resolved if r.get("conflict")),
        "conflicts": counts.get("conflicts", 0),
        "gaps": [name for name, value in (("attributes", len(facts)), ("photos", len(photos)), ("documents", len(documents))) if not value],
        "evidence_urls": sorted({s["url"] for s in sources if s["url"]} | {d["direct_url"] for d in documents}),
    }


# ------------------------------------------------------------------ runner


def run_units(
    units: Iterable[dict], *, workdir: Path, checkpoint_path: Path, factories: RunFactories | None = None,
    stages: tuple[int, ...] = DEFAULT_STAGES, clock: Callable[[], float] = lambda: 0.0, batch_id: str = "coverage-queue",
) -> dict:
    """Process units in order. Returns the checkpoint dict (also saved to disk)."""
    factories = factories or RunFactories()
    workdir.mkdir(parents=True, exist_ok=True)
    database = workdir / "batches.sqlite3"
    jobs.initialize(database)
    checkpoint = load_checkpoint(checkpoint_path)
    for unit in units:
        unit_id = unit["unit_id"]
        previous = checkpoint["units"].get(unit_id)
        if previous and previous["outcome"] in {"card", "review", "stopped"}:
            previous["resume_skips"] = previous.get("resume_skips", 0) + 1
            continue  # finished in an earlier pass: no call, no rerun
        entry = _process(unit, database, workdir, batch_id, factories, stages, clock)
        checkpoint["units"][unit_id] = entry
        save_checkpoint(checkpoint_path, checkpoint)
    save_checkpoint(checkpoint_path, checkpoint)
    return checkpoint


def _process(unit, database, workdir, batch_id, factories, stages, clock) -> dict:
    base = {
        "catalog_row": unit["catalog_row"], "brand": unit["brand"], "category": unit["category"], "seller_sku": unit["seller_sku"],
        "plan_status": unit["status"], "plan_reason": unit["reason"], "next_action": unit["next_action"],
        # Risks to verify together with the title, model and variant travel with the unit.
        "flags": list(unit.get("flags", [])), "sku_risk": unit.get("sku_risk", ""), "title": unit.get("title", ""),
    }
    if unit["status"] not in ADDRESSABLE_STATUSES_FOR_RUN:
        return {**base, "outcome": "stopped", "stop_code": unit["reason"], "stopped_before_run_once": True,
                "stop_detail": unit.get("detail") or f"Plan status {unit['status']}: {unit['next_action']}.", "network_calls_refused": []}

    blocked = set()
    for log in factories.logs(workdir):
        try:
            entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
        except (OSError, ValueError):
            entries = []
        blocked |= stopped_hosts_from_fetch_log(e for e in entries if isinstance(e, dict))
    stopped = [host for host in unit["hosts"] if host_matches(host, blocked)]
    if stopped:
        return {**base, "outcome": "stopped", "stop_code": "host_blocked", "stopped_before_run_once": True,
                "stop_detail": f"Host {stopped[0]} has a recorded 401/403/429 in a persisted fetch log; no request is made.", "network_calls_refused": []}

    session = factories.session
    refused_before = len(session.refused)
    product_id = _ensure_product(database, unit, batch_id)
    job_id = jobs.enqueue(database, product_id, list(stages))
    worker.run_once(database, clock=clock, **factories.resolve(workdir, clock))
    job = next(j for j in jobs.list_jobs(database, product_id) if j["id"] == job_id)
    refused = session.refused[refused_before:]
    if job["status"] not in TERMINAL_JOB_STATES:
        return {**base, "outcome": "stopped", "stop_code": "job_not_finished", "stopped_before_run_once": False,
                "stop_detail": job["message"], "job_id": job_id, "network_calls_refused": refused}
    card = _card(database, product_id, job)
    entry = {**base, "job_id": job_id, "product_id": product_id, "job_status": job["status"], "network_calls_refused": refused, "card": card,
             "stopped_before_run_once": False}
    sources = jobs.get_source_pages(database, product_id)
    if job["status"] == "done":
        entry.update(outcome="card", stop_code="")
    elif job["status"] == "needs_review" and _has_evidence(sources):
        entry.update(outcome="review", stop_code=_stop_code(job, sources, card["conflicts"]), stop_detail=job["message"])
    else:
        entry.update(outcome="stopped", stop_code=_stop_code(job, sources, card["conflicts"]), stop_detail=job["message"])
    return entry


def summarize(checkpoint: dict) -> dict:
    outcomes: dict[str, int] = {}
    stops: dict[str, int] = {}
    for entry in checkpoint["units"].values():
        outcomes[entry["outcome"]] = outcomes.get(entry["outcome"], 0) + 1
        if entry.get("stop_code"):
            stops[entry["stop_code"]] = stops.get(entry["stop_code"], 0) + 1
    return {"units": len(checkpoint["units"]), "outcomes": dict(sorted(outcomes.items())), "stop_codes": dict(sorted(stops.items()))}
