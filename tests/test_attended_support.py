import gc
import gzip
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import time

from product_tool import jobs, worker
from product_tool.adapters.common import SourceDocument
from product_tool.fetch_history import record_fetch_attempt, save_source_snapshot
from product_tool.adapters.lg_support import LGSupportAdapter, support_payload_codes
from product_tool.census.attended_support import (
    AttendedBudget, capture, looks_like_challenge, official_support_url,
    resource_allowed, response_relevant,
)


URL = "https://www.lg.com/kz/support/product-support/cs-DEMO.USAR/"


class UrlAndChallengeTests(unittest.TestCase):
    def test_only_observed_shape_and_official_resources(self):
        self.assertTrue(official_support_url(URL))
        self.assertFalse(official_support_url("https://other.test/kz/support/product-support/cs-DEMO.USAR/"))
        self.assertFalse(official_support_url(URL + "?test=1"))
        self.assertTrue(resource_allowed("https://gscs-b2c.lge.com/file.pdf"))
        self.assertFalse(resource_allowed("https://fake-lg.com/file.pdf"))

    def test_relevant_action_and_proxy(self):
        self.assertTrue(response_relevant(URL, "POST", True))
        self.assertTrue(response_relevant("https://www.lg.com/ncms/api/v1/support/proxy/productSupportPage", "GET", False))
        self.assertFalse(response_relevant("https://www.lg.com/kz/search", "GET", False))

    def test_challenge_ignores_script_word_and_clears_after_manual_navigation(self):
        self.assertTrue(looks_like_challenge(URL, "<body>Verify you are human</body>", 200))
        self.assertFalse(looks_like_challenge(URL, "<script>captcha</script><div class=support-product-area>DEMO</div>", 403))


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.stage = 0
        self.handlers = {}
        self.goto_calls = []

    def on(self, name, callback):
        self.handlers[name] = callback

    def goto(self, url, **_):
        self.goto_calls.append(url)
        self.url = url

    def content(self):
        if not self.stage:
            return "<html><body>Verify you are human</body></html>"
        return '<html><div class="support-product-area"><span class="model">DEMO.USAR</span><a href="/kz/support/product-support/product-registration/?csSalesCode=DEMO.USAR">Register</a><li><a id="download-manual-label-manualList-2" href="https://gscs-b2c.lge.com/open/downloadFile?fileId=abc">Russian</a></li></div></html>'


class FakeContext:
    def __init__(self):
        self.page = FakePage()
        self.pages = [self.page]
        self.routes = []
        self.handlers = {}
        self.closed = False

    def route(self, path, callback):
        self.routes.append((path, callback))

    def on(self, name, callback):
        self.handlers[name] = callback

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self):
        self.context = FakeContext()
        self.options = {}

    def launch_persistent_context(self, profile, **options):
        self.options = {"profile": profile, **options}
        return self.context


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class CaptureTests(unittest.TestCase):
    def test_manual_change_resumes_same_session_without_second_navigation(self):
        fake = FakePlaywright()
        messages = []
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)

            def pause(_):
                fake.chromium.context.page.stage = 1

            result = capture(URL, root / "capture", root / "profile",
                             budget=AttendedBudget(max_wait_seconds=10),
                             playwright_factory=lambda: fake, clock=lambda: 0,
                             pause=pause, announce=messages.append)
            self.assertEqual(result["outcome"], "captured")
            self.assertTrue(result["challenge_seen"])
            self.assertEqual(fake.chromium.context.page.goto_calls, [URL])
            self.assertEqual(fake.chromium.options["channel"], "chrome")
            self.assertFalse(fake.chromium.options["headless"])
            self.assertNotIn("args", fake.chromium.options)
            self.assertIn("Complete it yourself", " ".join(messages))
            with gzip.open(root / "capture" / "rendered_dom.html.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("DEMO.USAR", handle.read())
            self.assertEqual(json.loads((root / "capture" / "manifest.json").read_text())["outcome"], "captured")
            self.assertTrue(fake.chromium.context.closed)


class AdapterReplayTests(unittest.TestCase):
    def test_api_and_rendered_dom_link_manual_without_product_specs(self):
        article = "DEMO.NSAR + DEMO.USAR"
        file_url = "https://gscs-b2c.lge.com/open/downloadFile?fileId=abc123"
        html = ('<a href="/kz/support/product-support/product-registration/form?csSalesCode=DEMO.NSAR">Register</a>'
                '<li><a id="download-manual-label-manualList-2" href="' + file_url + '">Russian</a></li>')
        payload = {"productSupportPage": {"csSalesCode": "DEMO.NSAR", "manualSoftwareList": {
            "localeCode": "KZ", "csSalesCode": "DEMO.USAR", "modelData": {"csSalesCode": "DEMO.NSAR"},
            "manualList": {"manualList": [{"fileNamePrint": "Russian", "fileName": "abc123",
                                            "originalFileName": "Owners_Manual_RU.pdf", "fileUrl": "N/A"}]}}}}
        class Response:
            status_code = 200
            truncated = False
            url = file_url
            text = "%PDF-test"
            def raise_for_status(self): pass
        class PdfReplay:
            def get(self, url, **_):
                if url != file_url: raise AssertionError("unexpected URL")
                return Response()
        adapter = LGSupportAdapter(candidate_urls=(URL,), candidate_pages={URL: html},
                                   candidate_payloads={URL: payload}, documents_http=PdfReplay())
        self.assertEqual(support_payload_codes(payload), ("DEMO.NSAR", "DEMO.USAR"))
        support = adapter.find_source(article, deadline=time.monotonic() + 10)
        self.assertEqual(support.match_level, "full_sku")
        self.assertEqual(support.attributes, [])
        self.assertEqual(support.photos, [])
        assessment = {"accepted": False, "kind": "instruction_model_not_named",
                      "names_model": [], "model_masks": [], "conflicting_models": [],
                      "languages": {"russian_instruction": True}}
        with patch("product_tool.adapters.lg_support._pdf_pages", return_value=["Russian guide"]), \
             patch("product_tool.adapters.lg_support.assess_document", return_value=assessment):
            documents, report = adapter.find_documents(support, article, deadline=time.monotonic() + 10)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].title, "Owners_Manual_RU.pdf")
        self.assertEqual(documents[0].direct_url, file_url)
        self.assertEqual(report["files"][0]["evidence_relation"], "official_support_page")
        self.assertEqual(report["files"][0]["assessment"]["model_references"], [])


    def test_worker_reuses_saved_dom_and_api_without_network_or_done(self):
        html = ('<a href="/kz/support/product-support/product-registration/form?csSalesCode=DEMO.NSAR">Register</a>'
                '<li><a id="download-manual-label-manualList-2" href="https://gscs-b2c.lge.com/open/downloadFile?fileId=abc">Russian</a></li>')
        payload = {"productSupportPage": {"csSalesCode": "DEMO.NSAR", "manualSoftwareList": {
            "localeCode": "KZ", "csSalesCode": "DEMO.USAR", "modelData": {"csSalesCode": "DEMO.NSAR"}}}}
        class EmptySource:
            def __init__(self, key): self.source_key = self.site_name = key
            def find_source(self, *_args, **_kwargs):
                return SourceDocument(self.source_key, self.site_name, "", match_level="mismatch")
        class EmptyDns(EmptySource):
            document_urls = {}
            def __init__(self): super().__init__("dns")
        class NoNetwork:
            def get(self, *_args, **_kwargs): raise AssertionError("unexpected network")
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "batches.sqlite3"
            jobs.initialize(db)
            with sqlite3.connect(db) as connection:
                connection.execute("INSERT INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('b','test.xlsx','Sheet1','{}','now')")
                connection.execute("INSERT INTO products(id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (4,'b',2,'kit','LG',?,'','split system',0,'[]','{}')", ("DEMO.NSAR + DEMO.USAR",))
            connection.close()
            jobs.save_source_document(db, 4, SourceDocument("lg_kz_support", "LG KZ support", URL,
                                                             match_level="support_candidate", html=html))
            attempt = record_fetch_attempt(db, 4, "lg_kz_support_api", status="success",
                                           requested_url="https://www.lg.com/ncms/api/v1/support/proxy/productSupportPage?locale=KZ",
                                           final_url="https://www.lg.com/ncms/api/v1/support/proxy/productSupportPage?locale=KZ")
            save_source_snapshot(db, 4, "lg_kz_support_api", attempt,
                                 source_url="https://www.lg.com/ncms/api/v1/support/proxy/productSupportPage?locale=KZ",
                                 content=json.dumps(payload), content_type="application/json",
                                 extracted={"support_url": URL})
            job = jobs.enqueue(db, 4, [1])
            self.assertTrue(worker.run_once(db,
                adapter_factory=lambda: (EmptySource("lg_kz"), EmptySource("lg_ru"), EmptySource("sulpak")),
                dns_adapter_factory=EmptyDns,
                lg_support_adapter_factory=lambda: LGSupportAdapter(http=NoNetwork())))
            support = next(row for row in jobs.get_source_pages(db, 4) if row["source_key"] == "lg_kz_support")
            self.assertEqual(support["match_level"], "full_sku")
            self.assertFalse(support["photos"])
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute("SELECT status FROM search_jobs WHERE id=?", (job,)).fetchone()[0], "needs_review")
            connection.close()
            gc.collect()  # Release SQLite handles before Windows removes the temporary directory.

    def test_url_and_metadata_alone_never_confirm_bundle(self):
        adapter = LGSupportAdapter(candidate_urls=(URL,), candidate_pages={URL: '<title>DEMO.USAR</title>'})
        support = adapter.find_source("DEMO.NSAR + DEMO.USAR", deadline=time.monotonic() + 10)
        self.assertEqual(support.match_level, "support_candidate")


if __name__ == "__main__":
    unittest.main()
