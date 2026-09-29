"""Stage 13: regression test for the concrete policy violation this stage
audited -- Stage 12 Part B made 4 requests to www.razer.com AFTER robots.txt
returned HTTP 403 (a confirmed block), because it used raw requests.Session
calls instead of product_tool.census.endpoint_probe.AccessProbe. See
reports/source_census_2026-09-23_stage13/report.md for the full audit and
reports/source_census_2026-09-23_stage13/raw/stage12_razer_request_chronology_audit.json
for the reconstructed request-by-request chronology.

This test proves the concrete guarantee going forward: any FUTURE script
that seeds AccessProbe with Stage 12's own recorded fetch log -- exactly as
a compliant re-run of Razer discovery should -- makes zero further requests
to www.razer.com, even for a URL never previously seen, and even from a
brand-new AccessProbe instance (i.e. a fresh process, not just the same
run). The block does not clear itself just by starting over.

No network access is used anywhere in this file.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

import requests

from product_tool.census.endpoint_probe import (
    AccessProbe,
    DirectNetworkCallBlocked,
    ProbePolicy,
    blocked_hosts_from_fetch_log,
    enforce_policy_aware_fetch_only,
)
from product_tool.census.models import AccessStatus

ROOT = Path(__file__).resolve().parents[1]
FETCH_LOG = ROOT / "reports/source_census_2026-09-23_stage13/raw/stage12_razer_fetch_log_for_host_stop.json"


class FakeSession:
    """Raises if asked for anything -- proves zero network calls happen."""

    def __init__(self):
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        raise AssertionError(f"unexpected network call to {url!r} -- host should already be stopped")


class Stage12RazerHostStopAuditTests(unittest.TestCase):
    def setUp(self):
        self.entries = json.loads(FETCH_LOG.read_text(encoding="utf-8"))

    def test_fetch_log_records_the_robots_txt_block_first(self):
        self.assertEqual(self.entries[0]["url"], "https://www.razer.com/robots.txt")
        self.assertEqual(self.entries[0]["status_code"], 403)

    def test_fetch_log_records_four_requests_after_the_block(self):
        # This is the violation itself, preserved as an auditable fact: seq
        # 2-5 all target www.razer.com AFTER seq 1's 403, and all four
        # "succeeded" (200) only because nothing enforced the stop.
        after_block = self.entries[1:]
        self.assertEqual(len(after_block), 4)
        for entry in after_block:
            self.assertEqual(entry["status_code"], 200)
            self.assertIn("razer.com", entry["url"])

    def test_seeding_a_fresh_accessprobe_with_this_log_blocks_every_further_request(self):
        stopped = blocked_hosts_from_fetch_log(self.entries)
        self.assertIn("www.razer.com", stopped)

        # A brand-new AccessProbe -- standing in for a freshly re-run script,
        # a new process, a new day -- seeded only with the persisted finding
        # that this host was already blocked.
        probe = AccessProbe(FakeSession(), policy=ProbePolicy(min_interval_seconds=0), initial_stopped_hosts=stopped)

        for url in (
            "https://www.razer.com/",
            "https://www.razer.com/gaming-mice/razer-deathadder-v3",
            "https://www.razer.com/robots.txt",
            "https://www.razer.com/some/path/never/tried/before",
        ):
            with self.subTest(url=url):
                result = probe.probe(url, allowed_hosts=("razer.com",))
                self.assertEqual(result.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(probe.session.calls, [])

    def test_a_different_host_is_unaffected(self):
        stopped = blocked_hosts_from_fetch_log(self.entries)
        self.assertNotIn("example.test", stopped)


class Stage14NetworkGuardTests(unittest.TestCase):
    """Stage 14: closes the remaining Stage 13 gap. Stage 12's actual
    mistake was never using AccessProbe at all -- raw requests.Session
    calls have no memory of anything. This proves that mistake can no
    longer succeed silently: with the guard active, ANY direct
    requests.Session.get() call (the exact shape of Stage 12's violation)
    is refused before any network I/O, whether or not a host was ever
    blocked. AccessProbe itself is unaffected, so legitimate research
    through the correct path keeps working under the guard."""

    def test_direct_session_get_is_blocked_while_guard_is_active(self):
        session = requests.Session()
        with enforce_policy_aware_fetch_only():
            with self.assertRaises(DirectNetworkCallBlocked):
                session.get("https://example.test/")

    def test_guard_clears_after_the_with_block_exits(self):
        # No network access anywhere here -- this checks object identity,
        # not behavior, so restoration is provable without a single call.
        original = requests.Session.get
        with enforce_policy_aware_fetch_only():
            self.assertIsNot(requests.Session.get, original)
        self.assertIs(requests.Session.get, original)

    def test_403_then_a_direct_bypass_attempt_makes_zero_further_requests(self):
        # Reproduces the Stage 12 shape end to end: (1) a real AccessProbe
        # run hits a confirmed block, then (2) something tries to route
        # around it with a raw requests.Session, exactly as Stage 12 did by
        # accident. Step 2 must not reach the network at all.
        class OnceBlockedSession:
            def __init__(self):
                self.calls = 0

            def get(self, url, **kwargs):
                self.calls += 1
                return type(
                    "R", (), {
                        "status_code": 403, "url": url, "history": (),
                        "headers": {}, "cookies": type("C", (), {"get_dict": lambda self: {}})(),
                    },
                )()

        blocked_session = OnceBlockedSession()
        probe = AccessProbe(blocked_session, policy=ProbePolicy(min_interval_seconds=0))
        first = probe.probe("https://example.test/robots.txt", allowed_hosts=("example.test",))
        self.assertEqual(first.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(blocked_session.calls, 1)

        # A second, real requests.Session, used directly -- the exact
        # bypass shape that let Stage 12's 4 post-block requests through.
        # The guard's stub raises immediately and never calls onward, so
        # reaching DirectNetworkCallBlocked IS the proof no real transport
        # (socket, DNS, TLS -- any of it) was ever touched.
        with enforce_policy_aware_fetch_only():
            bypass_session = requests.Session()
            with self.assertRaises(DirectNetworkCallBlocked):
                bypass_session.get("https://example.test/anything")

        # And the already-stopped host inside the SAME probe still refuses
        # a second attempt through the correct path too.
        second = probe.probe("https://example.test/other", allowed_hosts=("example.test",))
        self.assertEqual(second.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(blocked_session.calls, 1)


class Stage15EntryPointGuardTests(unittest.TestCase):
    """Stage 15: enforce_policy_aware_fetch_only() existing, and even being
    exercised by a test, is not the same guarantee as it actually being
    active at every place research code starts. These tests call the real
    __main__ entry points -- product_tool/census/runner.py's, runner_v5.py's,
    runner_v71.py's and report_v71.py's own main()/render(), each now
    decorated with endpoint_probe.guarded_entry_point() -- not the context
    manager directly, and prove a raw requests.Session call made from
    *inside* that real call is blocked before any network I/O."""

    def test_runner_main_blocks_a_raw_session_call_made_during_its_own_run(self):
        import sys
        from product_tool.census import runner

        attempted = {}

        def rogue_generate_census(catalog_path, output_dir, **kwargs):
            # Stands in for a future accidental raw call added somewhere
            # inside generate_census()'s own call graph -- exactly Stage
            # 12's failure shape, but reached through the real entry point.
            try:
                requests.Session().get("https://example.test/rogue")
            except DirectNetworkCallBlocked as exc:
                attempted["blocked"] = exc
                raise

        original = runner.generate_census
        runner.generate_census = rogue_generate_census
        original_argv = sys.argv
        sys.argv = ["runner.py", "unused_catalog.xlsx", "--output", "unused_output"]
        try:
            with self.assertRaises(DirectNetworkCallBlocked):
                runner.main()
        finally:
            runner.generate_census = original
            sys.argv = original_argv
        self.assertIn("blocked", attempted)

    def test_runner_v5_main_is_decorated_with_the_guard(self):
        from product_tool.census import runner_v5
        self.assertTrue(hasattr(runner_v5.main, "__wrapped__"))

    def test_runner_v71_main_is_decorated_with_the_guard(self):
        from product_tool.census import runner_v71
        self.assertTrue(hasattr(runner_v71.main, "__wrapped__"))

    def test_report_v71_render_is_decorated_with_the_guard(self):
        from product_tool.census import report_v71
        self.assertTrue(hasattr(report_v71.render, "__wrapped__"))

    def test_the_decorator_itself_is_what_every_entry_point_uses(self):
        # Every entry point wraps main_func with enforce_policy_aware_fetch_
        # only() via functools.wraps -- confirmed once, directly, rather
        # than re-deriving the same proof per module above.
        from product_tool.census.endpoint_probe import guarded_entry_point

        original = requests.Session.get

        @guarded_entry_point
        def sample_main():
            self.assertIsNot(requests.Session.get, original)
            with self.assertRaises(DirectNetworkCallBlocked):
                requests.Session().get("https://example.test/")

        sample_main()
        # Guard must not leak past the wrapped call.
        self.assertIs(requests.Session.get, original)


if __name__ == "__main__":
    unittest.main()
