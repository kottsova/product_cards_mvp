"""Stage 52 regressions for shared PDF persistence and LG support identity."""
from __future__ import annotations

import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from product_tool import jobs, worker
from product_tool.adapters.common import ProductDocument, SourceDocument
from product_tool.adapters.lg import _augment_with_browser_search
from product_tool.adapters.lg_browser_search import BrowserCandidate, BrowserSearchResult
from product_tool.adapters.lg_support import LGSupportAdapter
from product_tool.fetch_history import latest_source_snapshot


class DocumentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "pilot.sqlite3"
        jobs.initialize(self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("INSERT INTO batches VALUES ('b','pilot.xlsx','Sheet1','{}','now')")
            connection.execute(
                "INSERT INTO products (id,batch_id,row_number,name,brand,search_code,"
                "alternate_code,category,needs_confirmation,issues_json,original_values_json) "
                "VALUES (1,'b',2,'Vacuum','LG','VC5316NNTS.APSQCIS','','vacuum',0,'[]','{}')"
            )
            connection.commit()
        self.ru_url = "https://www.lg.com/ru/support/product/lg-VC5316NNTS"
        self.kz_url = "https://www.lg.com/kz/support/product-support/cs-VC5316NNTS.APSQCIS/"
        for key, url in (("lg_ru", self.ru_url), ("lg_ru_support", self.ru_url),
                         ("lg_kz_support", self.kz_url)):
            jobs.save_source_document(self.db, 1, SourceDocument(key, "LG", url,
                                       match_level="full_sku", html="<h1>VC5316NNTS.APSQCIS</h1>"))
        self.pdf = "https://gscs-b2c.lge.com/open/downloadFile?fileId=same"

    def document(self, source_url, title="Russian manual"):
        return ProductDocument(title, "???????", "", "", self.pdf, source_url,
                               "VC5316NNTS", "VC5316NNTS.APSQCIS", source_url, True)

    def test_shared_pdf_is_reused_across_sources_and_reruns(self):
        jobs.save_documents(self.db, 1, "lg_ru", [self.document(self.ru_url)])
        first = jobs.get_documents(self.db, 1)[0]
        jobs.save_documents(self.db, 1, "lg_ru", [self.document(self.ru_url, "Updated manual")])
        jobs.save_documents(self.db, 1, "lg_kz_support", [self.document(self.kz_url)])
        docs = jobs.get_documents(self.db, 1)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["id"], first["id"])
        self.assertEqual(docs[0]["title"], "Updated manual")
        self.assertEqual(docs[0]["source_key"], "lg_ru")
        self.assertEqual(len(jobs.get_source_pages(self.db, 1)), 3)

    def test_duplicate_pdf_within_one_payload_is_one_document(self):
        jobs.save_documents(self.db, 1, "lg_ru", [self.document(self.ru_url),
                                                   self.document(self.ru_url)])
        self.assertEqual(len(jobs.get_documents(self.db, 1)), 1)

    def test_missing_refresh_removes_only_own_document(self):
        jobs.save_documents(self.db, 1, "lg_ru", [self.document(self.ru_url)])
        jobs.save_documents(self.db, 1, "lg_ru", [])
        self.assertEqual(jobs.get_documents(self.db, 1), [])
        jobs.save_documents(self.db, 1, "lg_kz_support", [self.document(self.kz_url)])
        self.assertEqual(jobs.get_documents(self.db, 1)[0]["source_key"], "lg_kz_support")

    def test_weaker_support_lookup_keeps_exact_page_and_audits_candidate(self):
        exact = SourceDocument("lg_ru_support", "LG RU support", self.ru_url,
                               found_model="32LQ63006LA.ARUG", match_level="full_sku",
                               html='<div data-product-id="32LQ63006LA.ARUG"></div>')
        weaker = SourceDocument("lg_ru_support", "LG RU support", self.ru_url + ".ARU",
                                found_model="32LQ63006LA.ARU", match_level="base_model",
                                html='<div data-product-id="32LQ63006LA.ARU"></div>')
        worker._save_lg_support_relation(self.db, 1, exact)
        worker._save_lg_support_relation(self.db, 1, weaker)
        page = next(x for x in jobs.get_source_pages(self.db, 1)
                    if x["source_key"] == "lg_ru_support")
        self.assertEqual((page["url"], page["match_level"]), (self.ru_url, "full_sku"))
        candidate = latest_source_snapshot(self.db, 1, "lg_ru_support_candidate")
        self.assertEqual(candidate["source_url"], weaker.url)
        self.assertEqual(candidate["extracted"]["found_model"], "32LQ63006LA.ARU")


class FakeResponse:
    def __init__(self, url, code):
        self.url = url
        self.text = f'<div data-product-id="{code}"></div>'
        self.status_code = 200

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, url, timeout):
        return self.response


class FakeSearch:
    def __init__(self, url):
        self.url = url

    def search(self, region, queries):
        return BrowserSearchResult(region, queries[0], "candidates_found",
                                   (BrowserCandidate(self.url, "support"),))


class SearchIdentityTests(unittest.TestCase):
    def test_joined_catalog_code_accepts_dotted_code_printed_on_support_page(self):
        url = "https://www.lg.com/ru/support/product/lg-GX"
        adapter = type("Adapter", (), {})()
        adapter.browser_search = FakeSearch(url)
        adapter.http = FakeSession(FakeResponse(url, "GX.DCISLLK"))
        adapter.clock = lambda: 0.0
        adapter.support_candidate_urls = []
        adapter.support_candidate_pages = {}
        doc = SourceDocument("lg_ru", "LG", "", match_level="mismatch")
        result = _augment_with_browser_search(doc, adapter, "GXDCISLLK", "GXDCISLLK", 10.0,
                                              region="ru")
        self.assertEqual(adapter.support_candidate_urls, [url])
        self.assertEqual(result.match_level, "mismatch")

    def test_support_content_confirms_joined_code_without_product_evidence(self):
        url = "https://www.lg.com/ru/support/product/lg-GX"
        html = '<div data-product-id="GX.DCISLLK"></div>'
        adapter = LGSupportAdapter(http=FakeSession(FakeResponse(url, "GX.DCISLLK")),
                                   candidate_urls=(url,), candidate_pages={url: html},
                                   clock=lambda: 0.0)
        page = adapter.find_source("GXDCISLLK", deadline=10.0)
        self.assertEqual((page.match_level, page.found_model),
                         ("full_sku", "GXDCISLLK"))
        self.assertEqual(page.attributes, [])
        self.assertEqual(page.photos, [])

    def test_different_commercial_suffix_is_still_rejected(self):
        url = "https://www.lg.com/ru/support/product/lg-A9K-MAX1"
        adapter = type("Adapter", (), {})()
        adapter.browser_search = FakeSearch(url)
        adapter.http = FakeSession(FakeResponse(url, "A9K-MAX1.ABBQCIS"))
        adapter.clock = lambda: 0.0
        adapter.support_candidate_urls = []
        adapter.support_candidate_pages = {}
        _augment_with_browser_search(SourceDocument("lg_ru", "LG", ""), adapter,
                                     "A9K_MAX1", "A9K_MAX1", 10.0, region="ru")
        self.assertEqual(adapter.support_candidate_urls, [])


if __name__ == "__main__":
    unittest.main()
