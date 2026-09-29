from __future__ import annotations

import gc
import gzip
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from product_tool.adapters.lg import lg_article_components, lg_base_model
from product_tool.adapters.lg_support import (
    LGSupportAdapter, is_official_support_url, printed_support_codes,
)

ARTICLE = "P12ED.NSAR + P12ED.USAR"
URL = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"


class Response:
    status_code = 200

    def __init__(self, html: str, url: str = URL):
        self.text, self.url = html, url
        self.content = html.encode()

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, html: str):
        self.html, self.calls = html, []

    def get(self, url, **_):
        self.calls.append(url)
        return Response(self.html)


class Stage44SupportTest(unittest.TestCase):
    def test_kit_query_variants_do_not_split_single_article(self):
        for value in (ARTICLE, "P12ED.NSAR/P12ED.USAR", "P12ED.NSAR P12ED.USAR", "P12ED.NSAR & P12ED.USAR"):
            self.assertEqual(lg_article_components(value), ("P12ED.NSAR", "P12ED.USAR"))
            self.assertEqual(lg_base_model(value), "P12ED")
        self.assertEqual(lg_article_components("MODEL/ONE"), ("MODEL/ONE",))

    def test_official_regional_route_and_false_positive_host(self):
        self.assertTrue(is_official_support_url(URL))
        self.assertTrue(is_official_support_url("https://www.lg.com/ru/support/product/lg-P12ED"))
        self.assertFalse(is_official_support_url("https://www.lg.com.evil.test/kz/support/product-support/cs-P12ED.USAR/"))

    def test_saved_official_shell_is_candidate_not_verified_kit(self):
        saved = next(Path("reports/lg_live_batch_2026-09-28_stage44/official_support").glob("001_*.gz"))
        with gzip.open(saved, "rt", encoding="utf-8") as stream:
            html = stream.read()
        self.assertEqual(printed_support_codes(html), ())
        session = Session(html)
        doc = LGSupportAdapter(http=session, candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10)
        self.assertEqual(session.calls, [URL])
        self.assertEqual((doc.url, doc.match_level, doc.found_model), (URL, "support_candidate", ""))
        self.assertFalse(doc.attributes or doc.photos)

    def test_one_component_is_not_entire_kit(self):
        html = '<div data-product-id="P12ED.USAR"></div><a href="/file.pdf">Russian manual</a>'
        doc = LGSupportAdapter(http=Session(html), candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10)
        self.assertEqual((doc.match_level, doc.found_model), ("component_only", "P12ED.USAR"))
        self.assertFalse(doc.attributes or doc.photos)

    def test_both_printed_codes_confirm_kit_and_title_does_not(self):
        html = '<title>P12ED.NSAR + P12ED.USAR</title><div data-product-id="P12ED.USAR"></div>'
        self.assertEqual(LGSupportAdapter(http=Session(html), candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10).match_level, "component_only")
        html += '<div data-cs-sales-code="P12ED.NSAR"></div>'
        doc = LGSupportAdapter(http=Session(html), candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10)
        self.assertEqual((doc.match_level, doc.found_model), ("full_sku", "P12ED.NSAR+P12ED.USAR"))

    def test_registration_link_can_confirm_second_component(self):
        html = ('<div data-product-id="P12ED.USAR"></div>'
                '<a href="/kz/support/product-support/product-registration/?csSalesCode=P12ED.NSAR">Register</a>')
        doc = LGSupportAdapter(http=Session(html), candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10)
        self.assertEqual(doc.match_level, "full_sku")
        self.assertIn("P12ED.NSAR", doc.evidence)
        other = html.replace("P12ED.NSAR", "P12EP.NSAR")
        self.assertEqual(LGSupportAdapter(http=Session(other), candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10).match_level, "component_only")

    def test_base_named_russian_pdf_is_accepted_only_with_full_official_kit_tie(self):
        from tests.test_stage23_owner_rules import RUSSIAN_NO_MODEL
        class PdfResponse:
            status_code = 200
            url = "https://gscs-b2c.lge.com/open/downloadFile?fileId=abc"
            text = "%PDF-fake"
            def raise_for_status(self):
                pass
        class PdfSession:
            def __init__(self):
                self.calls = 0
            def get(self, url, **_):
                self.calls += 1
                return PdfResponse()
        html = ('<div data-product-id="P12ED.USAR"></div>'
                '<li>Owner\u0027s Manual Russian P12ED'
                '<a href="https://gscs-b2c.lge.com/open/downloadFile?fileId=abc">Russian</a></li>')
        pdf = PdfSession()
        adapter = LGSupportAdapter(http=Session(html), candidate_urls=(URL,), documents_http=pdf)
        partial = adapter.find_source(ARTICLE, deadline=10**10)
        documents, report = adapter.find_documents(partial, ARTICLE, deadline=10**10)
        self.assertEqual((documents, report["outcome"], pdf.calls), ([], "kit_identity_unconfirmed", 0))
        full_html = html + '<a href="/kz/support/product-support/product-registration/?csSalesCode=P12ED.NSAR">Register</a>'
        adapter = LGSupportAdapter(http=Session(full_html), candidate_urls=(URL,), documents_http=pdf)
        full = adapter.find_source(ARTICLE, deadline=10**10)
        with patch("product_tool.adapters.lg_support._pdf_pages", return_value=[RUSSIAN_NO_MODEL + " P12ED"]):
            documents, report = adapter.find_documents(full, ARTICLE, deadline=10**10)
        self.assertEqual((len(documents), pdf.calls, report["outcome"]), (1, 1, "verified_russian_instruction"))
        self.assertEqual((documents[0].product_model, documents[0].source_url), ("P12ED", URL))
        self.assertEqual(report["files"][0]["assessment"]["model_references"], ["P12ED"])

    def test_repeated_save_updates_existing_product_without_duplicate(self):
        from product_tool import jobs
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "batch.sqlite3"
            jobs.initialize(db)
            with sqlite3.connect(db) as connection:
                connection.execute("INSERT INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('b','test.xlsx','Sheet1','{}','now')")
                connection.execute("INSERT INTO products(id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (4,'b',2,'kit','LG',?,'','split system',0,'[]','{}')", (ARTICLE,))
            connection.close()
            doc = LGSupportAdapter(http=Session('<div data-product-id="P12ED.USAR"></div>')).find_source(ARTICLE, deadline=10**10)
            jobs.save_source_document(db, 4, doc)
            jobs.save_source_document(db, 4, doc)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM products").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT count(*) FROM source_pages WHERE product_id=4 AND source_key='lg_kz_support'").fetchone()[0], 1)
            connection.close()
            gc.collect()

    def test_similar_model_not_accepted(self):
        html = '<div data-product-id="P12EP.USAR"></div>'
        doc = LGSupportAdapter(http=Session(html), candidate_urls=(URL,)).find_source(ARTICLE, deadline=10**10)
        self.assertEqual(doc.match_level, "support_candidate")


if __name__ == "__main__":
    unittest.main()
