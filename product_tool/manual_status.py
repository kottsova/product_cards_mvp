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


VERIFIED_LANGUAGE = "\u0420\u0443\u0441\u0441\u043a\u0438\u0439"

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



def record_incomplete(path: Path, product_id: int, article: str, evidence: list[dict]) -> None:
    """Record a concrete technical obstacle without claiming absence."""
    if not evidence or not any(item.get("official") and item.get("url")
                               and item.get("technical_reason") for item in evidence):
        raise ValueError("An incomplete search needs an official URL and technical reason")
    initialize(path)
    with storage._connection(path) as connection:
        prior = connection.execute(
            "SELECT outcome FROM official_manual_searches WHERE product_id=?", (product_id,)
        ).fetchone()
        if prior and prior["outcome"] == "not_found":
            return
        connection.execute("""
            INSERT INTO official_manual_searches(product_id, article, outcome, evidence_json, checked_at)
            VALUES (?, ?, 'incomplete', ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                article=excluded.article, outcome=excluded.outcome,
                evidence_json=excluded.evidence_json, checked_at=excluded.checked_at
        """, (product_id, article, json.dumps(evidence, ensure_ascii=False), storage._now()))


def unchecked_reason(path: Path, product_id: int, article: str) -> str:
    if russian_status(path, product_id, article) != UNCHECKED:
        return ""
    search = completed_search(path, product_id)
    if search and search["article"] == article and search["outcome"] == "incomplete":
        return "; ".join(item.get("technical_reason", "") for item in search["evidence"]
                         if item.get("technical_reason"))
    return ""

def _sibling_ids(path: Path, product_id: int, article: str) -> list[int]:
    product = jobs.get_product(path, product_id)
    if not product or product["brand"].strip().upper() != "LG" or product["search_code"] != article:
        return []
    with storage._connection(path) as connection:
        rows = connection.execute("""
            SELECT id FROM products WHERE id<>? AND upper(brand)='LG' AND search_code=?
            ORDER BY id DESC
        """, (product_id, article)).fetchall()
    return [row["id"] for row in rows]


def completed_search(path: Path, product_id: int) -> dict | None:
    product = jobs.get_product(path, product_id)
    try:
        with storage._connection(path) as connection:
            row = connection.execute(
                "SELECT article, outcome, evidence_json, checked_at FROM official_manual_searches WHERE product_id=?",
                (product_id,),
            ).fetchone()
            if not row and product and product["brand"].strip().upper() == "LG":
                row = connection.execute("""
                    SELECT m.article, m.outcome, m.evidence_json, m.checked_at
                    FROM official_manual_searches m JOIN products p ON p.id=m.product_id
                    WHERE upper(p.brand)='LG' AND p.search_code=? AND m.article=?
                    ORDER BY (m.outcome='not_found') DESC, m.checked_at DESC LIMIT 1
                """, (product["search_code"], product["search_code"])).fetchone()
    except sqlite3.OperationalError:
        return None
    return {**dict(row), "evidence": json.loads(row["evidence_json"])} if row else None


def effective_documents(path: Path, product_id: int, article: str) -> list[dict]:
    """Reuse verified official manuals only for the identical catalog article."""
    local_pages = jobs.get_source_pages(path, product_id)
    documents = []
    seen: dict[str, int] = {}
    for document in jobs.get_documents(path, product_id):
        item = {**document, "identity_confirmed": document_tied_to_article(article, document, local_pages)}
        seen[item["direct_url"]] = len(documents)
        documents.append(item)
    for other_id in _sibling_ids(path, product_id, article):
        pages = jobs.get_source_pages(path, other_id)
        for document in jobs.get_documents(path, other_id):
            if (document["language"] != VERIFIED_LANGUAGE or
                    not document["source_key"].startswith("lg_") or
                    not document_tied_to_article(article, document, pages)):
                continue
            item = {**document, "identity_confirmed": True,
                    "inherited_from_product_id": other_id}
            index = seen.get(item["direct_url"])
            if index is None:
                seen[item["direct_url"]] = len(documents)
                documents.append(item)
            elif not documents[index]["identity_confirmed"]:
                documents[index] = item
    return documents


def russian_status(path: Path, product_id: int, article: str, *, lg: bool = True) -> str:
    product = jobs.get_product(path, product_id)
    if product and product["brand"].strip().casefold() in {"samsung", "samsung electronics", "\u0441\u0430\u043c\u0441\u0443\u043d\u0433"}:
        from . import samsung_readiness
        if samsung_readiness.full_russian_instruction_confirmed(path, product_id):
            return VERIFIED
        search = completed_search(path, product_id)
        return NOT_FOUND if search and search["article"] == article and search["outcome"] == "not_found" else UNCHECKED
    documents = effective_documents(path, product_id, article) if lg else jobs.get_documents(path, product_id)
    for document in documents:
        if document["language"] == VERIFIED_LANGUAGE and (not lg or document["identity_confirmed"]):
            return VERIFIED
    search = completed_search(path, product_id)
    if search and search["article"] == article and search["outcome"] == "not_found":
        return NOT_FOUND
    return UNCHECKED
