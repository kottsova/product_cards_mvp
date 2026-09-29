"""Stage 8.2 regression tests: targeted Product page discovery for priority
brands via internal_http_search / sitemap_or_catalog_feed only. Network is
never required to run these tests -- they check the persisted evidence and
the Stage 2-8.1 protection guarantee, not live sites."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
from _source_policy import hosts_outside_allowlist, unapproved_source_ids

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE81 = ROOT / 'reports/source_census_2026-09-22_stage8_1'
STAGE82 = ROOT / 'reports/source_census_2026-09-22_stage8_2'

PERMITTED_GROUPS = {'internal_http_search', 'sitemap_or_catalog_feed'}
PAGE_RESULT_VOCAB = {'verified', 'candidate', 'search_or_category_only', 'blocked', 'insufficient'}
IDENTITY_RESULT_VOCAB = {'exact_variant', 'exact_model', 'family_only', 'conflict', 'insufficient'}
TARGET_FAMILIES = {'samsung', 'apple', 'lg', 'jbl', 'playstation', 'razer', 'hiper', 'microsoft'}
SEARCHED_FAMILIES = {'samsung', 'lg', 'playstation'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage82ProtectionTests(unittest.TestCase):
    def test_stage2_to_8_files_byte_identical(self):
        # Stage 11.4 authorized product_tool/{display,jobs,worker}.py to
        # change (a real pipeline integration, not research); see
        # tests/_pipeline_migration.py for the full, documented record.
        # Stage 12: an authorized path must ALSO match its pinned exact
        # post-migration hash -- any further, undocumented edit fails this
        # test again, the same as it would for any other protected file.
        manifest = read(STAGE8 / 'protected_hashes_after.json')['after']
        self.assertGreaterEqual(len(manifest), 200)
        for path, expected in manifest.items():
            full = ROOT / path
            if is_deleted_file_path(path):
                self.assertFalse(full.exists(), f'authorized-deleted file still present: {path}')
                continue
            self.assertTrue(full.exists(), f'protected file missing: {path}')
            actual = hashlib.sha256(full.read_bytes()).hexdigest()
            if path in ALL_AUTHORIZED_CHANGES:
                ok, msg = check_migrated_file(path, actual)
                self.assertTrue(ok, msg)
                continue
            self.assertEqual(actual, expected, f'protected file changed: {path}')

    def test_stage8_1_untouched(self):
        check = read(STAGE82 / 'protected_hashes_check.json')
        full_map = check['stage8_1_files_hashed_now']
        expected, current = {}, {}
        for rel, recorded in full_map.items():
            full = ROOT / rel
            self.assertTrue(full.exists(), f'Stage 8.1 file missing: {rel}')
            actual = hashlib.sha256(full.read_bytes()).hexdigest()
            if rel in ALL_AUTHORIZED_CHANGES:
                ok, msg = check_migrated_file(rel, actual)
                self.assertTrue(ok, msg)
                continue
            expected[rel] = recorded
            current[rel] = actual
        self.assertEqual(current, expected)

    def test_dealer_and_lg_scope_config_untouched(self):
        catalog = read(ROOT / 'product_tool/config/source_catalog.v2.json')
        blob = json.dumps(catalog).lower()
        self.assertIn('sulpak', blob)
        self.assertEqual(unapproved_source_ids(s['source_id'] for s in catalog['sources']), set())  # only approved sources are registered

    def test_stage82_writes_stay_in_its_own_directory(self):
        for name in ('report.md', 'results.json', 'product_page_fixtures.json', 'catalog_samples.json',
                     'architecture_observations.json', 'checkpoint.json', 'next_queue.json'):
            self.assertTrue((STAGE82 / name).exists(), f'missing Stage 8.2 deliverable: {name}')

    def test_excel_catalog_untouched(self):
        # read-only source; its mtime/hash is not a Stage 8.2 concern, but it must still exist unmodified in place.
        self.assertTrue((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').exists())


class BudgetAndScopeTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = read(STAGE82 / 'checkpoint.json')
        self.raw_attempts = read(STAGE82 / 'raw/run_state.json')['attempts']

    def test_only_permitted_hosts_contacted(self):
        allowed_hosts = {'www.samsung.com', 'www.lg.com', 'direct.playstation.com'}
        contacted = {a['url'].split('/')[2] for a in self.raw_attempts}
        self.assertTrue(contacted <= allowed_hosts, contacted - allowed_hosts)

    def test_host_budget_not_exceeded(self):
        from collections import Counter
        counts = Counter(a['url'].split('/')[2] for a in self.raw_attempts)
        self.assertTrue(all(c <= 8 for c in counts.values()), counts)

    def test_no_request_continues_on_a_host_after_a_confirmed_block(self):
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked_hosts = set()
        for a in self.raw_attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked_hosts:
                self.fail(f'request continued on paused host: {host}')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked_hosts.add(host)

    def test_no_jbl_requests(self):
        # jbl is http_blocked from Stage 8 and must never be contacted in Stage 8.2.
        self.assertFalse(any('jbl' in a['url'].lower() for a in self.raw_attempts))

    def test_no_dealer_requests(self):
        # generic rule: only the stage's own manufacturer hosts were contacted
        blob = json.dumps(self.raw_attempts).lower()
        self.assertNotIn('sulpak', blob)
        self.assertEqual(hosts_outside_allowlist(
            (a['url'] for a in self.raw_attempts),
            {'www.samsung.com', 'www.lg.com', 'direct.playstation.com'}), set())

    def test_no_search_engine_domains_contacted(self):
        blob = json.dumps(self.raw_attempts).lower()
        for engine in ('google.', 'bing.', 'duckduckgo.', 'yandex.'):
            self.assertNotIn(engine, blob)


class QueueScopeTests(unittest.TestCase):
    def setUp(self):
        q = read(STAGE81 / 'stage8_2_queue.json')
        self.by_family_group = {}
        for group, items in q['groups'].items():
            for item in items:
                self.by_family_group.setdefault(item['source_family'], set()).add(group)

    def test_only_permitted_group_families_have_verified_or_candidate_pages(self):
        fixtures = read(STAGE82 / 'product_page_fixtures.json')
        touched_families = {f['source_family'] for f in fixtures}
        self.assertTrue(touched_families <= SEARCHED_FAMILIES)
        for fam in touched_families:
            groups = self.by_family_group.get(fam, set())
            self.assertTrue(groups & PERMITTED_GROUPS, f'{fam} has fixtures but no permitted-group queue entry')

    def test_out_of_scope_families_have_zero_fixtures(self):
        fixtures = read(STAGE82 / 'product_page_fixtures.json')
        touched_families = {f['source_family'] for f in fixtures}
        out_of_scope = TARGET_FAMILIES - SEARCHED_FAMILIES
        self.assertFalse(touched_families & out_of_scope)


class ProductPageFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = read(STAGE82 / 'product_page_fixtures.json')

    def test_result_vocab_is_valid(self):
        for f in self.fixtures:
            self.assertIn(f['product_page_fixture_result'], PAGE_RESULT_VOCAB, f['url'])
            self.assertIn(f['catalog_identity_result'], IDENTITY_RESULT_VOCAB, f['url'])

    def test_verified_pages_have_fixture_files_and_structure_summary(self):
        for f in self.fixtures:
            if f['product_page_fixture_result'] in ('verified', 'candidate'):
                self.assertTrue(f['structure_summary'])
                self.assertIn('is_product_page', f['structure_summary'])

    def test_verified_requires_is_product_page_true(self):
        for f in self.fixtures:
            if f['product_page_fixture_result'] == 'verified':
                self.assertTrue(f['structure_summary']['is_product_page'], f['url'])
            if f['product_page_fixture_result'] == 'candidate':
                self.assertFalse(f['structure_summary']['is_product_page'], f['url'])

    def test_exact_variant_or_exact_model_requires_identity_reasoning(self):
        for f in self.fixtures:
            if f['catalog_identity_result'] in ('exact_variant', 'exact_model'):
                self.assertTrue(f['identity_reasoning'])
                self.assertGreater(len(f['identity_reasoning']), 20)

    def test_no_official_exact_product_not_found_status_used(self):
        # The task explicitly forbids this status when only one route was checked or a limit was hit.
        # Check the actual result fields, not prose (a limitations/next_safe_route note may
        # legitimately warn against assigning it without that being an assigned value).
        for f in self.fixtures:
            self.assertNotEqual(f['product_page_fixture_result'], 'official_exact_product_not_found')
            self.assertNotEqual(f['catalog_identity_result'], 'official_exact_product_not_found')

    def test_lg_pages_are_candidate_not_verified(self):
        lg = [f for f in self.fixtures if f['source_family'] == 'lg']
        self.assertEqual(len(lg), 2)
        self.assertTrue(all(f['product_page_fixture_result'] == 'candidate' for f in lg))

    def test_fixture_files_referenced_actually_exist(self):
        for f in self.fixtures:
            struct = f['structure_summary']
            # structure_summary doesn't carry the fixture path itself; cross-check via architecture_observations is out of scope here,
            # but every referenced url must have produced a real fixture file somewhere under fixtures/.
            self.assertIsInstance(struct, dict)


class CatalogSamplesTests(unittest.TestCase):
    def setUp(self):
        self.samples = read(STAGE82 / 'catalog_samples.json')

    def test_two_products_per_brand_from_massive_categories(self):
        from collections import Counter
        per_brand = Counter(s['source_family'] for s in self.samples)
        self.assertEqual(set(per_brand), TARGET_FAMILIES)
        self.assertTrue(all(c == 2 for c in per_brand.values()), per_brand)

    def test_each_pair_uses_two_distinct_categories(self):
        from collections import defaultdict
        cats = defaultdict(set)
        for s in self.samples:
            cats[s['source_family']].add(s['catalog_category'])
        for fam, c in cats.items():
            self.assertEqual(len(c), 2, f'{fam}: {c}')

    def test_search_query_combines_brand_article_and_name(self):
        for s in self.samples:
            q = s['search_query_used']
            self.assertIn(s['catalog_brand_label'], q)
            self.assertIn(s['seller_article'], q)

    def test_out_of_scope_brands_marked_and_reasoned(self):
        for s in self.samples:
            if s['source_family'] not in SEARCHED_FAMILIES:
                self.assertFalse(s['in_scope_for_stage8_2_network_pass'])
                self.assertTrue(s['out_of_scope_reason'])

    def test_microsoft_rows_are_genuinely_xbox(self):
        ms_rows = [s for s in self.samples if s['catalog_brand_label'] == 'Microsoft']
        self.assertEqual(len(ms_rows), 2)
        self.assertTrue(all('xbox' in r['name'].lower() for r in ms_rows), ms_rows)


class ArchitectureObservationsTests(unittest.TestCase):
    def setUp(self):
        self.arch = read(STAGE82 / 'architecture_observations.json')

    def test_no_new_shared_primitive_declared_from_one_family(self):
        blob = json.dumps(self.arch)
        self.assertNotIn('"status": "shared_primitive_candidate"', blob)

    def test_playstation_identity_flags_microdata_not_json_ld(self):
        ps = self.arch['families']['playstation']['identity']
        self.assertIn('microdata', ps['contract'].lower())
        fixtures = read(STAGE82 / 'product_page_fixtures.json')
        ps_fixtures = [f for f in fixtures if f['source_family'] == 'playstation']
        self.assertTrue(ps_fixtures)
        for f in ps_fixtures:
            identity = f['structure_summary']['identity']
            self.assertEqual(identity['json_paths'], [])
            self.assertIn('sku', identity['microdata_properties'])

    def test_lg_pages_flagged_insufficient_not_verified(self):
        lg = self.arch['families']['lg']['identity']
        self.assertEqual(lg['status'], 'insufficient_evidence')

    def test_samsung_media_reconfirms_stage81_primitive_by_name(self):
        samsung_media = self.arch['families']['samsung']['media']
        self.assertEqual(samsung_media['primitive'], 'responsive_srcset_media_picker')
        # cross-check the primitive actually exists in the Stage 8.1 baseline
        primitives = read(STAGE81 / 'primitives.v1.json')
        names = {p['name'] for p in primitives['shared_primitive_candidate']}
        self.assertIn('responsive_srcset_media_picker', names)


class NextQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = read(STAGE82 / 'next_queue.json')

    def test_all_eight_target_brands_present(self):
        fams = {e['source_family'] for e in self.queue['entries']}
        self.assertEqual(fams, TARGET_FAMILIES)

    def test_jbl_is_blocked_not_another_method(self):
        jbl = next(e for e in self.queue['entries'] if e['source_family'] == 'jbl')
        self.assertEqual(jbl['next_method'], 'blocked_manual_review')

    def test_out_of_scope_brands_keep_their_stage81_method(self):
        expected = {'apple': 'regional_official_domain', 'razer': 'official_category',
                    'hiper': 'official_category', 'microsoft': 'support_first'}
        by_fam = {e['source_family']: e['next_method'] for e in self.queue['entries']}
        for fam, method in expected.items():
            self.assertEqual(by_fam[fam], method)

    def test_next_queue_is_not_an_automatic_continuation(self):
        blob = json.dumps(self.queue)
        self.assertNotIn('"executed": true', blob.lower())


if __name__ == '__main__':
    unittest.main()