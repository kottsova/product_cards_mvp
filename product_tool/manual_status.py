"""Three-state Russian instruction status backed by completed official searches."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import jobs, storage
from .lg_identity import document_tied_to_article

VERIFIED = "Проверена"
NOT_FOUND = "Проверена, не найдена"
UNCHECKED = "Не проверена"


def initialize(path: Path) -> None:
    jobs.initialize(path)
    with storage._connection(path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS official_manual_searches (
                product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
                article TEXT NOT NULL,
                outcome TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                checked_at TEXT NOT NULL
            )
        """)


def record_completed_absence(path: Path, product_id: int, article: str, evidence: list[dict]) -> None:
    """Record a bounded completed search; attempted/unreachable pages do not qualify."""
    if not evidence or not any(
        item.get("checked") and item.get("official")
        and item.get("kind") == "official_manual_list"
        and item.get("exact_model") and item.get("russian_found") is False
        for item in evidence
    ):
        raise ValueError("A completed official manual search needs an exact official manual list")
    initialize(path)
    with storage._connection(path) as connection:
        connection.execute("""
            INSERT INTO official_manual_searches(product_id, article, outcome, evidence_json, checked_at)
            VALUES (?, ?, 'not_found', ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                article=excluded.article, outcome=excluded.outcome,
                evidence_json=excluded.evidence_json, checked_at=excluded.checked_at
        """, (product_id, article, json.dumps(evidence, ensure_ascii=False), storage._now()))


def completed_search(path: Path, product_id: int) -> dict | None:
    try:
        with storage._connection(path) as connection:
            row = connection.execute(
                "SELECT article, outcome, evidence_json, checked_at FROM official_manual_searches WHERE product_id=?",
                (product_id,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    return {**dict(row), "evidence": json.loads(row["evidence_json"])} if row else None


def russian_status(path: Path, product_id: int, article: str, *, lg: bool = True) -> str:
    sources = jobs.get_source_pages(path, product_id)
    for document in jobs.get_documents(path, product_id):
        if document["language"] == "Русский" and (not lg or document_tied_to_article(article, document, sources)):
            return VERIFIED
    search = completed_search(path, product_id)
    if search and search["article"] == article and search["outcome"] == "not_found":
        return NOT_FOUND
    return UNCHECKED
