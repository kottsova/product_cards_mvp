"""A dealer URL naming kit components is a lead, not proof from page content."""

import time
import unittest

from product_tool.adapters.sulpak import KNOWN_LG_URLS, SulpakAdapter
from tests.test_lg_workflow import FakeSession


class SulpakKitCandidateTests(unittest.TestCase):
    def test_owner_link_is_recorded_without_search_tracking_parameter(self):
        self.assertEqual(
            KNOWN_LG_URLS["P12ED.NSAR + P12ED.USAR"],
            "https://www.sulpak.kz/g/kondicioneriy_split_sistemiy_lg_p12ednsar___p12edusar",
        )

    def test_base_model_page_does_not_confirm_two_component_kit(self):
        url = KNOWN_LG_URLS["P12ED.NSAR + P12ED.USAR"]
        html = "<h1>Кондиционер LG P12ED</h1><table><tr><th>Цвет</th><td>Белый</td></tr></table>"
        result = SulpakAdapter(FakeSession({url: html})).find_source(
            "P12ED.NSAR + P12ED.USAR", deadline=time.monotonic() + 10
        )
        self.assertEqual(result.match_level, "unknown")
        self.assertFalse(result.attributes)
        self.assertFalse(result.photos)
        self.assertIn("не подтверждён", result.evidence)

    def test_both_codes_in_page_text_confirm_kit(self):
        url = KNOWN_LG_URLS["P12ED.NSAR + P12ED.USAR"]
        html = "<h1>Кондиционер LG P12ED.NSAR + P12ED.USAR</h1>"
        result = SulpakAdapter(FakeSession({url: html})).find_source(
            "P12ED.NSAR + P12ED.USAR", deadline=time.monotonic() + 10
        )
        self.assertEqual(result.match_level, "full_sku")


if __name__ == "__main__":
    unittest.main()
