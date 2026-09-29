"""Stage 11.2 regression tests: the corrected 14-item gallery extraction, the
video/cover evidence for the user-provided cdn.shopify.com URL, and the
untouched-registry guarantee. Network is never required."""
from pathlib import Path
import hashlib
import json
import unittest

from _source_policy import hosts_outside_allowlist

ROOT = Path(__file__).resolve().parents[1]
STAGE11_2 = ROOT / 'reports/source_census_2026-09-23_stage11_2'


def read(name):
    return json.loads((STAGE11_2 / name).read_text(encoding='utf-8'))


class GalleryRootCauseTests(unittest.TestCase):
    def setUp(self):
        self.data = read('offline_gallery_root_cause.json')

    def test_true_gallery_count_is_14(self):
        self.assertEqual(self.data['root_cause']['true_gallery_count'], 14)

    def test_five_annotated_images_identified_as_missed(self):
        self.assertEqual(len(self.data['root_cause']['items_stage11_missed']), 5)
        for item in self.data['root_cause']['items_stage11_missed']:
            self.assertIn('annotated', item['url'])

    def test_video_found_verbatim_in_saved_html(self):
        video = self.data['video_evidence']
        self.assertTrue(video['found_verbatim_in_saved_hyperx_page_html'])
        self.assertGreaterEqual(video['occurrence_count'], 1)

    def test_video_linkage_not_based_on_shared_cdn_alone(self):
        video = self.data['video_evidence']
        self.assertTrue(video['shares_same_page_template_id_as_the_14_image_gallery'])
        self.assertIn('not an inference from sharing a generic Shopify CDN', video['conclusion'])


class CompletenessCheckTests(unittest.TestCase):
    def setUp(self):
        self.phase1 = read('phase1_fresh_product_page_and_gallery_fix.json')

    def test_fresh_fetch_gallery_complete(self):
        check = self.phase1['corrected_gallery_completeness_check_fresh_page']
        self.assertEqual(check['expected'], 14)
        self.assertEqual(check['found'], 14)
        self.assertTrue(check['complete'])

    def test_method_is_dom_based_not_filename_substring(self):
        check = self.phase1['corrected_gallery_completeness_check_fresh_page']
        self.assertIn('data-media-id', check['method'])
        self.assertIn('not a filename/SKU substring filter', check['method'])

    def test_fresh_and_saved_gallery_sets_identical(self):
        self.assertTrue(self.phase1['comparison_to_stage11_snapshot']['gallery_urls_identical_set'])


class VideoAndCoverTests(unittest.TestCase):
    def setUp(self):
        self.phase2 = read('phase2_video_and_cover_check.json')

    def test_video_confirmed_mp4_and_reachable(self):
        v = self.phase2['video_check']
        self.assertTrue(v['succeeded'])
        self.assertEqual(v['http_status'], 206)
        self.assertEqual(v['content_type'], 'video/mp4')
        self.assertTrue(v['is_mp4_signature'])

    def test_video_not_fully_downloaded(self):
        v = self.phase2['video_check']
        self.assertLessEqual(v['bytes_actually_read_this_chunk'], 65536)
        self.assertGreater(v['declared_total_bytes'], 65536)

    def test_cover_image_verified_byte_complete_and_hashed(self):
        c = self.phase2['cover_check']
        self.assertTrue(c['succeeded'])
        self.assertTrue(c['byte_count_matches_declared_total'])
        self.assertEqual(len(c['sha256']), 64)

    def test_cover_image_not_committed_as_binary(self):
        self.assertIsNone(self.phase2['cover_check']['saved_as'])


class NoRawImageContentCommittedTests(unittest.TestCase):
    def test_no_binary_image_files_in_stage_directory(self):
        binary_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4'}
        found = [p for p in STAGE11_2.rglob('*') if p.suffix.lower() in binary_ext]
        self.assertEqual(found, [], f'raw binary content committed to repo: {found}')


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budget = read('budget_predeclaration.json')
        self.checkpoint = read('checkpoint.json')

    def test_budget_declared_before_requests(self):
        self.assertTrue(self.budget['declared_before_any_request'])
        self.assertEqual(set(self.budget['allowed_hosts']), {'hyperx.com', 'cdn.shopify.com'})

    def test_all_requests_on_allowed_hosts_within_budget(self):
        self.assertLessEqual(self.checkpoint['total_requests_made'], self.budget['limits']['max_requests_total'])
        for entry in self.checkpoint['request_log_full']:
            url = entry.get('requested_url', '')
            self.assertTrue('hyperx.com' in url or 'cdn.shopify.com' in url, url)

    def test_no_dealer_or_other_brand_hosts_contacted(self):
        urls = [entry['requested_url'] for entry in self.checkpoint['request_log_full']]
        self.assertEqual(hosts_outside_allowlist(urls, {'hyperx.com', 'cdn.shopify.com'}), set())
        for entry in self.checkpoint['request_log_full']:
            for forbidden in ('sulpak', 'kingston.com', 'hiper'):
                self.assertNotIn(forbidden, entry['requested_url'].lower())


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = read('card.json')

    def test_all_14_gallery_items_listed(self):
        self.assertEqual(len(self.card['gallery_14_items']), 14)
        kinds = {item['kind'] for item in self.card['gallery_14_items']}
        self.assertEqual(kinds, {'main_product_photo', 'annotated_feature_callout', 'angle_photo'})

    def test_field_needing_user_input_specific(self):
        field = self.card['field_needing_user_or_dealer_input']
        self.assertIn('9A273AA', field['exact_product'])
        self.assertIn('Quick Start Guide', field['missing_field'])
        self.assertGreaterEqual(len(field['official_pages_checked']), 2)

    def test_dealer_fallback_not_invoked_and_explained(self):
        status = self.card['dealer_fallback_status']
        self.assertIn('Not invoked', status)
        self.assertIn('Sulpak', status)

    def test_manual_gap_not_declared_absent(self):
        gaps_blob = json.dumps(self.card['open_gaps'])
        self.assertIn('unresolved, not claimed absent', gaps_blob)


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
        self.assertTrue(check['no_new_dealer_added_to_production_registry'])

    def test_all_prior_stages_unchanged_including_11_1(self):
        check = read('protected_hashes_check.json')
        self.assertGreaterEqual(check['prior_stage_file_count'], 640)
        self.assertIn('source_census_2026-09-23_stage11_1', check['prior_stage_directories_hashed'])
        for rel_dir, files in check['prior_stage_hashes'].items():
            for path, expected in files.items():
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, f'changed: {path}')

    def test_deliverables_present(self):
        for name in ('report.md', 'offline_gallery_root_cause.json', 'budget_predeclaration.json',
                     'card.json', 'checkpoint.json', 'protected_hashes_check.json'):
            self.assertTrue((STAGE11_2 / name).exists(), f'missing Stage 11.2 deliverable: {name}')


if __name__ == '__main__':
    unittest.main()
