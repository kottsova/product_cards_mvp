"""Stage 54.3: functional parity with the old general Google parser."""
import ast
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote_plus

from product_tool.census.old_parser_google import (
    OLD_PROFILE_DIR, OldParserGoogleBrowser, clean_google_result_url,
    google_general_search, original_candidate_function, original_search_function,
    OLD_SOURCE_FILE, OLD_SOURCE_SHA256,
)
from product_tool.adapters.lg_browser_search import LGBrowserSearch
from product_tool.adapters.common import SourceDocument
from product_tool import jobs, lg_discovery_pipeline
from product_tool.census.browser_runtime import BrowserFailure


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def inner_text(self, timeout):
        return "Search results"

    def evaluate_all(self, script):
        return self.page.links


class FakePage:
    def __init__(self, links=()):
        self.url = "about:blank"
        self.links = list(links)
        self.waits = []
        self.events = {}

    def goto(self, url, **kwargs):
        self.url = url
        self.goto_kwargs = kwargs

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)

    def locator(self, selector):
        return FakeLocator(self, selector)

    def on(self, event, callback):
        self.events[event] = callback


class FakeContext:
    def __init__(self, page):
        self.pages = [page]
        self.closed = False

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, context):
        self.context = context

    def launch_persistent_context(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self.context


class FakePlaywright:
    def __init__(self, page):
        self.chromium = FakeChromium(FakeContext(page))
        self.stopped = False

    def start(self):
        return self

    def stop(self):
        self.stopped = True


class OldParserParityTests(unittest.TestCase):
    def test_search_uses_original_url_wait_anchor_and_redirect_logic(self):
        page = FakePage([
            {"href": "https://www.google.com/url?q=https%3A%2F%2Fwww.lg.com%2Fuk%2Fovens%2Fzx123%2F&sa=U", "text": "ZX123"},
            {"href": "https://www.lg.com/uk/support/product/zx123", "text": "support"},
            {"href": "https://www.lg.com/uk/ovens/zx123/", "text": "duplicate"},
        ])
        results = google_general_search(page, 'site:lg.com "ZX123"')
        self.assertEqual(page.url, "https://www.google.com/search?q=" + quote_plus('site:lg.com "ZX123"') + "&hl=en")
        self.assertEqual(page.goto_kwargs, {"wait_until": "domcontentloaded", "timeout": 60000})
        self.assertEqual(page.waits, [1000])
        self.assertEqual(results, [("https://www.lg.com/uk/ovens/zx123", "ZX123")])
        self.assertEqual(clean_google_result_url("/url?q=https%3A%2F%2Fwww.lg.com%2Fuk%2Fovens%2Fzx123%2F"),
                         "https://www.lg.com/uk/ovens/zx123")

    def test_transferred_functions_match_old_ast(self):
        if not OLD_SOURCE_FILE.is_file():
            self.skipTest("original sibling source is not installed")
        old_bytes = OLD_SOURCE_FILE.read_bytes()
        self.assertEqual(hashlib.sha256(old_bytes).hexdigest(), OLD_SOURCE_SHA256)
        old = ast.parse(old_bytes.decode("utf-8-sig"))
        transferred = ast.parse(Path("product_tool/census/old_parser_google.py").read_text(encoding="utf-8-sig"))
        names = ("clean_google_result_url", "google_general_search", "normalize_text",
                 "extract_model_keywords", "url_belongs_to_domain", "is_global_catalog_like",
                 "is_global_homepage_like", "global_model_identifier",
                 "global_exact_identifier_in", "official_product_candidate")
        for name in names:
            original = next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == name)
            copy = next(node for node in transferred.body if isinstance(node, ast.FunctionDef) and node.name == name)
            self.assertEqual(ast.dump(copy, include_attributes=False),
                             ast.dump(original, include_attributes=False), name)

    def test_literal_old_source_exact_result_screening(self):
        function, source = original_search_function()
        self.assertEqual(source, "original_file")
        self.assertTrue(function.__code__.co_filename.endswith("find_product_pages.py"))
        candidate = original_candidate_function()
        self.assertTrue(candidate("https://www.lg.com/uk/ovens/zx123", "ZX123", "lg.com", "LG", "", "ZX123"))
        self.assertFalse(candidate("https://www.lg.com/uk/ovens/zx124", "ZX124", "lg.com", "LG", "", "ZX123"))

    def test_driver_uses_old_profile_executable_selection_and_flags(self):
        page = FakePage()
        playwright = FakePlaywright(page)
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)
            (profile / "Default").mkdir()
            driver = OldParserGoogleBrowser(profile, playwright_factory=lambda: playwright)
            driver.start()
            self.assertEqual(playwright.chromium.args, (str(profile),))
            self.assertEqual(playwright.chromium.kwargs, {
                "headless": False,
                "viewport": {"width": 1440, "height": 1200},
                "args": ["--disable-blink-features=AutomationControlled"],
            })
            self.assertIn("response", page.events)
            driver.close()
            self.assertTrue(playwright.chromium.context.closed)
            self.assertTrue(playwright.stopped)
        self.assertEqual(OLD_PROFILE_DIR.name, ".global_google_profile")

    def test_old_driver_reports_http_429_without_a_second_query(self):
        class Request:
            def __init__(self, frame):
                self.frame = frame
            def is_navigation_request(self):
                return True
        class Response:
            def __init__(self, url, frame):
                self.url = url
                self.status = 429
                self.request = Request(frame)
        class RateLimitedPage(FakePage):
            def __init__(self):
                super().__init__()
                self.main_frame = object()
                self.gotos = 0
            def goto(self, url, **kwargs):
                super().goto(url, **kwargs)
                self.gotos += 1
                self.events["response"](Response("https://www.google.com/sorry/index", self.main_frame))
        page = RateLimitedPage()
        playwright = FakePlaywright(page)
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)
            (profile / "Default").mkdir()
            driver = OldParserGoogleBrowser(profile, playwright_factory=lambda: playwright)
            driver.start()
            with self.assertRaises(BrowserFailure) as caught:
                driver.call("goto", url="https://www.google.com/search?q=site%3Alg.com+%22ZX123%22")
            self.assertEqual(str(caught.exception), "rate_limited")
            self.assertEqual(page.gotos, 1)
            driver.close()

    def test_old_parser_result_reaches_existing_exact_validation(self):
        class Driver:
            def start(self):
                self.source_kind = "original_file"
            def call(self, command, **args):
                return {"url": args["url"], "projection": {"fragments": [
                    {"type": "result_link", "url": "https://www.lg.com/uk/ovens/zx123/",
                     "title": "ZX123", "snippet": "", "old_parser_candidate": True}]},
                    "counts": {"old_parser_source": "original_file"}, "old_parser_source": "original_file"}
            def close(self):
                pass
        class Global:
            def __init__(self):
                self.calls = []
            def fetch_candidate(self, url, article, **kwargs):
                self.calls.append((url, article))
                return SourceDocument("lg_global", "LG UK", url, found_model=article,
                                      match_level="full_sku")
        with tempfile.TemporaryDirectory() as temp, patch(
                "product_tool.census.old_parser_google.OldParserGoogleBrowser", Driver), patch.object(
                jobs, "save_source_document") as save:
            search = LGBrowserSearch(Path(temp) / "log.json")
            global_adapter = Global()
            outcome = lg_discovery_pipeline.run_web_fallback(
                Path(temp) / "unused.sqlite3", "job", 1, "ZX123", "", search,
                kz=None, ru=None, global_adapter=global_adapter,
                deadline=100, stages=[1, 2, 3, 4], clock=lambda: 0)
            search.close()
        self.assertEqual(outcome.product_document.match_level, "full_sku")
        self.assertEqual(global_adapter.calls, [("https://www.lg.com/uk/ovens/zx123/", "ZX123")])
        save.assert_called_once()

    def test_default_production_google_calls_old_driver(self):
        class Driver:
            calls = []
            def start(self):
                self.calls.append("start")
            def call(self, command, **args):
                self.calls.append((command, args["url"]))
                return {"url": args["url"], "projection": {"fragments": [
                    {"type": "result_link", "url": "https://www.lg.com/uk/ovens/zx123-pro/",
                     "title": "ZX123 Pro", "snippet": "", "old_parser_candidate": False},
                    {"type": "result_link", "url": "https://www.lg.com/uk/ovens/zx123/",
                     "title": "ZX123", "snippet": "", "old_parser_candidate": True}]}, "counts": {}}
            def close(self):
                self.calls.append("close")
        with tempfile.TemporaryDirectory() as temp, patch(
                "product_tool.census.old_parser_google.OldParserGoogleBrowser", Driver):
            search = LGBrowserSearch(Path(temp) / "log.json")
            result = search.search_provider("google", 'site:lg.com "ZX123"')
            self.assertEqual(result.outcome, "candidates_found")
            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0].provider, "google_old_parser")
            self.assertEqual(result.candidates[0].url, "https://www.lg.com/uk/ovens/zx123/")
            self.assertTrue(any(isinstance(call, tuple) for call in Driver.calls))
            search.close()
            self.assertEqual(Driver.calls[-1], "close")


if __name__ == "__main__":
    unittest.main()
