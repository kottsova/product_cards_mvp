"""Stage 8.5 regression tests: point verification and completion of the
Samsung MS23K3614AK/BW catalog card (PDF content check, spec completeness,
image verification). Network is never required -- these check the
persisted evidence and the Stage 2-8.4 protection guarantee."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
from _source_policy import hosts_outside_allowlist

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE85 = ROOT / 'reports/source_census_2026-09-22_stage8_5'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage85ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_8_4_untouched(self):
        check = read(STAGE85 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now', 'stage8_2_1_files_hashed_now',
                    'stage8_2_2_files_hashed_now', 'stage8_3_files_hashed_now', 'stage8_4_files_hashed_now'):
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
        check = read(STAGE85 / 'protected_hashes_check.json')['catalog_and_registry_untouched']
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
        for name in ('report.md', 'evidence_separation.json', 'pdf_content_verification.json',
                     'specs_completeness.json', 'image_verification.json', 'card.json',
                     'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE85 / name).exists(), f'missing Stage 8.5 deliverable: {name}')


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = read(STAGE85 / 'checkpoint.json')
        self.attempts = read(STAGE85 / 'run_state.json')['attempts']

    def test_budget_declared_includes_pdf_serving_domain(self):
        allowed = self.checkpoint['budget_declared_before_first_request']['pre_declared_allowed_hosts']
        self.assertIn('org.downloadcenter.samsung.com', allowed)
        self.assertIn('downloadcenter.samsung.com', allowed)

    def test_within_plan(self):
        self.assertLessEqual(self.checkpoint['budget_actual']['total_requests'], self.checkpoint['budget_declared_before_first_request']['max_total'])
        for host, count in self.checkpoint['budget_actual']['by_host'].items():
            self.assertLessEqual(count, self.checkpoint['budget_declared_before_first_request']['max_per_host'])

    def test_only_pre_declared_hosts_contacted(self):
        allowed = set(self.checkpoint['budget_declared_before_first_request']['pre_declared_allowed_hosts'])
        for a in self.attempts:
            host = a['url'].split('/')[2]
            self.assertIn(host, allowed)

    def test_rejected_attempts_kept_separate_from_executed(self):
        self.assertIn('rejected_attempts', self.checkpoint)
        # Any rejected entry must not also appear counted among executed request results.
        rejected_urls = {r['url'] for r in self.checkpoint['rejected_attempts']}
        executed_urls = {a['url'] for a in self.attempts}
        self.assertEqual(rejected_urls & executed_urls, set())

    def test_no_chromium_or_search_engine_or_dealer_terms(self):
        blob = json.dumps(self.attempts).lower()
        for forbidden in ('chromium', 'google.', 'bing.', 'duckduckgo.', 'sulpak'):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(hosts_outside_allowlist((a['url'] for a in self.attempts), {'samsung.com'}), set())

    def test_no_request_continues_after_a_confirmed_block(self):
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked = set()
        for a in self.attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked:
                self.fail('request continued on paused host')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked.add(host)


class EvidenceSeparationTests(unittest.TestCase):
    def test_modelname_parameter_flagged_as_linkage_only(self):
        sep = read(STAGE85 / 'evidence_separation.json')
        pdf_strand = sep['independent_evidence_strands']['pdf_link_modelname_parameter']
        self.assertIn('NOT independent confirmation', pdf_strand['independence_note'])

    def test_four_independent_strands_present(self):
        sep = read(STAGE85 / 'evidence_separation.json')
        self.assertEqual(len(sep['independent_evidence_strands']), 4)


class PdfContentVerificationTests(unittest.TestCase):
    def setUp(self):
        self.pdf = read(STAGE85 / 'pdf_content_verification.json')

    def test_text_not_claimed_extracted(self):
        self.assertFalse(self.pdf['conclusion']['text_extracted'])

    def test_language_not_inferred_from_filename(self):
        self.assertIn('NOT used', self.pdf['conclusion']['language_not_inferred_from_filename'])

    def test_official_status_matches_the_instructed_fallback_exactly(self):
        self.assertEqual(self.pdf['conclusion']['official_status'], 'official PDF candidate; content/language not confirmed')

    def test_truncation_is_the_stated_reason_not_a_vague_failure(self):
        self.assertIn('1.5MB', self.pdf['conclusion']['reason'])

    def test_size_cap_not_raised(self):
        self.assertIn('Same 1,500,000-byte cap', self.pdf['method']['size_limit_respected'])


class SpecsCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.specs = read(STAGE85 / 'specs_completeness.json')

    def test_confirmed_fields_have_evidence(self):
        for f in self.specs['confirmed_with_evidence']:
            self.assertTrue(f['evidence'])

    def test_unknown_characteristics_listed_not_invented(self):
        self.assertGreaterEqual(len(self.specs['important_characteristics_still_unknown']), 5)
        for item in self.specs['labels_found_but_value_not_confirmed']:
            self.assertEqual(item['status'], 'label_present_value_not_found_in_static_text')


class ImageVerificationTests(unittest.TestCase):
    def test_image_confirmed_reachable_and_real(self):
        img = read(STAGE85 / 'image_verification.json')
        self.assertEqual(img['fit_for_card_use']['status'], 'confirmed')
        self.assertIn('png', img['fit_for_card_use']['evidence'].lower())


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = read(STAGE85 / 'card.json')

    def test_identity_result_exact_variant(self):
        self.assertEqual(self.card['identity_result'], 'exact_variant')

    def test_manual_not_confirmed_by_content(self):
        self.assertFalse(self.card['manual_confirmed_by_content'])

    def test_russian_not_confirmed(self):
        self.assertFalse(self.card['russian_language_confirmed'])

    def test_manual_field_status_is_the_exact_fallback_string(self):
        self.assertEqual(self.card['fields']['instruction_manual']['status'], 'official_pdf_candidate_content_language_not_confirmed')

    def test_missing_characteristics_not_empty(self):
        self.assertGreaterEqual(len(self.card['missing_characteristics']), 5)

    def test_export_readiness_is_partial_not_blocked_not_complete(self):
        status = self.card['export_readiness']['status']
        self.assertEqual(status, 'partially_ready')
        self.assertTrue(self.card['export_readiness']['blocking_or_flagged_gaps'])

    def test_every_confirmed_field_has_a_url(self):
        for name, f in self.card['fields'].items():
            if f['status'] == 'confirmed':
                self.assertIn('url', f, name)
                self.assertTrue(f['url'], name)


if __name__ == '__main__':
    unittest.main()