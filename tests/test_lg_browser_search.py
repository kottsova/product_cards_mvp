"""Stage 43: offline unit tests for adapters.lg_browser_search.LGBrowserSearch.

No real subprocess/network anywhere here -- a fake driver stands in for
census.browser_runtime.PlaywrightBrowser, and a fake BrowserRuntime stands in
for discover_runtime()'s result.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from product_tool.adapters import lg_browser_search as lbs
from product_tool.adapters import policy_fetch
from product_tool.census.browser_runtime import BrowserFailure, BrowserRuntime


AVAILABLE = BrowserRuntime(True, python="fake-python", runtime_version="playwright-fake", browser_version="fake-1")
UNAVAILABLE = BrowserRuntime(False, reason="no usable installed Python Playwright and Chromium pair")

SUPPORT_URL = "https://www.lg.com/ru/support/product/lg-RNC9.DRUSLLK"
PDP_URL = "https://www.lg.com/ru/audio/lg-rnc9"  # NOT a support URL -- must never be returned as a candidate


class FakeDriver:
    """Stands in for census.browser_runtime.PlaywrightBrowser. `states` maps a goto URL to either a
    ready-made state dict or an exception instance to raise."""

    def __init__(self, runtime, budget, allowed_hosts, *, states=None):
        self.runtime, self.budget, self.allowed_hosts = runtime, budget, allowed_hosts
        self.states = states or {}
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def start(self):
        return {"runtime_version": self.runtime.browser_version}

    def call(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command != "goto":
            raise AssertionError(f"unexpected command {command!r}")
        outcome = self.states.get(kwargs["url"])
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            return {"url": kwargs["url"], "projection": {"fragments": []}}
        return outcome

    def close(self):
        self.closed = True


def _fragments_state(url: str, links: list[tuple[str, str]]) -> dict:
    return {"url": url, "projection": {"fragments": [{"type": "result_link", "url": u, "title": t} for u, t in links]}}


class LGBrowserSearchTests(unittest.TestCase):
    def _instance(self, driver_factory, *, log_path=None, runtime=AVAILABLE):
        self._tmp = self._tmp if hasattr(self, "_tmp") else TemporaryDirectory()
        log_path = log_path or Path(self._tmp.name) / "lg_fetch_log.json"
        return lbs.LGBrowserSearch(log_path, runtime=runtime, driver_factory=driver_factory), log_path

    def tearDown(self):
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()

    def test_candidates_found_filters_to_support_urls_only(self):
        url = lbs.SEARCH_ROUTES["ru"].format(q="RNC9")
        states = {url: _fragments_state(url, [(SUPPORT_URL, "RNC9.DRUSLLK Аудиосистема"), (PDP_URL, "Аудиосистема RNC9")])}
        search, _ = self._instance(lambda *a: FakeDriver(*a, states=states))
        result = search.search("ru", ["RNC9"])
        self.assertEqual(result.outcome, "candidates_found")
        self.assertEqual([c.url for c in result.candidates], [SUPPORT_URL])
        self.assertEqual(result.candidates[0].kind, "support")

    def test_observed_kz_support_shape_is_a_candidate_not_an_identity(self):
        kz = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"
        self.assertTrue(lbs.is_lg_support_product_url(kz))
        self.assertFalse(lbs.is_lg_support_product_url("https://www.lg.com.evil.test/kz/support/product-support/cs-P12ED.USAR/"))
        self.assertFalse(lbs.is_lg_support_product_url("https://www.lg.com/kz/air-conditioners/lg-P12ED"))

    def test_no_candidates_tries_every_query_then_reports(self):
        full_url = lbs.SEARCH_ROUTES["ru"].format(q="MS2082F")
        base_url = lbs.SEARCH_ROUTES["ru"].format(q="MS2082")
        states = {full_url: _fragments_state(full_url, []), base_url: _fragments_state(base_url, [])}
        search, _ = self._instance(lambda *a: FakeDriver(*a, states=states))
        result = search.search("ru", ["MS2082F", "MS2082"])
        self.assertEqual(result.outcome, "no_candidates")
        self.assertIn("не нашёл", result.note)

    def test_second_query_used_when_first_finds_nothing(self):
        full_url = lbs.SEARCH_ROUTES["ru"].format(q="W4W8LVPKZHM.APBPCOM")
        base_url = lbs.SEARCH_ROUTES["ru"].format(q="W4W8LVPKZHM")
        states = {full_url: _fragments_state(full_url, []), base_url: _fragments_state(base_url, [(SUPPORT_URL, "hit")])}
        search, _ = self._instance(lambda *a: FakeDriver(*a, states=states))
        result = search.search("ru", ["W4W8LVPKZHM.APBPCOM", "W4W8LVPKZHM"])
        self.assertEqual(result.outcome, "candidates_found")
        self.assertEqual(result.query, "W4W8LVPKZHM")

    def test_confirmed_challenge_is_persisted_and_stops_a_later_instance(self):
        url = lbs.SEARCH_ROUTES["ru"].format(q="RNC9")
        states = {url: BrowserFailure("challenge_detected")}
        search, log_path = self._instance(lambda *a: FakeDriver(*a, states=states))
        result = search.search("ru", ["RNC9"])
        self.assertEqual(result.outcome, "challenge_detected")
        entries = policy_fetch.read_log(log_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["protection_status"], "challenge_confirmed")

        def never_called(*a):
            raise AssertionError("a stopped host must never launch a new driver")
        second, _ = self._instance(never_called, log_path=log_path)
        result2 = second.search("ru", ["RNC9"])
        self.assertEqual(result2.outcome, "host_stopped")

    def test_challenge_stops_further_queries_within_the_same_instance_too(self):
        url = lbs.SEARCH_ROUTES["ru"].format(q="X")
        driver_holder = {}
        def factory(*a):
            d = FakeDriver(*a, states={url: BrowserFailure("challenge_detected")})
            driver_holder["driver"] = d
            return d
        search, _ = self._instance(factory)
        search.search("ru", ["X"])
        result = search.search("ru", ["Y"])  # different query, same host -- must short-circuit, no new goto
        self.assertEqual(result.outcome, "host_stopped")
        self.assertEqual(len(driver_holder["driver"].calls), 1)  # only the first, failed goto

    def test_runtime_unavailable_is_explicit_not_silent(self):
        search, _ = self._instance(lambda *a: FakeDriver(*a), runtime=UNAVAILABLE)
        result = search.search("ru", ["RNC9"])
        self.assertEqual(result.outcome, "runtime_unavailable")
        self.assertIn("Playwright", result.note)

    def test_unknown_region_reports_route_not_available_without_touching_the_driver(self):
        def never_called(*a):
            raise AssertionError("no driver should be created for an unsupported region")
        search, _ = self._instance(never_called)
        result = search.search("kz", ["RNC9"])
        self.assertEqual(result.outcome, "route_not_available")

    def test_close_is_idempotent_and_safe_before_any_search(self):
        search, _ = self._instance(lambda *a: FakeDriver(*a))
        search.close()
        search.close()

    def test_driver_closed_after_use(self):
        url = lbs.SEARCH_ROUTES["ru"].format(q="RNC9")
        holder = {}
        def factory(*a):
            d = FakeDriver(*a, states={url: _fragments_state(url, [(SUPPORT_URL, "x")])})
            holder["driver"] = d
            return d
        search, _ = self._instance(factory)
        search.search("ru", ["RNC9"])
        search.close()
        self.assertTrue(holder["driver"].closed)


if __name__ == "__main__":
    unittest.main()
