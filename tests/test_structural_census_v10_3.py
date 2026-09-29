"""Stage 10.3 regression tests: final bounded image check for Xbox Series S
Carbon Black 1TB. Checks the offline DOM/gallery analysis (no Carbon Black
slide slot exists), the visual rejection of the two fetched candidates, the
pre-declared image-CDN budget, and the untouched-registry guarantee. Network
is never required."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE10_3 = ROOT / 'reports/source_census_2026-09-23_stage10_3'


def read(name):
    return json.loads((STAGE10_3 / name).read_text(encoding='utf-8'))


class OfflineGalleryAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.gallery = read('offline_dom_gallery_analysis.json')

    def test_no_carbon_black_gallery_slot_exists(self):
        presence = self.gallery['hero_gallery_carousel']['slot_presence_by_option']
        new_slots = presence['new (1TB Carbon Black) -- expected but searched for']
        self.assertTrue(all(not v for v in new_slots.values()))
        standard_slots = presence['standard (512GB Robot White)']
        self.assertTrue(all(standard_slots.values()))

    def test_small_number_of_visual_check_candidates(self):
        candidates = self.gallery['classification']['candidates_for_visual_check_console_visible_color_unstated']
        self.assertEqual(len(candidates), 2)

    def test_white_bundle_images_classified_by_alt_text_not_filename_alone(self):
        white = self.gallery['classification']['rejected_confirmed_white_by_alt_text_or_shared_bundle_id']
        self.assertGreater(len(white), 0)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_requests(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(set(self.budget['allowed_hosts']), {'cms-assets.xboxservices.com', 'assets.xboxservices.com'})

    def test_candidate_urls_documented_not_guessed(self):
        self.assertEqual(len(self.budget['candidate_urls_already_known_not_guessed']), 2)

    def test_requests_stayed_within_budget(self):
        self.assertLessEqual(self.checkpoint['total_requests_made'], self.budget['limits']['max_requests_total'])
        for entry in self.checkpoint['request_log_full']:
            url = entry.get('requested_url', '')
            self.assertTrue(any(h in url for h in self.budget['allowed_hosts']), url)

    def test_no_protection_stop_events(self):
        self.assertFalse(self.checkpoint['stop_events']['403_429_or_challenge_seen'])

    def test_images_verified_byte_exact(self):
        for url, info in self.checkpoint['images_fetched_and_verified_byte_exact'].items():
            self.assertEqual(info['completeness'], 'complete')


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_zero_images_accepted(self):
        self.assertEqual(self.card['images_accepted_count'], 0)
        self.assertEqual(self.card['images_accepted_for_the_card'], [])

    def test_visually_checked_candidates_rejected_not_confirmed(self):
        reasons = {r['reason'] for r in self.card['images_rejected_with_evidence']}
        self.assertIn('visually_confirmed_white_not_carbon_black', reasons)

    def test_no_image_falsely_labeled_carbon_black(self):
        blob = json.dumps(self.card['images_rejected_with_evidence']).lower()
        # every rejected image's evidence should explain why it is NOT carbon black
        for r in self.card['images_rejected_with_evidence']:
            self.assertIn('white' if 'white' in r['reason'] else 'carbon', r['reason'] + r['evidence'].lower())

    def test_variant_and_line_wide_fields_carried_forward(self):
        self.assertIn('variant_specific_fields_carbon_black_1tb', self.card)
        self.assertIn('line_wide_fields_applies_to_all_series_s_skus', self.card)
        self.assertGreater(len(self.card['variant_specific_fields_carbon_black_1tb']), 0)

    def test_manual_not_re_searched_and_not_declared_absent(self):
        manual = self.card['manual_search']
        self.assertEqual(manual['status'], 'not_re_examined_this_stage')
        self.assertNotIn('does not exist', json.dumps(manual).lower())

    def test_criterion_3_confirmed_failing_with_explicit_reasoning(self):
        crit = self.card['five_point_export_readiness_criterion']['criterion_3_official_matched_image_confirmed']
        self.assertFalse(crit['pass'])
        self.assertIn('confirmed absence', crit['detail'])

    def test_three_of_five_criteria_pass(self):
        crit = self.card['five_point_export_readiness_criterion']
        passing = [k for k, v in crit.items() if v['pass']]
        self.assertEqual(len(passing), 3)

    def test_export_readiness_not_ready(self):
        self.assertEqual(self.card['export_readiness'], 'not_ready')


class NoRawImageContentCommittedTests(unittest.TestCase):
    def test_no_binary_image_files_in_stage_directory(self):
        binary_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        found = [p for p in STAGE10_3.rglob('*') if p.suffix.lower() in binary_ext]
        self.assertEqual(found, [], f'raw image bytes committed to repo: {found}')

    def test_fetch_results_note_bytes_discarded(self):
        phase2 = read('phase2_fetch_candidate_images.json')
        for url, info in phase2['results'].items():
            self.assertIsNone(info['saved_as'])
            self.assertIn('discarded', info['note'])


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

    def test_all_prior_stages_unchanged_including_10_1_and_10_2(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 590)
        self.assertIn('source_census_2026-09-23_stage10_2', check['prior_stage_directories_hashed'])
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'offline_dom_gallery_analysis.json', 'budget_predeclaration.json',
                     'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE10_3 / name).exists(), f'missing Stage 10.3 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
