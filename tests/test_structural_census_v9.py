"""Stage 9 regression tests: first catalog-first full cycle for PlayStation
DualSense Cosmic Red. Network is never required -- these check the
persisted evidence and the Stage 2-8.6 protection guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE9 = ROOT / 'reports/source_census_2026-09-22_stage9'

IDENTITY_RESULT_VOCAB = {'exact_variant', 'exact_model', 'family_only', 'conflict', 'insufficient'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage9ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_8_6_untouched(self):
        check = read(STAGE9 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now', 'stage8_2_1_files_hashed_now',
                    'stage8_2_2_files_hashed_now', 'stage8_3_files_hashed_now', 'stage8_4_files_hashed_now',
                    'stage8_5_files_hashed_now', 'stage8_6_files_hashed_now'):
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
        check = read(STAGE9 / 'protected_hashes_check.json')['catalog_and_registry_untouched']
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
        for name in ('report.md', 'catalog_match.json', 'identity_ambiguity.json', 'evidence.json',
                     'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE9 / name).exists(), f'missing Stage 9 deliverable: {name}')


class CatalogMatchTests(unittest.TestCase):
    def setUp(self):
        self.match = read(STAGE9 / 'catalog_match.json')

    def test_both_candidate_rows_preserved_not_one_dropped(self):
        self.assertEqual(self.match['candidate_count'], 2)
        articles = {c['seller_article'] for c in self.match['candidates_found']}
        self.assertEqual(articles, {'CFI-ZCT1J 02', 'CFI-ZCT1W_cosmic_red'})

    def test_candidates_are_not_silently_merged(self):
        # each candidate keeps its own distinct seller article and name
        names = [c['name'] for c in self.match['candidates_found']]
        self.assertEqual(len(names), len(set(names)))


class IdentityAmbiguityTests(unittest.TestCase):
    def setUp(self):
        self.amb = read(STAGE9 / 'identity_ambiguity.json')

    def test_manufacturer_code_confirmed_absent_not_just_unchecked(self):
        search = self.amb['manufacturer_code_search_result']
        self.assertFalse(search['found_in_microdata'])
        self.assertFalse(search['found_in_visible_body_text'])
        self.assertIn('Zero matches', search['regex_scan_result'])

    def test_page_sku_not_conflated_with_catalog_code(self):
        self.assertIn('internal', self.amb['official_page_sku_interpretation'].lower())
        self.assertNotEqual(self.amb['official_page_sku_found'], 'CFI-ZCT1J')
        self.assertNotEqual(self.amb['official_page_sku_found'], 'CFI-ZCT1W')

    def test_ambiguity_not_resolved_by_assumption(self):
        self.assertIn('not', self.amb['which_row_this_report_treats_as_primary'].lower())


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read(STAGE9 / 'evidence.json')

    def test_color_confirmed_via_structured_field_not_url(self):
        color = self.evidence['fields']['color']
        self.assertEqual(color['status'], 'confirmed_structured')
        self.assertNotIn('url', color['source'].lower())

    def test_manual_not_concluded_nonexistent(self):
        manual = self.evidence['fields']['instruction_manual']
        self.assertEqual(manual['status'], 'not_found_in_checked_sources')
        self.assertIn('not as evidence the manual does not exist', manual['scope_note'])

    def test_specifications_marked_qualitative_not_complete(self):
        specs = self.evidence['fields']['specifications']
        self.assertEqual(specs['status'], 'partial_qualitative_only')
        self.assertTrue(specs['not_confirmed'])

    def test_no_broad_search_performed_for_manual(self):
        manual = self.evidence['fields']['instruction_manual']
        self.assertIn('no broad brand search', manual['scope_note'].lower())


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = read(STAGE9 / 'card.json')

    def test_identity_result_is_exact_model_not_exact_variant(self):
        self.assertIn(self.card['identity_result'], IDENTITY_RESULT_VOCAB)
        self.assertEqual(self.card['identity_result'], 'exact_model')

    def test_export_readiness_criterion_stated_explicitly_before_judging(self):
        self.assertTrue(self.card['export_readiness_criterion']['stated_explicitly'])
        self.assertGreaterEqual(len(self.card['export_readiness_criterion']['criteria']), 5)

    def test_gaps_not_labeled_minor_without_explicit_denial(self):
        # The card is allowed to use the word "minor" only to explicitly DENY
        # that a gap is minor (e.g. "not a minor gap") -- never to casually wave
        # one away. Any occurrence of "minor" must appear in a negation.
        blob = json.dumps(self.card).lower()
        self.assertNotIn('insignificant', blob)
        self.assertNotIn('trivial', blob)
        import re
        for m in re.finditer(r'.{0,30}minor', blob):
            self.assertIn('not', m.group(0), f'unqualified use of "minor": {m.group(0)!r}')

    def test_catalog_row_ambiguity_is_the_named_blocking_reason(self):
        check = self.card['criterion_check']
        self.assertFalse(check['2_specific_catalog_row_unambiguous'])
        self.assertIn('indistinguishable', check['2_reason'])
        self.assertIn('cannot be told apart', self.card['export_readiness']['reasoning'])

    def test_export_readiness_not_ready(self):
        self.assertEqual(self.card['export_readiness']['status'], 'not_ready')
        self.assertTrue(self.card['export_readiness']['what_would_close_it'])

    def test_both_catalog_candidates_referenced_in_card(self):
        articles = {c['seller_article'] for c in self.card['catalog_row']['candidates']}
        self.assertEqual(articles, {'CFI-ZCT1J 02', 'CFI-ZCT1W_cosmic_red'})


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = read(STAGE9 / 'checkpoint.json')
        self.attempts = read(STAGE9 / 'run_state.json')['attempts']

    def test_within_declared_budget(self):
        plan = self.checkpoint['budget_declared_before_first_request']
        self.assertLessEqual(self.checkpoint['budget_actual']['total_requests'], plan['request_limits']['max_total_requests'])
        for host, count in self.checkpoint['budget_actual']['by_host'].items():
            self.assertLessEqual(count, plan['request_limits']['max_requests_per_host'])

    def test_only_pre_declared_hosts_contacted(self):
        allowed = set(self.checkpoint['budget_declared_before_first_request']['pre_declared_allowed_hosts'])
        for a in self.attempts:
            self.assertIn(a['url'].split('/')[2], allowed)

    def test_pre_declared_hosts_not_forced_into_use(self):
        unused = self.checkpoint['pre_declared_but_unused_hosts']['hosts']
        contacted = {a['url'].split('/')[2] for a in self.attempts}
        self.assertEqual(contacted & set(unused), set())

    def test_no_request_continues_after_a_confirmed_block(self):
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked = set()
        for a in self.attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked:
                self.fail('request continued on paused host')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked.add(host)

    def test_samsung_not_investigated(self):
        self.assertFalse(self.checkpoint['samsung_investigated_this_stage'])
        blob = json.dumps(self.attempts).lower()
        self.assertNotIn('samsung', blob)


if __name__ == '__main__':
    unittest.main()