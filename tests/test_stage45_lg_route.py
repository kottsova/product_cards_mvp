from __future__ import annotations

import gc
import gzip
import sqlite3
import tempfile
import unittest
from pathlib import Path

from product_tool import jobs, worker
from product_tool.adapters.common import SourceDocument
from product_tool.adapters.lg_support import LGSupportAdapter

ARTICLE = "P12ED.NSAR + P12ED.USAR"
URL = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"
SAVED = next(Path("reports/lg_live_batch_2026-09-28_stage44/official_support").glob("001_*.gz"))


class ReplayResponse:
    status_code = 200
    url = URL

    def __init__(self, html):
        self.text = html

    def raise_for_status(self):
        pass


class ReplayHttp:
    def __init__(self, html):
        self.html, self.calls = html, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url != URL:
            raise AssertionError(f"unrecorded URL: {url}")
        return ReplayResponse(self.html)


class EmptyOfficial:
    def __init__(self, key):
        self.source_key = self.site_name = key

    def find_source(self, *args, **kwargs):
        return SourceDocument(self.source_key, self.site_name, "", match_level="mismatch")


class EmptyDealer:
    source_key = site_name = "sulpak"

    def find_source(self, *args, **kwargs):
        return SourceDocument(self.source_key, self.site_name, "", match_level="unknown")


class EmptyDns:
    source_key = site_name = "dns"
    document_urls = {}

    def find_source(self, *args, **kwargs):
        return SourceDocument(self.source_key, self.site_name, "", match_level="dealer_url_needed")


class ExistingLGSupportRouteTests(unittest.TestCase):
    def test_saved_candidate_is_reused_without_hardcoded_article_url(self):
        with gzip.open(SAVED, "rt", encoding="utf-8") as stream:
            html = stream.read()
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "batches.sqlite3"
            jobs.initialize(db)
            with sqlite3.connect(db) as connection:
                connection.execute("INSERT INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('b','test.xlsx','Sheet1','{}','now')")
                connection.execute("INSERT INTO products(id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (4,'b',2,'kit','LG',?,'','split system',0,'[]','{}')", (ARTICLE,))
            connection.close()
            jobs.save_source_document(db, 4, SourceDocument("lg_kz_support", "LG KZ support", URL,
                                      match_level="support_candidate", html=html))
            replay = ReplayHttp(html)
            job_id = jobs.enqueue(db, 4, [1])
            self.assertTrue(worker.run_once(db,
                adapter_factory=lambda: (EmptyOfficial("lg_kz"), EmptyOfficial("lg_ru"), EmptyDealer()),
                dns_adapter_factory=EmptyDns,
                lg_support_adapter_factory=lambda: LGSupportAdapter(http=replay)))
            with sqlite3.connect(db) as connection:
                status = connection.execute("SELECT status FROM search_jobs WHERE id=?", (job_id,)).fetchone()[0]
                count = connection.execute("SELECT count(*) FROM products").fetchone()[0]
            connection.close()
            support = next(row for row in jobs.get_source_pages(db, 4) if row["source_key"] == "lg_kz_support")
            self.assertEqual(replay.calls, [])
            self.assertEqual((status, count, support["match_level"]), ("needs_review", 1, "support_candidate"))
            self.assertFalse(support["photos"])
            self.assertFalse(jobs.get_documents(db, 4))
            gc.collect()  # jobs uses SQLite connection context managers; release Windows file handles.

    def test_browser_response_is_reused_without_second_fetch(self):
        html = '<div data-product-id="S3WER.ALWPCOM"></div>'
        candidate_url = "https://www.lg.com/kz/support/product-support/cs-S3WER.ALWPCOM/"
        replay = ReplayHttp(html)
        doc = LGSupportAdapter(http=replay,
            candidate_urls=(candidate_url,), candidate_pages={candidate_url: html}).find_source("S3WER.ALWPCOM", deadline=10**10)
        self.assertEqual(doc.match_level, "full_sku")
        self.assertEqual(replay.calls, [])


if __name__ == "__main__":
    unittest.main()
