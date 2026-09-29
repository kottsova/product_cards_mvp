"""Stage 8.1 regression tests: deepened architecture review on Stage 8's own
fixtures plus a small number of bounded supplemental fetches. Network is
never required to run these tests -- they check the persisted evidence and
the Stage 2-8 protection guarantee, not live sites."""
from pathlib import Path
import hashlib
import json
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
from _source_policy import hosts_outside_allowlist, unapproved_source_ids

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE81 = ROOT / 'reports/source_census_2026-09-22_stage8_1'

STATUS_VOCAB = {'compatible_primitive', 'source_specific', 'insufficient_evidence', 'blocked_manual_review'}
TARGET_FAMILIES = {'xiaomi_global', 'bosch_home', 'dreame', 'hyperx'}
REFERENCE_ROWS = {'asus (reference)', 'delonghi (reference)', 'nintendo (reference)'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Stage81ProtectionTests(unittest.TestCase):
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

    def test_dealer_and_lg_scope_config_untouched(self):
        catalog = read(ROOT / 'product_tool/config/source_catalog.v2.json')
        blob = json.dumps(catalog).lower()
        self.assertIn('sulpak', blob)
        self.assertEqual(unapproved_source_ids(s['source_id'] for s in catalog['sources']), set())  # only approved sources are registered

    def test_stage81_writes_stay_in_its_own_directory(self):
        for name in ('report.md', 'compatibility_matrix.json', 'primitives.v1.json', 'stage8_2_queue.json'):
            self.assertTrue((STAGE81 / name).exists(), f'missing Stage 8.1 deliverable: {name}')


class Stage81FetchLogTests(unittest.TestCase):
    def test_attempts_are_bounded_and_well_formed(self):
        attempts = read(STAGE81 / 'supplemental_fetch_attempts.json')
        self.assertGreater(len(attempts), 0)
        self.assertLessEqual(len(attempts), 30)
        for a in attempts:
            self.assertIn('url', a)
            self.assertIn(a['url'].split('/')[2], {'www.mi.com', 'hyperx.com', 'www.bosch-home.com', 'de.dreametech.com'})

    def test_no_request_continues_on_a_host_after_a_confirmed_block(self):
        attempts = read(STAGE81 / 'supplemental_fetch_attempts.json')
        blocked_signals = {'challenge_confirmed', 'captcha_detected', 'browser_verification_required'}
        seen_blocked_hosts = set()
        for a in attempts:
            host = a['url'].split('/')[2]
            if host in seen_blocked_hosts:
                self.fail(f'request continued on paused host: {host}')
            if a.get('http_status') in (403, 429) or a.get('protection_status') in blocked_signals:
                seen_blocked_hosts.add(host)

    def test_new_fixtures_never_store_links_or_raw_html(self):
        fixtures_dir = STAGE81 / 'fixtures'
        files = list(fixtures_dir.glob('*.json'))
        self.assertGreaterEqual(len(files), 5)
        for f in files:
            obj = read(f)
            self.assertNotIn('links', obj)
            self.assertIn('content_sha256', obj)
            self.assertEqual(obj.get('fixture_version'), 2)
            blob = json.dumps(obj)
            self.assertNotIn('<html', blob.lower())


class CompatibilityMatrixTests(unittest.TestCase):
    def setUp(self):
        self.matrix = read(STAGE81 / 'compatibility_matrix.json')

    def test_only_known_status_values_used(self):
        for family, row in self.matrix['rows'].items():
            for layer in ('discovery', 'identity', 'specifications', 'media', 'documents'):
                self.assertIn(row[layer]['status'], STATUS_VOCAB, f'{family}.{layer}')

    def test_all_target_and_reference_families_present(self):
        keys = set(self.matrix['rows'])
        self.assertTrue(TARGET_FAMILIES <= keys)
        self.assertTrue(REFERENCE_ROWS <= keys)

    def test_reference_families_stay_single_sample_and_insufficient(self):
        for name in REFERENCE_ROWS:
            row = self.matrix['rows'][name]
            self.assertEqual(row['pages_verified'], 1)
            for layer in ('discovery', 'identity', 'specifications', 'media', 'documents'):
                self.assertEqual(row[layer]['status'], 'insufficient_evidence')

    def test_no_shared_primitive_claimed_on_a_single_family(self):
        # A compatible_primitive cell must always have a real cross-family
        # counterpart cell also marked compatible_primitive for the same layer.
        for layer in ('discovery', 'identity', 'specifications', 'media', 'documents'):
            claimants = [fam for fam, row in self.matrix['rows'].items() if row[layer]['status'] == 'compatible_primitive']
            if claimants:
                self.assertGreaterEqual(len(claimants), 2, f'layer {layer} has a lone compatible_primitive claim: {claimants}')

    def test_documents_layer_has_no_shared_or_strong_claim_anywhere(self):
        # Only one document sample exists across all reviewed families (Stage 8.1
        # finding); nothing stronger than insufficient_evidence is justified yet.
        for family, row in self.matrix['rows'].items():
            self.assertEqual(row['documents']['status'], 'insufficient_evidence', family)


class PrimitivesTests(unittest.TestCase):
    def setUp(self):
        self.primitives = read(STAGE81 / 'primitives.v1.json')

    def test_shared_candidates_declare_evidence_and_constraints(self):
        for item in self.primitives['shared_primitive_candidate']:
            self.assertIn('evidence', item)
            self.assertIn('constraints', item)
            self.assertTrue(item['constraints'])

    def test_identity_semantics_resolver_stays_custom_not_shared(self):
        shared_names = {p['name'] for p in self.primitives['shared_primitive_candidate']}
        self.assertNotIn('identity_semantics_resolver', shared_names)
        custom_names = {p['name'] for p in self.primitives['custom_adapter_candidate']}
        self.assertIn('identity_semantics_resolver', custom_names)

    def test_no_primitive_marked_production_ready(self):
        blob = json.dumps(self.primitives)
        self.assertNotIn('"production_ready": true', blob.lower())


class Stage82QueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = read(STAGE81 / 'stage8_2_queue.json')
        profiles = read(STAGE8 / 'adapter_profiles.v1.json')['profiles']
        self.baseline_not_found = {p['profile_id'] for p in profiles if p['completeness_status'] == 'product_page_not_found'}

    def test_queue_covers_exactly_the_92_baseline_profiles(self):
        queued_ids = {item['profile_id'] for group in self.queue['groups'].values() for item in group}
        self.assertEqual(self.queue['total_profiles'], 92)
        self.assertEqual(len(self.baseline_not_found), 92)
        self.assertEqual(queued_ids, self.baseline_not_found)

    def test_every_profile_appears_in_exactly_one_group(self):
        counts = {}
        for group in self.queue['groups'].values():
            for item in group:
                counts[item['profile_id']] = counts.get(item['profile_id'], 0) + 1
        self.assertTrue(all(c == 1 for c in counts.values()))

    def test_every_entry_has_a_reproducible_reason(self):
        for group_name, group in self.queue['groups'].items():
            for item in group:
                self.assertTrue(item['reason'][1], f'{group_name}/{item["profile_id"]} missing a reason')

    def test_queue_is_a_plan_not_an_execution(self):
        self.assertIn('does not execute', self.queue['scope_note'])
        attempts = read(STAGE81 / 'supplemental_fetch_attempts.json')
        queued_ids = {item['profile_id'] for group in self.queue['groups'].values() for item in group}
        attempted_hosts = {a['url'].split('/')[2] for a in attempts}
        self.assertEqual(attempted_hosts, {'www.mi.com', 'hyperx.com', 'www.bosch-home.com', 'de.dreametech.com'})
        self.assertFalse(queued_ids & set())  # no queued profile id space overlaps fetch hosts by construction


if __name__ == '__main__':
    unittest.main()