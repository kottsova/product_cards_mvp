"""Versioned, additive SQLite migrations for the shared product pipeline."""

from __future__ import annotations

import sqlite3


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _migration_1(connection: sqlite3.Connection) -> None:
    if "identity_json" not in _columns(connection, "products"):
        connection.execute("ALTER TABLE products ADD COLUMN identity_json TEXT NOT NULL DEFAULT '{}'")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS fetch_attempts (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            requested_url TEXT NOT NULL DEFAULT '',
            final_url TEXT NOT NULL DEFAULT '',
            http_status INTEGER,
            duration_ms INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS fetch_attempts_by_product
            ON fetch_attempts(product_id, source_id, id);

        CREATE TABLE IF NOT EXISTS source_snapshots (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL,
            fetch_attempt_id INTEGER NOT NULL REFERENCES fetch_attempts(id) ON DELETE RESTRICT,
            source_url TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'text/html',
            content TEXT NOT NULL DEFAULT '',
            content_sha256 TEXT NOT NULL,
            extracted_json TEXT NOT NULL DEFAULT '{}',
            fetched_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS source_snapshots_latest
            ON source_snapshots(product_id, source_id, id DESC);

        CREATE TABLE IF NOT EXISTS identity_verifications (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL,
            source_snapshot_id INTEGER REFERENCES source_snapshots(id) ON DELETE SET NULL,
            level TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            evidence_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS identity_verifications_by_product
            ON identity_verifications(product_id, source_id, id);

        CREATE TABLE IF NOT EXISTS human_reviews (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            review_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            reason TEXT NOT NULL,
            provenance_json TEXT NOT NULL DEFAULT '{}',
            resolution_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS human_reviews_open
            ON human_reviews(product_id, status, id);
    """)


MIGRATIONS = ((_migration_1, "identity, fetch history, snapshots and review provenance"),)


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    for version, (migration, description) in enumerate(MIGRATIONS, start=1):
        if version in applied:
            continue
        migration(connection)
        connection.execute(
            "INSERT INTO schema_migrations(version, description) VALUES (?, ?)",
            (version, description),
        )


def _job_migration_1(connection: sqlite3.Connection) -> None:
    columns = _columns(connection, "resolved_attributes")
    if "full_sku_confirmed" not in columns:
        connection.execute("ALTER TABLE resolved_attributes ADD COLUMN full_sku_confirmed INTEGER NOT NULL DEFAULT 0")
    connection.execute("UPDATE source_pages SET source_key='lg_kz', site_name='LG Казахстан' WHERE source_key='lg' AND NOT EXISTS (SELECT 1 FROM source_pages newer WHERE newer.product_id=source_pages.product_id AND newer.source_key='lg_kz')")
    connection.execute("UPDATE extracted_attribute_facts SET source_page_id=(SELECT newer.id FROM source_pages old JOIN source_pages newer ON newer.product_id=old.product_id AND newer.source_key='lg_kz' WHERE old.id=extracted_attribute_facts.source_page_id) WHERE source_page_id IN (SELECT old.id FROM source_pages old WHERE old.source_key='lg' AND EXISTS (SELECT 1 FROM source_pages newer WHERE newer.product_id=old.product_id AND newer.source_key='lg_kz'))")
    connection.execute("DELETE FROM source_pages WHERE source_key='lg' AND EXISTS (SELECT 1 FROM source_pages newer WHERE newer.product_id=source_pages.product_id AND newer.source_key='lg_kz')")
    connection.execute("UPDATE extracted_attribute_facts SET source_key='lg_kz', site_name='LG Казахстан' WHERE source_key='lg'")


def _job_migration_2(connection: sqlite3.Connection) -> None:
    if "section" not in _columns(connection, "extracted_attribute_facts"):
        connection.execute("ALTER TABLE extracted_attribute_facts ADD COLUMN section TEXT NOT NULL DEFAULT ''")


def _job_migration_3(connection: sqlite3.Connection) -> None:
    if "value_cell" not in _columns(connection, "extracted_attribute_facts"):
        connection.execute("ALTER TABLE extracted_attribute_facts ADD COLUMN value_cell INTEGER")


JOB_MIGRATIONS = (
    (_job_migration_1, "LG source-key compatibility and resolution confirmation"),
    (_job_migration_2, "Preserve source specification section before canonical mapping"),
    (_job_migration_3, "Record whether an attribute came from a specification value cell"),
)


def apply_job_migrations(connection: sqlite3.Connection) -> None:
    """Apply migrations whose tables are created by the legacy jobs subsystem."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS job_schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    applied = {row[0] for row in connection.execute("SELECT version FROM job_schema_migrations")}
    for version, (migration, description) in enumerate(JOB_MIGRATIONS, start=1):
        if version in applied:
            continue
        migration(connection)
        connection.execute(
            "INSERT INTO job_schema_migrations(version, description) VALUES (?, ?)",
            (version, description),
        )
