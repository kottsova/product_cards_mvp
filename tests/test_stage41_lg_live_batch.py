"""Stage 41: full LG articles and cautious variant colour."""
import time
import unittest

from product_tool.adapters.sulpak import KNOWN_LG_URLS, SulpakAdapter
from product_tool.resolution import resolve_attributes
from tests.test_lg_workflow import FakeSession


class LgKitAndColourTests(unittest.TestCase):
    def test_normalized_kit_uses_observed_url_without_url_proof(self):
        url = KNOWN_LG_URLS["P12ED.NSAR + P12ED.USAR"]
        html = '<h1>LG P12ED</h1><table><tr><th>Colour</th><td>White</td></tr></table>'
        session = FakeSession({url: html})
        doc = SulpakAdapter(session).find_source("P12ED.NSAR+P12ED.USAR", deadline=time.monotonic() + 10)
        self.assertEqual(doc.url, url)
        self.assertEqual(doc.match_level, "unknown")
        self.assertEqual(doc.attributes, [])

    def test_kit_codes_in_page_content_with_spacing(self):
        url = KNOWN_LG_URLS["P12ED.NSAR + P12ED.USAR"]
        html = '<h1>LG P12ED.NSAR + P12ED.USAR</h1>'
        doc = SulpakAdapter(FakeSession({url: html})).find_source(
            "P12ED.NSAR+P12ED.USAR", deadline=time.monotonic() + 10)
        self.assertEqual(doc.match_level, "full_sku")

    def test_suffix_after_dot_does_not_prove_another_variant(self):
        from product_tool.adapters.supplier import find_full_sku
        found, _ = find_full_sku("P12ED.NSAR + P12ED.USAR.EXTRA", "P12ED.NSAR+P12ED.USAR")
        self.assertEqual(found, "")

    def test_official_text_can_name_spaced_kit(self):
        from product_tool.adapters.lg import _designation
        found, level, _ = _designation("LG P12ED.NSAR + P12ED.USAR", "P12ED.NSAR+P12ED.USAR", "P12ED")
        self.assertEqual((found, level), ("P12ED.NSAR+P12ED.USAR", "full_sku"))

    def test_base_model_colour_is_not_selected(self):
        fact = {"normalized_name": "color", "normalized_value": "white", "unit": "", "source_key": "lg_kz", "site_name": "LG KZ"}
        page = {"source_key": "lg_kz", "match_level": "base_model"}
        result = resolve_attributes([fact], [page])[0]
        self.assertEqual(result.selected_value, "")
        self.assertFalse(result.full_sku_confirmed)

    def test_body_colour_and_door_finish_do_not_leak_from_base_page(self):
        for name in ("color__body", "\u043e\u0442\u0434\u0435\u043b\u043a\u0430_\u0434\u0432\u0435\u0440\u0438"):
            with self.subTest(name=name):
                fact = {"normalized_name": name, "normalized_value": "graphite", "unit": "", "source_key": "lg_ru"}
                page = {"source_key": "lg_ru", "match_level": "base_model"}
                self.assertEqual(resolve_attributes([fact], [page])[0].selected_value, "")

    def test_exact_dealer_colour_over_base_model(self):
        facts = [
            {"normalized_name": "color", "normalized_value": "white", "unit": "", "source_key": "lg_kz", "site_name": "LG KZ"},
            {"normalized_name": "color", "normalized_value": "gray", "unit": "", "source_key": "sulpak", "site_name": "Sulpak"},
        ]
        pages = [{"source_key": "lg_kz", "match_level": "base_model"}, {"source_key": "sulpak", "match_level": "full_sku"}]
        result = resolve_attributes(facts, pages)[0]
        self.assertEqual(result.selected_value, "gray")
        self.assertTrue(result.full_sku_confirmed)
        self.assertIn("LG", result.reason)

    def test_exact_dns_colour_can_fill_variant_missing_from_official_base(self):
        facts = [
            {"normalized_name": "color", "normalized_value": "white", "unit": "", "source_key": "lg_kz"},
            {"normalized_name": "color", "normalized_value": "black", "unit": "", "source_key": "dns"},
        ]
        pages = [{"source_key": "lg_kz", "match_level": "base_model"}, {"source_key": "dns", "match_level": "model_and_code_confirmed"}]
        result = resolve_attributes(facts, pages)[0]
        self.assertEqual((result.selected_source, result.selected_value), ("dns", "black"))
        self.assertTrue(result.full_sku_confirmed)


    def test_exact_official_colour_precedes_agreeing_dns(self):
        facts = [
            {"normalized_name": "color", "normalized_value": "black", "unit": "", "source_key": "lg_kz"},
            {"normalized_name": "color", "normalized_value": "black", "unit": "", "source_key": "dns"},
        ]
        pages = [{"source_key": "lg_kz", "match_level": "full_sku"}, {"source_key": "dns", "match_level": "model_and_code_confirmed"}]
        result = resolve_attributes(facts, pages)[0]
        self.assertEqual((result.selected_source, result.selected_value), ("lg_kz", "black"))

    def test_exact_official_dealer_colour_dispute_requires_review(self):
        facts = [
            {"normalized_name": "color", "normalized_value": "white", "unit": "", "source_key": "lg_kz"},
            {"normalized_name": "color", "normalized_value": "black", "unit": "", "source_key": "dns"},
        ]
        pages = [{"source_key": "lg_kz", "match_level": "full_sku"}, {"source_key": "dns", "match_level": "model_and_code_confirmed"}]
        result = resolve_attributes(facts, pages)[0]
        self.assertEqual(result.selected_value, "")
        self.assertTrue(result.conflict)



if __name__ == "__main__":
    unittest.main()
