"""Offline tests for the DNS dealer-fallback integration (Stage 11.4):
source priority (official first, dealer fills only empty fields), conflict
handling, identity verification, provenance shape, host-role enforcement,
the 401-recorded-not-bypassed rule, and document content verification --
including the Stage 11.3 negative fixture (the original QuadCast manual,
which must never be accepted for QuadCast 2S / 9A273AA).

No network access is used anywhere in this file.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

import requests

from product_tool import jobs, worker
from product_tool.adapters.common import RawAttribute, SourceDocument
from product_tool.adapters.dns import DnsAdapter, DOCUMENT_HOST, PAGE_HOST, _document_language_label, check_identity
from product_tool.adapters.hyperx import HyperXAdapter
from product_tool.adapters.document_verification import verify_document
from product_tool.dealer_fallback import build_provenance, resolved_row_provenance
from product_tool.resolution import resolve_attributes
from product_tool.source_types import source_type

from _source_policy import unapproved_source_ids

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage11_4"
DNS_PAGE_URL = "https://www.dns-shop.ru/product/driver/e949b555b392d582/mikrofonnyj-komplekt-hyperx-quadcast-2-s-cernyj/"
DNS_DOC_URL = "https://drv.dns-shop.ru/drivers/Manuals/H/hyperx-quadcast-2-s_instrukcia_104913_30102025.pdf"


# --------------------------------------------------------------------------
# Lightweight fakes (no network, no requests library internals beyond shape)
# --------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, url, text="", status=200, headers=None, history=None, content=b""):
        self.url = url
        self.text = text
        self.status_code = status
        self.headers = headers or {}
        self.history = history or []
        self.content = content or text.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def close(self):
        pass


class FakeSession:
    """Records every call; raises if asked for anything not pre-registered
    (used to prove 'no known URL -> no network call' and 'wrong host is
    never requested')."""

    def __init__(self, responses: dict[str, FakeResponse] | None = None):
        self.responses = responses or {}
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url, timeout=10, headers=None, stream=False):
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected network call to {url!r} (no known/allowed candidate)")
        return self.responses[url]


def _fake_clock():
    t = {"v": 0.0}

    def clock():
        return t["v"]
    return clock


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. Source order / priority -- official first, dealer fills empty only
# --------------------------------------------------------------------------

class SourcePriorityTests(unittest.TestCase):
    """resolve_attributes() is not modified for DNS -- these tests prove the
    existing per-attribute logic already gives DNS the right priority tier
    without any change: official wins outright; a lone dealer/dns value for
    a field official never touched is surfaced but not silently trusted."""

    def _pages(self, **match_levels):
        return [{"source_key": key, "match_level": level} for key, level in match_levels.items()]

    def test_official_value_wins_dns_never_considered_for_that_field(self):
        facts = [
            {"normalized_name": "weight", "source_key": "lg_kz", "normalized_value": "белый", "unit": ""},
            {"normalized_name": "weight", "source_key": "dns", "normalized_value": "чёрный", "unit": ""},
        ]
        pages = self._pages(lg_kz="base_model", dns="model_and_code_confirmed")
        [resolved] = resolve_attributes(facts, pages)
        self.assertEqual(resolved.selected_source, "lg_kz")
        self.assertEqual(resolved.selected_value, "белый")
        self.assertFalse(resolved.conflict)

    def test_dns_fills_a_field_official_never_touched(self):
        facts = [{"normalized_name": "connectivity", "source_key": "dns", "normalized_value": "usb-c", "unit": ""}]
        pages = self._pages(dns="model_and_code_confirmed")
        [resolved] = resolve_attributes(facts, pages)
        self.assertEqual(resolved.selected_source, "dns")
        self.assertEqual(resolved.status, "needs_review")  # found, but never silently trusted alone

    def test_dns_value_never_silently_overwrites_official_even_when_official_is_base_model_only(self):
        facts = [
            {"normalized_name": "weight", "source_key": "lg_kz", "normalized_value": "1.84", "unit": "lb"},
            {"normalized_name": "weight", "source_key": "dns", "normalized_value": "710", "unit": "g"},
        ]
        pages = self._pages(lg_kz="base_model", dns="model_and_code_confirmed")
        [resolved] = resolve_attributes(facts, pages)
        self.assertEqual(resolved.selected_source, "lg_kz")
        self.assertNotEqual(resolved.selected_value, "710")


# --------------------------------------------------------------------------
# 2. Conflicts -> review, never silently applied
# --------------------------------------------------------------------------

class ConflictTests(unittest.TestCase):
    def test_two_differing_dealer_only_values_go_to_review(self):
        facts = [
            {"normalized_name": "color", "source_key": "dns", "normalized_value": "чёрный", "unit": ""},
            {"normalized_name": "color", "source_key": "some_other_dealer", "normalized_value": "серый", "unit": ""},
        ]
        pages = [{"source_key": "dns", "match_level": "model_and_code_confirmed"},
                 {"source_key": "some_other_dealer", "match_level": "unknown"}]
        [resolved] = resolve_attributes(facts, pages)
        self.assertEqual(resolved.status, "needs_review")
        self.assertTrue(resolved.conflict)
        self.assertEqual(resolved.selected_value, "")  # not silently picked


# --------------------------------------------------------------------------
# 3. Identity verification -- similar title alone is not sufficient
# --------------------------------------------------------------------------

class IdentityCheckTests(unittest.TestCase):
    def test_model_and_code_both_present_confirms(self):
        text = "HyperX QuadCast 2 S microphone, article 9A273AA in stock"
        result = check_identity(text, model_tokens=["QuadCast 2 S", "2S"], code="9A273AA",
                                manufacturer_codes=("9A273AA",))
        self.assertEqual(result.level, "model_and_code_confirmed")

    def test_code_elsewhere_on_page_does_not_confirm_manufacturer_field(self):
        text = "HyperX QuadCast 2 S microphone, article 9A273AA in stock"
        result = check_identity(text, model_tokens=["QuadCast 2 S"], code="9A273AA")
        self.assertEqual(result.level, "model_only")

    def test_similar_title_without_exact_code_is_not_fully_confirmed(self):
        # "QuadCast S" (older model) mentioned, but not the exact code -- must
        # not be treated as a full confirmation of 9A273AA.
        text = "HyperX QuadCast S microphone -- older generation"
        result = check_identity(text, model_tokens=["9A273AA"], code="9A273AA")
        self.assertEqual(result.level, "unconfirmed")

    def test_empty_page_text_is_unconfirmed(self):
        result = check_identity("", model_tokens=["QuadCast 2 S"], code="9A273AA")
        self.assertEqual(result.level, "unconfirmed")


# --------------------------------------------------------------------------
# 4. Provenance -- source_type='dealer', URL, evidence, identity level
# --------------------------------------------------------------------------

class ProvenanceTests(unittest.TestCase):
    def test_dns_field_provenance_carries_dealer_type_and_full_evidence(self):
        prov = build_provenance(
            field="connectivity", value="usb-c", unit="", source_key="dns",
            url=DNS_PAGE_URL, evidence="model_matched=True, code_matched=True",
            identity_match_level="model_and_code_confirmed", site_name="DNS",
        )
        self.assertEqual(prov.source_type, "dealer")
        self.assertEqual(prov.url, DNS_PAGE_URL)
        self.assertEqual(prov.identity_match_level, "model_and_code_confirmed")
        self.assertIn("code_matched=True", prov.evidence)

    def test_official_source_classified_as_official_not_dealer(self):
        self.assertEqual(source_type("lg_kz"), "official")
        self.assertEqual(source_type("dns"), "dealer")
        self.assertEqual(source_type("sulpak"), "dealer")
        self.assertEqual(source_type("something_unregistered"), "unknown")

    def test_resolved_row_provenance_looks_up_the_winning_source_page(self):
        row = {"normalized_name": "connectivity", "selected_value": "usb-c", "selected_unit": "", "selected_source": "dns"}
        pages_by_key = {"dns": {"url": DNS_PAGE_URL, "evidence": "e", "match_level": "model_and_code_confirmed", "site_name": "DNS"}}
        prov = resolved_row_provenance(row, pages_by_key)
        self.assertIsNotNone(prov)
        self.assertEqual(prov.source_type, "dealer")
        self.assertEqual(prov.url, DNS_PAGE_URL)

    def test_manual_and_multi_source_rows_have_no_single_page_provenance(self):
        self.assertIsNone(resolved_row_provenance({"normalized_name": "x", "selected_source": "manual"}, {}))
        self.assertIsNone(resolved_row_provenance({"normalized_name": "x", "selected_source": "sulpak+dns"}, {}))


# --------------------------------------------------------------------------
# 5. Host-role enforcement + no mass crawl
# --------------------------------------------------------------------------

class HostRoleTests(unittest.TestCase):
    def test_page_host_and_document_host_are_distinct(self):
        self.assertNotEqual(PAGE_HOST, DOCUMENT_HOST)
        self.assertEqual(PAGE_HOST, "www.dns-shop.ru")
        self.assertEqual(DOCUMENT_HOST, "drv.dns-shop.ru")

    def test_product_url_on_document_host_is_rejected_before_any_request(self):
        session = FakeSession({})  # any .get() call raises
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"X": DNS_DOC_URL})
        doc = adapter.find_source("X", deadline=100)
        self.assertEqual(session.calls, [])  # never contacted
        self.assertIn("not the allowed product-page host", doc.error)

    def test_document_url_on_page_host_is_rejected_before_any_request(self):
        session = FakeSession({})
        adapter = DnsAdapter(session, clock=_fake_clock(), document_urls={"X": DNS_PAGE_URL})
        data, reason = adapter.fetch_document_bounded(DNS_PAGE_URL, deadline=100)
        self.assertIsNone(data)
        self.assertIn("not the allowed document host", reason)
        self.assertEqual(session.calls, [])

    def test_unconfigured_search_code_makes_no_network_call(self):
        session = FakeSession({})  # would raise on any .get()
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"9A273AA": DNS_PAGE_URL})
        doc = adapter.find_source("SOME-OTHER-SKU-NOT-CONFIGURED", deadline=100, brand="TestBrand", name="Test Model")
        self.assertEqual(session.calls, [])
        self.assertEqual(doc.match_level, "dealer_url_needed")
        self.assertIn("Нет проверенного дилерского URL", doc.evidence)
        self.assertIn("TestBrand", doc.evidence)
        self.assertIn("Test Model", doc.evidence)

    def test_no_crawl_or_search_method_exists_on_the_adapter(self):
        for forbidden in ("crawl", "search", "discover", "scan_catalog"):
            self.assertFalse(hasattr(DnsAdapter, forbidden), f"DnsAdapter must not expose a {forbidden}() method")


class ManufacturerCodeFieldTests(unittest.TestCase):
    def test_exact_bracketed_manufacturer_code_accepts_only_full_catalog_row(self):
        html = '<h1>LG 32LQ63006LA</h1><table><tr><td>Код производителя</td><td>[32LQ63006LA.ARUG]</td></tr><tr><td>Вес</td><td>4 кг</td></tr></table>'
        url = "https://www.dns-shop.ru/product/lg-32lq63006la/"
        adapter = DnsAdapter(FakeSession({url: FakeResponse(url, html)}), clock=_fake_clock(),
                             urls={"32LQ63006LA.ARUG": url, "32LQ63006LA": url})
        full = adapter.find_source("32LQ63006LA.ARUG", deadline=100, model_tokens=["32LQ63006LA"])
        self.assertEqual(full.match_level, "model_and_code_confirmed")
        self.assertTrue(full.attributes)
        short = adapter.find_source("32LQ63006LA", deadline=100, model_tokens=["32LQ63006LA"])
        self.assertNotEqual(short.match_level, "model_and_code_confirmed")
        self.assertEqual(short.attributes, [])
        self.assertEqual(short.photos, [])

    def test_code_in_title_without_labelled_field_is_not_accepted(self):
        html = '<h1>LG 32LQ63006LA.ARUG</h1><table><tr><td>Вес</td><td>4 кг</td></tr></table>'
        url = "https://www.dns-shop.ru/product/lg-32lq63006la/"
        adapter = DnsAdapter(FakeSession({url: FakeResponse(url, html)}), clock=_fake_clock(),
                             urls={"32LQ63006LA.ARUG": url})
        found = adapter.find_source("32LQ63006LA.ARUG", deadline=100, model_tokens=["32LQ63006LA"])
        self.assertEqual(found.match_level, "model_only")
        self.assertEqual(found.attributes, [])

    def test_hidden_variant_code_does_not_confirm_page(self):
        html = '<h1>LG 32LQ63006LA</h1><div hidden><span>Код производителя</span><span>[32LQ63006LA.ARUG]</span></div>'
        url = "https://www.dns-shop.ru/product/lg-32lq63006la/"
        adapter = DnsAdapter(FakeSession({url: FakeResponse(url, html)}), clock=_fake_clock(),
                             urls={"32LQ63006LA.ARUG": url})
        found = adapter.find_source("32LQ63006LA.ARUG", deadline=100, model_tokens=["32LQ63006LA"])
        self.assertEqual(found.match_level, "model_only")

    def test_paired_div_field_and_document_gate(self):
        html = '<h1>LG 32LQ63006LA</h1><div><span>Код производителя</span><span>[32LQ63006LA.ARUG]</span></div>'
        url = "https://www.dns-shop.ru/product/lg-32lq63006la/"
        adapter = DnsAdapter(FakeSession({url: FakeResponse(url, html)}), clock=_fake_clock(),
                             urls={"32LQ63006LA.ARUG": url},
                             document_urls={"32LQ63006LA.ARUG": DNS_DOC_URL})
        docs, reason = adapter.find_documents("32LQ63006LA.ARUG", model_tokens=["32LQ63006LA"], deadline=100)
        self.assertEqual(docs, [])
        self.assertIn("has not confirmed", reason)
        found = adapter.find_source("32LQ63006LA.ARUG", deadline=100, model_tokens=["32LQ63006LA"])
        self.assertEqual(found.match_level, "model_and_code_confirmed")

    def test_russian_section_of_multilingual_dns_manual_counts_as_russian(self):
        self.assertEqual(_document_language_label(("en", "ru")), "Русский")


# --------------------------------------------------------------------------
# 6. HTTP 401 recorded, never bypassed
# --------------------------------------------------------------------------

class BlockedResponseTests(unittest.TestCase):
    def test_401_is_recorded_as_blocked_and_not_retried(self):
        session = FakeSession({DNS_PAGE_URL: FakeResponse(DNS_PAGE_URL, "", status=401)})
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"9A273AA": DNS_PAGE_URL})
        doc = adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(doc.match_level, "blocked")
        self.assertIn("401", doc.error)
        self.assertIn("Not retried", doc.error)
        self.assertEqual(session.calls, [DNS_PAGE_URL])  # exactly one attempt, no retry

    def test_redirect_off_allowed_host_is_not_followed(self):
        response = FakeResponse(DNS_PAGE_URL, "<html></html>", status=200, history=[
            type("Hop", (), {"url": DNS_PAGE_URL})()
        ])
        response.url = "https://evil.example.com/redirected"
        session = FakeSession({DNS_PAGE_URL: response})
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"9A273AA": DNS_PAGE_URL})
        doc = adapter.find_source("9A273AA", deadline=100)
        self.assertIn("Redirected off the allowed host", doc.error)


# --------------------------------------------------------------------------
# 7. Document content verification -- the Stage 11.3 negative fixture
# --------------------------------------------------------------------------

class DocumentVerificationTests(unittest.TestCase):
    def test_old_quadcast_manual_is_rejected_for_quadcast_2s(self):
        text = read_fixture("hyperx_quadcast_original_manual_excerpt.txt")
        result = verify_document(text, expected_model_tokens=["QuadCast 2 S", "2S"], expected_code="9A273AA")
        self.assertFalse(result.accepted)
        self.assertEqual(result.document_type, "model_mismatch")
        self.assertFalse(result.matched_model)
        self.assertFalse(result.matched_code)

    def test_old_quadcast_manual_does_mention_hyperx_but_not_the_right_model(self):
        text = read_fixture("hyperx_quadcast_original_manual_excerpt.txt")
        self.assertIn("HyperX", text)
        self.assertIn("HX-MICQC-BK", text)
        self.assertNotIn("9A273AA", text)

    def test_synthetic_quadcast_2s_manual_is_accepted(self):
        text = read_fixture("hyperx_quadcast_2s_manual_excerpt_synthetic.txt")
        result = verify_document(text, expected_model_tokens=["QuadCast 2 S", "2S"], expected_code="9A273AA")
        self.assertTrue(result.accepted)
        self.assertEqual(result.document_type, "instruction_manual")
        self.assertIn("ru", result.languages)
        self.assertIn("en", result.languages)

    def test_regulatory_document_rejected_even_when_model_and_code_match(self):
        text = read_fixture("declaration_of_conformity_excerpt_synthetic.txt")
        # This fixture deliberately DOES mention the right model and code --
        # proving regulatory exclusion takes priority over identity match.
        self.assertIn("9A273AA", text)
        self.assertIn("QuadCast 2 S", text)
        result = verify_document(text, expected_model_tokens=["QuadCast 2 S"], expected_code="9A273AA")
        self.assertFalse(result.accepted)
        self.assertEqual(result.document_type, "regulatory_excluded")

    def test_empty_text_is_never_accepted(self):
        result = verify_document("", expected_model_tokens=["QuadCast 2 S"], expected_code="9A273AA")
        self.assertFalse(result.accepted)

    def test_code_matches_but_conflicting_sibling_model_is_rejected(self):
        # The expected code (9A273AA) appears only in a passing compatibility
        # note; the document's own subject is a different, named sibling
        # model (QuadCast S). A code match alone must not be accepted when a
        # known conflicting model reference is also present.
        text = read_fixture("hyperx_quadcast_s_manual_with_2s_compatibility_note_synthetic.txt")
        self.assertIn("9A273AA", text)  # the match DOES occur in the text
        result = verify_document(
            text, expected_model_tokens=["QuadCast 2 S", "2S"], expected_code="9A273AA",
            conflicting_model_tokens=["QuadCast S"],
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.document_type, "conflicting_model_reference")
        self.assertTrue(result.matched_code)  # the code really was found...
        self.assertEqual(result.conflicting_reference_found, "QuadCast S")  # ...but so was the conflict

    def test_conflicting_code_also_triggers_rejection(self):
        text = "HyperX QuadCast 2 S manual. See also part 4P5P7AA for the earlier model."
        result = verify_document(
            text, expected_model_tokens=["QuadCast 2 S"], expected_code="9A273AA",
            conflicting_codes=["4P5P7AA"],
        )
        # Model matches (QuadCast 2 S is literally present) but a conflicting
        # sibling code is also present -- still rejected.
        self.assertTrue(result.matched_model)
        self.assertFalse(result.accepted)
        self.assertEqual(result.document_type, "conflicting_model_reference")

    def test_no_conflicting_list_supplied_does_not_reject(self):
        # Backward compatible: omitting conflicting_model_tokens/codes (the
        # default) behaves exactly as before Stage 11.5.
        text = read_fixture("hyperx_quadcast_2s_manual_excerpt_synthetic.txt")
        result = verify_document(text, expected_model_tokens=["QuadCast 2 S"], expected_code="9A273AA")
        self.assertTrue(result.accepted)


# --------------------------------------------------------------------------
# 8. Worker integration -- DNS runs, LG/Sulpak scope unchanged
# --------------------------------------------------------------------------

def seed_product(database: Path, *, brand: str, sku: str, name: str = "Товар") -> int:
    jobs.initialize(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO batches (id, filename, sheet_name, mapping_json, confirmed_at) VALUES ('b1','fixture.xlsx','Товары','{}','2026-01-01')"
        )
        cursor = connection.execute(
            "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
            "VALUES ('b1',2,?,?,?, '', 'Микрофоны',0,'[]','{}')",
            (name, brand, sku),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


class FakeDnsAdapter:
    """Test double matching DnsAdapter's public surface, for worker injection."""
    source_key = "dns"
    site_name = "DNS"

    def __init__(self, *, source_doc: SourceDocument, documents=None, doc_reason="no known document"):
        self._source_doc = source_doc
        self._documents = documents or []
        self._doc_reason = doc_reason
        self.calls = []
        self.document_urls = {}

    def find_source(self, search_code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
        self.calls.append(("find_source", search_code))
        return self._source_doc

    def find_documents(self, search_code, *, model_tokens, deadline):
        self.calls.append(("find_documents", search_code))
        return self._documents, self._doc_reason


class WorkerIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "batches.sqlite3"

    def test_dns_confirmed_for_non_lg_brand_yields_needs_review_not_done(self):
        product = seed_product(self.database, brand="HYPERX", sku="9A273AA", name="Микрофон QuadCast 2S Black")
        jobs.enqueue(self.database, product, [1, 3])
        dns_doc = SourceDocument(
            "dns", "DNS", DNS_PAGE_URL, found_model="9A273AA", match_level="model_and_code_confirmed",
            evidence="model_matched=True, code_matched=True",
            attributes=[RawAttribute("Connectivity", "USB-C")],
        )
        fake_dns = FakeDnsAdapter(source_doc=dns_doc)
        # Stage 15: 9A273AA is now a real production KNOWN_URLS entry in
        # adapters/hyperx.py -- urls={} here keeps this DNS-fallback test
        # from making an actual live request to hyperx.com via worker.py's
        # default (real-session) hyperx_adapter_factory.
        worker.run_once(
            self.database, clock=lambda: 0, dns_adapter_factory=lambda: fake_dns,
            hyperx_adapter_factory=lambda: HyperXAdapter(urls={}),
        )
        self.assertEqual(fake_dns.calls[0], ("find_source", "9A273AA"))
        status = jobs.list_jobs(self.database, product)[0]["status"]
        self.assertEqual(status, "needs_review")  # never silently "done" from one dealer source
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertIn("dns", pages)
        self.assertEqual(pages["dns"]["match_level"], "model_and_code_confirmed")

    def test_dns_unconfirmed_for_non_lg_brand_yields_error_same_as_before(self):
        # Samsung now has an official adapter; Cudy still exercises this
        # historical no-official-adapter branch.
        product = seed_product(self.database, brand="Cudy", sku="MODEL.123")
        jobs.enqueue(self.database, product, [1])
        unknown_doc = SourceDocument("dns", "DNS", "", match_level="unknown", evidence="No pre-verified DNS candidate.")
        fake_dns = FakeDnsAdapter(source_doc=unknown_doc)
        worker.run_once(self.database, clock=lambda: 0, dns_adapter_factory=lambda: fake_dns)
        self.assertEqual(jobs.list_jobs(self.database, product)[0]["status"], "error")

    def test_lg_adapter_factory_never_called_for_non_lg_brand(self):
        product = seed_product(self.database, brand="Samsung", sku="MODEL.123")
        jobs.enqueue(self.database, product, [1])
        called = {"v": False}

        def lg_factory():
            called["v"] = True
            raise AssertionError("LG/Sulpak fallback_factory must not start for non-LG brands")
        worker.run_once(self.database, lg_factory, clock=lambda: 0, dns_adapter_factory=lambda: FakeDnsAdapter(
            source_doc=SourceDocument("dns", "DNS", "", match_level="unknown", evidence="no candidate")))
        self.assertFalse(called["v"])

    def test_dns_document_rejected_content_never_saved(self):
        product = seed_product(self.database, brand="HYPERX", sku="9A273AA", name="Микрофон QuadCast 2S Black")
        jobs.enqueue(self.database, product, [1, 6])
        dns_doc = SourceDocument("dns", "DNS", DNS_PAGE_URL, match_level="model_and_code_confirmed", evidence="ok")
        fake_dns = FakeDnsAdapter(source_doc=dns_doc, documents=[], doc_reason="Document rejected: model_mismatch -- wrong product.")
        worker.run_once(
            self.database, clock=lambda: 0, dns_adapter_factory=lambda: fake_dns,
            hyperx_adapter_factory=lambda: HyperXAdapter(urls={}),
        )
        self.assertEqual(jobs.get_documents(self.database, product), [])

    def test_dns_document_accepted_is_saved_with_manufacturer_dealer_hosted_type(self):
        product = seed_product(self.database, brand="HYPERX", sku="9A273AA", name="Микрофон QuadCast 2S Black")
        jobs.enqueue(self.database, product, [1, 6])
        dns_doc = SourceDocument("dns", "DNS", DNS_PAGE_URL, match_level="model_and_code_confirmed", evidence="ok")
        accepted_document = {
            "title": "DNS document (instruction_manual)", "language": "en,ru",
            "direct_url": DNS_DOC_URL, "source_url": DNS_PAGE_URL,
            "product_model": "9A273AA", "support_model": "9A273AA",
            "relation_url": DNS_DOC_URL, "primary": False,
        }
        fake_dns = FakeDnsAdapter(source_doc=dns_doc, documents=[accepted_document], doc_reason="accepted")
        worker.run_once(
            self.database, clock=lambda: 0, dns_adapter_factory=lambda: fake_dns,
            hyperx_adapter_factory=lambda: HyperXAdapter(urls={}),
        )
        [saved] = jobs.get_documents(self.database, product)
        self.assertEqual(saved["direct_url"], DNS_DOC_URL)
        self.assertIn("instruction_manual", saved["title"])


# --------------------------------------------------------------------------
# 9. Sulpak allowlist preserved; the generic not_allowed exclusion rule
# --------------------------------------------------------------------------

class SulpakScopeAndExclusionRuleTests(unittest.TestCase):
    def test_sulpak_allowlist_unchanged(self):
        import json
        catalog = json.loads((Path(__file__).resolve().parents[1] / "product_tool/config/source_catalog.v2.json").read_text(encoding="utf-8"))
        sulpak = next(s for s in catalog["sources"] if s["source_id"] == "sulpak")
        self.assertEqual(
            set(sulpak["category_allowlist"]),
            {"Стиральные машины", "Сушильные машины", "Холодильники", "Пылесосы", "Микроволновые печи"},
        )
        self.assertEqual(sulpak["brands"], ["LG"])

    def test_not_allowed_sources_are_excluded_by_the_generic_rule_not_a_named_one(self):
        # Proves the exclusion mechanism itself (SourceCatalog.for_brand()
        # -- and, the same way, default_source_registry() in sources.py --
        # skip any record with official_status == "not_allowed") using a
        # synthetic example, and that the catalog holds only approved sources.
        from product_tool.census.models import SourceRecord
        from product_tool.census.registry import SourceCatalog
        import json
        catalog = json.loads((Path(__file__).resolve().parents[1] / "product_tool/config/source_catalog.v2.json").read_text(encoding="utf-8"))
        self.assertEqual(unapproved_source_ids(s["source_id"] for s in catalog["sources"]), set())
        synthetic = dict(next(s for s in catalog["sources"] if s["source_id"] == "sulpak"))
        synthetic.update(source_id="not_allowed_example", official_status="not_allowed", enabled=False)
        records = [SourceRecord.from_dict(s) for s in catalog["sources"]] + [SourceRecord.from_dict(synthetic)]
        matches = SourceCatalog(records).for_brand("LG")
        self.assertNotIn("not_allowed_example", {r.source_id for r in matches})

    def test_dns_not_added_to_production_registry(self):
        import json
        catalog = json.loads((Path(__file__).resolve().parents[1] / "product_tool/config/source_catalog.v2.json").read_text(encoding="utf-8"))
        self.assertNotIn("dns", [s["source_id"] for s in catalog["sources"]])


# --------------------------------------------------------------------------
# 10. dealer_url_needed -- explicit, ready-to-ask status when no URL exists
# --------------------------------------------------------------------------

class DealerUrlNeededTests(unittest.TestCase):
    def test_request_structure_has_brand_model_and_missing_fields(self):
        from product_tool.dealer_fallback import dealer_url_needed_request
        req = dealer_url_needed_request(
            brand="HYPERX", name="Микрофон QuadCast 2S Black", seller_code="9A273AA",
            missing_fields=["характеристики", "фото"],
        )
        self.assertEqual(req.status, "dealer_url_needed")
        self.assertEqual(req.brand, "HYPERX")
        self.assertEqual(req.seller_code, "9A273AA")
        self.assertEqual(req.missing_fields, ("характеристики", "фото"))
        self.assertIn("HYPERX", req.message)
        self.assertIn("9A273AA", req.message)
        self.assertIn("характеристики", req.message)

    def test_missing_fields_default_when_not_specified(self):
        from product_tool.dealer_fallback import dealer_url_needed_request
        req = dealer_url_needed_request(brand="X", name="Y", seller_code="Z")
        self.assertEqual(req.missing_fields, ())
        self.assertIn("не уточнено", req.message)

    def test_find_source_on_unconfigured_code_returns_this_exact_status(self):
        session = FakeSession({})
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"9A273AA": DNS_PAGE_URL})
        doc = adapter.find_source(
            "UNKNOWN-CODE", deadline=100, brand="HYPERX", name="Some Other Product",
            missing_fields=["инструкция"],
        )
        self.assertEqual(doc.match_level, "dealer_url_needed")
        self.assertIn("инструкция", doc.evidence)
        self.assertEqual(session.calls, [])

    def test_explicit_empty_missing_fields_means_not_needed_not_dealer_url_needed(self):
        # Stage 12: a caller that actually checked and found nothing missing
        # (an explicit [], as opposed to not checking at all -- None) must
        # not trigger an ask. This is what makes "no duplicate requests for
        # a row that has already been filled" possible at the worker level.
        session = FakeSession({})
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"9A273AA": DNS_PAGE_URL})
        doc = adapter.find_source(
            "UNKNOWN-CODE", deadline=100, brand="HYPERX", name="Some Other Product",
            missing_fields=[],
        )
        self.assertEqual(doc.match_level, "not_needed")
        self.assertNotIn("Нет проверенного дилерского URL", doc.evidence)
        self.assertEqual(session.calls, [])

    def test_known_url_is_not_fetched_when_official_sources_filled_every_requested_field(self):
        session = FakeSession({})
        adapter = DnsAdapter(session, clock=_fake_clock(), urls={"32LQ63006LA.ARUG": DNS_PAGE_URL})
        doc = adapter.find_source("32LQ63006LA.ARUG", deadline=100, missing_fields=[])
        self.assertEqual(doc.match_level, "not_needed")
        self.assertEqual(session.calls, [])


# --------------------------------------------------------------------------
# 10.1 Stage 12: worker._compute_missing_fields -- concrete, per-row, and
# stops re-asking once a field is genuinely filled (no duplicate requests)
# --------------------------------------------------------------------------

class ComputeMissingFieldsTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "batches.sqlite3"
        jobs.initialize(self.database)

    def test_only_requested_stages_are_considered(self):
        product = seed_product(self.database, brand="Razer", sku="RZ-TEST")
        # Nothing saved at all -- stage 1 alone requests no category, so
        # there is nothing to report missing yet.
        self.assertEqual(worker._compute_missing_fields(self.database, product, [1]), [])

    def test_lists_only_genuinely_empty_categories(self):
        product = seed_product(self.database, brand="Razer", sku="RZ-TEST")
        jobs.save_source_document(
            self.database, product,
            SourceDocument(
                "stub", "Stub", "https://example.invalid/", match_level="stub",
                evidence="stub", attributes=[RawAttribute("Connectivity", "USB-C")],
            ),
        )
        # Characteristics already have a fact from another source; photos
        # and instructions still have nothing.
        missing = worker._compute_missing_fields(self.database, product, [1, 3, 4, 6])
        self.assertEqual(missing, ["фото", "инструкция"])

    def test_all_three_missing_when_stages_requested_and_nothing_found(self):
        product = seed_product(self.database, brand="Razer", sku="RZ-TEST")
        missing = worker._compute_missing_fields(self.database, product, [1, 3, 4, 6])
        self.assertEqual(missing, ["характеристики", "фото", "инструкция"])

    def test_worker_stops_asking_once_the_gap_is_filled_elsewhere(self):
        # The concrete "no duplicate requests for one catalog row" case:
        # run once with a genuine gap (dealer_url_needed fires), close the
        # gap the same way an official/dealer source would, run again --
        # the second run must not repeat the same ask.
        # Stage 70: Razer now has an official adapter. This test concerns
        # generic dealer supplementation, so its fixture must remain generic.
        product = seed_product(self.database, brand="Generic", sku="GEN-TEST", name="Test Mouse")
        jobs.enqueue(self.database, product, [1, 3])
        real_dns = DnsAdapter(FakeSession({}), clock=_fake_clock())
        worker.run_once(self.database, clock=lambda: 0, dns_adapter_factory=lambda: real_dns)
        first_status = jobs.list_jobs(self.database, product)[0]
        self.assertEqual(first_status["status"], "error")
        self.assertIn("Не хватает", first_status["message"])
        self.assertIn("характеристики", first_status["message"])

        # Close the gap the same way a resolved official/dealer fact would.
        jobs.save_source_document(
            self.database, product,
            SourceDocument(
                "stub", "Stub", "https://example.invalid/", match_level="stub",
                evidence="stub", attributes=[RawAttribute("Sensor", "30K DPI")],
            ),
        )
        jobs.enqueue(self.database, product, [1, 3])
        worker.run_once(self.database, clock=lambda: 0, dns_adapter_factory=lambda: real_dns)
        second_status = jobs.list_jobs(self.database, product)[0]
        # No repeated ask about characteristics -- the only thing that was
        # ever missing has since been found, so this run must not surface
        # the same dealer_url_needed request again.
        self.assertNotIn("Не хватает", second_status["message"])
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertEqual(pages["dns"]["match_level"], "not_needed")


# --------------------------------------------------------------------------
# 11. Technopark preference -- documented, never called without a real URL
# --------------------------------------------------------------------------

class TechnoparkPolicyTests(unittest.TestCase):
    def test_technopark_classified_as_dealer_for_future_use(self):
        self.assertEqual(source_type("technopark"), "dealer")

    def test_no_technopark_adapter_module_exists_yet(self):
        # No verified URL -> no adapter built against one. This is the
        # literal code-level meaning of "don't request, don't claim a
        # QuadCast 2S manual exists there until a real URL is supplied."
        import importlib
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("product_tool.adapters.technopark")

    def test_dealer_fallback_module_documents_the_two_roles(self):
        import product_tool.dealer_fallback as module
        doc = module.__doc__
        self.assertIn("Technopark", doc)
        self.assertIn("CROSS-CHECK", doc)
        self.assertIn("supplementation", doc)


if __name__ == "__main__":
    unittest.main()
