"""LG model searches retain variants and handle explicit two-part kits."""

import time
import unittest

from product_tool.adapters.lg import LGAdapter, lg_article_components, lg_base_model
from product_tool.jobs import identification_status
from product_tool.importer import ColumnMapping, preview_row
from product_tool.worker import _effective_product_name, _lg_model_candidates_from_name
from tests.test_lg_workflow import FakeSession, lg_html


class LgModelSemanticsTests(unittest.TestCase):
    def test_missing_sitemap_page_is_not_a_contradicting_product(self):
        self.assertEqual(
            identification_status([{"source_key": "lg_kz", "match_level": "mismatch", "url": ""}]),
            "Источники не найдены за отведённое время",
        )
        self.assertEqual(
            identification_status([{"source_key": "lg_kz", "match_level": "mismatch", "url": "https://www.lg.com/kz/example"}]),
            "Найдено несоответствие артикула",
        )

    def test_full_article_and_base_model_remain_distinct(self):
        self.assertEqual(lg_base_model("S3WER.ALWPCOM"), "S3WER")
        self.assertEqual(lg_base_model("GC-B459MLWM.ADSQCIS"), "GC-B459MLWM")
        self.assertEqual(lg_base_model("CFI-ZCT1J 02"), "CFI-ZCT1J02")

    def test_explicit_kit_has_two_codes_and_one_shared_model(self):
        article = "P12ED.NSAR + P12ED.USAR"
        self.assertEqual(lg_article_components(article), ("P12ED.NSAR", "P12ED.USAR"))
        self.assertEqual(lg_base_model(article), "P12ED")
        self.assertEqual(lg_base_model("P12ED.NSAR + Q18ED.USAR"), "P12ED.NSAR+Q18ED.USAR")

    def test_descriptive_model_column_becomes_name_not_second_code(self):
        mapping = ColumnMapping(brand=3, search_code=1, fallback_code=2, header_row=1)
        item = preview_row(2, ("P12ED.NSAR + P12ED.USAR", "Кондиционер сплит-система P12ED", "LG"), mapping)
        self.assertEqual(item.name, "Кондиционер сплит-система P12ED")
        self.assertEqual(item.search_code, "P12ED.NSAR + P12ED.USAR")
        self.assertEqual(item.alternate_code, "")
        self.assertEqual(item.category, "Сплит-система")
        self.assertTrue(item.needs_confirmation)

    def test_existing_import_uses_name_from_descriptive_alternate_column(self):
        product = {"name": "", "alternate_code": "Микросистема ON77DK"}
        name = _effective_product_name(product)
        self.assertEqual(_lg_model_candidates_from_name(name, "ON77DKDRUSLLK"), ("ON77DK",))

    def test_family_page_can_be_found_without_confirming_kit(self):
        url = "https://www.lg.com/kz/air-conditioning/p12ed/"
        session = FakeSession({url: lg_html("P12ED")})
        result = LGAdapter(session).find_source("P12ED.NSAR + P12ED.USAR", deadline=time.monotonic() + 10)
        self.assertEqual(result.match_level, "base_model")
        self.assertEqual(result.found_model, "P12ED")
        self.assertEqual(result.url, url)

    def test_model_from_name_finds_only_base_page(self):
        url = "https://www.lg.com/kz/audio/on77dk/"
        session = FakeSession({url: lg_html("ON77DK")})
        result = LGAdapter(session).find_source("ON77DKDRUSLLK", deadline=time.monotonic() + 10, fallback_models=("ON77DK",))
        self.assertEqual(result.match_level, "base_model")
        self.assertEqual(result.found_model, "ON77DK")


if __name__ == "__main__":
    unittest.main()
