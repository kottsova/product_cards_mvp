"""Stage 11.3 regression tests: DNS product page + PDF check for HyperX
QuadCast 2S (9A273AA), content-verified model mismatch, and the formalized
DNS dealer-fallback rule. Network is never required."""
from pathlib import Path
import hashlib
import json
import unittest

from _source_policy import hosts_outside_allowlist, unapproved_source_ids

ROOT = Path(__file__).resolve().parents[1]
STAGE11_3 = ROOT / 'reports/source_census_2026-09-23_stage11_3'


def read(name):
    return json.loads((STAGE11_3 / name).read_text(encoding='utf-8'))


class DnsPageTests(unittest.TestCase):
    def setUp(self):
        self.phase1 = read('phase1_robots_and_dns_page.json')

    def test_page_was_blocked_401(self):
        self.assertEqual(self.phase1['page_http_status'], 401)

    def test_identity_not_confirmed_via_blocked_page(self):
        self.assertEqual(self.phase1['identity_check']['conclusion'], 'not_confirmed_insufficient_page_evidence')


class PdfContentVerificationTests(unittest.TestCase):
    def setUp(self):
        self.pdf = read('pdf_content_verification.json')

    def test_pdf_fetched_completely(self):
        phase2 = read('phase2_pdf_fetch.json')
        self.assertEqual(phase2['completeness'], 'complete')
        self.assertEqual(phase2['bytes_assembled'], phase2['declared_total_bytes'])

    def test_no_model_or_sku_mentions_found(self):
        self.assertEqual(self.pdf['model_name_quadcast_2s_mentions_in_pdf_text'], 0)
        self.assertEqual(self.pdf['manufacturer_code_9A273AA_mentions_in_pdf_text'], 0)

    def test_hyperx_mentioned_confirming_manufacturer_origin(self):
        self.assertGreater(self.pdf['hyperx_mentions_in_pdf_text'], 0)

    def test_languages_detected(self):
        self.assertIn('en', self.pdf['languages_present_overall'])
        self.assertIn('ru', self.pdf['languages_present_overall'])


class CardVerdictTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_pdf_verdict_is_content_verified_mismatch(self):
        verdict = self.card['pdf_content_verdict']['verdict']
        self.assertIn('MISMATCH', verdict)
        self.assertIn('REJECTED', verdict)

    def test_document_identified_as_original_quadcast_not_2s(self):
        detail = self.card['pdf_content_verdict']['part_number_found_throughout']
        self.assertIn('HX-MICQC', detail)
        self.assertIn('ORIGINAL', detail)

    def test_manufacturer_origin_confirmed_true(self):
        self.assertTrue(self.card['pdf_content_verdict']['is_manufacturer_produced'])

    def test_declarations_and_certificates_not_considered(self):
        self.assertIn('Not searched for', self.card['pdf_content_verdict']['declarations_certificates_note'])

    def test_manual_status_not_declared_absent(self):
        status = self.card['manual_status_for_9A273AA']
        self.assertEqual(status['status'], 'still_not_confirmed_online_not_declared_absent')
        self.assertIn('not a statement that no such document exists', status['explicit_statement'])

    def test_dealer_fallback_rule_recorded_with_priority_and_provenance_requirements(self):
        rule = self.card['dns_dealer_fallback_rule']
        self.assertIn('official source always has priority', rule['rule_text'])
        self.assertIn('own URL', rule['rule_text'])
        self.assertIn('never imported wholesale', rule['rule_text'])
        self.assertIn('goes to human review', rule['rule_text'])

    def test_rule_tested_only_on_9A273AA(self):
        self.assertIn('9A273AA only', self.card['dns_dealer_fallback_rule']['tested_this_stage_on'])

    def test_existing_dealer_scope_explicitly_unchanged(self):
        # The frozen card records this statement under a key ending in
        # '_unchanged'; pin its exact bytes instead of matching prose.
        rule = self.card['dns_dealer_fallback_rule']
        keys = [k for k in rule if k.endswith('_unchanged')]
        self.assertEqual(len(keys), 1)
        text = rule[keys[0]]
        self.assertIn('untouched this stage', text)
        self.assertEqual(hashlib.sha256(text.encode('utf-8')).hexdigest(),
                         'c762cba09be0723b60661add08c6303989a02b801fa4ff2958f9138368a5d970')

    def test_production_registry_not_modified_by_rule(self):
        self.assertIn('NOT modified', self.card['dns_dealer_fallback_rule']['production_registry_status'])


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_requests(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(set(self.budget['allowed_hosts']), {'www.dns-shop.ru', 'drv.dns-shop.ru'})

    def test_all_requests_on_allowed_hosts_within_budget(self):
        self.assertLessEqual(self.checkpoint['total_requests_made'], self.budget['limits']['max_requests_total'])
        for entry in self.checkpoint['request_log_full']:
            url = entry.get('requested_url', '')
            self.assertTrue('dns-shop.ru' in url, url)

    def test_no_other_dealer_or_brand_contacted(self):
        flags = [k for k in self.checkpoint if k.endswith('_contacted_this_stage')]
        self.assertEqual(len(flags), 1)
        self.assertFalse(self.checkpoint[flags[0]])
        urls = [entry['requested_url'] for entry in self.checkpoint['request_log_full']]
        self.assertEqual(hosts_outside_allowlist(urls, self.budget['allowed_hosts']), set())
        for entry in self.checkpoint['request_log_full']:
            for forbidden in ('sulpak', 'kingston.com', 'hiper', 'hyperx.com'):
                self.assertNotIn(forbidden, entry['requested_url'].lower())


class ProductionRegistryUntouchedTests(unittest.TestCase):
    def test_source_catalog_has_no_dns_entry(self):
        catalog = json.loads((ROOT / 'product_tool/config/source_catalog.v2.json').read_text(encoding='utf-8'))
        blob = json.dumps(catalog).lower()
        self.assertNotIn('dns-shop', blob)

    def test_sulpak_allowlist_unchanged(self):
        catalog = json.loads((ROOT / 'product_tool/config/source_catalog.v2.json').read_text(encoding='utf-8'))
        sulpak = next(s for s in catalog['sources'] if s['source_id'] == 'sulpak')
        self.assertEqual(set(sulpak['category_allowlist']), {'Стиральные машины', 'Сушильные машины', 'Холодильники', 'Пылесосы', 'Микроволновые печи'})

    def test_only_approved_sources_registered(self):
        catalog = json.loads((ROOT / 'product_tool/config/source_catalog.v2.json').read_text(encoding='utf-8'))
        self.assertEqual(unapproved_source_ids(s['source_id'] for s in catalog['sources']), set())


class IntegrityTests(unittest.TestCase):
    def test_catalog_and_registry_untouched(self):
        from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file
        check = read('protected_hashes_check.json')
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
        self.assertTrue(check['production_registry_unchanged_dns_not_added'])

    def test_all_prior_stages_unchanged_including_11_2(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 660)
        self.assertIn('source_census_2026-09-23_stage11_2', check['prior_stage_directories_hashed'])
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'phase1_robots_and_dns_page.json', 'phase2_pdf_fetch.json',
                     'pdf_content_verification.json', 'budget_predeclaration.json', 'card.json',
                     'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE11_3 / name).exists(), f'missing Stage 11.3 deliverable: {name}')

    def test_no_pdf_binary_committed(self):
        found = [p for p in STAGE11_3.rglob('*.pdf')]
        self.assertEqual(found, [], f'raw PDF bytes committed to repo: {found}')


if __name__ == '__main__':
    unittest.main()
