"""Persistent fetch attempts and immutable successful source snapshots."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from . import storage
from .identity import IdentityVerification


SUCCESS_STATUSES = {"success", "ok"}


def record_fetch_attempt(
    path: Path,
    product_id: int,
    source_id: str,
    *,
    status: str,
    requested_url: str = "",
    final_url: str = "",
    error: str = "",
    http_status: int | None = None,
    duration_ms: int | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> int:
    now = storage._now()
    started_at, finished_at = started_at or now, finished_at or now
    with storage._connection(path) as connection:
        cursor = connection.execute(
            "INSERT INTO fetch_attempts "
            "(product_id, source_id, status, error, started_at, finished_at, requested_url, "
            "final_url, http_status, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (product_id, source_id, status, error, started_at, finished_at, requested_url,
             final_url, http_status, duration_ms, now),
        )
        return int(cursor.lastrowid)


def save_source_snapshot(
    path: Path,
    product_id: int,
    source_id: str,
    fetch_attempt_id: int,
    *,
    source_url: str,
    content: str,
    extracted: dict[str, Any] | None = None,
    content_type: str = "text/html",
    fetched_at: str | None = None,
) -> int:
    """Persist immutable successful content; failed attempts are rejected."""
    with storage._connection(path) as connection:
        attempt = connection.execute(
            "SELECT status, product_id, source_id FROM fetch_attempts WHERE id=?",
            (fetch_attempt_id,),
        ).fetchone()
        if attempt is None:
            raise ValueError("FetchAttempt does not exist")
        if attempt["status"] not in SUCCESS_STATUSES:
            raise ValueError("A SourceSnapshot can only be created from a successful FetchAttempt")
        if attempt["product_id"] != product_id or attempt["source_id"] != source_id:
            raise ValueError("FetchAttempt does not belong to this product/source")
        cursor = connection.execute(
            "INSERT INTO source_snapshots "
            "(product_id, source_id, fetch_attempt_id, source_url, content_type, content, "
            "content_sha256, extracted_json, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (product_id, source_id, fetch_attempt_id, source_url, content_type, content,
             hashlib.sha256(content.encode("utf-8")).hexdigest(),
             storage._json(extracted or {}), fetched_at or storage._now()),
        )
        return int(cursor.lastrowid)


def latest_source_snapshot(path: Path, product_id: int, source_id: str) -> dict[str, Any] | None:
    with storage._connection(path) as connection:
        row = connection.execute(
            "SELECT * FROM source_snapshots WHERE product_id=? AND source_id=? ORDER BY id DESC LIMIT 1",
            (product_id, source_id),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["extracted"] = json.loads(result.pop("extracted_json"))
    return result


def reprocess_snapshot(snapshot: dict[str, Any], extractor: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """Recompute derived data without another network request or snapshot mutation."""
    return extractor(snapshot["content"])


def save_identity_verification(
    path: Path,
    product_id: int,
    source_id: str,
    verification: IdentityVerification,
    *,
    source_snapshot_id: int | None = None,
) -> int:
    evidence = []
    for item in verification.evidence:
        value = asdict(item)
        value["state"] = item.state.value
        evidence.append(value)
    with storage._connection(path) as connection:
        cursor = connection.execute(
            "INSERT INTO identity_verifications "
            "(product_id, source_id, source_snapshot_id, level, reason, evidence_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (product_id, source_id, source_snapshot_id, verification.level.value,
             verification.reason, storage._json(evidence), storage._now()),
        )
        return int(cursor.lastrowid)


def queue_human_review(
    path: Path,
    product_id: int,
    review_type: str,
    reason: str,
    provenance: dict[str, Any],
) -> int:
    with storage._connection(path) as connection:
        cursor = connection.execute(
            "INSERT INTO human_reviews "
            "(product_id, review_type, reason, provenance_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (product_id, review_type, reason, storage._json(provenance), storage._now()),
        )
        return int(cursor.lastrowid)
