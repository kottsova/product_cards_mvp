"""Stage 8.4 regression tests: short catalog-first Samsung cycle (Buds3 FE
catalog check + one microwave pilot card). Network is never required --
these check the persisted evidence and the Stage 2-8.3 protection
guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE84 = ROOT / 'reports/source_census_2026-09-22_stage8_4'

IDENTITY_RESULT_VOCAB = {'exact_variant', 'exact_model', 'family_only', 'conflict', 'insufficient'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage84ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_8_3_untouched(self):
        check = read(STAGE84 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now', 'stage8_2_1_files_hashed_now',
                    'stage8_2_2_files_hashed_now', 'stage8_3_files_hashed_now'):
            for rel, expected in check[key].items():
                full = ROOT / rel
                self.assertTrue(full.exists(), f'missing: {rel}')
                actual = hashlib.sha256(full.read_bytes()).hexdigest()
                if rel in ALL_AUTHORIZED_CHANGES:
                    ok, msg = check_migrated_file(rel, actual)
                    self.assertTrue(ok, msg)
                    continue
                self.assertEqual(actual, expected, f'changed: {rel}')

    def test_catalog_and_registry_untouched(self):
        check = read(STAGE84 / 'protected_hashes_check.json')['catalog_and_registry_untouched']
        actual_catalog = hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest()
        self.assertEqual(actual_catalog, check['catalog_sha256'])
        for name, expected in check['registry_files_sha256'].items():
            path = f'product_tool/config/{name}'
            actual = hashlib.sha256((ROOT / 'product_tool/config' / name).read_bytes()).hexdigest()
            if path in ALL_AUTHORIZED_CHANGES:
                ok, msg = check_migrated_file(path, actual)
                self.assertTrue(ok, msg)
                continue
            self.assertEqual(actual, expected)

    def test_deliverables_present(self):
        for name in ('report.md', 'buds3fe_catalog_check.json', 'candidate_selection.json', 'evidence.json',
                     'card_summary.json', 'documents.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE84 / name).exists(), f'missing Stage 8.4 deliverable: {name}')


class NoHistoricalModelRevisitTests(unittest.TestCase):
    def test_no_request_mentions_excluded_models(self):
        attempts = read(STAGE84 / 'run_state.json')['attempts']
        blob = json.dumps(attempts).lower()
        for term in ('s20', 'fold3', 'fold-3', 'n5300'):
            self.assertNotIn(term, blob)

    def test_only_samsung_domains_contacted(self):
        attempts = read(STAGE84 / 'run_state.json')['attempts']
        for a in attempts:
            host = a['url'].split('/')[2]
            self.assertTrue(host.endswith('samsung.com'), host)

    def test_budget_within_plan(self):
        checkpoint = read(STAGE84 / 'checkpoint.json')
        self.assertLessEqual(checkpoint['budget_actual']['total_requests'], checkpoint['budget_plan']['max_total'])
        for host, count in checkpoint['budget_actual']['by_host'].items():
            self.assertLessEqual(count, checkpoint['budget_plan']['max_per_host'])
        self.assertLessEqual(len(checkpoint['budget_actual']['hosts_contacted']), checkpoint['budget_plan']['max_hosts'])

    def test_no_request_continues_after_a_confirmed_block(self):
        attempts = read(STAGE84 / 'run_state.json')['attempts']
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked = set()
        for a in attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked:
                self.fail('request continued on paused host')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked.add(host)


class BudsCatalogCheckTests(unittest.TestCase):
    def setUp(self):
        self.check = read(STAGE84 / 'buds3fe_catalog_check.json')

    def test_no_match_found_is_honest_not_silently_dropped(self):
        self.assertEqual(self.check['result'], 'no_match_found')
        self.assertTrue(self.check['consequence'])

    def test_similar_model_not_used_as_substitute(self):
        self.assertIn('Buds2', str(self.check['closest_existing_samsung_audio_rows']))
        self.assertIn('not', self.check['closest_rows_not_used_as_substitute'].lower())

    def test_no_new_requests_made_for_buds(self):
        self.assertIn('no gap-closing requests were made', self.check['consequence'].lower())


class CandidateSelectionTests(unittest.TestCase):
    def setUp(self):
        self.selection = read(STAGE84 / 'candidate_selection.json')

    def test_excluded_models_named(self):
        self.assertEqual(set(self.selection['excluded_models']), {'Galaxy S20 FE', 'Galaxy Z Fold3', 'N5300 (Samsung TV)'})

    def test_appliance_category_does_not_require_novelty_evidence(self):
        self.assertFalse(self.selection['novelty_evidence_required'])

    def test_candidate_is_exact_catalog_article(self):
        self.assertEqual(self.selection['candidate']['seller_article'], 'MS23K3614AK/BW')

    def test_discovery_was_offline(self):
        self.assertIn('offline', self.selection['discovery_method'].lower())
        self.assertIn('zero new requests', self.selection['discovery_method'].lower())


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read(STAGE84 / 'evidence.json')

    def test_color_evidence_not_url_only(self):
        color = self.evidence['fields']['color']
        self.assertEqual(color['status'], 'confirmed')
        self.assertEqual(color['source'], 'HTML <title> tag')

    def test_model_code_cross_matched_against_catalog(self):
        code = self.evidence['fields']['manufacturer_model_code']
        self.assertIn('catalog', code['evidence'].lower())
        self.assertEqual(code['value'], 'MS23K3614AK/BW')

    def test_specs_completeness_marked_partial_not_complete(self):
        self.assertEqual(self.evidence['fields']['specifications_completeness']['status'], 'partial')

    def test_manual_language_claim_scoped_to_filename_not_content(self):
        manual = self.evidence['fields']['instruction_manual']
        self.assertIn('not', manual['language'].lower())
        self.assertIn('filename', manual['language'].lower())

    def test_manual_model_linkage_is_query_parameter_not_guess(self):
        manual = self.evidence['fields']['instruction_manual']
        self.assertIn('modelname=ms23k3614ak', manual['model_linkage_evidence'].lower())

    def test_regional_redirect_rejection_disclosed(self):
        detail = ' '.join(self.evidence['requests_detail'])
        self.assertIn('regional_redirect', detail.lower())


class CardSummaryTests(unittest.TestCase):
    def setUp(self):
        self.card = read(STAGE84 / 'card_summary.json')

    def test_variant_status_is_valid_and_exact_variant(self):
        item = self.card['items'][0]
        self.assertIn(item['model_variant_status'], IDENTITY_RESULT_VOCAB)
        self.assertEqual(item['model_variant_status'], 'exact_variant')

    def test_exact_variant_reasoning_names_a_variant_field(self):
        item = self.card['items'][0]
        self.assertIn('color', item['model_variant_status_reasoning'].lower())

    def test_buds3fe_status_present_and_unchanged_disposition(self):
        self.assertIn('Stage 8.3', self.card['buds3fe_status']['disposition'])

    def test_gaps_listed_not_hidden(self):
        item = self.card['items'][0]
        self.assertTrue(item['gaps'])


class DocumentsTests(unittest.TestCase):
    def test_manual_found_this_time_unlike_buds(self):
        docs = read(STAGE84 / 'documents.json')
        self.assertEqual(len(docs['documents_found_and_relevant']), 1)
        self.assertEqual(docs['documents_found_and_relevant'][0]['document_type'], 'User Manual')

    def test_not_found_never_conflated_with_does_not_exist(self):
        docs = read(STAGE84 / 'documents.json')
        self.assertIn('never conflated', docs['note'])


if __name__ == '__main__':
    unittest.main()