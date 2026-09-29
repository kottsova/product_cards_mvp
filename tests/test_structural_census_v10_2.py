"""Stage 10.2 regression tests: offline re-audit of the Xbox Series S landing
page (variant-specific vs line-wide field separation, the "Carbon-Aware" image
retraction), plus a bounded Russian-first manual search on support.xbox.com.
Network is never required -- these check persisted evidence, the pre-declared
budget, and the untouched-registry guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE10_2 = ROOT / 'reports/source_census_2026-09-23_stage10_2'


def read(name):
    return json.loads((STAGE10_2 / name).read_text(encoding='utf-8'))


class OfflineReverificationTests(unittest.TestCase):
    def setUp(self):
        self.reverif = read('offline_reverification.json')

    def test_carbon_aware_images_corrected(self):
        corr = self.reverif['carbon_aware_images_correction']
        self.assertIn('INCORRECT in Stage 10.1', corr['correction'])
        self.assertIn('sustainability', corr['correction'])

    def test_no_genuine_color_specific_image_found(self):
        search = self.reverif['genuine_color_specific_image_search']
        self.assertEqual(search['assets_with_color_words_in_filename'], [])

    def test_storage_confirmed_variant_specific_and_live(self):
        storage = self.reverif['storage_reverification']
        self.assertEqual(storage['classification'], 'variant_specific')
        self.assertFalse(storage['inside_html_comment'])

    def test_dimensions_and_weight_confirmed_line_wide(self):
        dw = self.reverif['dimensions_and_weight_reverification']
        self.assertEqual(dw['classification'], 'line_wide_not_variant_specific')
        self.assertFalse(dw['dimensions']['inside_html_comment'])
        self.assertFalse(dw['weight']['inside_html_comment'])

    def test_dead_selector_copy_identified_but_not_relied_upon(self):
        sel = self.reverif['variant_selector_markup']
        commented = [c for c in sel['copies_found'] if c['inside_html_comment']]
        live = [c for c in sel['copies_found'] if not c['inside_html_comment']]
        self.assertGreaterEqual(len(commented), 1)
        self.assertGreaterEqual(len(live), 1)

    def test_seller_article_confirmed_absent_and_not_required(self):
        handling = self.reverif['seller_article_handling']
        self.assertTrue(handling['confirmed_absent_from_page'])
        self.assertEqual(handling['seller_article'], 'XXU-00015')


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_requests(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(self.budget['allowed_hosts'], ['support.xbox.com'])

    def test_russian_prioritized_in_budget(self):
        self.assertIn('Russian first', self.budget['language_priority'])

    def test_all_requests_on_allowed_host_within_budget(self):
        self.assertLessEqual(self.checkpoint['total_requests_made'], self.budget['limits']['max_requests_total'])
        for entry in self.checkpoint['request_log_full']:
            self.assertIn('support.xbox.com', entry['requested_url'])

    def test_ru_sitemap_url_not_guessed(self):
        self.assertIn('sitemap index', self.budget['seed_urls_note'])


class ManualSearchTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_russian_checked_first(self):
        self.assertTrue(self.card['manual_search']['russian_checked_first'])

    def test_manual_status_not_confirmed_present_or_absent(self):
        status = self.card['manual_search']['status']
        self.assertEqual(status, 'not_confirmed_present_and_not_confirmed_absent')

    def test_manual_gap_never_claims_no_manual_exists(self):
        text = self.card['manual_search']['explicit_statement'].lower()
        self.assertIn('neither confirmed present', text)
        self.assertIn('not a statement that no manual exists', text)

    def test_pdf_search_found_nothing_and_says_so(self):
        pdf = self.card['manual_search']['pdf_search_result']
        self.assertEqual(pdf['pdf_urls_found'], 0)


class CardCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_image_criterion_corrected_to_fail(self):
        crit = self.card['five_point_export_readiness_criterion']['criterion_3_official_matched_image_confirmed']
        self.assertFalse(crit['pass'])
        self.assertIn('CORRECTED', crit['detail'])

    def test_variant_specific_and_line_wide_fields_separated(self):
        variant_fields = {f['field'] for f in self.card['variant_specific_fields_carbon_black_1tb']}
        line_wide_fields = {f['field'] for f in self.card['line_wide_fields_applies_to_all_series_s_skus']}
        self.assertTrue(variant_fields.isdisjoint(line_wide_fields))
        self.assertIn('Объём накопителя', variant_fields)
        self.assertIn('Процессор (CPU)', line_wide_fields)

    def test_dimensions_weight_carry_explicit_caveat(self):
        for f in self.card['line_wide_fields_applies_to_all_series_s_skus']:
            if f['field'] in ('Габариты', 'Вес'):
                self.assertIn('caveat', f)

    def test_three_of_five_criteria_pass(self):
        crit = self.card['five_point_export_readiness_criterion']
        passing = [k for k, v in crit.items() if v['pass']]
        self.assertEqual(len(passing), 3)

    def test_export_readiness_not_ready(self):
        self.assertEqual(self.card['export_readiness'], 'not_ready')

    def test_exportable_and_not_ready_sections_both_present(self):
        self.assertIn('what_is_already_exportable_with_evidence', self.card)
        self.assertIn('what_is_not_ready', self.card)


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

    def test_all_prior_stages_unchanged_including_10_and_10_1(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 550)
        self.assertIn('source_census_2026-09-23_stage10_1', check['prior_stage_directories_hashed'])
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'offline_reverification.json', 'budget_predeclaration.json',
                     'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE10_2 / name).exists(), f'missing Stage 10.2 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
