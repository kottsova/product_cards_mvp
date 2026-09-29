"""Structured evidence kept next to a card (Stage 26).

The job message and the source rows carry text; a card's evidence LEVELS (how the variant was confirmed, what each document fact is, what a dealer changed) are structured, so the readiness
verdict and the export read them instead of parsing sentences. One JSON payload per (product, kind); open review items go to the shared `human_reviews` table
(fetch_history.queue_human_review), one open item per (product, review type), replaced on a re-run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import fetch_history, storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS card_evidence (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (product_id, kind)
)
"""


def save(database: Path, product_id: int, kind: str, payload: dict[str, Any]) -> None:
    with storage._connection(database) as connection:
        connection.execute(SCHEMA)
        connection.execute(
            "INSERT INTO card_evidence (product_id, kind, payload_json, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(product_id, kind) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at",
            (product_id, kind, storage._json(payload), storage._now()),
        )


def load(database: Path, product_id: int, kind: str) -> dict[str, Any] | None:
    with storage._connection(database) as connection:
        connection.execute(SCHEMA)
        row = connection.execute("SELECT payload_json FROM card_evidence WHERE product_id=? AND kind=?", (product_id, kind)).fetchone()
    return json.loads(row["payload_json"]) if row else None


def replace_review(database: Path, product_id: int, review_type: str, reason: str, provenance: dict[str, Any]) -> int:
    """One open review item per (product, type): an older open one is dropped, a resolved one is left alone."""
    with storage._connection(database) as connection:
        connection.execute("DELETE FROM human_reviews WHERE product_id=? AND review_type=? AND status='open'", (product_id, review_type))
    return fetch_history.queue_human_review(database, product_id, review_type, reason, provenance)


def clear_review(database: Path, product_id: int, review_type: str) -> None:
    with storage._connection(database) as connection:
        connection.execute("DELETE FROM human_reviews WHERE product_id=? AND review_type=? AND status='open'", (product_id, review_type))


def open_reviews(database: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(database) as connection:
        rows = connection.execute("SELECT review_type, reason, provenance_json FROM human_reviews WHERE product_id=? AND status='open' ORDER BY id", (product_id,)).fetchall()
    return [{"review_type": r["review_type"], "reason": r["reason"], "provenance": json.loads(r["provenance_json"])} for r in rows]
