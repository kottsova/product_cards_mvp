"""Local SQLite storage for Excel drafts and confirmed batches."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .importer import ImportPreview


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _connection(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connection(path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sheet_name TEXT,
                mapping_json TEXT
            );
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                mapping_json TEXT NOT NULL,
                confirmed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                row_number INTEGER NOT NULL,
                name TEXT NOT NULL,
                brand TEXT NOT NULL,
                search_code TEXT NOT NULL,
                alternate_code TEXT NOT NULL,
                category TEXT NOT NULL,
                needs_confirmation INTEGER NOT NULL,
                issues_json TEXT NOT NULL,
                original_values_json TEXT NOT NULL,
                UNIQUE(batch_id, row_number)
            );
            CREATE INDEX IF NOT EXISTS products_by_batch ON products(batch_id, category);
        """)


def create_draft(path: Path, draft_id: str, filename: str) -> None:
    with _connection(path) as connection:
        connection.execute(
            "INSERT INTO drafts (id, filename, created_at) VALUES (?, ?, ?)",
            (draft_id, filename, _now()),
        )


def get_draft(path: Path, draft_id: str) -> dict[str, Any] | None:
    with _connection(path) as connection:
        row = connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    mapping_json = result.pop("mapping_json")
    result["mapping"] = json.loads(mapping_json) if mapping_json else None
    return result


def update_draft_mapping(
    path: Path, draft_id: str, sheet_name: str, mapping: dict[str, int | None]
) -> None:
    with _connection(path) as connection:
        connection.execute(
            "UPDATE drafts SET sheet_name = ?, mapping_json = ? WHERE id = ?",
            (sheet_name, _json(mapping), draft_id),
        )


def confirm_draft(
    path: Path,
    draft_id: str,
    preview: ImportPreview,
    products: list[dict[str, Any]],
) -> None:
    with _connection(path) as connection:
        draft = connection.execute("SELECT filename FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise ValueError("Черновик не найден или партия уже подтверждена")
        connection.execute(
            "INSERT INTO batches (id, filename, sheet_name, mapping_json, confirmed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (draft_id, draft["filename"], preview.sheet_name, _json(asdict(preview.mapping)), _now()),
        )
        connection.executemany(
            "INSERT INTO products (batch_id, row_number, name, brand, search_code, "
            "alternate_code, category, needs_confirmation, issues_json, original_values_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    draft_id,
                    product["row_number"],
                    product["name"],
                    product["brand"],
                    product["search_code"],
                    product["alternate_code"],
                    product["category"],
                    int(product["needs_confirmation"]),
                    _json(product["issues"]),
                    _json(product["original_values"]),
                )
                for product in products
            ],
        )
        connection.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))


def list_batches(path: Path) -> list[dict[str, Any]]:
    with _connection(path) as connection:
        rows = connection.execute(
            "SELECT batches.*, COUNT(products.id) AS product_count "
            "FROM batches LEFT JOIN products ON products.batch_id = batches.id "
            "GROUP BY batches.id ORDER BY batches.confirmed_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_batch(path: Path, batch_id: str) -> dict[str, Any] | None:
    with _connection(path) as connection:
        batch = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        if batch is None:
            return None
        rows = connection.execute(
            "SELECT * FROM products WHERE batch_id = ? ORDER BY row_number", (batch_id,)
        ).fetchall()
    result = dict(batch)
    result["mapping"] = json.loads(result.pop("mapping_json"))
    result["products"] = [dict(row) for row in rows]
    return result