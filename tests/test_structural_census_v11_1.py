"""Stage 11.1 regression tests: image integrity+visual re-audit for 9A273AA,
the sku/offers.sku "not independent evidence" correction, and a scoped
HyperX adapter-repeatability check across a keyboard and a mouse candidate.
Network is never required -- these check persisted evidence, the pre-declared
budget, and the untouched-registry guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE11_1 = ROOT / 'reports/source_census_2026-09-23_stage11_1'


def read(name):
    return json.loads((STAGE11_1 / name).read_text(encoding='utf-8'))


class CardReauditTests(unittest.TestCase):
    def setUp(self):
        self.reaudit = read('offline_card_reaudit.json')

    def test_sku_offers_sku_not_treated_as_independent(self):
        corr = self.reaudit['correction']
        self.assertIn('ONE JSON-LD', corr['issue'])
        self.assertIn('not a second, independently-sourced signal', corr['issue'])

    def test_identity_verdict_not_changed_by_the_correction(self):
        self.assertFalse(self.reaudit['correction']['does_this_change_the_identity_verdict'])

    def test_manual_status_carried_forward_open(self):
        manual = self.reaudit['manual_status_carried_forward_unchanged']
        self.assertTrue(manual['quick_start_guide_listed_in_box_contents'])
        self.assertFalse(manual['online_document_confirmed'])
        self.assertFalse(manual['language_confirmed'])


class ImageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.phase1 = read('phase1_robots_and_images.json')

    def test_two_images_verified_complete_and_hashed(self):
        results = self.phase1['image_results']
        self.assertEqual(len(results), 2)
        for url, r in results.items():
            self.assertEqual(r['completeness'], 'complete')
            self.assertEqual(len(r['sha256']), 64)
            self.assertTrue(r['host_is_official_confirmed_host'])

    def test_images_not_committed_as_binary_files(self):
        for url, r in self.phase1['image_results'].items():
            self.assertIsNone(r['saved_as'])

    def test_robots_disallow_does_not_cover_cdn_shop_files(self):
        for rule in self.phase1['robots_disallow_rules']:
            self.assertFalse('cdn/shop/files' in rule)


class NoRawImageContentCommittedTests(unittest.TestCase):
    def test_no_binary_image_files_in_stage_directory(self):
        binary_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        found = [p for p in STAGE11_1.rglob('*') if p.suffix.lower() in binary_ext]
        self.assertEqual(found, [], f'raw image bytes committed to repo: {found}')


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

    def test_no_kingston_hiper_or_other_brand_contacted(self):
        for entry in self.checkpoint['request_log_full']:
            for forbidden in ('kingston.com', 'hiper', 'xbox.com', 'playstation.com', 'samsung.com', 'microsoft.com'):
                self.assertNotIn(forbidden, entry['requested_url'].lower())


class AdditionalRowsTests(unittest.TestCase):
    def setUp(self):
        self.data = read('additional_rows_and_adapter_status.json')

    def test_two_additional_rows_selected(self):
        self.assertEqual(set(self.data['additional_catalog_rows'].keys()), {'keyboard', 'mouse'})

    def test_mouse_confirmed_exact_sku_match(self):
        mouse = self.data['additional_catalog_rows']['mouse']['identity_check']
        self.assertTrue(mouse['exact_match'])
        self.assertEqual(mouse['conclusion'], 'confirmed_by_exact_code_match')

    def test_keyboard_regional_mismatch_not_papered_over(self):
        kb = self.data['additional_catalog_rows']['keyboard']['identity_check']
        self.assertFalse(kb['exact_match'])
        self.assertTrue(kb['base_code_match'])
        self.assertEqual(kb['conclusion'], 'model_line_confirmed_exact_regional_variant_not_confirmed')

    def test_additionalProperty_value_population_varies_by_page(self):
        pop = self.data['component_matrix']['specifications_additionalProperty_json_ld']['value_population_by_page']
        self.assertEqual(pop['microphone']['populated_with_real_values'], 0)
        self.assertGreater(pop['keyboard']['populated_with_real_values'], 0)

    def test_srcset_correction_recorded(self):
        media = self.data['component_matrix']['media_dom_responsive_srcset']
        self.assertIn('CORRECTION_to_stage8_1_characterization', media)
        self.assertIn('logo', media['CORRECTION_to_stage8_1_characterization'].lower())


class AdapterCardTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_adapter_verdict_distinguishes_shape_from_identity(self):
        verdict = self.card['hyperx_adapter_status']['adapter_verdict']
        self.assertIn('EXTRACTION SHAPE', verdict)
        self.assertIn('does NOT support a fully repeatable', verdict)

    def test_image_evidence_upgraded_with_visual_confirmation(self):
        images = self.card['quadcast_2s_9A273AA']['image_evidence_upgraded']['verified_images']
        self.assertEqual(len(images), 2)
        for img in images:
            self.assertTrue(img['official_host_confirmed'])
            self.assertEqual(img['byte_integrity'], 'complete')
            self.assertIn('Yes', img['visual_content_confirmed'])

    def test_only_two_of_nine_images_upgraded(self):
        note = self.card['quadcast_2s_9A273AA']['image_evidence_upgraded']['note']
        self.assertIn('2 of the 9', note)

    def test_gaps_listed(self):
        self.assertGreaterEqual(len(self.card['gaps']), 3)


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

    def test_all_prior_stages_unchanged_including_11(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 620)
        self.assertIn('source_census_2026-09-23_stage11', check['prior_stage_directories_hashed'])
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'offline_card_reaudit.json', 'additional_rows_and_adapter_status.json',
                     'budget_predeclaration.json', 'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE11_1 / name).exists(), f'missing Stage 11.1 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
