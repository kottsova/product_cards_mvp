"""Stage 8.6 regression tests: bounded verification of large official
instructions as a reusable pipeline capability. Network is never required --
the completeness-classification logic is unit-tested against synthetic
responses (monkeypatched requests.Session.get), and the rest checks
persisted evidence plus the Stage 2-8.5 protection guarantee."""
import hashlib
import importlib.util
import json
import sys
import unittest

from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file, is_deleted_file_path
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STAGE8 = ROOT / 'reports/source_census_2026-09-22_stage8'
STAGE86 = ROOT / 'reports/source_census_2026-09-22_stage8_6'
LIB_PATH = STAGE86 / 'scripts/lib.py'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _load_lib_fresh():
    mod_name = 'stage86_lib_under_test'
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code, headers, body, url='https://downloadcenter.samsung.com/content/fake.pdf', history=None):
        self.status_code = status_code
        self.headers = headers
        self._body = body
        self.url = url
        self.history = history or []

    def iter_content(self, chunk_size=32_768):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class Stage86ProtectionTests(unittest.TestCase):
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

    def test_stage8_1_through_8_5_untouched(self):
        check = read(STAGE86 / 'protected_hashes_check.json')
        for key in ('stage8_1_files_hashed_now', 'stage8_2_files_hashed_now', 'stage8_2_1_files_hashed_now',
                    'stage8_2_2_files_hashed_now', 'stage8_3_files_hashed_now', 'stage8_4_files_hashed_now',
                    'stage8_5_files_hashed_now'):
            for rel, expected in check[key].items():
                full = ROOT / rel
                self.assertTrue(full.exists(), f'missing: {rel}')
                actual = hashlib.sha256(full.read_bytes()).hexdigest()
                if rel in ALL_AUTHORIZED_CHANGES:
                    ok, msg = check_migrated_file(rel, actual)
                    self.assertTrue(ok, msg)
                    continue
                self.assertEqual(actual, expected, f'changed: {rel}')

    def test_stage8_5_card_specifically_unchanged(self):
        # the most important single file to double-check: Stage 8.5's own conclusion must not be edited.
        card_path = ROOT / 'reports/source_census_2026-09-22_stage8_5/card.json'
        card = read(card_path)
        self.assertFalse(card['manual_confirmed_by_content'])
        self.assertFalse(card['russian_language_confirmed'])

    def test_catalog_and_registry_untouched(self):
        check = read(STAGE86 / 'protected_hashes_check.json')['catalog_and_registry_untouched']
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
        for name in ('report.md', 'offline_review.json', 'budget_predeclaration.json', 'budget_revision.json',
                     'assembly_result_attempt1_6mb_cap.json', 'assembly_result.json', 'content_verification.json',
                     'updated_card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE86 / name).exists(), f'missing Stage 8.6 deliverable: {name}')

    def test_no_raw_pdf_bytes_committed(self):
        for f in STAGE86.rglob('*'):
            self.assertNotIn(f.suffix.lower(), ('.pdf',), f'raw PDF committed: {f}')


class CompletenessClassificationUnitTests(unittest.TestCase):
    """Exercises fetch_document_bounded()'s classification logic with fully
    synthetic, monkeypatched HTTP responses -- no network."""

    def setUp(self):
        self.lib = _load_lib_fresh()
        self.lib.STATE['attempts'] = []
        self.lib.STATE['rejected_attempts'] = []
        self.lib.save_state = lambda: None  # don't touch the real run_state.json from unit tests

    def test_range_supported_full_assembly_reports_complete(self):
        total = 3_000_000
        chunk = self.lib.DOCUMENT_CHUNK_BYTES

        def fake_get(url, timeout, headers, allow_redirects, stream):
            rng = headers['Range'].split('=')[1]
            start, end = (int(x) for x in rng.split('-'))
            end = min(end, total - 1)
            body = b'\xff' * (end - start + 1)
            return FakeResponse(206, {
                'Content-Range': f'bytes {start}-{end}/{total}', 'ETag': '"same"',
                'Last-Modified': 'Tue, 23 Jul 2019 07:48:12 GMT',
            }, body)

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'complete')
        self.assertEqual(len(result['bytes']), total)
        self.assertEqual(result['declared_total_bytes'], total)

    def test_truncated_binary_detected_as_exceeding_declared_cap(self):
        total = self.lib.MAX_DOCUMENT_TOTAL_BYTES + 1_000_000  # deliberately over the cap

        def fake_get(url, timeout, headers, allow_redirects, stream):
            return FakeResponse(206, {'Content-Range': f'bytes 0-{self.lib.DOCUMENT_CHUNK_BYTES - 1}/{total}', 'ETag': '"x"'},
                                 b'\x00' * self.lib.DOCUMENT_CHUNK_BYTES)

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'unknown_completeness')
        self.assertIsNone(result['bytes'])
        self.assertIn('exceeds_declared_cap', result['reason'])

    def test_byte_count_used_not_text_length(self):
        # A body containing bytes that are NOT valid UTF-8 (e.g. 0xFF) must still be
        # counted by its true byte length -- this is the Stage 8.4 bug this stage fixes.
        # A repeated valid 2-byte UTF-8 sequence (\xc3\xa9 = 'e') decodes cleanly but at
        # HALF the character length of its byte length -- this is what makes measuring
        # len(decoded_string) as a stand-in for byte count unreliable (the Stage 8.4 bug).
        total = 500_000
        raw_body = b'\xc3\xa9' * (total // 2)

        def fake_get(url, timeout, headers, allow_redirects, stream):
            return FakeResponse(206, {'Content-Range': f'bytes 0-{total - 1}/{total}', 'ETag': '"x"'}, raw_body)

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'complete')
        # The true byte length must match exactly -- decoding this body as UTF-8 with
        # errors='replace' would have collapsed pairs into single replacement chars,
        # producing a shorter "length" than the real byte count.
        self.assertEqual(len(result['bytes']), total)
        decoded_len = len(raw_body.decode('utf-8', errors='replace'))
        self.assertNotEqual(decoded_len, total, 'test body should actually exercise the lossy-decoding discrepancy')

    def test_etag_mismatch_between_parts_aborts_assembly(self):
        total = 3_000_000
        calls = {'n': 0}

        def fake_get(url, timeout, headers, allow_redirects, stream):
            calls['n'] += 1
            rng = headers['Range'].split('=')[1]
            start, end = (int(x) for x in rng.split('-'))
            end = min(end, total - 1)
            etag = '"version-A"' if calls['n'] == 1 else '"version-B"'
            body = b'\x00' * (end - start + 1)
            return FakeResponse(206, {'Content-Range': f'bytes {start}-{end}/{total}', 'ETag': etag}, body)

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'unknown_completeness')
        self.assertIn('different_document_versions', result['reason'])

    def test_total_size_mismatch_between_parts_aborts_assembly(self):
        calls = {'n': 0}

        def fake_get(url, timeout, headers, allow_redirects, stream):
            calls['n'] += 1
            rng = headers['Range'].split('=')[1]
            start, end = (int(x) for x in rng.split('-'))
            total = 3_000_000 if calls['n'] == 1 else 9_999_999  # total changes mid-assembly
            end = min(end, total - 1)
            body = b'\x00' * (end - start + 1)
            return FakeResponse(206, {'Content-Range': f'bytes {start}-{end}/{total}', 'ETag': '"same"'}, body)

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'unknown_completeness')
        self.assertIn('total_size_changed', result['reason'])

    def test_range_unsupported_no_content_length_is_unknown_not_complete(self):
        def fake_get(url, timeout, headers, allow_redirects, stream):
            return FakeResponse(200, {}, b'\x00' * 1000)  # ignores Range, no Content-Length

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'unknown_completeness')

    def test_range_unsupported_but_content_length_matches_is_complete(self):
        body = b'\x00' * 900_000

        def fake_get(url, timeout, headers, allow_redirects, stream):
            return FakeResponse(200, {'Content-Length': str(len(body))}, body)

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'complete')
        self.assertEqual(len(result['bytes']), len(body))

    def test_range_unsupported_content_length_bigger_than_read_is_partial(self):
        def fake_get(url, timeout, headers, allow_redirects, stream):
            return FakeResponse(200, {'Content-Length': '5000000'}, b'\x00' * 1000)  # claims more than delivered

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'partial')

    def test_redirect_to_unapproved_host_rejected(self):
        def fake_get(url, timeout, headers, allow_redirects, stream):
            fake_history_resp = type('H', (), {'url': 'https://evil.example/redirected.pdf'})()
            return FakeResponse(206, {'Content-Range': 'bytes 0-999/1000', 'ETag': '"x"'}, b'\x00' * 1000,
                                 url='https://evil.example/redirected.pdf', history=[fake_history_resp])

        with patch.object(self.lib.probe.session, 'get', side_effect=fake_get):
            result = self.lib.fetch_document_bounded('https://downloadcenter.samsung.com/content/fake.pdf',
                                                       {'downloadcenter.samsung.com'}, reason='unit test')
        self.assertEqual(result['completeness'], 'unknown_completeness')
        self.assertIn('probe_failed', result['reason'])


class LiveResultConsistencyTests(unittest.TestCase):
    """Checks the persisted evidence from the actual live run against the
    checkpoint/report claims (no network -- reads only)."""

    def setUp(self):
        self.attempts = read(STAGE86 / 'run_state.json')['attempts']

    def test_all_parts_share_identical_etag_and_last_modified(self):
        etags = {a.get('etag') for a in self.attempts if a.get('etag')}
        last_mods = {a.get('last_modified') for a in self.attempts if a.get('last_modified')}
        self.assertEqual(len(etags), 1, etags)
        self.assertEqual(len(last_mods), 1, last_mods)

    def test_assembled_size_matches_declared_total(self):
        assembly = read(STAGE86 / 'assembly_result.json')
        self.assertEqual(assembly['completeness'], 'complete')
        self.assertEqual(assembly['bytes_assembled'], assembly['declared_total_bytes'])

    def test_first_attempt_stopped_before_exceeding_original_cap(self):
        attempt1 = read(STAGE86 / 'assembly_result_attempt1_6mb_cap.json')
        self.assertEqual(attempt1['completeness'], 'unknown_completeness')
        self.assertIsNone(attempt1['bytes_assembled'])

    def test_only_pre_declared_hosts_contacted(self):
        checkpoint = read(STAGE86 / 'checkpoint.json')
        allowed = set(checkpoint['budget_declared_before_first_request']['pre_declared_allowed_hosts'])
        for a in self.attempts:
            self.assertIn(a['url'].split('/')[2], allowed)


class ContentVerificationTests(unittest.TestCase):
    def setUp(self):
        self.cv = read(STAGE86 / 'content_verification.json')

    def test_manual_status_confirmed_by_content_not_by_filename(self):
        self.assertEqual(self.cv['is_user_manual']['status'], 'confirmed_by_content')
        self.assertIn('not inferred from any url or filename', self.cv['is_user_manual']['evidence'].lower())

    def test_model_match_stronger_than_family_only(self):
        self.assertEqual(self.cv['model_or_family_match']['status'], 'confirmed_by_content_exact_code_not_just_family')

    def test_all_four_languages_content_verified(self):
        langs = [s['language'] for s in self.cv['languages_actually_present']['sections']]
        self.assertEqual(len(langs), 4)
        self.assertTrue(any('Russian' in l for l in langs))

    def test_file_structure_valid(self):
        self.assertEqual(self.cv['file_structure']['status'], 'valid_and_fully_parseable')
        self.assertEqual(self.cv['file_structure']['num_pages'], 80)


class UpdatedCardTests(unittest.TestCase):
    def setUp(self):
        self.card = read(STAGE86 / 'updated_card.json')

    def test_manual_confirmed_true(self):
        self.assertTrue(self.card['manual_confirmed_by_content'])

    def test_russian_confirmed_true(self):
        self.assertTrue(self.card['russian_language_confirmed'])

    def test_manual_field_status_updated(self):
        self.assertEqual(self.card['fields']['instruction_manual']['status'], 'confirmed_by_content')

    def test_missing_characteristics_unchanged_from_stage85(self):
        stage85_card = read(ROOT / 'reports/source_census_2026-09-22_stage8_5/card.json')
        self.assertEqual(self.card['missing_characteristics'], stage85_card['missing_characteristics'])

    def test_supersedes_field_names_stage85_without_claiming_to_overwrite_it(self):
        self.assertIn('unmodified', self.card['supersedes'])


class BudgetRevisionTests(unittest.TestCase):
    def test_revision_declared_with_reason_before_requests(self):
        rev = read(STAGE86 / 'budget_revision.json')
        self.assertIn('trigger', rev)
        self.assertIn('revised_document_assembly_limits', rev)
        self.assertEqual(rev['revised_document_assembly_limits']['max_document_total_bytes']['revised'], 12_000_000)

    def test_original_declaration_untouched(self):
        original = read(STAGE86 / 'budget_predeclaration.json')
        self.assertEqual(original['document_assembly_limits']['max_document_total_bytes'], 6_000_000)


if __name__ == '__main__':
    unittest.main()