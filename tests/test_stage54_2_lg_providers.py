"""Stage 54.2 sequential provider and official identity regression."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from product_tool import jobs, lg_discovery_pipeline
from product_tool.adapters.access_stop import RATE_LIMIT
from product_tool.adapters.common import SourceDocument
from product_tool.adapters.lg_browser_search import (
    BrowserCandidate, BrowserSearchResult, LGBrowserSearch,
)
from product_tool.adapters.policy_fetch import record_stop
from product_tool.census.browser_runtime import BrowserRuntime
from tests.test_lg_browser_search import FakeDriver, _fragments_state

QUERY = 'site:lg.com "ZZ1000"'
URL = 'https://www.lg.com/uk/appliances/zz1000/'
WRONG = 'https://www.lg.com/uk/appliances/other/'
SUPPORT = 'https://www.lg.com/ru/support/product/lg-ZZ1000'
AVAILABLE = BrowserRuntime(True, python='fake', browser_version='fake')


class FakeSearch:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []
        self.events = []

    def provider_queries(self, article, **kwargs):
        return (QUERY,)

    def search_provider(self, provider, query):
        self.calls.append((provider, query))
        return self.outcomes.get(provider, BrowserSearchResult('global', query, 'no_candidates'))

    def search_google(self, query):
        return self.search_provider('google', query)

    def _trace(self, **event):
        self.events.append(event)


class FakeGlobal:
    def __init__(self, levels):
        self.levels = levels
        self.calls = []

    def fetch_candidate(self, url, article, **kwargs):
        self.calls.append(url)
        return SourceDocument('lg_global', 'LG UK', url, found_model=article,
                              match_level=self.levels.get(url, 'unknown'))


def result(provider, *entries):
    candidates = tuple(BrowserCandidate(url, kind, title, position, QUERY,
                                        provider + '_browser')
                       for position, (url, kind, title) in enumerate(entries, 1))
    return BrowserSearchResult('global', QUERY,
                               'candidates_found' if candidates else 'no_candidates', candidates)


class ProviderFallbackTests(unittest.TestCase):
    def run_pipeline(self, search, global_adapter, article='ZZ1000'):
        with patch.object(jobs, 'save_source_document') as save:
            outcome = lg_discovery_pipeline.run_google_fallback(
                Path('unused.sqlite3'), 'job', 1, article, '', search,
                kz=None, ru=None, global_adapter=global_adapter,
                deadline=100, stages=[1, 2, 3, 4], clock=lambda: 0)
        return outcome, save

    def test_google_429_moves_to_bing_and_exact_stops_before_ddg(self):
        search = FakeSearch({
            'google': BrowserSearchResult('global', QUERY, 'rate_limited'),
            'bing': result('bing', (URL, 'product', 'Official ZZ1000')),
        })
        outcome, save = self.run_pipeline(search, FakeGlobal({URL: 'full_sku'}))
        self.assertEqual(outcome.product_document.url, URL)
        self.assertEqual([provider for provider, _ in search.calls], ['google', 'bing'])
        self.assertEqual(save.call_count, 1)
        self.assertEqual(search.events[-1]['provider'], 'bing_browser')
        self.assertEqual(search.events[-1]['decision'], 'accepted')

    def test_google_challenge_moves_to_next_provider(self):
        search = FakeSearch({
            'google': BrowserSearchResult('global', QUERY, 'challenge_detected'),
            'bing': result('bing', (URL, 'product', 'Official ZZ1000')),
        })
        outcome, _ = self.run_pipeline(search, FakeGlobal({URL: 'full_sku'}))
        self.assertEqual(outcome.product_document.match_level, 'full_sku')
        self.assertEqual([p for p, _ in search.calls], ['google', 'bing'])

    def test_bing_wrong_model_does_not_hide_next_exact_result(self):
        search = FakeSearch({
            'google': BrowserSearchResult('global', QUERY, 'host_stopped'),
            'bing': result('bing', (WRONG, 'product', 'Other'),
                           (URL, 'product', 'ZZ1000')),
        })
        global_adapter = FakeGlobal({WRONG: 'unknown', URL: 'full_sku'})
        outcome, save = self.run_pipeline(search, global_adapter)
        self.assertEqual(global_adapter.calls, [WRONG, URL])
        self.assertEqual(outcome.product_document.url, URL)
        self.assertEqual([e['decision'] for e in search.events if e.get('opened')],
                         ['rejected', 'accepted'])
        self.assertEqual(save.call_count, 1)

    def test_family_page_cannot_upgrade_variant_kit(self):
        search = FakeSearch({'bing': result('bing', (URL, 'product', 'ZZ1000 family'))})
        outcome, _ = self.run_pipeline(search, FakeGlobal({URL: 'base_model'}),
                                       'ZZ1000.NSAR + ZZ1000.USAR')
        self.assertEqual(outcome.product_document.match_level, 'base_model')
        self.assertFalse(any(e.get('decision') == 'accepted' for e in search.events))

    def test_support_page_does_not_replace_product_page(self):
        search = FakeSearch({'bing': result('bing', (SUPPORT, 'support', 'ZZ1000 support'))})
        outcome, save = self.run_pipeline(search, FakeGlobal({}))
        self.assertIsNone(outcome.product_document)
        self.assertEqual(outcome.support_urls, (SUPPORT,))
        save.assert_not_called()

    def test_provider_stop_is_host_specific(self):
        from urllib.parse import quote
        bing_url = 'https://www.bing.com/search?q=' + quote(QUERY)
        with TemporaryDirectory() as temp:
            log = Path(temp) / 'fetch.json'
            record_stop(log, 'www.google.com', RATE_LIMIT)
            factory = lambda *args: FakeDriver(*args, states={
                bing_url: _fragments_state(bing_url, [(URL, 'Official ZZ1000')])})
            search = LGBrowserSearch(log, runtime=AVAILABLE, driver_factory=factory)
            self.assertEqual(search.search_provider('google', QUERY).outcome, 'host_stopped')
            self.assertEqual(search.search_provider('bing', QUERY).outcome, 'candidates_found')
            search.close()

    def test_provider_subdomain_stop_blocks_only_that_provider(self):
        with TemporaryDirectory() as temp:
            log = Path(temp) / 'fetch.json'
            record_stop(log, 'r.bing.com', RATE_LIMIT)
            search = LGBrowserSearch(log, runtime=AVAILABLE,
                driver_factory=lambda *args: self.fail('Bing must not navigate'))
            self.assertEqual(search.search_provider('bing', QUERY).outcome, 'host_stopped')
            self.assertFalse(search._host_stopped('www.google.com'))
            self.assertFalse(search._host_stopped('duckduckgo.com'))
            search.close()

    def test_broad_query_only_after_zero_candidates_for_single_model(self):
        broad = 'site:lg.com ZZ1000 LG'
        class TwoQueries(FakeSearch):
            def provider_queries(self, article, **kwargs):
                return (QUERY, broad)
        search = TwoQueries({
            'google': BrowserSearchResult('global', QUERY, 'host_stopped'),
            'bing': result('bing', (WRONG, 'product', 'Wrong model')),
        })
        self.run_pipeline(search, FakeGlobal({WRONG: 'unknown'}))
        self.assertNotIn(('bing', broad), search.calls)

        class BroaderResult(TwoQueries):
            def search_provider(self, provider, query):
                self.calls.append((provider, query))
                if provider == 'google':
                    return BrowserSearchResult('global', query, 'host_stopped')
                if provider == 'bing' and query == broad:
                    return result('bing', (URL, 'product', 'ZZ1000'))
                return BrowserSearchResult('global', query, 'no_candidates')
        search = BroaderResult({})
        outcome, _ = self.run_pipeline(search, FakeGlobal({URL: 'full_sku'}))
        self.assertEqual(outcome.product_document.url, URL)
        self.assertIn(('bing', broad), search.calls)
        self.assertFalse(any(provider == 'duckduckgo' for provider, _ in search.calls))

    def test_query_plan_is_bounded_and_uses_no_known_product_url(self):
        queries = LGBrowserSearch.provider_queries('ZZ1000')
        self.assertEqual(queries, (QUERY, 'site:lg.com ZZ1000 LG'))
        self.assertLessEqual(len(queries), 3)
        for source in ('product_tool/adapters/lg_browser_search.py',
                       'product_tool/lg_discovery_pipeline.py',
                       'product_tool/census/browser_projection.js'):
            text = Path(source).read_text(encoding='utf-8')
            self.assertNotIn('MS2082F', text)
            self.assertNotIn('P12ED.NSAR', text)


if __name__ == '__main__':
    unittest.main()
