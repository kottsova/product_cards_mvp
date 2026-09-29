from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from product_tool.adapters.lg import _product_designation
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.sulpak import SulpakAdapter


class _NoNetwork:
    def __init__(self):
        self.headers = {}
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("network must not be called")


class Stage42LGTest(unittest.TestCase):
    def test_main_pdp_sales_code_confirms_full_refrigerator_article(self):
        full = "GC-B459MLWM.ADSQCIS"
        kz = BeautifulSoup("""<div class="price-area__PD0033" data-analytics='{"data-pim-sku":"GC-B459MLWM.ADSQCIS.EEAK.KZ.C"}'></div>""", "html.parser")
        ru = BeautifulSoup('<div class="GPC0009" data-adobe-salesmodelcode="GC-B459MLWM" data-adobe-salessuffixcode="ADSQCIS"></div>', "html.parser")
        self.assertEqual(_product_designation(kz, full, "GC-B459MLWM", region="kz")[:2], (full, "full_sku"))
        self.assertEqual(_product_designation(ru, full, "GC-B459MLWM", region="ru")[:2], (full, "full_sku"))

    def test_unrelated_or_component_codes_do_not_confirm_variant_or_kit(self):
        other = BeautifulSoup("""<div class="price-area__PD0033" data-analytics='{"data-pim-sku":"GC-B459MLWM.OTHER"}'></div><h1>GC-B459MLWM</h1>""", "html.parser")
        self.assertEqual(_product_designation(other, "GC-B459MLWM.ADSQCIS", "GC-B459MLWM", region="kz")[1], "base_model")
        other_with_full_text = BeautifulSoup("""<div class="price-area__PD0033" data-analytics='{"data-pim-sku":"GC-B459MLWM.OTHER"}'></div><h1>GC-B459MLWM.ADSQCIS</h1>""", "html.parser")
        self.assertNotEqual(_product_designation(other_with_full_text, "GC-B459MLWM.ADSQCIS", "GC-B459MLWM", region="kz")[1], "full_sku")
        components = BeautifulSoup("""<div class="price-area__PD0033" data-analytics='{"data-pim-sku":"P12ED.NSAR"}'></div><h1>P12ED</h1>""", "html.parser")
        self.assertEqual(_product_designation(components, "P12ED.NSAR + P12ED.USAR", "P12ED", region="kz")[1], "base_model")

    def test_exact_official_fact_is_not_labeled_base_only(self):
        from product_tool.resolution import resolve_attributes
        fact = {"normalized_name": "capacity", "normalized_value": "374", "unit": "l", "source_key": "lg_kz", "site_name": "LG KZ"}
        page = {"source_key": "lg_kz", "match_level": "full_sku"}
        result = resolve_attributes([fact], [page])[0]
        self.assertEqual((result.status, result.selected_source, result.full_sku_confirmed), ("full_sku_lg", "lg_kz", True))
        self.assertNotIn("base", result.reason.lower())

    def test_sulpak_candidate_is_not_requested_after_other_page_challenge(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "log.json"
            log.write_text(json.dumps([{"url": "https://www.sulpak.kz/g/parovoj_shkaf_lg_styler_s3wer_alwpcom", "checked_at": datetime.now(timezone.utc).isoformat(), "status_code": 200, "access_status": "captcha_or_blocked", "protection_status": "challenge_confirmed"}]), encoding="utf-8")
            transport = _NoNetwork()
            session = PolicyAwareSession(log, allowed_hosts=("www.sulpak.kz", "sulpak.kz"), underlying=transport, min_interval_seconds=0)
            document = SulpakAdapter(session).find_source("P12ED.NSAR + P12ED.USAR", deadline=10**10)
            self.assertEqual(transport.calls, 0)
            self.assertEqual(document.match_level, "unknown")
            self.assertIn("policy_host_stopped", document.error)
            self.assertIn("s3wer_alwpcom", document.evidence.lower())
            self.assertIn("не отправлялся", document.evidence)
            self.assertIn("p12ednsar", document.url.lower())


if __name__ == "__main__":
    unittest.main()
