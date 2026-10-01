"""Stage 54.4 official LG sitemap discovery and validation contracts."""
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from product_tool.lg_sitemap_discovery import (LGOfficialSitemapDiscovery,
    ROBOTS_URL, model_keys, normalized_slug, parse_sitemap)
from product_tool.lg_discovery_pipeline import run_sitemap_fallback
from product_tool.adapters.common import SourceDocument

ROOT = 'https://www.lg.com/sitemap.xml'
REGION = 'https://www.lg.com/uk/uk-index.xml'
LEAF = 'https://www.lg.com/uk/sitemap.xml'
PDP = 'https://www.lg.com/uk/microwaves/solo/zx123/'

def xml(kind, urls):
    tag = 'sitemap' if kind == 'sitemapindex' else 'url'
    return ('<' + kind + ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
            ''.join('<' + tag + '><loc>' + u + '</loc></' + tag + '>' for u in urls) +
            '</' + kind + '>').encode()

class Response:
    def __init__(self, content, status=200):
        self.content = content
        self.text = content.decode()
        self.status_code = status
        self.ok = status == 200
        self.truncated = False

class HTTP:
    def __init__(self, leaf=None, broken=False):
        self.mapping = {ROBOTS_URL: b'User-agent: *\nSitemap: ' + ROOT.encode(),
                        ROOT: xml('sitemapindex', [REGION]),
                        REGION: xml('sitemapindex', [LEAF]),
                        LEAF: leaf if leaf is not None else xml('urlset', [PDP])}
        if broken:
            self.mapping[LEAF] = b'<bad>'
        self.calls = []
    def get(self, url, timeout):
        self.calls.append(url)
        return Response(self.mapping[url])

class SitemapTest(unittest.TestCase):
    def discover(self, article='ZX123', leaf=None, broken=False):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        http = HTTP(leaf, broken)
        events = []
        discovery = LGOfficialSitemapDiscovery(http, Path(tmp.name), clock=lambda: 0,
                                               wall_clock=lambda: 100, trace_callback=events.append)
        return discovery, http, events, discovery.discover(article, deadline=100)

    def test_exact_token_from_official_chain_and_kz_ru_miss(self):
        discovery, http, events, found = self.discover()
        self.assertEqual([x.url for x in found], [PDP])
        self.assertEqual(http.calls, [ROBOTS_URL, ROOT, REGION, LEAF])
        self.assertEqual(found[0].chain, (ROBOTS_URL, ROOT, REGION, LEAF))
        self.assertEqual(found[0].matched_key, 'zx123')

    def test_wrong_model_rejected(self):
        self.assertFalse(self.discover('ZX124')[3])

    def test_family_base_only_is_candidate_not_exact(self):
        leaf = xml('urlset', ['https://www.lg.com/uk/microwaves/solo/zx123/'])
        found = self.discover('ZX123.ABC', leaf)[3]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].matched_key, 'zx123')

    def test_support_url_is_not_product(self):
        leaf = xml('urlset', ['https://www.lg.com/uk/support/product/zx123/'])
        self.assertFalse(self.discover(leaf=leaf)[3])

    def test_cache_reuse(self):
        discovery, http, _, first = self.discover()
        self.assertEqual(len(first), 1)
        second = LGOfficialSitemapDiscovery(http, discovery.cache_dir, clock=lambda: 0,
                                            wall_clock=lambda: 101).discover('ZX123', deadline=100)
        self.assertEqual(second, first)
        self.assertEqual(len(http.calls), 4)

    def test_broken_leaf_does_not_raise(self):
        discovery, _, events, found = self.discover(broken=True)
        self.assertFalse(found)
        self.assertTrue(any(e.get('outcome') == 'failed' for e in events))

    def test_broken_sitemap_continues_to_next_leaf(self):
        extra = 'https://www.lg.com/uk/product.xml'
        http = HTTP(broken=True)
        http.mapping[REGION] = xml('sitemapindex', [LEAF, extra])
        http.mapping[extra] = xml('urlset', [PDP])
        with TemporaryDirectory() as temp:
            discovery = LGOfficialSitemapDiscovery(http, Path(temp), clock=lambda: 0,
                                                   wall_clock=lambda: 100)
            found = discovery.discover('ZX123', deadline=100)
        self.assertEqual([candidate.url for candidate in found], [PDP])
        self.assertEqual(found[0].sitemap_url, extra)

    def test_network_request_budget(self):
        with TemporaryDirectory() as temp:
            http = HTTP()
            discovery = LGOfficialSitemapDiscovery(http, Path(temp), clock=lambda: 0,
                                                   wall_clock=lambda: 100, max_requests=3)
            self.assertFalse(discovery.discover('ZX123', deadline=100))
            self.assertEqual(http.calls, [ROBOTS_URL, ROOT, REGION])

    def test_cache_ttl_reloads(self):
        with TemporaryDirectory() as temp:
            http = HTTP()
            first = LGOfficialSitemapDiscovery(http, Path(temp), clock=lambda: 0,
                                               wall_clock=lambda: 100)
            self.assertTrue(first.discover('ZX123', deadline=100))
            later = LGOfficialSitemapDiscovery(http, Path(temp), clock=lambda: 0,
                                               wall_clock=lambda: 100 + 24 * 60 * 60 + 1)
            self.assertTrue(later.discover('ZX123', deadline=100))
            self.assertEqual(len(http.calls), 8)
    def test_gzip_and_size_limit(self):
        kind, locs = parse_sitemap(gzip.compress(xml('urlset', [PDP])), LEAF + '.gz')
        self.assertEqual((kind, locs), ('urlset', [PDP]))
        from product_tool import lg_sitemap_discovery as module
        with patch.object(module, 'MAX_XML_BYTES', 20):
            with self.assertRaises(ValueError):
                parse_sitemap(gzip.compress(xml('urlset', [PDP])), LEAF + '.gz')

    def test_case_insensitive_lookup(self):
        self.assertEqual(normalized_slug(PDP.upper()), 'zx123')
        self.assertEqual(model_keys('zX123'), ('zx123',))

    def test_no_model_specific_url_in_implementation(self):
        source = Path('product_tool/lg_sitemap_discovery.py').read_text(encoding='utf-8').lower()
        self.assertNotIn('ms2082f', source)
        self.assertNotIn('p12ed', source)
        self.assertNotIn('s40t', source)

    def test_exact_validation_persists_and_skips_web_gate(self):
        discovery, _, events, found = self.discover()
        doc = SourceDocument('lg_global', 'LG UK', PDP, found_model='ZX123',
                             match_level='full_sku', evidence='main product h1',
                             attributes=[('Power', '700 W')])
        class Global:
            def fetch_candidate(self, url, article, deadline):
                return doc
        with patch('product_tool.lg_discovery_pipeline.jobs.save_source_document') as save:
            result = run_sitemap_fallback(Path('unused'), 'job', 1, 'ZX123', discovery,
                                          kz=None, ru=None, global_adapter=Global(),
                                          deadline=100, stages=[1, 2, 3, 4], clock=lambda: 0)
        self.assertIs(result.product_document, doc)
        save.assert_called_once()
        self.assertTrue(any(e.get('event') == 'sitemap_validation' and e.get('decision') == 'accepted' for e in events))

    def test_base_only_document_rejected(self):
        discovery, _, events, _ = self.discover('ZX123.ABC')
        class Global:
            def fetch_candidate(self, url, article, deadline):
                return SourceDocument('lg_global', 'LG UK', url, match_level='base_model')
        with patch('product_tool.lg_discovery_pipeline.jobs.save_source_document') as save:
            result = run_sitemap_fallback(Path('unused'), 'job', 1, 'ZX123.ABC', discovery,
                                          kz=None, ru=None, global_adapter=Global(),
                                          deadline=100, stages=[1, 2, 3, 4], clock=lambda: 0)
        self.assertIsNone(result.product_document)
        save.assert_not_called()
        self.assertTrue(any(e.get('event') == 'sitemap_validation' and e.get('decision') == 'rejected' for e in events))

if __name__ == '__main__':
    unittest.main()

class WorkerOrderingTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'jobs.sqlite3'
        from product_tool import jobs
        jobs.initialize(self.database)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("INSERT INTO batches VALUES ('b','file.xlsx','Items','{}','2026-01-01')")
            self.pid = db.execute(
                "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
                "VALUES ('b',2,'Appliance','LG','ZX123','','Appliance',0,'[]','{}')").lastrowid
            db.commit()
        jobs.enqueue(self.database, self.pid, [1,3,4])

    def run_worker(self, exact=False, sitemap_doc=None):
        from product_tool import worker, lg_discovery_pipeline
        class Official:
            def __init__(self, key): self.source_key = self.site_name = key
            def find_source(self, *args, **kwargs):
                return SourceDocument(self.source_key, self.site_name,
                    'https://www.lg.com/kz/appliances/zx123/' if exact and self.source_key == 'lg_kz' else '',
                    match_level='full_sku' if exact and self.source_key == 'lg_kz' else 'mismatch')
        class Browser:
            def __init__(self): self.trace_callback = None
            def search_google(self, *args): raise AssertionError('web search must be mocked')
            def _trace(self, **event): pass
            def close(self): pass
        class DNS:
            def find_source(self, *args, **kwargs):
                return SourceDocument('dns','DNS','',match_level='dealer_url_needed')
        from product_tool.lg_discovery_pipeline import SitemapFallbackOutcome, GoogleFallbackOutcome
        with patch.object(lg_discovery_pipeline, 'run_sitemap_fallback',
                          return_value=SitemapFallbackOutcome(sitemap_doc)) as sitemap, \
             patch.object(lg_discovery_pipeline, 'run_web_fallback',
                          return_value=GoogleFallbackOutcome()) as web:
            worker.run_once(self.database,
                adapter_factory=lambda: (Official('lg_kz'),Official('lg_ru'),Official('sulpak'),Browser()),
                lg_sitemap_discovery_factory=lambda: object(),
                dns_adapter_factory=DNS, clock=lambda: 0)
            return sitemap.call_count, web.call_count

    def test_regional_exact_skips_sitemap_and_web(self):
        self.assertEqual(self.run_worker(exact=True), (0,0))

    def test_sitemap_exact_skips_web(self):
        doc = SourceDocument('lg_global','LG UK',PDP,found_model='ZX123',match_level='full_sku')
        self.assertEqual(self.run_worker(sitemap_doc=doc), (1,0))

    def test_sitemap_miss_runs_web(self):
        self.assertEqual(self.run_worker(), (1,1))



if __name__ == '__main__':
    unittest.main()
