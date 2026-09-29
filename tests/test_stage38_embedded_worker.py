"""The ordinary website must start processing without a second terminal."""

from pathlib import Path
import os
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from product_tool import lg_batch, worker
from product_tool.web import create_app


class EmbeddedWorkerTests(unittest.TestCase):
    def test_uploaded_categories_are_selected_without_pilot_list(self):
        rows = [
            {"id": number, "brand": "LG", "category": f"Своя категория {number}", "search_code": f"MODEL-{number}"}
            for number in range(1, 13)
        ]
        rows.append({"id": 13, "brand": "LG", "category": "Своя категория 1", "search_code": "ANOTHER"})
        rows.append({"id": 14, "brand": "Samsung", "category": "Своя категория 14", "search_code": "OTHER"})
        self.assertEqual(lg_batch.default_ids(rows), set(range(1, 13)))

    def test_site_starts_queue_processor(self):
        with TemporaryDirectory() as directory:
            called = Event()

            def fake_run_once(_database):
                called.set()
                return False

            with patch.object(worker, "run_once", side_effect=fake_run_once):
                with TestClient(create_app(Path(directory), start_worker=True)):
                    self.assertTrue(called.wait(3), "The website did not start its worker")

    def test_ordinary_one_command_app_starts_worker_by_default(self):
        with TemporaryDirectory() as directory:
            called = Event()

            def fake_run_once(_database):
                called.set()
                return False

            with patch.dict(os.environ, {"PRODUCT_CARDS_DATA_DIR": directory}):
                with patch.object(worker, "run_once", side_effect=fake_run_once):
                    with TestClient(create_app()):
                        self.assertTrue(called.wait(3))

    def test_existing_worker_lock_prevents_duplicate_processing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            called = Event()
            with patch.object(worker, "run_once", side_effect=lambda _database: called.set() or False):
                with worker.single_worker(root):
                    with TestClient(create_app(root, start_worker=True)):
                        self.assertFalse(called.wait(0.2), "A second worker took the same queue")
                with TestClient(create_app(root, start_worker=True)):
                    self.assertTrue(called.wait(3), "Queue did not resume after lock release")


if __name__ == "__main__":
    unittest.main()
