"""Stage 24: the Samsung selection rules and the recorded batch 1 (offline; reads the saved reports).

Owner rules: one product per category in small batches, the rest queued; only NEW models for smartphones/tablets/wearables/electronics, old models only in home appliances;
no blind minimum-hash pick that gives old electronics; the N5300 TV and Galaxy Buds3 FE are never counted; the microwave keeps its earlier evidence.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "reports/source_census_2026-09-25_stage24"


def load(name):
    return json.loads((STAGE / name).read_text(encoding="utf-8"))


spec = importlib.util.spec_from_file_location("stage24_selection", STAGE / "scripts/01_categories_and_selection.py")
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class Categories(unittest.TestCase):
    def test_every_catalog_category_is_listed_and_the_rest_is_queued_not_cancelled(self):
        data = load("raw/samsung_categories.json")
        cats = data["categories"]
        self.assertEqual((len(cats), data["catalog_rows"]), (31, 1182))
        self.assertEqual(sum(c["rows"] for c in cats), 1182)
        batch = [c["category"] for c in cats if c["batch"] == 1]
        self.assertEqual(sorted(batch), sorted(["Телевизоры", "Смартфоны", "Планшеты", "Пылесосы", "Стиральные машины", "Микроволновые печи"]))
        self.assertEqual({c["status"] for c in cats if c["batch"] != 1}, {"queued"})
        self.assertEqual(len([c for c in cats if c["batch"] != 1]), 25)

    def test_one_proposal_per_category(self):
        proposals = load("raw/selection_proposal.json")["proposals"]
        self.assertEqual(len(proposals), 31)
        self.assertEqual(len({p["category"] for p in proposals}), 31)


class ExclusionsAndReuse(unittest.TestCase):
    def test_the_n5300_tv_and_buds3_fe_are_never_proposed(self):
        data = load("raw/selection_proposal.json")
        for p in data["proposals"]:
            self.assertNotIn("N5300", p["article"].upper())
            self.assertNotIn("R420", p["article"].upper())
            for fallback in p["fallbacks"]:
                self.assertNotIn("N5300", fallback.upper())
        self.assertIn("UE43N5300AUXCE", data["excluded"])
        self.assertIn("Galaxy Buds3 FE", data["excluded"])

    def test_the_microwave_keeps_its_saved_evidence(self):
        by = {p["category"]: p for p in load("raw/selection_proposal.json")["proposals"]}
        self.assertEqual(by["Микроволновые печи"]["article"], "MS23K3614AK/BW")
        self.assertIn("Новых запросов не требуется", by["Микроволновые печи"]["reason"])


class ElectronicsAreNewAppliancesMayBeOld(unittest.TestCase):
    def setUp(self):
        self.by = {p["category"]: p for p in load("raw/selection_proposal.json")["proposals"]}

    def test_the_tv_is_the_newest_model_year_in_the_catalog(self):
        article = self.by["Телевизоры"]["article"]
        self.assertEqual(selection.tv_year_letter(article), "H")  # the newest year letter the catalog has; QN70H / S85H
        self.assertNotEqual(selection.tv_year_letter("QE43Q60BAUXCE"), "H")

    def test_phones_and_tablets_are_kz_coded_and_from_the_newest_year_the_catalog_has_for_that_code(self):
        for category in ("Смартфоны", "Планшеты"):
            self.assertTrue(self.by[category]["article"].endswith("SKZ"), category)
        self.assertIn("A36", self.by["Смартфоны"]["title"])
        self.assertNotRegex(self.by["Смартфоны"]["title"], r"S20|S21|S22|A03|A13")  # no old phone from a blind hash pick

    def test_wearables_and_earbuds_without_a_current_model_get_no_card(self):
        for category in ("Фитнес-браслеты", "Наушники беспроводные", "Гарнитуры"):
            self.assertEqual(self.by[category]["article"], "", category)
            self.assertTrue(self.by[category]["provisional"])

    def test_appliances_may_be_old_and_the_class_is_recorded(self):
        for category in ("Пылесосы", "Стиральные машины", "Холодильники", "Духовые шкафы"):
            self.assertEqual(self.by[category]["class"], "appliance")
        for category in ("Телевизоры", "Смартфоны", "Планшеты", "Смарт-часы", "Мониторы"):
            self.assertEqual(self.by[category]["class"], "electronics")

    def test_selection_helpers(self):
        self.assertEqual(selection.tv_year_letter("QE100QN80FUX"), "F")
        self.assertEqual(selection.tv_year_letter("QE48S85HAEXCE"), "H")
        self.assertTrue(selection.clean("QE48S85HAEXCE"))
        self.assertFalse(selection.clean("QE32LS03TB_SU"))
        self.assertFalse(selection.clean("QE43LS05BBUXRU_141385979"))


class BatchOneRecord(unittest.TestCase):
    def test_declared_before_run_and_within_budget(self):
        declaration, result = load("raw/batch1_declaration.json"), load("raw/batch1_result.json")
        self.assertLess(declaration["declared_at"], result["started_at"])
        self.assertEqual((declaration["budget"]["max_real_requests_total"], declaration["budget"]["max_real_requests_per_category"]), (30, 10))
        self.assertLessEqual(result["requests_made"], 30)
        self.assertEqual(result["halted"], "")
        declaration_b, result_b = load("raw/batch1b_declaration.json"), load("raw/batch1b_result.json")
        self.assertLess(declaration_b["declared_at"], result_b["finished_at"])
        self.assertLessEqual(result_b["requests_made"], 3)
        self.assertLess(result["finished_at"], declaration_b["declared_at"])  # the correction was declared after batch 1 ended

    def test_only_official_samsung_hosts_were_asked(self):
        result = load("raw/batch1_result.json")
        for step in result["steps"] + load("raw/batch1b_result.json")["steps"]:
            self.assertRegex(step["url"], r"^https://(?:[a-z0-9\-]+\.)*samsung\.com/")

    def test_no_bulk_processing_and_at_most_one_product_page_per_declared_category_except_the_disclosed_correction(self):
        steps = load("raw/batch1_result.json")["steps"]
        pages = [s for s in steps if "product page" in s["step"]]
        self.assertEqual(len(pages), 5)  # TV, S25 Ultra family page (declared rule), tablets (asset url, 404), vacuum, washer
        self.assertEqual(sum(1 for s in load("raw/batch1b_result.json")["steps"] if "A37 product page" in s["step"]), 1)

    def test_results_that_the_report_states(self):
        cats = load("raw/batch1_result.json")["categories"]
        self.assertEqual(cats["Телевизоры"]["chosen"], "QE48S85HAEXCE")
        self.assertTrue(cats["Телевизоры"]["currency_confirmed_by_hub"])
        self.assertEqual(cats["Пылесосы"]["page"]["sku_vs_catalog_article"], "exact_article")
        self.assertEqual(cats["Стиральные машины"]["page"]["sku_vs_catalog_article"], "exact_article")
        self.assertFalse(cats["Телевизоры"]["page"]["json_ld_product"])
        for category in ("Телевизоры", "Пылесосы", "Стиральные машины"):
            self.assertEqual(cats[category]["page"]["generic_dom_spec_rows"], 0)
        self.assertEqual(cats["Пылесосы"]["page"]["document"]["assessment"]["languages"], ["kk"])  # the first link was Kazakh
        b = load("raw/batch1b_result.json")["result"]
        self.assertTrue(b["vacuum_ru"]["assessment"]["russian_instruction"])
        self.assertEqual(b["vacuum_ru"]["model_name_printed_by_the_page_link"], "SC18M21D0VG")
        self.assertTrue(re.match(r"SM-A376E", b["a37"]["json_ld_fields"]["sku"][0]))


if __name__ == "__main__":
    unittest.main()
