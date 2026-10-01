"""Runtime SQLite changes after user uploads; validate structure and consistency."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import unittest

from product_tool.migrations import JOB_MIGRATIONS, MIGRATIONS


class LiveDBInvariantTests(unittest.TestCase):
    def test_live_database_integrity_and_schema_migrations(self):
        database = Path(__file__).resolve().parents[1] / "data" / "batches.sqlite3"
        if not database.exists():
            self.skipTest("live SQLite is local runtime state and is not tracked in Git")
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual([row[0] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version")],
                list(range(1, len(MIGRATIONS) + 1)))
            self.assertEqual([row[0] for row in connection.execute(
                "SELECT version FROM job_schema_migrations ORDER BY version")],
                list(range(1, len(JOB_MIGRATIONS) + 1)))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
