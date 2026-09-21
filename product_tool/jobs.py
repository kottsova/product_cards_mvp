"""Persistent queue plus multi-source evidence and attribute resolution."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from . import storage
from .adapters.common import SourceDocument
from .normalization import normalize_facts
from .resolution import resolve_attributes


ACTIVE = ("queued", "running")
STAGE_NAMES = {1: "Источники", 2: "Описание", 3: "Характеристики", 4: "Фото"}


def initialize(path: Path) -> None:
    """Idempotent migration: only creates new objects, preserving old data."""
    storage.initialize(path)
    with storage._connection(path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS product_results (
                product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
                page_url TEXT NOT NULL DEFAULT '',
                match_status TEXT NOT NULL DEFAULT 'none',
                candidate_urls_json TEXT NOT NULL DEFAULT '[]',
                description TEXT NOT NULL DEFAULT '',
                attributes_json TEXT NOT NULL DEFAULT '{}',
                photos_json TEXT NOT NULL DEFAULT '[]',
                sources_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS search_jobs (
                id TEXT PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                stages_json TEXT NOT NULL,
                status TEXT NOT NULL,
                current_stage INTEGER,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );
            CREATE INDEX IF NOT EXISTS jobs_by_product ON search_jobs(product_id, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_product
                ON search_jobs(product_id) WHERE status IN ('queued', 'running');
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
                stage INTEGER,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_by_job ON job_events(job_id, id);

            CREATE TABLE IF NOT EXISTS source_pages (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                site_name TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                found_model TEXT NOT NULL DEFAULT '',
                match_level TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '',
                fetched_at TEXT NOT NULL,
                error TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                photos_json TEXT NOT NULL DEFAULT '[]',
                UNIQUE(product_id, source_key)
            );
            CREATE INDEX IF NOT EXISTS source_pages_by_product
                ON source_pages(product_id, source_key);

            CREATE TABLE IF NOT EXISTS extracted_attribute_facts (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                source_page_id INTEGER NOT NULL REFERENCES source_pages(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                site_name TEXT NOT NULL,
                raw_name TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                unit TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS facts_by_product_name
                ON extracted_attribute_facts(product_id, normalized_name, source_key);

            CREATE TABLE IF NOT EXISTS resolved_attributes (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                normalized_name TEXT NOT NULL,
                selected_value TEXT NOT NULL DEFAULT '',
                selected_unit TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                selected_source TEXT NOT NULL DEFAULT '',
                conflict INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(product_id, normalized_name)
            );

            CREATE TABLE IF NOT EXISTS manual_attribute_decisions (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                normalized_name TEXT NOT NULL,
                selected_value TEXT NOT NULL,
                selected_unit TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(product_id, normalized_name)
            );
        """)


def get_product(path: Path, product_id: int) -> dict[str, Any] | None:
    with storage._connection(path) as connection:
        row = connection.execute(
            "SELECT products.*, batches.filename, batches.sheet_name "
            "FROM products JOIN batches ON batches.id = products.batch_id WHERE products.id = ?",
            (product_id,),
        ).fetchone()
    return dict(row) if row else None


def _decode_job(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["stages"] = json.loads(result.pop("stages_json"))
    return result


def list_jobs(path: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM search_jobs WHERE product_id = ? ORDER BY created_at DESC, rowid DESC",
            (product_id,),
        ).fetchall()
    return [_decode_job(row) for row in rows]


def list_events(path: Path, job_id: str) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def enqueue(path: Path, product_id: int, stages: list[int]) -> str:
    if not stages or any(stage not in STAGE_NAMES for stage in stages):
        raise ValueError("Выберите хотя бы один этап 1–4.")
    job_id, now = uuid4().hex, storage._now()
    with storage._connection(path) as connection:
        product = connection.execute(
            "SELECT brand FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            raise ValueError("Товар не найден.")
        if product["brand"].strip().casefold() not in {"lg", "lg electronics", "лджи", "элджи"}:
            raise ValueError("Fallback Mechta и Sulpak сейчас доступен только для LG.")
        try:
            connection.execute(
                "INSERT INTO search_jobs "
                "(id, product_id, stages_json, status, message, created_at, updated_at) "
                "VALUES (?, ?, ?, 'queued', ?, ?, ?)",
                (job_id, product_id, storage._json(sorted(set(stages))), "Ожидает worker.", now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Поиск для этого товара уже стоит в очереди или выполняется.") from exc
        connection.execute(
            "INSERT INTO job_events (job_id, level, message, created_at) VALUES (?, 'info', ?, ?)",
            (job_id, "Задание добавлено в очередь.", now),
        )
    return job_id


def recover_interrupted(path: Path) -> int:
    now = storage._now()
    with storage._connection(path) as connection:
        rows = connection.execute("SELECT id FROM search_jobs WHERE status = 'running'").fetchall()
        for row in rows:
            connection.execute(
                "UPDATE search_jobs SET status='queued', current_stage=NULL, message=?, updated_at=? "
                "WHERE id=?",
                ("Worker перезапущен; задание снова в очереди.", now, row["id"]),
            )
            connection.execute(
                "INSERT INTO job_events (job_id, level, message, created_at) "
                "VALUES (?, 'warning', ?, ?)",
                (row["id"], "Worker перезапущен; задание будет повторено.", now),
            )
    return len(rows)


def claim_next(path: Path) -> dict[str, Any] | None:
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM search_jobs WHERE status='queued' ORDER BY created_at, rowid LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE search_jobs SET status='running', message=?, started_at=?, updated_at=? WHERE id=?",
            ("Worker начал обработку.", now, now, row["id"]),
        )
        connection.execute(
            "INSERT INTO job_events (job_id, level, message, created_at) "
            "VALUES (?, 'info', ?, ?)",
            (row["id"], "Worker начал обработку.", now),
        )
        result = _decode_job(row)
        result["status"] = "running"
        return result


def progress(
    path: Path, job_id: str, stage: int | None, message: str,
    *, level: str = "info", source_url: str = "",
) -> None:
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute(
            "UPDATE search_jobs SET current_stage=?, message=?, updated_at=? WHERE id=?",
            (stage, message, now, job_id),
        )
        connection.execute(
            "INSERT INTO job_events (job_id, stage, level, message, source_url, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, stage, level, message, source_url, now),
        )


def finish(path: Path, job_id: str, status: str, message: str) -> None:
    if status not in {"done", "needs_review", "not_found", "error"}:
        raise ValueError("Неизвестный конечный статус.")
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute(
            "UPDATE search_jobs SET status=?, message=?, updated_at=?, finished_at=? WHERE id=?",
            (status, message, now, now, job_id),
        )
        connection.execute(
            "INSERT INTO job_events (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
            (job_id, "info" if status == "done" else "warning", message, now),
        )


def save_source_document(
    path: Path,
    product_id: int,
    document: SourceDocument,
    *,
    update_description: bool = True,
    update_attributes: bool = True,
    update_photos: bool = True,
) -> None:
    """Upsert source evidence while preserving results of unselected stages."""
    normalized = normalize_facts(document.attributes) if update_attributes else []
    with storage._connection(path) as connection:
        previous = connection.execute(
            "SELECT description, photos_json FROM source_pages WHERE product_id=? AND source_key=?",
            (product_id, document.source_key),
        ).fetchone()
        description = (
            document.description if update_description
            else previous["description"] if previous else ""
        )
        photos = (
            document.photos if update_photos
            else json.loads(previous["photos_json"]) if previous else []
        )
        connection.execute(
            "INSERT INTO source_pages "
            "(product_id, source_key, site_name, url, found_model, match_level, evidence, "
            "fetched_at, error, description, photos_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(product_id, source_key) DO UPDATE SET "
            "site_name=excluded.site_name, url=excluded.url, found_model=excluded.found_model, "
            "match_level=excluded.match_level, evidence=excluded.evidence, "
            "fetched_at=excluded.fetched_at, error=excluded.error, "
            "description=excluded.description, photos_json=excluded.photos_json",
            (
                product_id, document.source_key, document.site_name, document.url,
                document.found_model, document.match_level, document.evidence,
                document.fetched_at, document.error, description, storage._json(photos),
            ),
        )
        page = connection.execute(
            "SELECT id FROM source_pages WHERE product_id=? AND source_key=?",
            (product_id, document.source_key),
        ).fetchone()
        if update_attributes:
            connection.execute(
                "DELETE FROM extracted_attribute_facts WHERE product_id=? AND source_key=?",
                (product_id, document.source_key),
            )
            connection.executemany(
                "INSERT INTO extracted_attribute_facts "
                "(product_id, source_page_id, source_key, site_name, raw_name, raw_value, "
                "normalized_name, normalized_value, unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        product_id, page["id"], document.source_key, document.site_name,
                        fact.raw_name, fact.raw_value, fact.normalized_name,
                        fact.normalized_value, fact.unit,
                    )
                    for fact in normalized
                ],
            )

def get_source_pages(path: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM source_pages WHERE product_id=? "
            "ORDER BY CASE source_key WHEN 'lg' THEN 1 WHEN 'sulpak' THEN 2 ELSE 3 END",
            (product_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["photos"] = json.loads(item.pop("photos_json"))
        result.append(item)
    return result


def get_facts(path: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM extracted_attribute_facts WHERE product_id=? "
            "ORDER BY normalized_name, source_key, id",
            (product_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_manual_decisions(path: Path, product_id: int) -> dict[str, dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM manual_attribute_decisions WHERE product_id=?", (product_id,)
        ).fetchall()
    return {row["normalized_name"]: dict(row) for row in rows}


def resolve_product(path: Path, product_id: int) -> None:
    sources = get_source_pages(path, product_id)
    facts = get_facts(path, product_id)
    manual = get_manual_decisions(path, product_id)
    resolved = resolve_attributes(facts, sources, manual)
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute("DELETE FROM resolved_attributes WHERE product_id=?", (product_id,))
        connection.executemany(
            "INSERT INTO resolved_attributes "
            "(product_id, normalized_name, selected_value, selected_unit, status, reason, "
            "selected_source, conflict, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    product_id, item.normalized_name, item.selected_value, item.selected_unit,
                    item.status, item.reason, item.selected_source, int(item.conflict), now,
                )
                for item in resolved
            ],
        )


def save_manual_decision(
    path: Path, product_id: int, normalized_name: str,
    selected_value: str, selected_unit: str = "", reason: str = "",
) -> None:
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute(
            "INSERT INTO manual_attribute_decisions "
            "(product_id, normalized_name, selected_value, selected_unit, reason, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(product_id, normalized_name) DO UPDATE SET "
            "selected_value=excluded.selected_value, selected_unit=excluded.selected_unit, "
            "reason=excluded.reason, updated_at=excluded.updated_at",
            (product_id, normalized_name, selected_value, selected_unit, reason, now),
        )
    resolve_product(path, product_id)


def get_resolved(path: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM resolved_attributes WHERE product_id=? ORDER BY normalized_name",
            (product_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def comparison_rows(path: Path, product_id: int) -> list[dict[str, Any]]:
    facts = get_facts(path, product_id)
    resolved = {row["normalized_name"]: row for row in get_resolved(path, product_id)}
    grouped: dict[str, dict[str, Any]] = {}
    for fact in facts:
        row = grouped.setdefault(fact["normalized_name"], {
            "normalized_name": fact["normalized_name"], "sources": {},
        })
        row["sources"].setdefault(fact["source_key"], fact)
    for name in sorted(set(grouped) | set(resolved)):
        row = grouped.setdefault(name, {"normalized_name": name, "sources": {}})
        row["resolved"] = resolved.get(name)
    return [grouped[name] for name in sorted(grouped)]


def identification_status(source_pages: list[dict[str, Any]]) -> str:
    by_key = {page["source_key"]: page for page in source_pages}
    lg = by_key.get("lg", {})
    confirmed = [
        key for key in ("sulpak", "mechta")
        if by_key.get(key, {}).get("match_level") == "full_sku"
    ]
    if len(confirmed) == 2:
        return "Полный артикул подтверждён двумя поставщиками"
    if confirmed == ["sulpak"]:
        return "Полный артикул подтверждён Sulpak"
    if confirmed == ["mechta"]:
        return "Полный артикул подтверждён Mechta"
    if any(page.get("match_level") == "mismatch" for page in source_pages):
        return "Найдено несоответствие артикула"
    if lg.get("match_level") == "full_sku":
        return "Полный артикул найден на LG"
    if lg.get("match_level") == "base_model":
        return "Найдена только базовая модель, требуется подтверждение артикула"
    return "Источники не найдены за отведённое время"


def get_result(path: Path, product_id: int) -> dict[str, Any]:
    """Compatibility view for existing templates/tests."""
    sources = get_source_pages(path, product_id)
    lg = next((page for page in sources if page["source_key"] == "lg"), None)
    return {
        "page_url": lg["url"] if lg else "",
        "match_status": lg["match_level"] if lg else "none",
        "candidate_urls": [],
        "description": lg["description"] if lg else "",
        "attributes": {
            row["normalized_name"]: row["selected_value"]
            for row in get_resolved(path, product_id) if row["selected_value"]
        },
        "photos": lg["photos"] if lg else [],
        "sources": {"link": lg["url"]} if lg and lg["url"] else {},
    }
