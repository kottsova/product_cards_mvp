"""Persistent product search queue, progress, and sourced results."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from . import storage


ACTIVE = ("queued", "running")
STAGE_NAMES = {1: "Ссылка", 2: "Описание", 3: "Характеристики", 4: "Фото"}


def initialize(path: Path) -> None:
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
        """)


def get_product(path: Path, product_id: int) -> dict[str, Any] | None:
    with storage._connection(path) as connection:
        row = connection.execute(
            "SELECT products.*, batches.filename, batches.sheet_name "
            "FROM products JOIN batches ON batches.id = products.batch_id "
            "WHERE products.id = ?",
            (product_id,),
        ).fetchone()
    return dict(row) if row else None


def get_result(path: Path, product_id: int) -> dict[str, Any]:
    with storage._connection(path) as connection:
        row = connection.execute(
            "SELECT * FROM product_results WHERE product_id = ?", (product_id,)
        ).fetchone()
    if row is None:
        return {
            "page_url": "", "match_status": "none", "candidate_urls": (),
            "description": "", "attributes": {}, "photos": [], "sources": {},
        }
    result = dict(row)
    for field in ("candidate_urls", "attributes", "photos", "sources"):
        result[field] = json.loads(result.pop(f"{field}_json"))
    return result


def list_jobs(path: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM search_jobs WHERE product_id = ? ORDER BY created_at DESC, rowid DESC",
            (product_id,),
        ).fetchall()
    return [_decode_job(row) for row in rows]


def get_job(path: Path, job_id: str) -> dict[str, Any] | None:
    with storage._connection(path) as connection:
        row = connection.execute("SELECT * FROM search_jobs WHERE id = ?", (job_id,)).fetchone()
    return _decode_job(row) if row else None


def _decode_job(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["stages"] = json.loads(result.pop("stages_json"))
    return result


def list_events(path: Path, job_id: str) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def enqueue(path: Path, product_id: int, stages: list[int]) -> str:
    if not stages or any(stage not in STAGE_NAMES for stage in stages):
        raise ValueError("Выберите хотя бы один этап 1–4.")
    normalized = sorted(set(stages))
    job_id = uuid4().hex
    now = storage._now()
    with storage._connection(path) as connection:
        product = connection.execute(
            "SELECT brand FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            raise ValueError("Товар не найден.")
        if product["brand"].strip().casefold() not in {"lg", "lg electronics", "лджи", "элджи"}:
            raise ValueError("На этом этапе поиск доступен только для товаров LG.")
        try:
            connection.execute(
                "INSERT INTO search_jobs "
                "(id, product_id, stages_json, status, message, created_at, updated_at) "
                "VALUES (?, ?, ?, 'queued', ?, ?, ?)",
                (job_id, product_id, storage._json(normalized), "Ожидает worker.", now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Поиск для этого товара уже стоит в очереди или выполняется.") from exc
        connection.execute(
            "INSERT INTO job_events (job_id, stage, level, message, created_at) "
            "VALUES (?, NULL, 'info', ?, ?)",
            (job_id, "Задание добавлено в очередь.", now),
        )
    return job_id


def recover_interrupted(path: Path) -> int:
    now = storage._now()
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT id FROM search_jobs WHERE status = 'running'"
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE search_jobs SET status = 'queued', current_stage = NULL, "
                "message = ?, updated_at = ? WHERE id = ?",
                ("Worker перезапущен; задание снова в очереди.", now, row["id"]),
            )
            connection.execute(
                "INSERT INTO job_events (job_id, stage, level, message, created_at) "
                "VALUES (?, NULL, 'warning', ?, ?)",
                (row["id"], "Worker перезапущен; задание будет повторено.", now),
            )
    return len(rows)


def claim_next(path: Path) -> dict[str, Any] | None:
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM search_jobs WHERE status = 'queued' ORDER BY created_at, rowid LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE search_jobs SET status = 'running', message = ?, started_at = ?, "
            "updated_at = ? WHERE id = ?",
            ("Worker начал обработку.", now, now, row["id"]),
        )
        connection.execute(
            "INSERT INTO job_events (job_id, stage, level, message, created_at) "
            "VALUES (?, NULL, 'info', ?, ?)",
            (row["id"], "Worker начал обработку.", now),
        )
        job = _decode_job(row)
        job["status"] = "running"
        return job


def progress(
    path: Path, job_id: str, stage: int | None, message: str,
    *, level: str = "info", source_url: str = ""
) -> None:
    now = storage._now()
    with storage._connection(path) as connection:
        connection.execute(
            "UPDATE search_jobs SET current_stage = ?, message = ?, updated_at = ? WHERE id = ?",
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
            "UPDATE search_jobs SET status = ?, message = ?, updated_at = ?, finished_at = ? "
            "WHERE id = ?",
            (status, message, now, now, job_id),
        )
        connection.execute(
            "INSERT INTO job_events (job_id, stage, level, message, created_at) "
            "VALUES (?, NULL, ?, ?, ?)",
            (job_id, "info" if status == "done" else "warning", message, now),
        )


def _ensure_result(connection: sqlite3.Connection, product_id: int) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO product_results (product_id, updated_at) VALUES (?, ?)",
        (product_id, storage._now()),
    )


def save_link(path: Path, product_id: int, url: str, candidates: tuple[str, ...]) -> None:
    with storage._connection(path) as connection:
        _ensure_result(connection, product_id)
        row = connection.execute(
            "SELECT sources_json FROM product_results WHERE product_id = ?", (product_id,)
        ).fetchone()
        sources = json.loads(row["sources_json"])
        sources["link"] = url
        connection.execute(
            "UPDATE product_results SET page_url = ?, match_status = 'exact', "
            "candidate_urls_json = ?, sources_json = ?, updated_at = ? WHERE product_id = ?",
            (url, storage._json(candidates), storage._json(sources), storage._now(), product_id),
        )


def save_review(path: Path, product_id: int, candidates: tuple[str, ...]) -> None:
    with storage._connection(path) as connection:
        _ensure_result(connection, product_id)
        connection.execute(
            "UPDATE product_results SET match_status = 'needs_review', "
            "candidate_urls_json = ?, updated_at = ? WHERE product_id = ?",
            (storage._json(candidates), storage._now(), product_id),
        )


def save_field(path: Path, product_id: int, field: str, value: Any, source_url: str) -> None:
    columns = {"description": "description", "attributes": "attributes_json", "photos": "photos_json"}
    if field not in columns:
        raise ValueError("Неизвестное поле результата.")
    stored = value if field == "description" else storage._json(value)
    with storage._connection(path) as connection:
        _ensure_result(connection, product_id)
        row = connection.execute(
            "SELECT sources_json FROM product_results WHERE product_id = ?", (product_id,)
        ).fetchone()
        sources = json.loads(row["sources_json"])
        sources[field] = source_url
        connection.execute(
            f"UPDATE product_results SET {columns[field]} = ?, sources_json = ?, "
            "updated_at = ? WHERE product_id = ?",
            (stored, storage._json(sources), storage._now(), product_id),
        )