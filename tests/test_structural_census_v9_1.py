"""Stage 9.1 regression tests: offline disambiguation of the two DualSense
Cosmic Red catalog rows, separating product/variant identity from
catalog-row mapping. Network is never required -- these check persisted
evidence and the Stage 2-9 protection guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE9 = ROOT / 'reports/source_census_2026-09-22_stage9'
STAGE9_1 = ROOT / 'reports/source_census_2026-09-22_stage9_1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage9_1ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_stage9_untouched(self):
        check = read(STAGE9_1 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now', 'stage8_2_1_files_hashed_now',
                    'stage8_2_2_files_hashed_now', 'stage8_3_files_hashed_now', 'stage8_4_files_hashed_now',
                    'stage8_5_files_hashed_now', 'stage8_6_files_hashed_now', 'stage9_files_hashed_now'):
            for rel, expected in check[key].items():
                full = ROOT / rel
                self.assertTrue(full.exists(), f'missing: {rel}')
                actual = hashlib.sha256(full.read_bytes()).hexdigest()
                if rel in ALL_AUTHORIZED_CHANGES:
                    ok, msg = check_migrated_file(rel, actual)
                    self.assertTrue(ok, msg)
                    continue
                self.assertEqual(actual, expected, f'changed: {rel}')

    def test_stage9_own_card_left_untouched(self):
        # Stage 9's card.json must still say identity_result exact_model and
        # keep its own (now-superseded-in-new-reporting-only) framing intact.
        stage9_card = read(STAGE9 / 'card.json')
        self.assertEqual(stage9_card['identity_result'], 'exact_model')
        self.assertIn('cannot be told apart', stage9_card['export_readiness']['reasoning'])

    def test_catalog_and_registry_untouched(self):
        check = read(STAGE9_1 / 'protected_hashes_check.json')['catalog_and_registry_untouched']
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
        for name in ('report.md', 'offline_row_analysis.json', 'known_routes_review.json',
                     'identity_variant_vs_catalog_mapping.json', 'card.json', 'checkpoint.json',
                     'protected_hashes_check.json', 'budget_predeclaration.json'):
            self.assertTrue((STAGE9_1 / name).exists(), f'missing Stage 9.1 deliverable: {name}')


class OfflineRowAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.analysis = read(STAGE9_1 / 'offline_row_analysis.json')

    def test_no_dedicated_manufacturer_code_field_in_catalog(self):
        self.assertFalse(self.analysis['catalog_schema_full']['dedicated_manufacturer_or_region_code_field_exists'])
        self.assertEqual(self.analysis['catalog_schema_full']['total_columns'], 8)

    def test_both_rows_present_with_full_fields(self):
        row_j = self.analysis['row_CFI-ZCT1J_02']
        row_w = self.analysis['row_CFI-ZCT1W_cosmic_red']
        self.assertEqual(row_j['Артикул продавца'], 'CFI-ZCT1J 02')
        self.assertEqual(row_w['Артикул продавца'], 'CFI-ZCT1W_cosmic_red')

    def test_seller_article_alone_not_treated_as_variant_proof(self):
        field = next(f for f in self.analysis['field_by_field_comparison'] if f['field'].startswith('Артикул продавца'))
        self.assertEqual(field['is_variant_evidence'], 'unverified')

    def test_marketplace_metadata_fields_not_treated_as_variant_evidence(self):
        for prefix in ('Артикулы WB', 'ТНВЭД', 'Повторов'):
            field = next(f for f in self.analysis['field_by_field_comparison'] if f['field'].startswith(prefix))
            self.assertFalse(field['is_variant_evidence'])

    def test_no_rows_merged_or_deleted_in_conclusion(self):
        self.assertIn('No rows were merged or deleted', self.analysis['conclusion'])


class KnownRoutesReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = read(STAGE9_1 / 'known_routes_review.json')

    def test_only_one_official_dualsense_cosmic_red_listing_exists(self):
        self.assertEqual(len(self.review['route_1_controllers_category_link_index']['links_found']), 1)

    def test_no_substantial_difference_found_offline(self):
        self.assertFalse(self.review['substantial_difference_offline_finding']['found'])

    def test_no_known_route_left_to_check(self):
        self.assertFalse(self.review['known_route_capable_of_confirming_a_difference']['exists'])

    def test_zero_requests_decision_documented(self):
        self.assertIn('0 new HTTP requests', self.review['decision'])


class IdentityVsMappingTests(unittest.TestCase):
    def setUp(self):
        self.doc = read(STAGE9_1 / 'identity_variant_vs_catalog_mapping.json')

    def test_question_1_variant_confirmed(self):
        self.assertEqual(self.doc['question_1_is_the_product_variant_confirmed_by_official_features']['status'], 'confirmed')

    def test_question_2_both_rows_linked_not_one_dropped(self):
        q2 = self.doc['question_2_can_this_confirmed_variant_be_linked_to_catalog_rows']
        articles = {r['seller_article'] for r in q2['per_row_mapping']}
        self.assertEqual(articles, {'CFI-ZCT1J 02', 'CFI-ZCT1W_cosmic_red'})
        self.assertFalse(q2['rows_merged_or_deleted'])

    def test_neither_row_claims_manufacturer_code_confirmed(self):
        q2 = self.doc['question_2_can_this_confirmed_variant_be_linked_to_catalog_rows']
        for row in q2['per_row_mapping']:
            self.assertFalse(row['manufacturer_code_confirmed_for_this_row'])

    def test_caveat_distinguishes_absence_of_conflict_from_proof_of_identity(self):
        q2 = self.doc['question_2_can_this_confirmed_variant_be_linked_to_catalog_rows']
        self.assertIn('not proof that they denote', q2['explicit_caveat'])

    def test_stage9_framing_explicitly_corrected_not_silently(self):
        self.assertIn('Stage 9', self.doc['correction_to_stage_9_framing'])
        self.assertIn('byte-identical', self.doc['correction_to_stage_9_framing'])


class CardV2Tests(unittest.TestCase):
    def setUp(self):
        self.card = read(STAGE9_1 / 'card.json')

    def test_identity_result_still_exact_model(self):
        self.assertEqual(self.card['identity_result'], 'exact_model')

    def test_export_readiness_criterion_stated_explicitly(self):
        self.assertTrue(self.card['export_readiness_criterion']['stated_explicitly'])
        self.assertGreaterEqual(len(self.card['export_readiness_criterion']['criteria']), 5)

    def test_criterion_2_now_passes_criterion_4_still_fails(self):
        check = self.card['criterion_check']
        self.assertTrue(check['2_rows_linked_by_stated_evidence'])
        self.assertFalse(check['4_specifications_sufficient_for_listing'])

    def test_specs_gap_and_manual_gap_are_separate_entries(self):
        gap_texts = [g['gap'] for g in self.card['gaps']]
        specs_gaps = [g for g in gap_texts if 'specification' in g.lower()]
        manual_gaps = [g for g in gap_texts if 'manual' in g.lower()]
        self.assertEqual(len(specs_gaps), 1)
        self.assertEqual(len(manual_gaps), 1)
        self.assertNotEqual(specs_gaps[0], manual_gaps[0])

    def test_export_readiness_not_ready_for_specs_reason_not_ambiguity(self):
        er = self.card['export_readiness']
        self.assertEqual(er['status'], 'not_ready')
        self.assertIn('criterion 4', er['reasoning'])

    def test_gaps_not_labeled_minor_without_explicit_denial(self):
        blob = json.dumps(self.card).lower()
        self.assertNotIn('insignificant', blob)
        self.assertNotIn('trivial', blob)
        import re
        for m in re.finditer(r'.{0,30}minor', blob):
            self.assertIn('not', m.group(0), f'unqualified use of "minor": {m.group(0)!r}')

    def test_both_catalog_rows_referenced(self):
        articles = {r['seller_article'] for r in self.card['catalog_rows']['rows']}
        self.assertEqual(articles, {'CFI-ZCT1J 02', 'CFI-ZCT1W_cosmic_red'})


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = read(STAGE9_1 / 'checkpoint.json')

    def test_zero_requests_made(self):
        self.assertEqual(self.checkpoint['budget_actual']['total_requests'], 0)
        self.assertEqual(self.checkpoint['request_log'], [])

    def test_no_other_products_searched(self):
        self.assertTrue(self.checkpoint['no_other_products_searched_this_stage'])

    def test_samsung_not_investigated(self):
        self.assertFalse(self.checkpoint['samsung_investigated_this_stage'])


if __name__ == '__main__':
    unittest.main()