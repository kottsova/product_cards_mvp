"""Stage 11 regression tests: (A) an offline count-reconciliation addendum to
Stage 10.3 (no Xbox conclusion change), and (B) a catalog-first full cycle for
HyperX QuadCast 2S Black, matched against Stage 8.1's confirmed fixture.
Network is never required -- these check persisted evidence, the pre-declared
budget, the separated general-contract-check vs identity-verification steps,
and the untouched-registry guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE11 = ROOT / 'reports/source_census_2026-09-23_stage11'
STAGE10_3 = ROOT / 'reports/source_census_2026-09-23_stage10_3'


def read(name):
    return json.loads((STAGE11 / name).read_text(encoding='utf-8'))


class XboxAddendumTests(unittest.TestCase):
    def setUp(self):
        self.addendum = read('xbox_stage10_3_addendum.json')

    def test_reconciliation_sums_match(self):
        recon = self.addendum['reconciliation']
        rejected_sum = recon['breakdown']['counted_in_the_17_rejected_figure']['sum']
        excluded_sum = recon['breakdown']['NOT_counted_in_the_17_kept_as_a_separate_excluded_list']['sum']
        self.assertEqual(rejected_sum, 17)
        self.assertEqual(rejected_sum + excluded_sum, recon['total_elements_classified_across_all_6_categories'])

    def test_stage10_3_conclusion_explicitly_unchanged(self):
        self.assertTrue(self.addendum['reconciliation']['stage10_3_conclusion_unchanged'])

    def test_stage10_3_own_artifacts_untouched(self):
        # card.json / offline_dom_gallery_analysis.json must still exist and be readable,
        # and their content must be exactly what this addendum quotes from.
        card = json.loads((STAGE10_3 / 'card.json').read_text(encoding='utf-8'))
        self.assertEqual(card['images_rejected_count'], 17)

    def test_two_visually_checked_candidates_hashed(self):
        candidates = self.addendum['visually_checked_candidates_hashed']
        self.assertEqual(len(candidates), 2)
        for c in candidates:
            self.assertEqual(len(c['sha256']), 64)
            self.assertTrue(c['byte_count_matches_declared_total'])
            self.assertEqual(c['rejection_reason'], 'visually_confirmed_white_not_carbon_black')


class OfflineCatalogMatchTests(unittest.TestCase):
    def setUp(self):
        self.match = read('offline_catalog_and_fixture_match.json')

    def test_hyperx_and_kingston_kept_separate(self):
        sep = self.match['brand_separation']
        self.assertGreater(sep['HYPERX_row_count'], 0)
        self.assertGreater(sep['Kingston_hyperx_labeled_row_count'], 0)

    def test_selected_row_is_quadcast_2s_black(self):
        row = self.match['selected_row']
        self.assertEqual(row['Артикул продавца'], '9A273AA')
        self.assertEqual(row['Бренд'], 'HYPERX')
        self.assertIn('QuadCast 2S Black', row['Наименование'])

    def test_confirmed_pages_reference_stage8_1_fixtures(self):
        pages = self.match['stage8_1_confirmed_official_pages']
        self.assertIn('https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone', pages)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_requests(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(self.budget['allowed_hosts'], ['hyperx.com'])

    def test_all_requests_on_allowed_host_within_budget(self):
        self.assertLessEqual(self.checkpoint['total_requests_made'], self.budget['limits']['max_requests_total'])
        for entry in self.checkpoint['request_log_full']:
            self.assertIn('hyperx.com', entry['requested_url'])

    def test_no_confirmed_protection_stop(self):
        self.assertFalse(self.checkpoint['stop_events']['403_429_confirmed_challenge_seen'])

    def test_no_other_brand_hosts_contacted(self):
        for entry in self.checkpoint['request_log_full']:
            for forbidden in ('xbox.com', 'microsoft.com', 'playstation.com', 'samsung.com', 'kingston.com'):
                self.assertNotIn(forbidden, entry['requested_url'])


class IdentityVerificationTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_general_contract_check_separate_from_identity(self):
        self.assertIn('general_contract_check_vs_identity_verification', self.card)
        self.assertIn('identity_verification_separate_step', self.card)

    def test_contract_signature_matches_stage8_1(self):
        self.assertTrue(self.card['general_contract_check_vs_identity_verification']['general_extractor_contract_signature_match_vs_stage8_1_fixture'])

    def test_identity_confirmed_by_exact_sku_match(self):
        idv = self.card['identity_verification_separate_step']
        self.assertTrue(idv['sku_exact_match'])
        self.assertEqual(idv['catalog_seller_article'], idv['official_page_sku_value'])


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_four_of_five_criteria_pass(self):
        crit = self.card['five_point_export_readiness_criterion']
        passing = [k for k, v in crit.items() if v['pass']]
        self.assertEqual(len(passing), 4)
        self.assertFalse(crit['criterion_5_manual_confirmed_present_or_absence_noted']['pass'])

    def test_manual_not_declared_absent(self):
        manual = self.card['manual_search']
        self.assertNotEqual(manual['status'], 'confirmed_absent')
        self.assertIn('not a statement that no manual exists', manual['explicit_statement'].lower())

    def test_manual_physical_inclusion_stated(self):
        self.assertIn('Quick Start Guide', self.card['manual_search']['physical_inclusion_confirmed'])

    def test_specifications_contain_real_values_not_empty(self):
        specs = {f['field']: f['value'] for f in self.card['exportable_fields_with_evidence']}
        self.assertIn('Frequency Response', specs)
        self.assertEqual(specs['Frequency Response'], '20Hz - 20kHz')

    def test_images_reference_exact_sku_in_filename(self):
        images = [f for f in self.card['exportable_fields_with_evidence'] if 'Изображени' in f['field']]
        self.assertTrue(any('9a273aa' in f['value'].lower() for f in images if isinstance(f['value'], str)))


class IntegrityTests(unittest.TestCase):
    def test_catalog_and_registry_untouched(self):
        check = read('protected_hashes_check.json')
        actual_catalog = hashlib.sha256((ROOT / 'data/catalog_2026-09-21_filtered.xlsx').read_bytes()).hexdigest()
        self.assertEqual(actual_catalog, check['catalog_sha256'])
        from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file
        for name, expected in check['registry_files_sha256'].items():
            path = f'product_tool/config/{name}'
            actual = hashlib.sha256((ROOT / 'product_tool/config' / name).read_bytes()).hexdigest()
            if path in ALL_AUTHORIZED_CHANGES:
                ok, msg = check_migrated_file(path, actual)
                self.assertTrue(ok, msg)
                continue
            self.assertEqual(actual, expected)

    def test_all_prior_stages_unchanged_including_8_1_and_10_3(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 600)
        self.assertIn('source_census_2026-09-22_stage8_1', check['prior_stage_directories_hashed'])
        self.assertIn('source_census_2026-09-23_stage10_3', check['prior_stage_directories_hashed'])
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'xbox_stage10_3_addendum.json', 'offline_catalog_and_fixture_match.json',
                     'budget_predeclaration.json', 'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE11 / name).exists(), f'missing Stage 11 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
