"""Stage 10.1 regression tests: bounded verification of www.xbox.com and
support.xbox.com as candidate Microsoft/Xbox sources, and targeted confirmation
of the Xbox Series S Carbon 1TB variant against catalog row XXU-00015. Network
is never required -- these check persisted evidence, the pre-declared budget,
host-role separation, and the untouched-registry guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE10_1 = ROOT / 'reports/source_census_2026-09-23_stage10_1'


def read(name):
    return json.loads((STAGE10_1 / name).read_text(encoding='utf-8'))


class OfflineProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.provenance = read('offline_provenance.json')

    def test_only_two_named_hosts_in_scope(self):
        self.assertEqual(set(self.provenance['links_in_scope_for_this_stage']), {'www.xbox.com', 'support.xbox.com'})

    def test_microsoft_store_links_excluded_this_stage(self):
        for url in self.provenance['links_excluded_this_stage_explicit_user_scope']:
            self.assertIn('www.microsoft.com', url)

    def test_origin_page_matches_stage10_evidence(self):
        origin = self.provenance['origin_page']
        self.assertEqual(origin['http_status'], 200)
        self.assertEqual(origin['final_url_after_redirect'], 'https://support.microsoft.com/en-us/all-products-list')


class ResearchSourceProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = read('research_source_profile.json')

    def test_not_enabled_and_not_research_enabled_initially(self):
        for domain in self.profile['domains']:
            self.assertFalse(domain['enabled'])
        self.assertIn('NOT merged', self.profile['usage'])

    def test_official_domains_registry_not_touched_by_this_profile(self):
        official = json.loads((ROOT / 'product_tool/config/official_domains.v1.json').read_text(encoding='utf-8'))
        blob = json.dumps(official).lower()
        self.assertNotIn('xbox.com', blob)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.revision = read('budget_revision_1_document_fetch.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_requests(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(set(self.budget['allowed_hosts']), {'www.xbox.com', 'support.xbox.com'})

    def test_revision_declared_before_further_requests(self):
        self.assertTrue(self.revision['declared_before_any_request_under_these_values'])

    def test_all_requests_stayed_on_allowed_hosts(self):
        for entry in self.checkpoint['request_log_full']:
            url = entry.get('requested_url', '')
            self.assertTrue('www.xbox.com' in url or 'support.xbox.com' in url, url)

    def test_no_protection_stop_events(self):
        self.assertFalse(self.checkpoint['stop_events']['403_429_or_challenge_seen'])


class HostRoleTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_www_xbox_com_confirmed_product_role(self):
        host = self.card['host_confirmations']['www.xbox.com']
        self.assertEqual(host['official_status_this_stage'], 'confirmed_official')
        self.assertIn('product_page', host['role_confirmed_this_stage'])

    def test_support_xbox_com_role_support_but_content_unverified(self):
        host = self.card['host_confirmations']['support.xbox.com']
        self.assertIn('support', host['role_confirmed_this_stage'])
        self.assertIn('content_access_blocker', host)


class VariantEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_exact_variant_found_and_not_confused_with_other_skus(self):
        ev = self.card['variant_evidence']
        self.assertTrue(ev['found'])
        self.assertIn('Carbon Black', ev['matches_target_variant'])
        self.assertEqual(len(ev['not_confused_with']), 2)

    def test_seller_sku_absence_not_treated_as_problem(self):
        self.assertIn('not expected to appear', self.card['variant_evidence']['caveat'])

    def test_linkage_states_descriptive_not_code_confirmed(self):
        linkage = self.card['catalog_row_to_official_variant_linkage']
        self.assertEqual(linkage['linkage_status'], 'linked_by_descriptive_consistency_not_code_confirmed')
        self.assertFalse(linkage['manufacturer_code_confirmed_on_official_page'])
        self.assertEqual(linkage['conflicting_fields'], [])


class CardReadinessTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_four_of_five_criteria_pass(self):
        crit = self.card['five_point_export_readiness_criterion']
        passing = [k for k, v in crit.items() if v['pass']]
        self.assertEqual(len(passing), 4)
        self.assertFalse(crit['criterion_5_manual_confirmed_present_or_absence_noted']['pass'])

    def test_export_readiness_not_ready_but_reason_is_narrow(self):
        self.assertEqual(self.card['export_readiness'], 'not_ready')
        self.assertIn('criterion 5', self.card['export_readiness_reason'])

    def test_manual_gap_not_falsely_marked_absent(self):
        manual = self.card['not_exportable_this_stage']['instruction_manual']
        self.assertNotIn('confirmed absent', manual.lower())
        self.assertIn('javascript', manual.lower())

    def test_no_promotion_to_production_registry_recorded(self):
        outcome = self.card['research_source_profile_outcome']
        blob = ' '.join(outcome.values())
        self.assertIn('NOT promoted', blob)
        self.assertIn('non-promotion note applies', blob)


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
        self.assertTrue(check['no_host_promoted_to_registries_this_stage'])

    def test_stage10_and_all_prior_stage_files_unchanged(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 500)
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'offline_provenance.json', 'research_source_profile.json',
                     'budget_predeclaration.json', 'budget_revision_1_document_fetch.json',
                     'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE10_1 / name).exists(), f'missing Stage 10.1 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
