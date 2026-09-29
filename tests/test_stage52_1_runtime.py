"""Stage 52.1: legacy stop audit and user-facing synthetic refusal."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from product_tool.adapters import access_stop, policy_fetch
from product_tool.adapters.policy_session import PolicyResponse, STOPPED
from product_tool.web import create_app


class LegacyRuntimeTests(unittest.TestCase):
    def test_legacy_challenge_migrates_once_and_expires_without_losing_history(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "lg_fetch_log.json"
            old = {"url": "https://www.lg.com/kz/example", "status_code": 200,
                   "protection_status": "challenge_confirmed",
                   "checked_at": "2026-09-26T10:00:00+00:00"}
            path.write_text(json.dumps([old]), encoding="utf-8")
            now = datetime(2026, 9, 30, tzinfo=timezone.utc)
            self.assertEqual(policy_fetch.migrate_legacy_stop_log(path, now=now), 1)
            first = policy_fetch.read_log(path)
            self.assertEqual(first[0], old)
            self.assertEqual(first[1]["event"], "legacy_stop_migrated")
            self.assertEqual(first[1]["reason"], "challenge")
            self.assertEqual(first[1]["scope"], "domain")
            self.assertEqual(first[1]["expires_at"], "2026-09-26T10:30:00+00:00")
            self.assertFalse(first[1]["active_at_migration"])
            self.assertNotIn("www.lg.com", access_stop.stopped_hosts(first, now=now))
            self.assertIn("www.lg.com", access_stop.stopped_hosts(first, now=datetime(2026, 9, 26, 10, 1, tzinfo=timezone.utc)))
            original_bytes = path.read_bytes()
            self.assertEqual(policy_fetch.migrate_legacy_stop_log(path, now=now), 0)
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_manual_fatal_remain_active_and_rate_limit_expires(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fetch_log.json"
            old_rate = {"url": "https://rate.example/x", "status_code": 429,
                        "checked_at": "2026-09-26T10:00:00+00:00"}
            entries = [old_rate, access_stop.stop_event("manual.example", "manual"),
                       access_stop.stop_event("fatal.example", "fatal")]
            path.write_text(json.dumps(entries), encoding="utf-8")
            self.assertEqual(policy_fetch.migrate_legacy_stop_log(path), 1)
            active = access_stop.active_stops(policy_fetch.read_log(path))
            self.assertNotIn("rate.example", active)
            self.assertIn("manual.example", active)
            self.assertIn("fatal.example", active)

    def test_production_directory_startup_migration_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "lg_fetch_log.json"
            log.write_text(json.dumps([{"url": "https://www.lg.com/kz/example",
                                        "status_code": 200, "protection_status": "challenge_confirmed",
                                        "checked_at": "2026-09-26T10:00:00+00:00"}]), encoding="utf-8")
            create_app(root, start_worker=False)
            database = root / "batches.sqlite3"
            with closing(sqlite3.connect(database)) as connection:
                migrations_before = connection.execute("select count(*) from job_schema_migrations").fetchone()[0]
                integrity = connection.execute("pragma integrity_check").fetchone()[0]
            log_before = log.read_bytes()
            create_app(root, start_worker=False)
            with closing(sqlite3.connect(database)) as connection:
                migrations_after = connection.execute("select count(*) from job_schema_migrations").fetchone()[0]
            self.assertEqual(integrity, "ok")
            self.assertEqual(migrations_after, migrations_before)
            self.assertEqual(log.read_bytes(), log_before)
            self.assertEqual(len(policy_fetch.read_log(log)), 2)

    def test_ui_distinguishes_internal_stop_from_actual_http_403(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(root, start_worker=False)
            db = root / "batches.sqlite3"
            with closing(sqlite3.connect(db)) as connection:
                connection.execute("insert into batches(id,filename,sheet_name,mapping_json,confirmed_at) values(?,?,?,?,?)",
                                   ("batch", "sample.xlsx", "Sheet1", "{}", "2026-09-30T00:00:00+00:00"))
                connection.execute("insert into products(id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) values(?,?,?,?,?,?,?,?,?,?,?)",
                                   (1, "batch", 2, "Sample", "LG", "SAMPLE", "", "Audio", 0, "[]", "{}"))
                for key, error in (("lg_kz", "HTTP-ошибка: HTTP 403 [policy_host_stopped]"),
                                   ("lg_ru", "HTTP-ошибка: HTTP 403")):
                    connection.execute("insert into source_pages(product_id,source_key,site_name,url,found_model,match_level,evidence,fetched_at,error,description,photos_json) values(?,?,?,?,?,?,?,?,?,?,?)",
                                       (1, key, key, "", "", "unknown", "", "2026-09-30T00:00:00+00:00", error, "", "[]"))
                connection.execute("insert into search_jobs(id,product_id,stages_json,status,current_stage,message,created_at,updated_at) values(?,?,?,?,?,?,?,?)",
                                   ("old-job", 1, "[1]", "needs_review", 1, "", "2026-09-30T00:00:00+00:00", "2026-09-30T00:00:00+00:00"))
                connection.execute("insert into job_events(job_id,stage,level,message,source_url,created_at) values(?,?,?,?,?,?)",
                                   ("old-job", 1, "warning", "LG KZ: HTTP 403 [policy_host_stopped]", "", "2026-09-30T00:00:00+00:00"))
                connection.commit()
            with TestClient(app) as client:
                page = client.get("/products/1")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Внутренний access-stop: запрос к этой странице не отправлялся.", page.text)
            self.assertIn("HTTP-ошибка: HTTP 403", page.text)
            self.assertNotIn("policy_host_stopped", page.text)
            self.assertIn("LG KZ: ", page.text)
            self.assertEqual(PolicyResponse("https://example.test", 403).status_code, 403)
            with self.assertRaisesRegex(Exception, "HTTP 403"):
                PolicyResponse("https://example.test", 403).raise_for_status()
            with self.assertRaisesRegex(Exception, "policy_host_stopped"):
                PolicyResponse("https://example.test", 403, marker=STOPPED).raise_for_status()
