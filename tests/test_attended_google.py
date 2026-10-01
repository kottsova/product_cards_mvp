"""Offline attended Google transport and persistent-session regression."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from product_tool.adapters.access_stop import active_stops, stop_event
from product_tool.adapters.policy_fetch import append_log_entry, read_log
from product_tool.census.attended_google import AttendedGoogleBrowser, google_search_url
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.census.browser_runtime import BrowserFailure, BrowserRuntime

URL = "https://www.google.com/search?q=site%3Alg.com%20%22MS2082F%22&hl=en"
UK = "https://www.lg.com/uk/microwaves/solo/ms2082f/"
RUNTIME = BrowserRuntime(True, python="fake", runtime_version="fake", browser_version="fake")


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.stage = 0
        self.goto_calls = []
        self.handlers = {}
        self.main_frame = object()
        self.last_policy = None

    def on(self, name, callback): self.handlers[name] = callback
    def goto(self, url, **kwargs):
        self.goto_calls.append(url)
        self.url = url
    def evaluate(self, script, policy):
        self.last_policy = policy
        if not self.stage:
            return {"protection": True, "overflow": False, "fragments": []}
        return {"protection": False, "overflow": False,
                "fragments": [{"type": "result_link", "url": UK,
                               "title": "LG MS2082F microwave", "snippet": "20 litre oven"}]}


class FakeContext:
    def __init__(self):
        self.page = FakePage()
        self.pages = [self.page]
        self.closed = False
    def route(self, pattern, callback): pass
    def on(self, name, callback): pass
    def close(self): self.closed = True


class FakePlaywright:
    def __init__(self):
        self.context = FakeContext()
        self.options = {}
        self.chromium = self
    def launch_persistent_context(self, profile, **options):
        self.options = {"profile": profile, **options}
        return self.context
    def __enter__(self): return self
    def __exit__(self, *args): pass


class AttendedGoogleTests(unittest.TestCase):
    def test_only_declared_google_query_is_eligible(self):
        self.assertTrue(google_search_url(URL))
        self.assertFalse(google_search_url("https://www.google.com/search?q=shoes"))
        self.assertFalse(google_search_url("https://www.google.com.evil.test/search?q=site:lg.com"))

    def test_manual_challenge_resumes_same_chrome_session_and_saves_projection(self):
        fake = FakePlaywright()
        messages = []
        with TemporaryDirectory() as root:
            root = Path(root)
            log = root / "fetch.json"
            append_log_entry(log, stop_event("www.google.com", "challenge"))
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com", "gstatic.com"),
                profile_dir=root / "profile", output_dir=root / "capture",
                fetch_log_path=log, playwright_factory=lambda: fake,
                clock=lambda: 0, pause=lambda seconds: setattr(fake.context.page, "stage", 1),
                announce=messages.append)
            driver.start()
            try:
                state = driver.call("goto", url=URL, queries=["MS2082F"])
            finally:
                driver.close()
            self.assertEqual(fake.context.page.goto_calls, [URL])
            self.assertEqual(fake.options["channel"], "chrome")
            self.assertFalse(fake.options["headless"])
            self.assertNotIn("args", fake.options)
            self.assertTrue(fake.context.closed)
            self.assertEqual(state["projection"]["fragments"][0]["url"], UK)
            self.assertIn("www.lg.com", fake.context.page.last_policy["allowed_hosts"])
            self.assertNotIn("www.lg.com", driver.allowed_hosts)
            self.assertIn("Automation is paused", " ".join(messages))
            saved = json.loads((root / "capture" / "search_projection.json").read_text(encoding="utf-8"))
            self.assertTrue(saved["challenge_seen"])
            self.assertEqual(saved["projection"]["fragments"][0]["snippet"], "20 litre oven")
            self.assertNotIn("www.google.com", active_stops(read_log(log)))

    def test_403_challenge_can_be_completed_manually(self):
        fake = FakePlaywright()
        with TemporaryDirectory() as root:
            root = Path(root)
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=root / "fetch.json",
                playwright_factory=lambda: fake, clock=lambda: 0,
                pause=lambda seconds: (setattr(fake.context.page, "stage", 1),
                                       setattr(driver, "last_document_status", 200)))
            driver.start()
            driver.last_document_status = 403
            try:
                result = driver.call("goto", url=URL, queries=["MS2082F"])
            finally:
                driver.close()
            self.assertEqual(result["projection"]["fragments"][0]["url"], UK)
            self.assertEqual(fake.context.page.goto_calls, [URL])
    def test_waits_for_rendered_results_without_second_navigation(self):
        fake = FakePlaywright()
        calls = []
        def evaluate(script, policy):
            calls.append(policy)
            fragments = [] if len(calls) < 3 else [
                {"type": "result_link", "url": UK, "title": "LG MS2082F"}]
            return {"protection": False, "overflow": False, "fragments": fragments}
        fake.context.page.evaluate = evaluate
        with TemporaryDirectory() as root:
            root = Path(root)
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=root / "fetch.json",
                playwright_factory=lambda: fake, clock=lambda: 0,
                pause=lambda seconds: None)
            driver.start()
            try:
                state = driver.call("goto", url=URL, queries=["MS2082F"])
            finally:
                driver.close()
            self.assertEqual(len(calls), 3)
            self.assertEqual(fake.context.page.goto_calls, [URL])
            self.assertEqual(state["projection"]["fragments"][0]["url"], UK)
    def test_plain_403_records_http_stop_and_cannot_be_attended_away(self):
        fake = FakePlaywright()
        fake.context.page.stage = 1
        with TemporaryDirectory() as root:
            root = Path(root)
            log = root / "fetch.json"
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=log,
                playwright_factory=lambda: fake, clock=lambda: 0)
            driver.start()
            driver.last_document_status = 403
            driver.last_document_url = URL
            try:
                with self.assertRaises(BrowserFailure) as failure:
                    driver.call("goto", url=URL, queries=["MS2082F"])
                self.assertEqual(str(failure.exception), "http_denied")
            finally:
                driver.close()
            entry = read_log(log)[-1]
            self.assertEqual((entry["url"], entry["status_code"], entry["reason"]),
                             (URL, 403, "http_access_denied"))
            blocked = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=log,
                playwright_factory=lambda: FakePlaywright())
            with self.assertRaises(BrowserFailure):
                blocked.start()
    def test_unfinished_manual_challenge_returns_temporary_challenge_outcome(self):
        fake = FakePlaywright()
        ticks = iter((0, 0, 2))
        with TemporaryDirectory() as root:
            root = Path(root)
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=root / "fetch.json",
                playwright_factory=lambda: fake, clock=lambda: next(ticks),
                pause=lambda seconds: None, max_wait_seconds=1)
            driver.start()
            try:
                with self.assertRaises(BrowserFailure) as failure:
                    driver.call("goto", url=URL, queries=["MS2082F"])
                self.assertEqual(str(failure.exception), "challenge_detected")
            finally:
                driver.close()
            self.assertEqual(fake.context.page.goto_calls, [URL])
            self.assertFalse((root / "capture" / "search_projection.json").exists())
    def test_rate_limit_records_exact_response_url_and_stops(self):
        fake = FakePlaywright()
        with TemporaryDirectory() as root:
            root = Path(root)
            log = root / "fetch.json"
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=log,
                playwright_factory=lambda: fake, clock=lambda: 0)
            driver.start()
            driver.rate_limit_url = URL
            try:
                with self.assertRaises(BrowserFailure) as failure:
                    driver.call("goto", url=URL, queries=["MS2082F"])
                self.assertEqual(str(failure.exception), "rate_limited")
            finally:
                driver.close()
            entry = read_log(log)[-1]
            self.assertEqual((entry["url"], entry["status_code"], entry["reason"]),
                             (URL, 429, "rate_limit"))
            self.assertIn("www.google.com", active_stops(read_log(log)))

    def test_manual_stop_cannot_be_resolved_by_attended_search(self):
        fake = FakePlaywright()
        with TemporaryDirectory() as root:
            root = Path(root)
            log = root / "fetch.json"
            append_log_entry(log, stop_event("www.google.com", "manual"))
            driver = AttendedGoogleBrowser(RUNTIME, BrowserBudget(),
                ("www.google.com", "google.com"), profile_dir=root / "profile",
                output_dir=root / "capture", fetch_log_path=log,
                playwright_factory=lambda: fake)
            with self.assertRaises(BrowserFailure):
                driver.start()
            self.assertEqual(fake.options, {})


if __name__ == "__main__": unittest.main()
