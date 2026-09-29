"""Stage 8.2.1 regression tests: Samsung smartphones sitemap-gap closure,
scoped to www.samsung.com/kz_ru/ only. Network is never required -- these
check the persisted evidence and the Stage 2-8.2 protection guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
from _source_policy import hosts_outside_allowlist, unapproved_source_ids

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE82 = ROOT / 'reports/source_census_2026-09-22_stage8_2'
STAGE821 = ROOT / 'reports/source_census_2026-09-22_stage8_2_1'

PAGE_RESULT_VOCAB = {'verified', 'candidate', 'listing_only', 'blocked', 'insufficient'}
IDENTITY_RESULT_VOCAB = {'exact_variant', 'exact_model', 'family_only', 'conflict', 'insufficient'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage821ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_and_stage8_2_untouched(self):
        check = read(STAGE821 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now'):
            for rel, expected in check[key].items():
                full = ROOT / rel
                self.assertTrue(full.exists(), f'missing: {rel}')
                actual = hashlib.sha256(full.read_bytes()).hexdigest()
                if rel in ALL_AUTHORIZED_CHANGES:
                    ok, msg = check_migrated_file(rel, actual)
                    self.assertTrue(ok, msg)
                    continue
                self.assertEqual(actual, expected, f'changed: {rel}')

    def test_dealer_and_lg_scope_config_untouched(self):
        catalog = read(ROOT / 'product_tool/config/source_catalog.v2.json')
        blob = json.dumps(catalog).lower()
        self.assertIn('sulpak', blob)
        self.assertEqual(unapproved_source_ids(s['source_id'] for s in catalog['sources']), set())  # only approved sources are registered

    def test_deliverables_present(self):
        for name in ('report.md', 'results.json', 'catalog_samples.json', 'sitemap_evidence.json',
                     'product_page_fixtures.json', 'samsung_template_comparison.json', 'checkpoint.json', 'next_queue.json'):
            self.assertTrue((STAGE821 / name).exists(), f'missing Stage 8.2.1 deliverable: {name}')


class BudgetAndScopeTests(unittest.TestCase):
    def setUp(self):
        self.attempts = read(STAGE821 / 'raw/run_state.json')['attempts']
        self.checkpoint = read(STAGE821 / 'checkpoint.json')

    def test_only_samsung_kz_ru_contacted(self):
        for a in self.attempts:
            self.assertEqual(a['url'].split('/')[2], 'www.samsung.com')
            self.assertIn('/kz_ru/', a['url'])

    def test_small_budget_not_exceeded(self):
        self.assertLessEqual(len(self.attempts), 6)
        self.assertLessEqual(self.checkpoint['budget']['used'], self.checkpoint['budget']['max_total'])

    def test_budget_was_not_fully_exhausted_by_force(self):
        # instructions: don't expand the budget automatically to force a result.
        self.assertGreater(self.checkpoint['budget']['remaining_unused'], 0)

    def test_no_request_continues_after_a_confirmed_block(self):
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked = set()
        for a in self.attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked:
                self.fail('request continued on paused host')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked.add(host)

    def test_no_other_brand_or_domain_contacted(self):
        blob = json.dumps(self.attempts).lower()
        for forbidden in ('sulpak', 'lg.com', 'hyperx', 'bosch', 'jbl', 'apple.com', 'google.', 'bing.'):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(hosts_outside_allowlist((a['url'] for a in self.attempts), {'www.samsung.com'}), set())

    def test_no_internal_search_query_urls(self):
        # the task forbids using Samsung's internal JS search on this stage.
        for a in self.attempts:
            self.assertNotIn('?search=', a['url'])
            self.assertNotIn('&search=', a['url'])


class SitemapEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read(STAGE821 / 'sitemap_evidence.json')

    def test_offline_evidence_reused_before_new_requests(self):
        self.assertEqual(self.evidence['offline_evidence_reused']['robots_txt']['new_requests_needed'], 0)
        self.assertEqual(self.evidence['offline_evidence_reused']['sitemap_xml_index']['new_requests_needed'], 0)
        self.assertEqual(self.evidence['offline_evidence_reused']['b2c_sitemap_already_checked_in_stage8_2']['new_requests_needed'], 0)

    def test_conclusion_uses_a_precise_status(self):
        status = self.evidence['conclusion']['sitemap_route_status']
        self.assertNotEqual(status, 'official_exact_product_not_found')
        self.assertTrue(status)

    def test_unproven_branches_not_opened(self):
        opened_urls = {a['url'] for a in read(STAGE821 / 'raw/run_state.json')['attempts']}
        for entry in self.evidence['branches_deliberately_not_opened']:
            self.assertNotIn(entry['url'], opened_urls)


class ProductPageFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = read(STAGE821 / 'product_page_fixtures.json')

    def test_result_vocab_is_valid(self):
        for f in self.fixtures:
            self.assertIn(f['product_page_fixture_result'], PAGE_RESULT_VOCAB, f['url'])
            self.assertIn(f['catalog_identity_result'], IDENTITY_RESULT_VOCAB, f['url'])

    def test_candidate_pages_are_not_marked_exact(self):
        for f in self.fixtures:
            if f['product_page_fixture_result'] == 'candidate':
                self.assertNotIn(f['catalog_identity_result'], ('exact_variant', 'exact_model'))

    def test_no_official_exact_product_not_found_status_used(self):
        for f in self.fixtures:
            self.assertNotEqual(f['product_page_fixture_result'], 'official_exact_product_not_found')
            self.assertNotEqual(f['catalog_identity_result'], 'official_exact_product_not_found')

    def test_marketing_name_match_alone_not_exact_model(self):
        # Both smartphone pages textually match "Galaxy S25/S26 Ultra" + "Samsung" but
        # must not be classified exact_model on text alone.
        for f in self.fixtures:
            if f['source_family'] == 'samsung' and 'smartphones' in f['url']:
                self.assertNotEqual(f['catalog_identity_result'], 'exact_model')

    def test_is_product_page_false_matches_candidate_not_verified(self):
        for f in self.fixtures:
            struct = f['structure_summary']
            if struct.get('is_product_page') is False:
                self.assertNotEqual(f['product_page_fixture_result'], 'verified')


class CatalogSamplesTests(unittest.TestCase):
    def setUp(self):
        self.samples = read(STAGE821 / 'catalog_samples.json')

    def test_at_most_two_smartphones_from_one_category(self):
        self.assertLessEqual(len(self.samples), 2)
        self.assertTrue(all(s['catalog_category'] == 'Смартфоны' for s in self.samples))
        self.assertTrue(all(s['source_family'] == 'samsung' for s in self.samples))

    def test_base_model_kept_separate_from_memory_and_color(self):
        for s in self.samples:
            self.assertIn('base_model', s)
            self.assertIn('memory_variant', s)
            self.assertIn('color_variant', s)
            # the base model string itself should not already contain the memory figure
            self.assertNotIn('GB', s['base_model'])

    def test_search_query_includes_brand_article_and_name(self):
        for s in self.samples:
            q = s['search_query_used']
            self.assertIn(s['catalog_brand_label'], q)
            self.assertIn(s['seller_article'], q)
            self.assertIn(s['base_model'], q)


class TemplateComparisonTests(unittest.TestCase):
    def setUp(self):
        self.comparison = read(STAGE821 / 'samsung_template_comparison.json')

    def test_identity_storage_flagged_different(self):
        self.assertFalse(self.comparison['layers']['identity_storage']['same'])

    def test_srcset_primitive_recheck_is_not_applicable_not_silently_confirmed(self):
        recheck = self.comparison['responsive_srcset_media_picker_recheck']
        self.assertFalse(recheck['applies_to_samsung_smartphone_pages'])

    def test_no_new_shared_primitive_declared(self):
        blob = json.dumps(self.comparison)
        self.assertNotIn('"status": "shared_primitive_candidate"', blob)

    def test_adapter_verdict_is_not_a_single_uniform_template(self):
        verdict = self.comparison['samsung_adapter_shape_conclusion']['verdict']
        self.assertNotIn('single_uniform_template', verdict)
        self.assertNotIn('fully_separate', verdict)


class NextQueueTests(unittest.TestCase):
    def test_samsung_smartphones_queued_with_allowed_method(self):
        q = read(STAGE821 / 'next_queue.json')
        allowed = {'official_category', 'regional_official_domain', 'support_first'}
        entry = next(e for e in q['entries'] if e['source_family'] == 'samsung')
        self.assertIn(entry['next_method'], allowed)
        self.assertEqual(entry['route_result_status'], 'mobile_sitemap_no_product_urls')

    def test_next_queue_not_executed(self):
        q = read(STAGE821 / 'next_queue.json')
        blob = json.dumps(q).lower()
        self.assertNotIn('"executed": true', blob)


if __name__ == '__main__':
    unittest.main()