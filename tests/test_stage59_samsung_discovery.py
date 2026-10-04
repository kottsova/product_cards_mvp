"""Stage 59 Samsung fallback and evidence boundary tests."""
from __future__ import annotations

import json
import time
import unittest
from types import SimpleNamespace

from product_tool.adapters.samsung_source import SamsungAdapter, exact_support_url, support_manual_links
from product_tool.adapters.samsung import extract_identity
from product_tool import samsung_readiness
from product_tool.adapters.common import RawAttribute
from product_tool.normalization import normalize_facts
from product_tool.resolution import resolve_attributes


class Reply:
    status_code = 200
    def __init__(self, url, text):
        self.url, self.text = url, text
    def raise_for_status(self):
        pass


class Transport:
    def __init__(self, pages):
        self.pages, self.calls = pages, []
    def get(self, url, timeout):
        self.calls.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected request: {url}")
        return Reply(url, self.pages[url])


def sitemap(*urls):
    return '<urlset>' + ''.join(f'<url><loc>{url}</loc></url>' for url in urls) + '</urlset>'


def product(code):
    return ("<html><head><script type=\"application/ld+json\">" +
            json.dumps({"@context": "https://schema.org", "@type": "Product", "sku": code}) +
            "</script></head><body><div class=\"pdd32-product-spec\"></div></body></html>")


class Browser:
    def __init__(self, urls):
        self.urls, self.calls = urls, []
    def search_provider(self, provider, query):
        self.calls.append((provider, query))
        return SimpleNamespace(outcome="results", candidates=tuple(SimpleNamespace(url=url) for url in self.urls))


class SamsungDiscoveryStage59(unittest.TestCase):
    def test_ru_sitemap_exact_is_used_after_kz_miss(self):
        code = "DV90T5240AW/LP"
        url = "https://www.samsung.com/ru/dryers/dv90t5240aw-lp/"
        pages = {"https://www.samsung.com/kz_ru/vd-sitemap.xml": sitemap(),
                 "https://www.samsung.com/kz_ru/da-sitemap.xml": sitemap(),
                 "https://www.samsung.com/ru/vd-sitemap.xml": sitemap(url),
                 url: product(code)}
        transport = Transport(pages)
        browser = Browser(())
        adapter = SamsungAdapter(transport, regional_search=True, browser_search=browser)
        source = adapter.find_source(code, deadline=time.monotonic() + 30)
        self.assertEqual(source.url, url)
        self.assertEqual(source.match_level, "full_sku")
        self.assertEqual(adapter.reports[code]["route"]["found_via"], "https://www.samsung.com/ru/vd-sitemap.xml")
        self.assertFalse(browser.calls)
        self.assertEqual(transport.calls[-1], url)

    def test_external_skips_support_and_wrong_product_then_validates_exact(self):
        code = "MC32DG7646KKBW"
        support = "https://www.samsung.com/ru/support/model/MC32DG7646KKBW/"
        wrong = "https://www.samsung.com/ru/microwave-ovens/other-model/"
        exact = "https://www.samsung.com/ru/microwave-ovens/mc32dg7646kkbw/"
        pages = {f"https://www.samsung.com/{region}/{kind}-sitemap.xml": sitemap()
                 for region in ("kz_ru", "ru") for kind in ("vd", "da")}
        pages.update({wrong: product("MC32DG7646KKE1"), exact: product(code)})
        browser = Browser((support, wrong, exact))
        transport = Transport(pages)
        adapter = SamsungAdapter(transport, regional_search=True, browser_search=browser)
        source = adapter.find_source(code, deadline=time.monotonic() + 30)
        self.assertEqual(source.url, exact)
        self.assertEqual(source.match_level, "full_sku")
        self.assertNotIn(support, transport.calls)
        self.assertLess(transport.calls.index("https://www.samsung.com/ru/da-sitemap.xml"), transport.calls.index(wrong))
        self.assertEqual([c["match_level"] for c in adapter.reports[code]["candidates"]], ["unknown", "full_sku"])
        self.assertEqual([c["decision"] for c in adapter.reports[code]["external_results"]], ["rejected", "rejected", "accepted"])

    def test_support_manual_list_is_typed_and_only_exact_link_is_used(self):
        code = "QE55QN90FAUXCE"
        pdp = "https://www.samsung.com/kz_ru/tvs/model/"
        html = '<a href="/kz_ru/support/model/QE55QN90FAUXCE/#downloads">exact</a><a href="/kz_ru/support/model/QE55QN90FAUXCF/">other</a>'
        self.assertEqual(exact_support_url(html, pdp, code), "https://www.samsung.com/kz_ru/support/model/QE55QN90FAUXCE/")
        items = [{"contentsTypeCode": "PM", "fileName": "start_here.html", "downloadUrl": "https://org.downloadcenter.samsung.com/online", "languageList": [{"code": "RU"}]},
                 {"contentsTypeCode": "UM", "fileName": "user_RU.pdf", "downloadUrl": "https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?ModelName=QE55QN90FAU&CDCttType=UM", "languageList": [{"code": "RU"}]}]
        links, typed = support_manual_links('<script>{"manuals":' + json.dumps(items) + '}</script>')
        self.assertEqual(len(typed), 2)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].model_name, "QE55QN90FAU")

    def test_overview_number_inherits_unit_only_from_identical_field_value(self):
        name = "\u0412\u0435\u0441 \u041d\u0435\u0442\u0442\u043e"
        facts = normalize_facts([RawAttribute(name, "49", "overview"), RawAttribute(name, "49 \u043a\u0433", "detail")])
        self.assertEqual([(f.normalized_value, f.unit) for f in facts], [("49", "kg"), ("49", "kg")])
        facts = normalize_facts([RawAttribute(name, "48", "overview"), RawAttribute(name, "49 \u043a\u0433", "detail")])
        self.assertEqual(facts[0].unit, "")

    def test_catalog_annotation_does_not_upgrade_page_sku_to_exact(self):
        code = "Jet_VS20A95973B/EV_Bespoke"
        page_code = "VS20A95973B/EV"
        identity = extract_identity(product(page_code), "https://www.samsung.com/ru/vacuum-cleaners/stick/vs20a95973b-ev/", code)
        self.assertEqual(identity.level, "base_model")
        self.assertIn("catalog_annotation_contains_page_sku", identity.evidence)

    def test_shared_resolution_confirms_only_exact_samsung_page(self):
        fact = {"source_key": "samsung", "site_name": "Samsung", "normalized_name": "capacity", "normalized_value": "9", "unit": "kg"}
        exact = resolve_attributes([fact], [{"source_key": "samsung", "match_level": "full_sku", "error": ""}])[0]
        weak = resolve_attributes([fact], [{"source_key": "samsung", "match_level": "base_model", "error": ""}])[0]
        self.assertEqual(exact.status, "full_sku_official")
        self.assertTrue(exact.full_sku_confirmed)
        self.assertEqual(weak.status, "official_base_only")
        self.assertFalse(weak.full_sku_confirmed)

    def test_weak_page_and_unaccepted_pdf_are_not_verified(self):
        pages = [{"source_key": "samsung", "match_level": "code_in_page_text", "error": ""}]
        photo = {"source_key": "samsung", "kind": "product_gallery", "asset_key": "https://images.samsung.com/robot-vr30t80313w-ev"}
        self.assertFalse(samsung_readiness.photo_verified(photo, pages, "VR30T80313W/EV_1"))
        document = {"direct_url": "https://org.downloadcenter.samsung.com/manual.pdf"}
        self.assertFalse(samsung_readiness.document_verified(document, {"documents": [{"final_url": document["direct_url"], "facts": {"acceptance": {"accepted": False}}}]}))


if __name__ == "__main__":
    unittest.main()
