"""Stage 20: the LG adapters' network calls go through the shared policy-aware fetch with a persisted log.

Everything is offline: the transport is an in-memory double, the log lives in a temp directory.
"""
from __future__ import annotations

import json
import unittest
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests

from product_tool import jobs, worker
from product_tool.adapters import lg_policy
from product_tool.adapters.common import SourceError, fetch_with_retry
from product_tool.adapters.lg import LG_KZ_SITEMAP, LGAdapter, LGRUAdapter, lg_session
from product_tool.adapters.lg_policy import default_lg_adapters
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import BUDGET, NOT_ALLOWED, STOPPED, PolicyAwareSession, RequestBudget, request_budget
from product_tool.adapters.sulpak import SulpakAdapter
from product_tool.coverage import executor
from product_tool.coverage.facts import load_config, recorded_blocked_hosts

from coverage_controls import FixtureSession, _lg_pages

URL = "https://www.lg.com/kz/laundry/x/"
CONFIRMED = '<html><body>Attention Required<div class="g-recaptcha" data-x="1"></div></body></html>'
SUSPECTED = "<html><body>" + "An ordinary product page with plenty of visible text. " * 12 + "Security check</body></html>"
ORDINARY = "<html><body>" + "An ordinary product page with plenty of visible text. " * 12 + "</body></html>"


def session(log: Path, pages: dict, **kw) -> tuple[PolicyAwareSession, FixtureSession]:
    transport = FixtureSession(pages)
    return PolicyAwareSession(log, allowed_hosts=("www.lg.com", "lg.com"), underlying=transport, min_interval_seconds=0.0, sleep=lambda _s: None, **kw), transport


def fetch(client, url=URL):
    try:
        return fetch_with_retry(client, url, deadline=1e9, clock=lambda: 0.0)
    except SourceError as exc:
        return exc


class StoppedHostSurvivesTheNextRun(unittest.TestCase):
    def two_runs(self, first_page):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "lg_fetch_log.json"
            first, first_transport = session(log, {URL: first_page})
            outcome = fetch(first)
            entries = json.loads(log.read_text(encoding="utf-8"))
            second, second_transport = session(log, {URL: (200, ORDINARY)})
            second_outcome = fetch(second)
            return outcome, entries, second_outcome, second_transport, first_transport, recorded_blocked_hosts(load_config(), Path(tmp), extra_logs=(log,)), second

    def test_403_is_logged_and_a_new_instance_makes_no_request(self):
        outcome, entries, second_outcome, second_transport, first_transport, planner_view, second = self.two_runs((403, "blocked"))
        self.assertIsInstance(outcome, SourceError)
        self.assertEqual(entries[0]["status_code"], 403)
        self.assertEqual(second_transport.calls, [])
        self.assertIn(STOPPED, str(second_outcome))
        self.assertIn("www.lg.com", planner_view)

    def test_429_is_logged_and_never_retried_against_a_stopped_host(self):
        outcome, entries, second_outcome, second_transport, first_transport, planner_view, second = self.two_runs((429, "slow down"))
        self.assertEqual(first_transport.calls, [URL])  # fetch_with_retry's retry hit the stopped host: no second request
        self.assertEqual(entries[0]["status_code"], 429)
        self.assertEqual(second_transport.calls, [])
        self.assertIn("www.lg.com", planner_view)

    def test_401_in_the_log_stops_the_next_run(self):
        outcome, entries, second_outcome, second_transport, first_transport, planner_view, second = self.two_runs((401, "no"))
        self.assertEqual(entries[0]["status_code"], 401)
        self.assertEqual(second_transport.calls, [])
        self.assertIn(STOPPED, str(second_outcome))

    def test_a_confirmed_challenge_with_http_200_is_never_a_page_and_stops_the_next_run(self):
        outcome, entries, second_outcome, second_transport, first_transport, planner_view, second = self.two_runs((200, CONFIRMED))
        self.assertIsInstance(outcome, SourceError)
        self.assertIn("policy_challenge_confirmed", str(outcome))
        self.assertEqual((entries[0]["status_code"], entries[0]["protection_status"]), (200, "challenge_confirmed"))
        self.assertEqual(second_transport.calls, [])
        self.assertIn("www.lg.com", planner_view)

    def test_challenge_suspected_alone_is_logged_and_stops_nothing(self):
        outcome, entries, second_outcome, second_transport, first_transport, planner_view, second = self.two_runs((200, SUSPECTED))
        self.assertEqual(outcome.status_code, 200)
        self.assertEqual(outcome.text, SUSPECTED)  # the page is handed to the adapter as before
        self.assertEqual(entries[0]["protection_status"], "challenge_suspected")
        self.assertEqual(second_transport.calls, [URL])
        self.assertEqual(second_outcome.status_code, 200)
        self.assertNotIn("www.lg.com", planner_view)

    def test_one_host_stopping_does_not_stop_another(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "lg_fetch_log.json"
            log.write_text(json.dumps([{"url": "https://www.lg.com/kz/x", "status_code": 403}]), encoding="utf-8")
            self.assertEqual(stopped_hosts_from_fetch_log(json.loads(log.read_text(encoding="utf-8"))), frozenset({"www.lg.com"}))
            other = PolicyAwareSession(log, allowed_hosts=("www.sulpak.kz",), underlying=FixtureSession({"https://www.sulpak.kz/g/x": (200, ORDINARY)}), min_interval_seconds=0.0)
            self.assertEqual(fetch(other, "https://www.sulpak.kz/g/x").status_code, 200)


class PolicyRules(unittest.TestCase):
    def test_a_host_outside_the_allowlist_is_refused_without_a_request(self):
        with TemporaryDirectory() as tmp:
            client, transport = session(Path(tmp) / "l.json", {})
            self.assertIn(NOT_ALLOWED, str(fetch(client, "https://evil.example/x")))
            self.assertEqual(transport.calls, [])

    def test_the_request_budget_refuses_before_the_request_and_counts_only_real_requests(self):
        with TemporaryDirectory() as tmp:
            pages = {f"https://www.lg.com/kz/p{i}/": (200, ORDINARY) for i in range(8)}
            client, transport = session(Path(tmp) / "l.json", pages)
            budget = RequestBudget(max_per_row=3, max_total=4)
            with request_budget(budget):
                budget.begin_row("a")
                results = [fetch(client, f"https://www.lg.com/kz/p{i}/") for i in range(5)]
                self.assertEqual([getattr(r, "status_code", None) for r in results[:3]], [200, 200, 200])
                self.assertIn(BUDGET, str(results[3]))
                budget.begin_row("b")
                self.assertEqual(fetch(client, "https://www.lg.com/kz/p5/").status_code, 200)
                self.assertIn(BUDGET, str(fetch(client, "https://www.lg.com/kz/p6/")))  # 4 in total
            self.assertEqual(len(transport.calls), 4)
            self.assertEqual((budget.total, budget.row), (4, 1))

    def test_a_sitemap_is_read_once_for_a_whole_batch(self):
        with TemporaryDirectory() as tmp:
            client, transport = session(Path(tmp) / "l.json", {LG_KZ_SITEMAP: (200, "<urlset></urlset>")})
            with request_budget(RequestBudget(max_per_row=5, max_total=60)) as budget:
                for row in ("a", "b", "c"):
                    budget.begin_row(row)
                    self.assertEqual(fetch(client, LG_KZ_SITEMAP).status_code, 200)
            self.assertEqual(transport.calls, [LG_KZ_SITEMAP])
            self.assertEqual(budget.total, 1)

    def test_a_new_session_of_the_same_run_reuses_the_sitemap_but_another_run_does_not(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "a" / "l.json"
            first, first_transport = session(log, {LG_KZ_SITEMAP: (200, "<urlset></urlset>")})
            self.assertEqual(fetch(first, LG_KZ_SITEMAP).status_code, 200)
            second, second_transport = session(log, {LG_KZ_SITEMAP: (200, "<urlset></urlset>")})  # the worker builds a new session per job
            self.assertEqual(fetch(second, LG_KZ_SITEMAP).status_code, 200)
            self.assertEqual((first_transport.calls, second_transport.calls), ([LG_KZ_SITEMAP], []))
            other, other_transport = session(Path(tmp) / "b" / "l.json", {LG_KZ_SITEMAP: (200, "<urlset></urlset>")})
            fetch(other, LG_KZ_SITEMAP)
            self.assertEqual(other_transport.calls, [LG_KZ_SITEMAP])

    def test_responses_can_be_recorded_for_offline_diagnosis(self):
        from product_tool.adapters.policy_session import record_responses
        import gzip
        with TemporaryDirectory() as tmp:
            client, _ = session(Path(tmp) / "l.json", {URL: (200, ORDINARY), "https://www.lg.com/kz/missing/": (404, "")})
            with record_responses(Path(tmp) / "rec"):
                fetch(client)
                fetch(client, "https://www.lg.com/kz/missing/")
            index = [json.loads(line) for line in (Path(tmp) / "rec/index.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([(e["url"], e["status"]) for e in index], [(URL, 200), ("https://www.lg.com/kz/missing/", 404)])
            with gzip.open(Path(tmp) / "rec" / index[0]["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                self.assertEqual(handle.read(), ORDINARY)
            self.assertEqual(index[1]["saved_as"], "")  # an error without a body saves no file

    def test_the_adapters_own_headers_reach_the_request(self):
        with TemporaryDirectory() as tmp:
            transport = FixtureSession({URL: (200, ORDINARY)})
            transport.headers.update({"User-Agent": "Mozilla/5.0 test", "Accept-Language": "ru-RU"})
            captured = {}
            original = transport.get

            def spy(url, **kw):
                captured.update(kw)
                return original(url, **kw)
            transport.get = spy
            client = PolicyAwareSession(Path(tmp) / "l.json", allowed_hosts=("www.lg.com",), underlying=transport, min_interval_seconds=0.0)
            client.headers.update({"User-Agent": "Mozilla/5.0 changed by an adapter"})
            fetch(client)
            self.assertEqual(captured["headers"]["User-Agent"], "Mozilla/5.0 changed by an adapter")
            self.assertEqual(transport.headers["Accept-Language"], "ru-RU")


class LgBehaviourIsUnchanged(unittest.TestCase):
    """The same LG adapters over the same pages give the same documents with and without the policy session."""

    def documents(self, wrap):
        sku = "MS2032GAS"
        sulpak_url = "https://www.sulpak.kz/g/mikrovolnovaya_pech_lg_ms2032gas"
        pages = _lg_pages(sku, sulpak_url)
        out = {}
        with TemporaryDirectory() as tmp:
            lg_http = wrap(FixtureSession(pages), Path(tmp) / "l.json", ("www.lg.com",))
            sulpak_http = wrap(FixtureSession(pages), Path(tmp) / "l.json", ("www.sulpak.kz",))
            kz = LGAdapter(lg_http, clock=lambda: 0.0).find_source(sku, deadline=1e9)
            ru = LGRUAdapter(lg_http, clock=lambda: 0.0).find_source(sku, deadline=1e9)
            sp = SulpakAdapter(sulpak_http, clock=lambda: 0.0, urls={sku: sulpak_url}).find_source(sku, deadline=1e9)
        for key, doc in (("kz", kz), ("ru", ru), ("sulpak", sp)):
            out[key] = (doc.match_level, doc.url, doc.found_model, doc.error, [(a.name, a.value) for a in doc.attributes], list(doc.photos), doc.description)
        return out

    def test_kz_ru_and_sulpak_results_are_identical(self):
        bare = self.documents(lambda transport, log, hosts: transport)
        policy = self.documents(lambda transport, log, hosts: PolicyAwareSession(log, allowed_hosts=hosts, underlying=transport, min_interval_seconds=0.0, sleep=lambda _s: None))
        self.assertEqual(policy, bare)
        self.assertEqual(policy["kz"][0], "full_sku")
        self.assertEqual(policy["sulpak"][0], "full_sku")
        self.assertEqual((policy["ru"][0], policy["ru"][3]), ("mismatch", ""))  # Stage 21: the RU sitemap lists no page -> a miss, not an HTTP error

    def test_default_adapters_use_the_policy_session_and_keep_the_lg_headers(self):
        with TemporaryDirectory() as tmp:
            kz, ru, sulpak, browser_search = default_lg_adapters(Path(tmp), clock=lambda: 0.0)
            self.assertIs(kz.http, ru.http)
            self.assertIsInstance(kz.http, PolicyAwareSession)
            self.assertIsInstance(sulpak.http, PolicyAwareSession)
            self.assertEqual(kz.http.headers["User-Agent"], lg_session().headers["User-Agent"])
            self.assertEqual(kz.http.headers["Accept-Language"], "ru-RU,ru;q=0.9,en;q=0.7")
            self.assertEqual(kz.http.log_path, Path(tmp) / "lg_fetch_log.json")
            self.assertEqual(sulpak.http.log_path, kz.http.log_path)
            self.assertEqual(kz.http.request_count, 0)
            # Stage 43: the worker's real default wires a real LGBrowserSearch (same log) into both
            # adapters -- it never launches anything at construction time (lazy), only when a row's
            # sitemap lookup misses full_sku and .search() is actually called.
            self.assertIs(kz.browser_search, browser_search)
            self.assertIs(ru.browser_search, browser_search)
            self.assertEqual(browser_search.log_path, kz.http.log_path)


class WorkerDefaultPathStopsHostsAcrossRuns(unittest.TestCase):
    def run_row(self, database, sku, transport_pages):
        product = executor._ensure_product(database, {"catalog_row": hash(sku) % 10000 + 2, "brand": "LG", "category": "Микроволновые печи", "title": "t", "seller_sku": sku}, "b")
        jobs.enqueue(database, product, [1, 3, 4, 6])
        transports = []

        def build(directory, *, clock):
            lg, sulpak = FixtureSession(transport_pages), FixtureSession({})
            transports.append((lg, sulpak))
            # browser_search=False: this offline test must never launch a real browser subprocess, even
            # when a row's sitemap lookup misses full_sku and the Stage 43 fallback would otherwise fire.
            return default_lg_adapters(directory, clock=clock, underlying_lg=lg, underlying_sulpak=sulpak, browser_search=False)

        with patch.object(worker, "default_lg_adapters", build), patch("product_tool.adapters.policy_session._LAST_REQUEST_AT", [0.0]):
            with patch("product_tool.adapters.policy_session.time.sleep", lambda _s: None):
                worker.run_once(database, clock=lambda: 0.0, dns_adapter_factory=lambda: _NoDealer())
        return jobs.list_jobs(database, product)[0], transports[0]

    def test_a_403_in_one_run_keeps_lg_com_stopped_in_the_next_run(self):
        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "batches.sqlite3"
            jobs.initialize(database)
            job1, (lg1, _) = self.run_row(database, "MS2032GAS", {LG_KZ_SITEMAP: (403, "blocked")})
            self.assertEqual(lg1.calls, [LG_KZ_SITEMAP])  # one request; the LG RU lookup and the retry found the host stopped
            log = json.loads((Path(tmp) / "lg_fetch_log.json").read_text(encoding="utf-8"))
            self.assertEqual([e["status_code"] for e in log], [403])
            job2, (lg2, _) = self.run_row(database, "MS2032GAS2", {LG_KZ_SITEMAP: (200, "<urlset></urlset>")})
            self.assertEqual(lg2.calls, [])  # a new run, a new adapter set: no request to lg.com at all
            self.assertIn(job2["status"], {"error", "needs_review"})
            self.assertIn(STOPPED, "".join(s["error"] for s in jobs.get_source_pages(database, job2["product_id"])))

    def test_the_default_worker_path_really_uses_the_policy_adapters(self):
        source = Path(worker.__file__).read_text(encoding="utf-8")
        self.assertIn("default_lg_adapters(database.parent,clock=clock)", source)
        self.assertNotIn("LGAdapter(clock=clock)", source)


class _NoDealer:
    source_key, site_name, document_urls = "dns", "DNS", {}

    def find_source(self, *a, **k):
        from product_tool.adapters.common import SourceDocument
        return SourceDocument("dns", "DNS", "", match_level="unknown")

    def find_documents(self, *a, **k):
        return [], "-"


class PlannerReadsTheLgLog(unittest.TestCase):
    def test_the_lg_fetch_log_is_a_host_stop_source_for_the_planner(self):
        self.assertIn("data/lg_fetch_log.json", load_config()["host_stop_logs"]["runtime_optional"])


if __name__ == "__main__":
    unittest.main()
