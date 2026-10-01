"""Append-only, per-job search diagnostics. Search results never prove product identity."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import storage


def initialize(path: Path) -> None:
    with storage._connection(path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS discovery_trace (
                id INTEGER PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                event_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS discovery_trace_by_job ON discovery_trace(job_id, id)")


def record(path: Path, job_id: str, product_id: int, event: dict[str, Any]) -> None:
    if not event.get("event") or not event.get("timestamp"):
        raise ValueError("discovery trace requires event and timestamp")
    with storage._connection(path) as connection:
        connection.execute(
            "INSERT INTO discovery_trace(job_id, product_id, event_json, created_at) VALUES (?, ?, ?, ?)",
            (job_id, product_id, json.dumps(event, ensure_ascii=False, sort_keys=True), event["timestamp"]),
        )


def for_job(path: Path, job_id: str) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT event_json FROM discovery_trace WHERE job_id=? ORDER BY id", (job_id,)
        ).fetchall()
    return [json.loads(row["event_json"]) for row in rows]
