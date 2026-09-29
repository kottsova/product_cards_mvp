"""Stage 14: offline tests for adapters/hyperx.py -- HyperX's own identity
check (base-code vs code#region-suffix), and end-to-end parsing of the
synthetic Product-page fixtures into a SourceDocument with evidence and
explicit gaps.

Stage 15 wired 2 real, human-confirmed URLs into production KNOWN_URLS (see
adapters/hyperx.py's module docstring and tests/test_hyperx_stage15_
catalog_route.py, which re-validates identity/extraction against the real
saved Stage 11/11.1 pages, not these synthetic fixtures). Most tests here
still inject their own urls+session, exactly like the existing DNS/LG/
Sulpak test conventions, to keep exercising the code paths in isolation
from whatever KNOWN_URLS currently holds. No network access is used
anywhere in this file.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from product_tool.adapters.hyperx import HyperXAdapter, check_identity, split_hyperx_code
from product_tool.adapters.structured_page import ROLE_GALLERY, ROLE_JSON_LD, extract_json_ld_product

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage14_hyperx"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


QUADCAST_URL = "https://hyperx.com/products/hyperx-quadcast-2s-black"
PULSEFIRE_URL = "https://hyperx.com/products/hyperx-pulsefire-fuse"
ALLOY_ABA_URL = "https://hyperx.com/products/hyperx-alloy-rise-75-us"


class FakeResponse:
    """Stage 16: shaped for AccessProbe.probe(), not a bare requests.get()
    call -- HyperXAdapter's ordinary fetch path goes through
    adapters/policy_fetch.py's PolicyAwareFetcher (AccessProbe) now, so its
    test double needs everything probe() itself touches: a redirect
    history of prior responses (each needing its own .url), a real dict of
    headers, a .cookies.get_dict() method and a chunked .iter_content()."""
    def __init__(self, url: str, text: str, status: int = 200, history=(), headers=None):
        self.url, self.text, self.status_code, self.history = url, text, status, history
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self.text.encode("utf-8"),))

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, pages: dict[str, FakeResponse]):
        self.pages = pages
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected call to {url!r}")
        return self.pages[url]


def _tmp_log_path(case: unittest.TestCase) -> Path:
    """A fresh, isolated fetch-log path per test -- never the adapter's own
    real default path, which would leak state across separate test runs
    on the same machine."""
    tmp = TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    return Path(tmp.name) / "hyperx_fetch_log.json"


def _fake_clock():
    t = {"v": 0.0}

    def clock():
        return t["v"]
    return clock


# --------------------------------------------------------------------------
# 1. split_hyperx_code / check_identity -- pure logic, no HTML at all
# --------------------------------------------------------------------------

class SplitCodeTests(unittest.TestCase):
    def test_bare_code_has_no_suffix(self):
        self.assertEqual(split_hyperx_code("9a273aa"), ("9A273AA", ""))

    def test_code_with_region_suffix(self):
        self.assertEqual(split_hyperx_code("7g7a4aa#acb"), ("7G7A4AA", "ACB"))

    def test_empty_string_is_not_special_cased_into_an_error(self):
        self.assertEqual(split_hyperx_code(""), ("", ""))


class CheckIdentityTests(unittest.TestCase):
    def test_exact_bare_code_match_is_exact_variant(self):
        fields = extract_json_ld_product(read("quadcast_2s_black_9a273aa_synthetic.html"), QUADCAST_URL)
        result = check_identity(fields, catalog_code="9A273AA")
        self.assertEqual(result.level, "exact_variant")

    def test_matching_base_but_different_region_suffix_is_base_code_confirmed_not_exact(self):
        fields = extract_json_ld_product(read("alloy_rise_75_aba_region_mismatch_synthetic.html"), ALLOY_ABA_URL)
        result = check_identity(fields, catalog_code="7G7A4AA#ACB")
        self.assertEqual(result.level, "base_code_confirmed")
        self.assertNotEqual(result.level, "exact_variant")
        self.assertEqual(result.page_base, "7G7A4AA")
        self.assertEqual(result.page_suffix, "ABA")

    def test_different_base_code_is_mismatch(self):
        fields = extract_json_ld_product(read("pulsefire_fuse_a1ky6aa_synthetic.html"), PULSEFIRE_URL)
        result = check_identity(fields, catalog_code="9A273AA")
        self.assertEqual(result.level, "mismatch")

    def test_no_identity_fields_at_all_is_unknown(self):
        result = check_identity([], catalog_code="9A273AA")
        self.assertEqual(result.level, "unknown")


# --------------------------------------------------------------------------
# 2. HyperXAdapter.parse_page -- full SourceDocument + rich field evidence
# --------------------------------------------------------------------------

class ParsePageTests(unittest.TestCase):
    def setUp(self):
        self.adapter = HyperXAdapter(FakeSession({}), clock=_fake_clock(), fetch_log_path=_tmp_log_path(self))

    def test_quadcast_2s_is_an_exact_variant_with_evidence_and_gaps(self):
        result = self.adapter.parse_page(read("quadcast_2s_black_9a273aa_synthetic.html"), QUADCAST_URL, catalog_code="9A273AA")
        doc = result.document
        self.assertEqual(doc.match_level, "exact_variant")
        self.assertEqual(doc.found_model, "9A273AA")
        self.assertIn("exact_variant", doc.evidence)
        # Real gaps: no manual/document link exists on this synthetic page.
        self.assertTrue(doc.attributes)
        self.assertTrue(doc.photos)

    def test_every_extracted_field_carries_url_evidence_role_and_confirmation(self):
        result = self.adapter.parse_page(read("quadcast_2s_black_9a273aa_synthetic.html"), QUADCAST_URL, catalog_code="9A273AA")
        self.assertTrue(result.extracted_fields)
        for field in result.extracted_fields:
            self.assertTrue(field.url)
            self.assertTrue(field.evidence)
            self.assertTrue(field.role)
            self.assertTrue(field.confirmation)

    def test_pulsefire_fuse_is_an_exact_variant(self):
        result = self.adapter.parse_page(read("pulsefire_fuse_a1ky6aa_synthetic.html"), PULSEFIRE_URL, catalog_code="A1KY6AA")
        self.assertEqual(result.document.match_level, "exact_variant")
        self.assertEqual(result.document.found_model, "A1KY6AA")

    def test_pulsefire_fuse_has_no_video_field_reported_honestly(self):
        result = self.adapter.parse_page(read("pulsefire_fuse_a1ky6aa_synthetic.html"), PULSEFIRE_URL, catalog_code="A1KY6AA")
        self.assertFalse(any(f.role == "video" for f in result.extracted_fields))

    def test_regional_keyboard_mismatch_never_gets_exact_variant(self):
        result = self.adapter.parse_page(read("alloy_rise_75_aba_region_mismatch_synthetic.html"), ALLOY_ABA_URL, catalog_code="7G7A4AA#ACB")
        self.assertEqual(result.document.match_level, "base_code_confirmed")
        self.assertNotEqual(result.document.match_level, "exact_variant")

    def test_only_confirmed_gallery_images_are_saved_as_photos_never_the_logo(self):
        result = self.adapter.parse_page(read("quadcast_2s_black_9a273aa_synthetic.html"), QUADCAST_URL, catalog_code="9A273AA")
        for photo_url in result.document.photos:
            self.assertNotIn("logo", photo_url.lower())
        gallery_fields = [f for f in result.extracted_fields if f.role == ROLE_GALLERY]
        self.assertEqual(len(gallery_fields), 3)

    def test_quick_start_guide_mention_never_becomes_a_document_and_is_not_a_url(self):
        result = self.adapter.parse_page(read("quadcast_2s_black_9a273aa_synthetic.html"), QUADCAST_URL, catalog_code="9A273AA")
        blob = " ".join(a.value for a in result.document.attributes)
        # Box-contents text may legitimately mention "Quick Start Guide" as
        # an included accessory -- but never as something with a URL.
        self.assertNotIn("http", blob)


# --------------------------------------------------------------------------
# 3. HyperXAdapter.find_source / find_documents -- host policy, no real URL
# --------------------------------------------------------------------------

class FindSourceTests(unittest.TestCase):
    def test_no_known_url_yields_official_url_needed_and_zero_network_calls(self):
        # Stage 15: 9A273AA/A1KY6AA are now real KNOWN_URLS entries in
        # production, so this uses an explicit empty urls dict (any of the
        # other 39 HyperX catalog rows) rather than relying on 9A273AA
        # itself being absent.
        session = FakeSession({})
        adapter = HyperXAdapter(session, clock=_fake_clock(), urls={}, fetch_log_path=_tmp_log_path(self))
        doc = adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(doc.match_level, "official_url_needed")
        self.assertEqual(session.calls, [])
        self.assertIn("9A273AA", doc.evidence)

    def test_production_known_urls_keeps_the_two_human_confirmed_rows(self):
        # Stage 18 added rows from the URL-discovery wave; the two Stage 15
        # rows are unchanged, and the full map is pinned to its evidence file
        # by tests/test_coverage_queue.py (KnownUrlsMatchTheirEvidence).
        from product_tool.adapters.hyperx import KNOWN_URLS
        self.assertEqual(KNOWN_URLS["9A273AA"], "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone")
        self.assertEqual(KNOWN_URLS["A1KY6AA"], "https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse")

    def test_injected_url_and_session_yields_exact_variant(self):
        session = FakeSession({QUADCAST_URL: FakeResponse(QUADCAST_URL, read("quadcast_2s_black_9a273aa_synthetic.html"))})
        adapter = HyperXAdapter(session, clock=_fake_clock(), urls={"9A273AA": QUADCAST_URL}, fetch_log_path=_tmp_log_path(self))
        doc = adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(doc.match_level, "exact_variant")
        self.assertEqual(session.calls, [QUADCAST_URL])

    def test_url_on_a_disallowed_host_is_rejected_before_any_request(self):
        session = FakeSession({})
        adapter = HyperXAdapter(session, clock=_fake_clock(), urls={"9A273AA": "https://example.test/hyperx-quadcast-2s"}, fetch_log_path=_tmp_log_path(self))
        doc = adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(session.calls, [])
        self.assertIn("not", doc.error.lower())

    def test_blocked_status_is_recorded_not_bypassed(self):
        session = FakeSession({QUADCAST_URL: FakeResponse(QUADCAST_URL, "", status=403)})
        adapter = HyperXAdapter(session, clock=_fake_clock(), urls={"9A273AA": QUADCAST_URL}, fetch_log_path=_tmp_log_path(self))
        doc = adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(doc.match_level, "blocked")
        self.assertEqual(session.calls, [QUADCAST_URL])

    def test_find_documents_never_returns_a_document_from_box_contents_text(self):
        session = FakeSession({})
        adapter = HyperXAdapter(session, clock=_fake_clock(), urls={"9A273AA": QUADCAST_URL}, fetch_log_path=_tmp_log_path(self))
        documents, reason = adapter.find_documents("9A273AA", deadline=100)
        self.assertEqual(documents, [])
        self.assertIn("не найдена", reason.lower())

    def test_find_documents_with_no_known_url_says_so_explicitly(self):
        adapter = HyperXAdapter(FakeSession({}), clock=_fake_clock(), urls={}, fetch_log_path=_tmp_log_path(self))
        documents, reason = adapter.find_documents("9A273AA", deadline=100)
        self.assertEqual(documents, [])
        self.assertIn("нет проверенного", reason.lower())


if __name__ == "__main__":
    unittest.main()
