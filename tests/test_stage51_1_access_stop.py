"""Offline regression for expiring, auditable production host stops."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from product_tool.adapters import access_stop, policy_fetch
from product_tool.adapters.dns import DnsAdapter
from product_tool.census.endpoint_probe import ProbePolicy
from product_tool.census.attended_support import AttendedBudget, capture
from tests.test_attended_support import FakePlaywright, URL as SUPPORT_URL


URL = "https://www.example.com/product"
HOST = "www.example.com"
CHALLENGE_HTML = '<html>Verify you are human<div class="g-recaptcha"></div></html>'
ORDINARY_HTML = "<html><body>Product with normal content and a specification table.</body></html>"


class Response:
    def __init__(self, status: int, body: str):
        self.url, self.status_code, self.text = URL, status, body
        self.history, self.headers, self.encoding = (), {}, "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self.text.encode("utf-8"),))

    def close(self):
        pass


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **_kwargs):
        self.calls.append(url)
        return self.responses.pop(0)


class AccessStopLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "fetch_log.json"
        self.now = datetime.now(timezone.utc)

    def test_challenge_creates_timed_stop_with_required_context(self):
        session = Session(Response(200, CHALLENGE_HTML))
        fetcher = policy_fetch.PolicyAwareFetcher(
            self.log, session=session, policy=ProbePolicy(min_interval_seconds=0),
            wall_clock=lambda: self.now)
        fetcher.get(URL, allowed_hosts=(HOST,))
        entry = policy_fetch.read_log(self.log)[0]
        self.assertEqual(entry["domain"], HOST)
        self.assertEqual(entry["reason"], "challenge")
        self.assertEqual(entry["scope"], "domain")
        self.assertTrue(entry["created_at"])
        self.assertEqual(entry["last_attempt_at"], entry["created_at"])
        self.assertTrue(entry["source_session"])
        self.assertEqual(datetime.fromisoformat(entry["expires_at"]) -
                         datetime.fromisoformat(entry["created_at"]), timedelta(minutes=30))
        self.assertTrue(fetcher.host_stopped(URL))
        self.assertEqual(session.calls, [URL])

    def test_expired_challenge_allows_one_new_request_even_in_same_fetcher(self):
        now = [self.now]
        session = Session(Response(200, CHALLENGE_HTML), Response(200, ORDINARY_HTML))
        fetcher = policy_fetch.PolicyAwareFetcher(
            self.log, session=session, policy=ProbePolicy(min_interval_seconds=0),
            wall_clock=lambda: now[0])
        fetcher.get(URL, allowed_hosts=(HOST,))
        self.assertTrue(fetcher.host_stopped(URL))
        now[0] += timedelta(minutes=31)
        self.assertFalse(fetcher.host_stopped(URL))
        second = fetcher.get(URL, allowed_hosts=(HOST,))
        self.assertEqual(second.http_status, 200)
        self.assertEqual(session.calls, [URL, URL])
        self.assertEqual(len(policy_fetch.read_log(self.log)), 2)

    def test_attended_resolution_only_clears_challenge(self):
        policy_fetch.record_stop(self.log, HOST, access_stop.CHALLENGE)
        policy_fetch.record_stop(self.log, HOST, access_stop.RATE_LIMIT)
        self.assertIn(HOST, policy_fetch.stopped_hosts_from_fetch_log(policy_fetch.read_log(self.log)))
        policy_fetch.resolve_attended_challenge(self.log, HOST, source_session="attended:session")
        active = access_stop.active_stops(policy_fetch.read_log(self.log))
        self.assertEqual([record["reason"] for record in active[HOST]], ["rate_limit"])
        self.assertEqual(len(policy_fetch.read_log(self.log)), 3)  # immutable history

    def test_successful_attended_capture_resolves_stop_without_erasing_history(self):
        policy_fetch.record_stop(self.log, "www.lg.com", access_stop.CHALLENGE)
        browser = FakePlaywright()

        def user_finishes_challenge(_seconds):
            browser.chromium.context.page.stage = 1

        result = capture(SUPPORT_URL, Path(self.tmp.name) / "capture",
                         Path(self.tmp.name) / "profile", fetch_log_path=self.log,
                         budget=AttendedBudget(max_wait_seconds=10),
                         playwright_factory=lambda: browser, clock=lambda: 0,
                         pause=user_finishes_challenge, announce=lambda _message: None)
        self.assertEqual(result["outcome"], "captured")
        self.assertTrue(result["challenge_seen"])
        self.assertTrue(result["challenge_stop_resolved"])
        self.assertEqual(browser.chromium.context.page.goto_calls, [SUPPORT_URL])
        self.assertNotIn("www.lg.com", policy_fetch.stopped_hosts_from_fetch_log(policy_fetch.read_log(self.log)))
        self.assertEqual([event.get("event", "response") for event in policy_fetch.read_log(self.log)],
                         ["stop", "response", "stop_resolved"])

    def test_attended_navigation_respects_manual_fatal_and_rate_limit_stops(self):
        for reason in (access_stop.MANUAL, access_stop.FATAL, access_stop.RATE_LIMIT):
            with self.subTest(reason=reason):
                self.log.unlink(missing_ok=True)
                policy_fetch.record_stop(self.log, "www.lg.com", reason)
                with self.assertRaisesRegex(ValueError, "forbids attended navigation"):
                    capture(SUPPORT_URL, Path(self.tmp.name) / "capture",
                            Path(self.tmp.name) / "profile", fetch_log_path=self.log,
                            playwright_factory=lambda: FakePlaywright(),
                            announce=lambda _message: None)

    def test_manual_and_fatal_stops_survive_attended_success_and_time(self):
        for reason in (access_stop.MANUAL, access_stop.FATAL):
            policy_fetch.record_stop(self.log, HOST, reason)
        policy_fetch.resolve_attended_challenge(self.log, HOST)
        later = self.now + timedelta(days=365)
        active = access_stop.active_stops(policy_fetch.read_log(self.log), now=later)
        self.assertEqual({record["reason"] for record in active[HOST]}, {"manual", "fatal"})

    def test_rate_limit_has_separate_backoff_and_expires(self):
        entries = [access_stop.stop_event(HOST, "rate_limit", at=self.now)]
        self.assertIn(HOST, access_stop.stopped_hosts(entries, now=self.now + timedelta(minutes=59)))
        self.assertNotIn(HOST, access_stop.stopped_hosts(entries, now=self.now + timedelta(hours=1)))
        self.assertEqual(datetime.fromisoformat(entries[0]["expires_at"]) - self.now,
                         timedelta(hours=1))

    def test_legacy_challenge_is_audit_history_not_forever_stop(self):
        old = {"url": URL, "status_code": 200, "protection_status": "challenge_confirmed",
               "checked_at": "2026-09-26T10:00:00+00:00"}
        self.assertNotIn(HOST, access_stop.stopped_hosts([old], now=self.now))
        self.assertIn(HOST, access_stop.stopped_hosts([old], now=datetime(2026, 9, 26, 10, 1,
                                                                          tzinfo=timezone.utc)))
        self.assertNotIn(HOST, access_stop.stopped_hosts([{"url": URL, "status_code": 200,
                                                          "protection_status": "challenge_confirmed"}], now=self.now))

    def test_401_403_and_429_do_not_turn_into_permanent_challenges(self):
        entries = [{"url": URL, "status_code": status, "checked_at": self.now.isoformat()}
                   for status in (401, 403, 429)]
        active = access_stop.active_stops(entries, now=self.now)
        self.assertEqual({item["reason"] for item in active[HOST]},
                         {"http_access_denied", "rate_limit"})
        self.assertNotIn(HOST, access_stop.stopped_hosts(entries, now=self.now + timedelta(hours=6)))

    def test_dns_401_is_recorded_and_next_adapter_does_not_repeat_request(self):
        url = "https://www.dns-shop.ru/product/known/"

        class DNSResponse:
            status_code = 401
            history = ()
            headers = {}

            def __init__(self):
                self.url = url

            def close(self):
                pass

        class DNSHttp:
            def __init__(self, forbid=False):
                self.headers, self.calls, self.forbid = {}, 0, forbid

            def get(self, *_args, **_kwargs):
                self.calls += 1
                if self.forbid:
                    raise AssertionError("DNS was requested despite active 401 stop")
                return DNSResponse()

        first_http = DNSHttp()
        first = DnsAdapter(first_http, clock=lambda: 0, urls={"X": url},
                           fetch_log_path=self.log)
        result = first.find_source("X", deadline=100)
        self.assertIn("401", result.error)
        self.assertEqual(first_http.calls, 1)
        self.assertEqual(policy_fetch.read_log(self.log)[0]["reason"], "http_access_denied")

        next_http = DNSHttp(forbid=True)
        next_adapter = DnsAdapter(next_http, clock=lambda: 0, urls={"X": url},
                                  fetch_log_path=self.log)
        blocked = next_adapter.find_source("X", deadline=100)
        self.assertEqual(blocked.match_level, "blocked")
        self.assertEqual(next_http.calls, 0)


if __name__ == "__main__":
    unittest.main()
