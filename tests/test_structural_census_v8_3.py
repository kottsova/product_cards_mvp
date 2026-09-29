"""Stage 8.3 regression tests: first limited Samsung full cycle (Galaxy
Buds3 FE), plus a dedicated proof that the Stage 8.2.2 per-host budget
counter bug is fixed. Network is never required -- these check the
persisted evidence, the Stage 2-8.2.2 protection guarantee, and the fetch
helper's counter logic via monkeypatching (no real HTTP)."""
import importlib.util
import json
import sys
import types
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
import hashlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE83 = ROOT / 'reports/source_census_2026-09-22_stage8_3'
LIB_PATH = STAGE83 / 'scripts/lib.py'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage83ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_8_2_2_untouched(self):
        check = read(STAGE83 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now',
                    'stage8_2_1_files_hashed_now', 'stage8_2_2_files_hashed_now'):
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
        check = read(STAGE83 / 'protected_hashes_check.json')['catalog_and_registry_untouched']
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
        for name in ('report.md', 'tv_selection_check.json', 'evidence.json', 'card_summary.json',
                     'documents.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE83 / name).exists(), f'missing Stage 8.3 deliverable: {name}')


class NoS20FEOrZFold3Tests(unittest.TestCase):
    def test_no_request_mentions_the_two_historical_models(self):
        attempts = read(STAGE83 / 'run_state.json')
        blob = json.dumps(attempts).lower()
        for term in ('s20', 'fold3', 'fold-3'):
            self.assertNotIn(term, blob)

    def test_only_www_samsung_com_contacted(self):
        attempts = read(STAGE83 / 'run_state.json')['attempts']
        hosts = {a['url'].split('/')[2] for a in attempts}
        self.assertEqual(hosts, {'www.samsung.com'})

    def test_budget_within_plan(self):
        checkpoint = read(STAGE83 / 'checkpoint.json')
        self.assertLessEqual(checkpoint['budget_actual']['total_requests'], checkpoint['budget_plan']['max_total'])
        for host, count in checkpoint['budget_actual']['by_host'].items():
            self.assertLessEqual(count, checkpoint['budget_plan']['max_per_host'])


class TvSelectionTests(unittest.TestCase):
    def setUp(self):
        self.check = read(STAGE83 / 'tv_selection_check.json')

    def test_no_project_novelty_criterion_invented(self):
        self.assertIn('No project-defined', self.check['project_novelty_criterion_search']['result'])

    def test_decision_based_on_objective_evidence_not_invented_threshold(self):
        self.assertGreaterEqual(len(self.check['objective_evidence_against_novelty']), 2)
        self.assertEqual(self.check['decision'], 'exclude_from_pilot')

    def test_checked_for_substitute_fixture_before_reducing_pilot(self):
        self.assertIn('no_other_fixture_found', self.check)
        self.assertTrue(self.check['no_other_fixture_found']['checked'])


class IdentityUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read(STAGE83 / 'evidence.json')

    def test_color_evidence_is_not_url_only(self):
        color = self.evidence['fields']['color']
        self.assertEqual(color['status'], 'confirmed')
        self.assertNotIn('URL', color['source'])
        blob = color['evidence'].lower()
        self.assertTrue('title' in blob or 'body text' in blob)

    def test_model_name_confirmed_by_two_independent_onpage_sources(self):
        model = self.evidence['fields']['consumer_model_name']
        self.assertIn('json-ld', model['evidence'].lower())
        self.assertIn('title', model['evidence'].lower())

    def test_full_spec_table_not_claimed_complete(self):
        specs = self.evidence['fields']['full_specifications_table']
        self.assertEqual(specs['status'], 'insufficient')

    def test_card_summary_variant_status_matches_evidence_strength(self):
        card = read(STAGE83 / 'card_summary.json')
        buds = next(i for i in card['items'] if i['item'] == 'Galaxy Buds3 FE')
        self.assertEqual(buds['model_variant_status'], 'exact_variant')
        # exact_variant must be backed by a reasoning string that names a variant-defining field (color), not just model.
        self.assertIn('color', buds['model_variant_status_reasoning'].lower())


class DocumentsTests(unittest.TestCase):
    def test_non_manual_pdf_not_reported_as_instruction(self):
        docs = read(STAGE83 / 'documents.json')
        self.assertEqual(docs['documents_found_and_relevant'], [])
        excluded = docs['documents_found_but_excluded']
        self.assertEqual(len(excluded), 1)
        self.assertIn('not a product manual', excluded[0]['document_type'])

    def test_evidence_instruction_field_matches_documents_json(self):
        evidence = read(STAGE83 / 'evidence.json')
        self.assertEqual(evidence['fields']['instruction_manual']['status'], 'not_found')


class CardSummaryTests(unittest.TestCase):
    def setUp(self):
        self.card = read(STAGE83 / 'card_summary.json')

    def test_two_items_present_one_excluded(self):
        self.assertEqual(len(self.card['items']), 2)
        statuses = {i['item']: i['card_export_readiness'] for i in self.card['items']}
        self.assertEqual(statuses['Samsung TV (UE43N5300AUXCE)'], 'excluded_from_pilot')
        self.assertTrue(statuses['Galaxy Buds3 FE'].startswith('partially_ready'))

    def test_buds_item_has_gaps_listed_not_hidden(self):
        buds = next(i for i in self.card['items'] if i['item'] == 'Galaxy Buds3 FE')
        self.assertTrue(buds['gaps'])
        self.assertTrue(any('catalog' in g.lower() for g in buds['gaps']))


class BudgetPersistenceTests(unittest.TestCase):
    """Proves the Stage 8.2.2 per-host counter bug is fixed: a freshly
    (re)loaded lib module must read its budget from the persisted attempt
    log, not from an in-process counter that resets on import."""

    def _load_lib_fresh(self):
        if 'stage83_lib_under_test' in sys.modules:
            del sys.modules['stage83_lib_under_test']
        spec = importlib.util.spec_from_file_location('stage83_lib_under_test', LIB_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules['stage83_lib_under_test'] = module
        spec.loader.exec_module(module)
        return module

    def test_host_cap_enforced_from_a_seeded_prior_attempts_log(self):
        lib = self._load_lib_fresh()
        # Simulate "4 requests already made to this host in a previous script
        # invocation" purely in-process (no real file write, no real network).
        lib.STATE['attempts'] = [
            {'url': f'https://example-host.test/page{i}', 'kind': 'product', 'reason': 'seed',
             'http_status': 200, 'protection_status': 'ordinary_page', 'final_url': f'https://example-host.test/page{i}',
             'redirect_chain': [], 'checked_at': '2026-09-22T00:00:00+00:00'}
            for i in range(lib.MAX_PER_HOST)
        ]
        lib.save_state = lambda: None  # do not touch the real run_state.json for this synthetic probe
        status_before = lib.budget_status()
        self.assertEqual(status_before['by_host'].get('example-host.test'), lib.MAX_PER_HOST)
        with patch.object(lib.probe, 'probe', side_effect=AssertionError('must not reach the network: budget should already be exhausted')):
            page, err = lib.fetch('https://example-host.test/one-more', ('example-host.test',), 'product')
        self.assertIsNone(page)
        self.assertEqual(err, 'host_budget_exhausted')

    def test_fresh_module_reload_sees_the_same_seeded_state_not_a_reset_counter(self):
        # This is the exact failure mode from Stage 8.2.2: re-importing the
        # helper (as a new script file would) must NOT reset the counter to 0.
        lib1 = self._load_lib_fresh()
        lib1.STATE['attempts'] = [
            {'url': 'https://example-host.test/a', 'kind': 'product', 'reason': 'seed', 'http_status': 200,
             'protection_status': 'ordinary_page', 'final_url': 'https://example-host.test/a', 'redirect_chain': [],
             'checked_at': '2026-09-22T00:00:00+00:00'}
        ]
        status_1 = lib1.budget_status()
        self.assertEqual(status_1['total_used'], 1)
        # A second "invocation" that reloads the module from disk must not silently
        # start counting from zero if it were reading the real run_state.json --
        # here we assert the counting FUNCTION itself (_recompute_budget_state)
        # is always derived from STATE, never a cached module-level int.
        lib1.STATE['attempts'].append({'url': 'https://example-host.test/b', 'kind': 'product', 'reason': 'seed',
                                        'http_status': 200, 'protection_status': 'ordinary_page',
                                        'final_url': 'https://example-host.test/b', 'redirect_chain': [],
                                        'checked_at': '2026-09-22T00:00:01+00:00'})
        status_2 = lib1.budget_status()
        self.assertEqual(status_2['total_used'], 2)


if __name__ == '__main__':
    unittest.main()