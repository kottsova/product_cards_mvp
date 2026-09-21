"""Persistent queue plus multi-source evidence and attribute resolution."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from . import storage
from .adapters.common import PhotoCandidate, ProductDocument, SourceDocument
from .display import display_name_ru, display_source, display_status, display_value
from .normalization import normalize_facts
from .resolution import resolve_attributes


ACTIVE = ("queued", "running")
STAGE_NAMES = {1: "Источники и модель", 2: "Описание", 3: "Характеристики", 4: "Фотографии", 6: "Инструкции"}


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

            CREATE TABLE IF NOT EXISTS product_documents (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                source_page_id INTEGER REFERENCES source_pages(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                title TEXT NOT NULL,
                language TEXT NOT NULL,
                document_date TEXT NOT NULL DEFAULT '',
                size TEXT NOT NULL DEFAULT '',
                direct_url TEXT NOT NULL,
                source_url TEXT NOT NULL,
                product_model TEXT NOT NULL,
                support_model TEXT NOT NULL,
                relation_url TEXT NOT NULL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                fetched_at TEXT NOT NULL,
                UNIQUE(product_id, direct_url)
            );
            CREATE TABLE IF NOT EXISTS photo_candidates (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                source_page_id INTEGER NOT NULL REFERENCES source_pages(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                url TEXT NOT NULL,
                asset_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                selected INTEGER NOT NULL DEFAULT 0,
                excluded_reason TEXT NOT NULL DEFAULT '',
                fetched_at TEXT NOT NULL,
                UNIQUE(product_id, source_key, asset_key)
            );        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(resolved_attributes)")}
        if "full_sku_confirmed" not in columns:
            connection.execute("ALTER TABLE resolved_attributes ADD COLUMN full_sku_confirmed INTEGER NOT NULL DEFAULT 0")
        connection.execute("UPDATE source_pages SET source_key='lg_kz', site_name='LG Казахстан' WHERE source_key='lg' AND NOT EXISTS (SELECT 1 FROM source_pages newer WHERE newer.product_id=source_pages.product_id AND newer.source_key='lg_kz')")
        connection.execute("UPDATE extracted_attribute_facts SET source_page_id=(SELECT newer.id FROM source_pages old JOIN source_pages newer ON newer.product_id=old.product_id AND newer.source_key='lg_kz' WHERE old.id=extracted_attribute_facts.source_page_id) WHERE source_page_id IN (SELECT old.id FROM source_pages old WHERE old.source_key='lg' AND EXISTS (SELECT 1 FROM source_pages newer WHERE newer.product_id=old.product_id AND newer.source_key='lg_kz'))")
        connection.execute("DELETE FROM source_pages WHERE source_key='lg' AND EXISTS (SELECT 1 FROM source_pages newer WHERE newer.product_id=source_pages.product_id AND newer.source_key='lg_kz')")
        connection.execute("UPDATE extracted_attribute_facts SET source_key='lg_kz', site_name='LG Казахстан' WHERE source_key='lg'")

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
    if update_photos:
        save_photo_candidates(path, product_id, document.source_key, document.photo_candidates or [PhotoCandidate(url, url, "product_gallery") for url in document.photos])


def get_source_pages(path: Path, product_id: int) -> list[dict[str, Any]]:
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT * FROM source_pages WHERE product_id=? "
            "ORDER BY CASE source_key WHEN 'lg_kz' THEN 1 WHEN 'lg_ru' THEN 2 WHEN 'sulpak' THEN 3 WHEN 'mechta' THEN 4 ELSE 5 END",
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
            "selected_source, conflict, full_sku_confirmed, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    product_id, item.normalized_name, item.selected_value, item.selected_unit,
                    item.status, item.reason, item.selected_source, int(item.conflict),
                    int(item.full_sku_confirmed), now,
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
        row = grouped.setdefault(fact["normalized_name"], {"normalized_name": fact["normalized_name"], "sources": {}, "raw_names": []})
        row["sources"].setdefault(fact["source_key"], fact)
        row["raw_names"].append(fact["raw_name"])
    for name in sorted(set(grouped) | set(resolved)):
        row = grouped.setdefault(name, {"normalized_name": name, "sources": {}, "raw_names": []})
        row["display_name"] = display_name_ru(name, row["raw_names"])
        for fact in row["sources"].values():
            fact["display_value"] = display_value(fact["normalized_value"], fact["unit"])
            fact["display_source"] = display_source(fact["source_key"], fact["site_name"])
        item = resolved.get(name)
        if item:
            item["display_value"] = display_value(item["selected_value"], item["selected_unit"]) if item["selected_value"] else ""
            item["display_status"] = display_status(item["status"])
            item["display_source"] = display_source(item["selected_source"])
        row["resolved"] = item
    return [grouped[name] for name in sorted(grouped, key=lambda x: grouped[x]["display_name"])]


def result_counts(path: Path, product_id: int) -> dict[str, int]:
    rows=get_resolved(path,product_id)
    return {
        "conflicts": sum(bool(x["conflict"]) for x in rows),
        "official_base_only": sum(x["status"]=="official_base_only" for x in rows),
        "supplier_confirmed": sum(bool(x.get("full_sku_confirmed")) and x["status"]!="manual" for x in rows),
    }
def identification_status(source_pages: list[dict[str, Any]]) -> str:
    by_key = {page["source_key"]: page for page in source_pages}
    official = [by_key.get(key, {}) for key in ("lg_kz", "lg_ru", "lg")]
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
    if any(page.get("match_level") == "full_sku" for page in official):
        return "Полный артикул найден на LG"
    if any(page.get("match_level") == "base_model" for page in official):
        return "Найдена только базовая модель, требуется подтверждение артикула"
    return "Источники не найдены за отведённое время"


def get_result(path: Path, product_id: int) -> dict[str, Any]:
    """Compatibility view for existing templates/tests."""
    sources = get_source_pages(path, product_id)
    lg = next((page for page in sources if page["source_key"] in {"lg_kz", "lg_ru", "lg"}), None)
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

def save_photo_candidates(path: Path, product_id: int, source_key: str, candidates: list[PhotoCandidate]) -> None:
    now=storage._now()
    with storage._connection(path) as connection:
        page=connection.execute("SELECT id FROM source_pages WHERE product_id=? AND source_key=?",(product_id,source_key)).fetchone()
        if not page: return
        previous={row["asset_key"]:row["selected"] for row in connection.execute("SELECT asset_key,selected FROM photo_candidates WHERE product_id=? AND source_key=?",(product_id,source_key))}
        connection.execute("DELETE FROM photo_candidates WHERE product_id=? AND source_key=?",(product_id,source_key))
        for item in candidates:
            selected=previous.get(item.asset_key, int(source_key in {"lg_kz","lg_ru"} and item.kind=="product_gallery" and not item.excluded_reason))
            connection.execute("INSERT INTO photo_candidates (product_id,source_page_id,source_key,url,asset_key,kind,width,height,selected,excluded_reason,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(product_id,page["id"],source_key,item.url,item.asset_key,item.kind,item.width,item.height,selected,item.excluded_reason,now))


def get_photo_candidates(path: Path, product_id: int, *, include_excluded: bool=True) -> list[dict[str,Any]]:
    query="SELECT pc.*,sp.site_name FROM photo_candidates pc JOIN source_pages sp ON sp.id=pc.source_page_id WHERE pc.product_id=?"
    if not include_excluded: query += " AND pc.kind!='excluded'"
    query += " ORDER BY pc.source_key, pc.kind, pc.id"
    with storage._connection(path) as connection: rows=connection.execute(query,(product_id,)).fetchall()
    return [dict(x) for x in rows]


def set_photo_selection(path: Path, product_id: int, asset_keys: list[str], *, mode: str="exact", source_key: str="") -> None:
    with storage._connection(path) as connection:
        if mode=="none": connection.execute("UPDATE photo_candidates SET selected=0 WHERE product_id=?",(product_id,))
        elif mode=="official": connection.execute("UPDATE photo_candidates SET selected=CASE WHEN source_key IN ('lg_kz','lg_ru') AND kind='product_gallery' THEN 1 ELSE 0 END WHERE product_id=?",(product_id,))
        elif mode=="source": connection.execute("UPDATE photo_candidates SET selected=1 WHERE product_id=? AND source_key=? AND kind='product_gallery'",(product_id,source_key))
        else:
            connection.execute("UPDATE photo_candidates SET selected=0 WHERE product_id=?",(product_id,))
            connection.executemany("UPDATE photo_candidates SET selected=1 WHERE product_id=? AND asset_key=?",[(product_id,key) for key in asset_keys])


def save_documents(path: Path, product_id: int, source_key: str, documents: list[ProductDocument]) -> None:
    now=storage._now()
    with storage._connection(path) as connection:
        page=connection.execute("SELECT id FROM source_pages WHERE product_id=? AND source_key=?",(product_id,source_key)).fetchone()
        connection.execute("DELETE FROM product_documents WHERE product_id=? AND source_key=?",(product_id,source_key))
        if page:
            connection.executemany("INSERT INTO product_documents (product_id,source_page_id,source_key,title,language,document_date,size,direct_url,source_url,product_model,support_model,relation_url,is_primary,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[(product_id,page["id"],source_key,d.title,d.language,d.document_date,d.size,d.direct_url,d.source_url,d.product_model,d.support_model,d.relation_url,int(d.primary),now) for d in documents])


def get_documents(path: Path, product_id: int) -> list[dict[str,Any]]:
    with storage._connection(path) as connection: rows=connection.execute("SELECT * FROM product_documents WHERE product_id=? ORDER BY is_primary DESC, document_date DESC,id",(product_id,)).fetchall()
    return [dict(x) for x in rows]
