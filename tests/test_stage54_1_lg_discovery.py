"""Offline Stage 54.1 discovery, identity, trace, and evidence lifecycle regression."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3
import unittest

from bs4 import BeautifulSoup

from product_tool import discovery_trace, jobs, lg_discovery_pipeline, worker
from product_tool.adapters.common import PhotoCandidate, RawAttribute, SourceDocument
from product_tool.adapters.lg_browser_search import (
    BrowserCandidate, BrowserSearchResult, LGBrowserSearch,
)
from product_tool.adapters.lg_global import _own_model, official_product_url
from product_tool.adapters.lg_support import LGSupportAdapter
from product_tool.census.browser_runtime import BrowserFailure, BrowserRuntime
from tests.test_lg_browser_search import FakeDriver, _fragments_state

UK_URL = "https://www.lg.com/uk/microwaves/solo/ms2082f/"
AVAILABLE = BrowserRuntime(True, python="fake", runtime_version="fake", browser_version="fake")


class Stage541DiscoveryTests(unittest.TestCase):
    def test_queries_cover_kit_components_base_and_spaced_model(self):
        self.assertEqual(LGBrowserSearch.google_queries("P12ED.NSAR + P12ED.USAR"), (
            'site:lg.com "P12ED.NSAR"', 'site:lg.com "P12ED.USAR"', 'site:lg.com "P12ED"'))
        self.assertEqual(LGBrowserSearch.google_queries("MS2082F", descriptive_name="LG MS 2082 F"), (
            'site:lg.com "MS2082F"', 'site:lg.com "MS 2082 F"'))
        self.assertEqual(LGBrowserSearch.google_queries("S40T"), ('site:lg.com "S40T"',))

    def test_google_uses_existing_browser_and_traces_result_without_identity_upgrade(self):
        query = 'site:lg.com "MS2082F"'
        from urllib.parse import quote
        search_url = "https://www.google.com/search?q=" + quote(query) + "&hl=en"
        state = _fragments_state(search_url, [(UK_URL, "LG MS2082F microwave"),
                                              ("https://example.test/p/ms2082f", "dealer")])
        holder = {}
        def factory(*args):
            holder["driver"] = FakeDriver(*args, states={search_url: state})
            return holder["driver"]
        with TemporaryDirectory() as temp:
            browser = LGBrowserSearch(Path(temp) / "fetch.json", runtime=AVAILABLE,
                                      driver_factory=factory)
            events = []
            browser.trace_callback = events.append
            result = browser.search_google(query)
            browser.close()
        self.assertEqual(result.outcome, "candidates_found")
        self.assertEqual([(c.url, c.kind, c.position) for c in result.candidates],
                         [(UK_URL, "product", 1)])
        self.assertEqual(holder["driver"].calls[0][1]["search_result_hosts"], ["www.lg.com"])
        self.assertTrue(any(event.get("event") == "result" and event.get("url") == UK_URL
                            and event.get("decision") == "candidate" for event in events))
        self.assertFalse(any(event.get("identity") == "exact" for event in events))

    def test_google_429_is_rate_limit_and_replay_does_not_reissue_request(self):
        from urllib.parse import quote
        from product_tool.adapters.policy_fetch import read_log
        query = 'site:lg.com "MS2082F"'
        search_url = "https://www.google.com/search?q=" + quote(query) + "&hl=en"
        with TemporaryDirectory() as temp:
            log = Path(temp) / "fetch.json"
            states = {search_url: BrowserFailure("rate_limited", {"rate_limit_url": search_url})}
            search = LGBrowserSearch(log, runtime=AVAILABLE,
                driver_factory=lambda *args: FakeDriver(*args, states=states))
            outcome = search.search_google(query)
            search.close()
            self.assertEqual(outcome.outcome, "rate_limited")
            self.assertEqual(read_log(log)[-1]["reason"], "rate_limit")
            cached = BrowserSearchResult("global", query, "candidates_found",
                (BrowserCandidate(UK_URL, "product", "LG MS2082F", 1, query,
                                  "google_browser", "20 litre oven"),))
            replay = LGBrowserSearch(log, runtime=AVAILABLE,
                driver_factory=lambda *args: self.fail("cached result must not navigate"),
                preloaded_google_results={query: cached})
            events = []
            replay.trace_callback = events.append
            self.assertEqual(replay.search_google(query), cached)
            self.assertEqual(events[1]["snippet"], "20 litre oven")
            self.assertEqual(events[1]["position"], 1)
            replay.close()
            # The attended transport already wrote the exact 429 response URL.
            # Search must not append a second entry guessed from the query URL.
            already_log = Path(temp) / "already.json"
            already_recorded = LGBrowserSearch(already_log, runtime=AVAILABLE,
                driver_factory=lambda *args: FakeDriver(*args, states={
                    search_url: BrowserFailure("rate_limited", {
                        "rate_limit_url": "https://www.google.com/sorry/",
                        "rate_limit_recorded": True})}))
            self.assertEqual(already_recorded.search_google(query).outcome, "rate_limited")
            already_recorded.close()
            self.assertEqual(read_log(already_log), [])

    def test_global_product_needs_own_page_identity(self):
        self.assertTrue(official_product_url(UK_URL))
        self.assertFalse(official_product_url("https://www.lg.com.evil.test/uk/microwaves/solo/ms2082f/"))
        self.assertFalse(official_product_url("https://www.lg.com/uk/support/product/ms2082f/"))
        html = BeautifulSoup('<h1>LG 20L Solo Microwave MS2082F</h1>', "html.parser")
        self.assertEqual(_own_model(html, UK_URL, "MS2082F")[:2], ("MS2082F", "full_sku"))
        self.assertNotEqual(_own_model(html, UK_URL, "MS2082F.ARUG")[1], "full_sku")
        wrong = BeautifulSoup('<h1>MS2082F related</h1><div class="GPC0009" '
                              'data-adobe-salesmodelcode="MS2044V" data-adobe-salessuffixcode="A"></div>',
                              "html.parser")
        self.assertEqual(_own_model(wrong, UK_URL, "MS2082F")[1], "unknown")
        kit = BeautifulSoup('<h1>LG P12ED</h1>', "html.parser")
        self.assertNotEqual(_own_model(kit, "https://www.lg.com/uk/air-conditioners/p12ed/",
                                        "P12ED.NSAR + P12ED.USAR")[1], "full_sku")

    def test_rejected_first_three_do_not_hide_fourth_exact_candidate(self):
        wrong = [f"https://www.lg.com/uk/microwaves/solo/ms2044v{i}/" for i in range(3)]
        candidates = tuple(BrowserCandidate(url, "product", "result", i + 1,
                                            'site:lg.com "MS2082F"', "google_browser")
                           for i, url in enumerate([*wrong, UK_URL]))
        class FakeBrowser:
            def __init__(self): self.events = []
            def google_queries(self, article, **kwargs): return ('site:lg.com "MS2082F"',)
            def search_google(self, query): return BrowserSearchResult("global", query, "candidates_found", candidates)
            def _trace(self, **event): self.events.append(event)
        class FakeGlobal:
            def fetch_candidate(self, url, article, **kwargs):
                return SourceDocument("lg_global", "LG UK", url,
                                      found_model=article if url == UK_URL else "",
                                      match_level="full_sku" if url == UK_URL else "unknown")
        browser = FakeBrowser()
        with patch.object(jobs, "save_source_document") as save:
            outcome = lg_discovery_pipeline.run_google_fallback(
                Path("unused.sqlite3"), "job", 1, "MS2082F", "", browser,
                kz=None, ru=None, global_adapter=FakeGlobal(), deadline=100,
                stages=[1, 2, 3, 4], clock=lambda: 0)
        self.assertEqual(outcome.product_document.url, UK_URL)
        self.assertEqual(save.call_count, 1)
        self.assertEqual([e["decision"] for e in browser.events],
                         ["rejected", "rejected", "rejected", "accepted"])
        self.assertTrue(all(e["opened"] for e in browser.events))

    def test_support_adapter_reaches_fourth_after_three_other_codes(self):
        urls = tuple(f"https://www.lg.com/ru/support/product/lg-MODEL{i}" for i in range(4))
        pages = {url: f'<div data-product-id="OTHER{i}"></div>' for i, url in enumerate(urls[:3])}
        pages[urls[3]] = '<div data-product-id="MODEL4"></div>'
        adapter = LGSupportAdapter(candidate_urls=urls, candidate_pages=pages, clock=lambda: 0)
        decisions = []
        adapter.decision_callback = lambda *args: decisions.append(args)
        result = adapter.find_source("MODEL4", deadline=10)
        self.assertEqual(result.match_level, "full_sku")
        self.assertEqual(result.url, urls[3])
        self.assertEqual([item[3] for item in decisions],
                         ["rejected", "rejected", "rejected", "accepted"])

    def test_run_once_uses_global_candidate_after_regional_misses(self):
        with TemporaryDirectory() as temp:
            database = Path(temp) / "jobs.sqlite3"
            jobs.initialize(database)
            connection = sqlite3.connect(database)
            try:
                connection.execute("INSERT INTO batches VALUES ('b','file.xlsx','Items','{}','2026-01-01')")
                product_id = connection.execute(
                    "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
                    "VALUES ('b',2,'Microwave','LG','MS2082F','','Microwave',0,'[]','{}')").lastrowid
                connection.commit()
            finally:
                connection.close()
            jobs.enqueue(database, product_id, [1, 3, 4])
            class EmptyOfficial:
                def __init__(self, key):
                    self.source_key, self.site_name = key, key
                def find_source(self, *args, **kwargs):
                    return SourceDocument(self.source_key, self.site_name, "",
                                          match_level="mismatch")
            class EmptyDealer(EmptyOfficial):
                pass
            class FakeBrowser:
                def __init__(self): self.trace_callback = None; self.queries = []
                def google_queries(self, article, **kwargs):
                    return LGBrowserSearch.google_queries(article, **kwargs)
                def search_google(self, query):
                    self.queries.append(query)
                    return BrowserSearchResult("global", query, "candidates_found",
                        (BrowserCandidate(UK_URL, "product", "MS2082F", 1, query, "google_browser"),))
                def _trace(self, **event):
                    if self.trace_callback:
                        from datetime import datetime, timezone
                        self.trace_callback({"timestamp": datetime.now(timezone.utc).isoformat(), **event})
                def close(self): pass
            class FakeGlobal:
                def fetch_candidate(self, url, article, **kwargs):
                    return SourceDocument("lg_global", "LG UK", url, found_model=article,
                                          match_level="full_sku",
                                          attributes=[RawAttribute("Capacity", "20 L")],
                                          photo_candidates=[PhotoCandidate("https://www.lg.com/uk/a.jpg", "a", "product_gallery")])
            class FakeDNS:
                def find_source(self, *args, **kwargs):
                    return SourceDocument("dns", "DNS", "", match_level="dealer_url_needed")
            browser = FakeBrowser()
            self.assertTrue(worker.run_once(database,
                lambda: (EmptyOfficial("lg_kz"), EmptyOfficial("lg_ru"), EmptyDealer("sulpak"), browser),
                lg_global_adapter_factory=FakeGlobal, dns_adapter_factory=FakeDNS,
                clock=lambda: 0))
            self.assertTrue(browser.queries)
            pages = jobs.get_source_pages(database, product_id)
            self.assertEqual(next(p for p in pages if p["source_key"] == "lg_global")["match_level"], "full_sku")
            self.assertEqual(len([e for e in discovery_trace.for_job(database,
                jobs.list_jobs(database, product_id)[0]["id"]) if e.get("decision") == "accepted"]), 1)

            connection = sqlite3.connect(database)
            try:
                soundbar_id = connection.execute(
                    "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
                    "VALUES ('b',3,'Soundbar','LG','S40T','','Audio',0,'[]','{}')").lastrowid
                connection.commit()
            finally:
                connection.close()
            jobs.enqueue(database, soundbar_id, [1, 3, 4])
            class ExactOfficial(EmptyOfficial):
                def find_source(self, *args, **kwargs):
                    return SourceDocument(self.source_key, self.site_name,
                        "https://www.lg.com/kz/speakers/soundbars/s40t/",
                        found_model="S40T", match_level="full_sku",
                        attributes=[RawAttribute("Power", "100 W")])
            before = len(browser.queries)
            self.assertTrue(worker.run_once(database,
                lambda: (ExactOfficial("lg_kz"), EmptyOfficial("lg_ru"),
                         EmptyDealer("sulpak"), browser),
                lg_global_adapter_factory=FakeGlobal, dns_adapter_factory=FakeDNS,
                clock=lambda: 0))
            self.assertEqual(len(browser.queries), before)
            # A later network miss must not turn this already verified KZ page
            # into an unnecessary Google search.
            jobs.enqueue(database, soundbar_id, [1, 3, 4])
            self.assertTrue(worker.run_once(database,
                lambda: (EmptyOfficial("lg_kz"), EmptyOfficial("lg_ru"),
                         EmptyDealer("sulpak"), browser),
                lg_global_adapter_factory=FakeGlobal, dns_adapter_factory=FakeDNS,
                clock=lambda: 0))
            self.assertEqual(len(browser.queries), before)
            self.assertEqual(next(page for page in jobs.get_source_pages(database, soundbar_id)
                                  if page["source_key"] == "lg_kz")["match_level"], "full_sku")
            latest = jobs.list_jobs(database, soundbar_id)[0]["id"]
            self.assertTrue(any(event.get("event") == "provider_skip" and
                                event.get("reason") == "exact_kz_ru_product_page_present"
                                for event in discovery_trace.for_job(database, latest)))

    def test_trace_and_exact_evidence_survive_weaker_refresh(self):
        with TemporaryDirectory() as temp:
            database = Path(temp) / "jobs.sqlite3"
            jobs.initialize(database)
            connection = sqlite3.connect(database)
            try:
                connection.execute("INSERT INTO batches VALUES ('b','file.xlsx','Items','{}','2026-01-01')")
                product_id = connection.execute(
                    "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
                    "VALUES ('b',2,'Microwave','LG','MS2082F','','Microwave',0,'[]','{}')").lastrowid
                connection.execute("INSERT INTO search_jobs(id,product_id,stages_json,status,message,created_at,updated_at) "
                                   "VALUES ('job',?,'[1,3,4]','done','','2026-01-01','2026-01-01')", (product_id,))
                connection.commit()
            finally:
                connection.close()
            discovery_trace.initialize(database)
            event = {"event":"result", "timestamp":"2026-01-01T00:00:00Z", "provider":"google_browser",
                     "query":'site:lg.com "MS2082F"', "position":1, "title":"LG MS2082F",
                     "snippet":"", "url":UK_URL, "domain":"www.lg.com", "region":"uk",
                     "candidate_type":"product", "opened":False, "decision":"candidate"}
            discovery_trace.record(database, "job", product_id, event)
            discovery_trace.initialize(database)
            self.assertEqual(discovery_trace.for_job(database, "job"), [event])
            exact = SourceDocument("lg_global", "LG UK", UK_URL,
                                   found_model="MS2082F", match_level="full_sku",
                                   attributes=[RawAttribute("Capacity", "20 L")],
                                   photo_candidates=[PhotoCandidate("https://www.lg.com/uk/a.jpg", "a", "product_gallery")])
            jobs.save_source_document(database, product_id, exact,
                                      update_description=True, update_attributes=True, update_photos=True)
            weak = SourceDocument("lg_global", "LG UK", UK_URL,
                                  found_model="MS2082F", match_level="base_model")
            jobs.save_source_document(database, product_id, weak,
                                      update_description=True, update_attributes=True, update_photos=True)
            page = next(x for x in jobs.get_source_pages(database, product_id) if x["source_key"] == "lg_global")
            self.assertEqual(page["match_level"], "full_sku")
            self.assertEqual(len([x for x in jobs.get_facts(database, product_id)
                                  if x["source_key"] == "lg_global"]), 1)
            self.assertEqual(len([x for x in jobs.get_photo_candidates(database, product_id)
                                  if x["source_key"] == "lg_global"]), 1)
            del page
            import gc
            gc.collect()


if __name__ == "__main__":
    unittest.main()
