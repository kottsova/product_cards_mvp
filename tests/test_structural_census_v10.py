"""Stage 10 regression tests: Xbox/Microsoft catalog-first full cycle. Network
is never required -- these check persisted evidence, the brand-separation
rule (Xbox-in-name must not auto-merge into the Microsoft brand), the
pre-declared bounded-request budget, and the untouched-registry guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE10 = ROOT / 'reports/source_census_2026-09-23_stage10'


def read(name):
    return json.loads((STAGE10 / name).read_text(encoding='utf-8'))


class OfflineRowAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.analysis = read('offline_row_analysis.json')

    def test_catalog_schema_has_no_dedicated_manufacturer_code_field(self):
        self.assertEqual(self.analysis['schema_columns'], [
            'Бренд', 'Категория', 'Артикул продавца', 'Артикулы WB', 'Наименование',
            'Альтернативные наименования', 'ТНВЭД', 'Повторов в выгрузках',
        ])

    def test_asus_rog_xbox_ally_not_merged_into_microsoft_brand(self):
        breakdown = self.analysis['brand_label_breakdown']
        self.assertIn('Asus', breakdown)
        self.assertIn('Microsoft', breakdown)
        self.assertEqual(breakdown['Asus']['row_count'], 3)
        self.assertEqual(breakdown['Microsoft']['row_count'], 45)

    def test_selected_row_is_xbox_series_s_carbon_1tb(self):
        row = self.analysis['selected_row']
        self.assertEqual(row['Артикул продавца'], 'XXU-00015')
        self.assertEqual(row['Бренд'], 'Microsoft')
        self.assertIn('Xbox Series S Carbon 1TB', row['Наименование'])

    def test_selection_reason_cites_capacity_and_color_variant_markers(self):
        reason = self.analysis['selection_reason']
        self.assertIn('1TB', reason)
        self.assertIn('Carbon', reason)
        self.assertIn('512GB', reason)


class KnownRoutesReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = read('known_routes_review.json')

    def test_no_registered_product_page_domain_for_microsoft(self):
        self.assertFalse(self.review['official_domains_v1_has_microsoft_or_xbox_entry'])
        self.assertFalse(self.review['source_catalog_v2_has_microsoft_or_xbox_entry'])

    def test_only_support_microsoft_com_is_a_confirmed_route(self):
        record = self.review['source_research_v1_microsoft_family_record']
        self.assertEqual(record['page_hosts'], ['support.microsoft.com'])
        self.assertEqual(record['support_hosts'], ['support.microsoft.com'])
        self.assertEqual(record['source_role'], 'support')
        self.assertEqual(record['asset_document_hosts'], [])


class BudgetAndProbeTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.probe = read('bounded_probe_result.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_any_request(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(self.budget['allowed_hosts'], ['support.microsoft.com'])

    def test_requests_stayed_within_declared_budget(self):
        self.assertLessEqual(self.probe['total_requests_made'], self.budget['limits']['max_requests_total'])
        for entry in self.probe['request_log']:
            host_ok = 'support.microsoft.com' in entry['requested_url']
            self.assertTrue(host_ok, entry['requested_url'])

    def test_off_host_xbox_links_recorded_but_not_followed(self):
        self.assertGreater(self.probe['off_host_links_total_seen'], 0)
        self.assertEqual(self.probe['candidate_xbox_links_found_on_support_page_same_host'], [])
        for url in self.probe['off_host_links_seen_but_not_followed']:
            self.assertNotIn('support.microsoft.com', url)

    def test_checkpoint_matches_probe_log(self):
        self.assertEqual(self.checkpoint['total_requests_made'], self.probe['total_requests_made'])
        self.assertEqual(len(self.checkpoint['requests_executed']), self.probe['total_requests_made'])


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_export_readiness_not_ready(self):
        self.assertEqual(self.card['export_readiness'], 'not_ready')

    def test_brand_entity_confirmed_but_model_not(self):
        self.assertEqual(self.card['identity_statuses']['brand_entity_identity']['status'], 'confirmed_official')
        self.assertEqual(self.card['identity_statuses']['product_line_identity_xbox_series_s']['status'], 'not_confirmed')

    def test_exportable_fields_list_is_not_empty(self):
        self.assertGreaterEqual(len(self.card['exportable_fields_with_evidence']), 1)

    def test_five_point_criterion_all_documented(self):
        criterion = self.card['five_point_export_readiness_criterion']
        self.assertEqual(len(criterion), 5)
        for detail in criterion.values():
            self.assertIn('detail', detail)

    def test_manual_gap_states_not_searched_not_confirmed_absent(self):
        manual = self.card['identity_statuses']['instruction_manual']
        self.assertEqual(manual['status'], 'not_searched')


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

    def test_prior_stage_directories_hashed_and_unchanged(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 400)
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'offline_row_analysis.json', 'known_routes_review.json',
                     'budget_predeclaration.json', 'bounded_probe_result.json', 'card.json',
                     'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE10 / name).exists(), f'missing Stage 10 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
