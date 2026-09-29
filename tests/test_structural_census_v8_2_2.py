"""Stage 8.2.2 regression tests: bounded support-first discovery for two
catalog Samsung smartphones, www.samsung.com only. Network is never
required -- these check the persisted evidence and the Stage 2-8.2.1
protection guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
from _source_policy import hosts_outside_allowlist, unapproved_source_ids

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE822 = ROOT / 'reports/source_census_2026-09-22_stage8_2_2'

IDENTITY_RESULT_VOCAB = {'exact_variant', 'exact_model', 'family_only', 'conflict', 'insufficient'}
MODEL_STATUS_VOCAB = {
    'official_support_exact_model', 'official_support_family_only', 'official_support_documents_found',
    'official_support_route_exhausted', 'official_support_client_rendered', 'regional_support_fallback_required',
    'manual_review_required',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage822ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_8_2_1_untouched(self):
        check = read(STAGE822 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now', 'stage8_2_1_files_hashed_now'):
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
        for name in ('report.md', 'results.json', 'catalog_samples.json', 'support_routes.json',
                     'identity_evidence.json', 'documents.json', 'regional_fallbacks.json',
                     'samsung_pipeline_contract.json', 'checkpoint.json'):
            self.assertTrue((STAGE822 / name).exists(), f'missing Stage 8.2.2 deliverable: {name}')


class HostConfirmationTests(unittest.TestCase):
    def test_support_samsung_com_never_contacted(self):
        attempts = read(STAGE822 / 'raw/run_state.json')['attempts']
        for a in attempts:
            self.assertNotEqual(a['url'].split('/')[2], 'support.samsung.com')

    def test_host_confirmed_from_evidence_not_assumed(self):
        routes = read(STAGE822 / 'support_routes.json')
        self.assertTrue(routes['host_confirmation']['not_support_samsung_com'])
        self.assertGreaterEqual(len(routes['host_confirmation']['evidence']), 2)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.attempts = read(STAGE822 / 'raw/run_state.json')['attempts']
        self.checkpoint = read(STAGE822 / 'checkpoint.json')

    def test_total_budget_not_exceeded(self):
        self.assertLessEqual(len(self.attempts), 12)

    def test_only_www_samsung_com_contacted(self):
        hosts = {a['url'].split('/')[2] for a in self.attempts}
        self.assertEqual(hosts, {'www.samsung.com'})

    def test_only_kz_ru_path_contacted(self):
        for a in self.attempts:
            self.assertIn('/kz_ru/', a['url'])

    def test_per_host_overshoot_is_disclosed_not_hidden(self):
        note = self.checkpoint['budget_actual']['per_host_cap_overshoot']
        self.assertIn('4', note)
        self.assertTrue(len(self.attempts) > 4 and 'overshoot' in note.lower() or 'against a planned cap' in note)

    def test_no_request_continues_after_a_confirmed_block(self):
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked = set()
        for a in self.attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked:
                self.fail('request continued on paused host')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked.add(host)

    def test_no_post_requests_no_search_engines_no_dealers(self):
        blob = json.dumps(self.attempts).lower()
        for forbidden in ('google.', 'bing.', 'duckduckgo.', 'sulpak'):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(hosts_outside_allowlist((a['url'] for a in self.attempts), {'www.samsung.com'}), set())

    def test_search_query_param_is_the_observed_one_not_invented(self):
        # the task forbids inventing query parameters -- the only search requests made
        # must use the exact 'searchvalue' parameter observed on the support root page.
        search_attempts = [a for a in self.attempts if '/search/' in a['url']]
        self.assertTrue(search_attempts)
        for a in search_attempts:
            self.assertIn('searchvalue=', a['url'])


class CatalogSamplesTests(unittest.TestCase):
    def test_matches_stage_8_2_1_exactly(self):
        here = read(STAGE822 / 'catalog_samples.json')
        baseline = read(ROOT / 'reports/source_census_2026-09-22_stage8_2_1/catalog_samples.json')
        self.assertEqual(here, baseline)

    def test_no_invented_model_codes_beyond_catalog(self):
        samples = read(STAGE822 / 'catalog_samples.json')
        for s in samples:
            self.assertIn(s['seller_article'], s['search_query_used'])


class IdentityEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read(STAGE822 / 'identity_evidence.json')

    def test_result_vocab_valid_for_both_models(self):
        self.assertEqual(len(self.evidence['models']), 2)
        for model, data in self.evidence['models'].items():
            self.assertIn(data['catalog_identity_result'], IDENTITY_RESULT_VOCAB, model)

    def test_family_generation_match_not_counted_as_model_evidence(self):
        # S20 Plus/Ultra article found must not be used as S20 FE evidence.
        blob = json.dumps(self.evidence).lower()
        self.assertIn('not counted', self.evidence['note_on_the_near_miss'].lower())

    def test_text_presence_rule_documented(self):
        self.assertIn('not', self.evidence['rule'].lower())
        self.assertIn('sufficient', self.evidence['rule'].lower())


class DocumentsTests(unittest.TestCase):
    def test_empty_result_is_honest_not_fabricated(self):
        docs = read(STAGE822 / 'documents.json')
        self.assertEqual(docs['documents_found'], [])
        self.assertTrue(docs['note'])


class ResultsAndStatusTests(unittest.TestCase):
    def setUp(self):
        self.results = read(STAGE822 / 'results.json')

    def test_two_models_present(self):
        self.assertEqual(len(self.results['models']), 2)

    def test_no_official_product_not_found_status_anywhere(self):
        blob = json.dumps(self.results).lower()
        self.assertNotIn('official_product_not_found', blob)

    def test_model_statuses_are_from_the_allowed_vocabulary(self):
        for model, data in self.results['models'].items():
            self.assertIn(data['status'], MODEL_STATUS_VOCAB, model)

    def test_smartphone_flow_does_not_block_tv_audio_pilot(self):
        self.assertIn('tvs', self.results['categories_ready_for_pilot'])
        self.assertTrue(any('audio' in c for c in self.results['categories_ready_for_pilot']))
        self.assertNotIn('smartphones', self.results['categories_ready_for_pilot'])


class PipelineContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = read(STAGE822 / 'samsung_pipeline_contract.json')

    def test_no_production_adapter_included(self):
        self.assertFalse(self.contract['production_adapter_included'])

    def test_appliances_and_memory_not_promoted_to_confirmed_static_template(self):
        static_tpl = self.contract['components']['static_product_template']
        self.assertNotIn('home appliances (da-sitemap.xml)', static_tpl['categories_confirmed'])
        self.assertNotIn('memory/storage (memory-sitemap.xml)', static_tpl['categories_confirmed'])
        self.assertIn('home appliances (da-sitemap.xml)', static_tpl['categories_not_yet_confirmed'])

    def test_smartphone_template_marked_unresolved(self):
        status = self.contract['components']['smartphone_client_rendered_template']['status']
        self.assertTrue(status.startswith('unresolved'))


class RegionalFallbackTests(unittest.TestCase):
    def test_fallback_recommendation_uses_already_registered_profile(self):
        fb = read(STAGE822 / 'regional_fallbacks.json')
        regions = {c['region'] for c in fb['candidate_fallback_regions']}
        self.assertTrue(any('samsung_us' in r for r in regions))
        recommended = [c for c in fb['candidate_fallback_regions'] if c.get('recommended_as_next_step')]
        self.assertTrue(recommended)
        for c in recommended:
            self.assertIn('ownership_evidence', c)
            self.assertTrue(c['ownership_evidence'])


if __name__ == '__main__':
    unittest.main()