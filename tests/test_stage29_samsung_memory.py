"""Stage 29: group 5A (memory storage), one product per category, and the wearables currency check.
Offline on the saved responses (tests/_samsung_replay.py); the recorded result of the real requests is read as data. No socket is opened."""
from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import _samsung_replay as R
from product_tool import samsung_readiness
from product_tool.adapters import samsung
from product_tool.adapters.sitemap_urls import sitemap_locs

ROOT = Path(__file__).resolve().parents[1]
S29 = ROOT / "reports/source_census_2026-09-26_stage29"
RAW = S29 / "raw"
CARDS = (("Внутренние SSD-накопители", "MZ-77E500BW"), ("Flash-накопители", "MUF-64BE3/APC"), ("Внешние SSD-накопители", "MU-PC1T0H/WW"), ("Карты памяти", "MB-MC64HARU"))


def load(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


class GroupWasDeclaredFirstAndStayedInsideItsBudget(unittest.TestCase):
    DECLARATION, RESULT = load("batch5a_declaration.json"), load("batch5a_result.json")

    def test_declared_before_the_first_request_and_only_group_5a(self):
        self.assertLess(self.DECLARATION["declared_at"], self.RESULT["started_at"])
        self.assertEqual([(c, p["article"]) for c, p in self.DECLARATION["products"].items()], list(CARDS))
        self.assertEqual((self.DECLARATION["budget"]["max_real_requests_total"], self.DECLARATION["budget"]["max_real_requests_per_product"], self.DECLARATION["dealer"]["requests"]), (13, 7, 0))
        self.assertIn("group 5B", self.DECLARATION["not_done"])

    def test_requests_were_official_hosts_only_and_nothing_stopped(self):
        budget = self.RESULT["budget"]
        self.assertEqual((budget["spent_total"], self.RESULT["stopped_hosts_after_run"], self.RESULT["halted_before_finishing"], self.RESULT["not_started"]), (7, [], [], []))
        self.assertLessEqual(budget["spent_total"], budget["max_total"])
        self.assertTrue(all(e["status_code"] == 200 for e in self.RESULT["fetch_log_entries"]))
        hosts = {e["url"].split("/")[2] for e in budget["log"]}
        self.assertLessEqual(hosts, {"www.samsung.com", "org.downloadcenter.samsung.com"})
        self.assertEqual(sum(1 for e in budget["log"] if e["url"].endswith("memory-sitemap.xml")), 1)     # the sitemap was read once for the whole group

    def test_every_page_address_came_from_the_sitemap(self):
        listed = set(sitemap_locs(R.PAGES["https://www.samsung.com/kz_ru/memory-sitemap.xml"][1]))
        for card in self.RESULT["cards"]:
            self.assertIn(card["page_evidence"]["route"]["found_via"].rsplit("/", 1)[-1], ("memory-sitemap.xml",))
            self.assertIn(next(s["url"] for k, s in card["sources"].items() if k == "samsung"), listed)


class CardsAsRecordedInTheRealRun(unittest.TestCase):
    """What the code of Stage 29 concluded from the real responses (the record itself; Stage 30 changed two rules, see tests/test_stage30_samsung_rules.py)."""
    RESULT = load("batch5a_result.json")

    def card(self, article):
        return next(c for c in self.RESULT["cards"] if c["article"] == article)

    def test_job_status_and_readiness_were_kept_apart(self):
        self.assertEqual({c["article"]: c["job_status"] for c in self.RESULT["cards"]}, {"MZ-77E500BW": "done", "MUF-64BE3/APC": "done", "MU-PC1T0H/WW": "needs_review", "MB-MC64HARU": "done"})
        self.assertEqual({c["article"]: c["readiness"]["verdict"] for c in self.RESULT["cards"]},
                         {"MZ-77E500BW": "export_ready_with_gaps", "MUF-64BE3/APC": "export_ready_with_gaps", "MU-PC1T0H/WW": "needs_verification", "MB-MC64HARU": "export_ready_with_gaps"})

    def test_the_variant_was_confirmed_by_the_page_content_not_by_the_address(self):
        self.assertEqual({c["article"]: c["readiness"]["page_match_level"] for c in self.RESULT["cards"]},
                         {"MZ-77E500BW": "full_sku", "MUF-64BE3/APC": "full_sku", "MU-PC1T0H/WW": "code_in_page_text", "MB-MC64HARU": "full_sku"})
        self.assertEqual(self.card("MU-PC1T0H/WW")["photos"]["gallery_selected"], 0)                 # 12 found, none bound to the variant at that time

    def test_a_generic_support_link_is_not_an_instruction(self):
        for article in ("MUF-64BE3/APC", "MU-PC1T0H/WW", "MB-MC64HARU"):
            self.assertIn("instruction_missing", self.card(article)["readiness"]["blocking_gaps"])
            self.assertEqual(self.card(article)["readiness"]["instruction"]["saved"], 0)
            self.assertEqual(self.card(article)["document_files_assessed"], [])

    def test_no_dealer_request_was_made(self):
        self.assertEqual([e for e in self.RESULT["budget"]["log"] if "dns" in e["url"] or "tehnopark" in e["url"]], [])


class RussianSectionOfTheSsdLeaflet(unittest.TestCase):
    """The leaflet is a 15-page multilingual sheet whose Russian part is five short bullet points on page 8: recorded as a fact, not decided here."""

    def test_the_russian_section_exists_but_stays_below_the_instruction_threshold(self):
        record = next(r for r in json.loads((S29 / "docs_extract/index.json").read_text(encoding="utf-8")) if "Installation_Guide" in r["url"])
        with gzip.open(S29 / "docs_extract" / record["text_file"], "rt", encoding="utf-8") as handle:
            pages = handle.read().split("\n\f\n")
        self.assertEqual(len(pages), 15)
        self.assertIn("RUS\n• Для", pages[7])
        facts = samsung.assess_samsung_document(pages, "MZ-77E500BW", "MZ-77E500", "full_sku")
        self.assertIn("ru", facts["languages_by_text"])
        self.assertFalse(facts["russian_by_text"])
        self.assertFalse(facts["names_catalog_model"]["exact"])


class WearablesCurrencyCheck(unittest.TestCase):
    CHECK = load("wearables_currency_check.json")

    def test_watch7_is_not_current_because_the_same_official_sitemap_lists_newer_generations(self):
        self.assertEqual(self.CHECK["requests_made"], 0)
        watch = self.CHECK["watch"]
        self.assertEqual(watch["catalog_article"], "SM-L300NZEACIS")
        self.assertTrue(watch["page_listed_in_official_sitemap"])
        self.assertTrue({"watch8", "watch8-classic", "watch9", "ultra2"} <= set(watch["newer_generations_listed"]))
        self.assertEqual(watch["verdict"], "not_a_novelty")

    def test_fit3_is_the_newest_band_listed_but_its_novelty_is_not_proved(self):
        band = self.CHECK["band"]
        self.assertEqual(band["catalog_article"], "SM-R390NZSACIS")
        self.assertEqual(band["lines_listed"], ["fit3"])
        self.assertEqual(band["verdict"], "newest_listed_novelty_not_proved_owner_decision")


if __name__ == "__main__":
    unittest.main()
