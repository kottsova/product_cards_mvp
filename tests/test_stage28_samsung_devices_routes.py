"""Stage 28: the dishwasher's limited attempt (60 MB ceiling), the robot vacuum's device split by explicit evidence, the observed route to the next Samsung categories, and the batch proposal.
Offline on the saved responses (tests/_samsung_replay.py); the recorded reports of the real requests are read as data. No socket is opened."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import _samsung_replay as R
from product_tool import card_evidence, jobs, samsung_readiness
from product_tool.adapters import samsung
from product_tool.adapters.samsung import PART_GROUP, SpecItem, assign_devices, manual_device_tables, spec_attributes
from product_tool.adapters.samsung_source import default_samsung_adapter, route_for
from product_tool.adapters.sitemap_urls import sitemap_locs

ROOT = Path(__file__).resolve().parents[1]
S28 = ROOT / "reports/source_census_2026-09-26_stage28"
RAW = S28 / "raw"


def load(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


class DishwasherAttemptWasDeclaredAndLimited(unittest.TestCase):
    DECLARATION = load("dishwasher_declaration.json")
    RESULT = load("dishwasher_result.json")

    def test_declared_first_and_inside_its_budget(self):
        self.assertLess(self.DECLARATION["declared_at"], self.RESULT["started_at"])
        self.assertEqual((self.DECLARATION["budget"]["max_real_http_requests"], self.DECLARATION["budget"]["document_ceiling_bytes"]), (2, 60_000_000))
        self.assertLessEqual(self.RESULT["budget"]["spent"], 2)
        self.assertEqual(self.RESULT["budget"]["spent"], 1)
        self.assertEqual(self.RESULT["stopped_hosts"], [])
        self.assertEqual([s["step"] for s in self.RESULT["steps"]], ["document"])                  # no page, no other file
        self.assertEqual(self.RESULT["steps"][0]["url"], self.DECLARATION["candidate"]["href"])   # the already known link
        self.assertTrue(all(e["status_code"] == 200 for e in self.RESULT["fetch_log"]))

    def test_the_file_was_read_by_its_text_and_the_owner_rules_decided(self):
        self.assertEqual(self.RESULT["outcome"], "obtained_and_assessed")
        facts = next(f["facts"] for f in self.RESULT["files"] if f.get("facts"))
        self.assertGreater(next(f["bytes"] for f in self.RESULT["files"]), 40_000_000)             # it was over the old cap
        self.assertTrue(facts["russian_by_text"])
        self.assertTrue(facts["names_catalog_model"]["exact"])
        self.assertEqual((facts["tied_by_official_page"], facts["acceptance"]["basis"], facts["conflicting_models"]), ("exact_page", "exact_code_in_pdf", []))


class DishwasherCardBeforeAndAfter(unittest.TestCase):
    CARD = [("Машины посудомоечные", "DW60M5050BB/WT")]

    def test_the_recorded_evidence_makes_the_ordinary_path_use_the_file_without_a_download(self):
        with TemporaryDirectory() as tmp:
            run = R.run_products(Path(tmp), cards=self.CARD)
            r = samsung_readiness.card_readiness(run["database"], run["outcomes"][0]["product_id"])
            self.assertEqual((r["verdict"], r["blocking_gaps"], r["instruction"]["acceptance_basis"], r["instruction"]["assessed_from"]), ("export_ready", [], "exact_code_in_pdf", "recorded"))
            self.assertFalse(any("ContentsFile" in c for c in run["replay"].calls))
            self.assertEqual(run["outcomes"][0]["status"], "done")

    def test_when_the_candidate_is_not_read_the_status_is_candidate_not_verified_and_english_does_not_replace_it(self):
        with TemporaryDirectory() as tmp:
            run = R.run_products(Path(tmp), cards=self.CARD, recorded_documents={})            # default cap 40 MB: the file is cut again
            pid = run["outcomes"][0]["product_id"]
            r = samsung_readiness.card_readiness(run["database"], pid)
            self.assertEqual(r["blocking_gaps"], ["instruction_russian_candidate_not_verified"])
            self.assertNotIn("instruction_language_not_russian", r["gaps"])
            self.assertIn("instruction_only_non_russian_file_saved", r["advisory_gaps"])
            self.assertEqual(r["instruction"]["russian_saved"], 0)
            self.assertIn("это не значит, что русской инструкции нет", r["gap_reasons"]["instruction_russian_candidate_not_verified"])
            messages = " ".join(e["message"] for e in jobs.list_events(run["database"], run["outcomes"][0]["job_id"]))
            self.assertIn("Кандидат на русскую инструкцию не проверен", messages)
            self.assertNotIn("Русской инструкции нет", messages)

    def test_the_declared_ceiling_gets_the_file_in_the_replay_too(self):
        with TemporaryDirectory() as tmp:
            run = R.run_products(Path(tmp), cards=self.CARD, recorded_documents={}, document_cap=60_000_000)
            r = samsung_readiness.card_readiness(run["database"], run["outcomes"][0]["product_id"])
            self.assertEqual((r["blocking_gaps"], r["instruction"]["acceptance_basis"], r["instruction"]["assessed_from"]), ([], "exact_code_in_pdf", "file"))


class RobotVacuumDevicesFromExplicitEvidence(unittest.TestCase):
    URL = R.page_url("vr50t95735w-ev/")
    ITEMS = samsung.extract_spec_table(R.PAGES[URL][1])
    MANUAL = next(v for k, v in R.DOCUMENT_TEXT.items() if "VR9500" in k)

    def tables(self):
        return manual_device_tables(self.MANUAL, "VR50T95735W/EV")

    def test_the_manuals_tables_name_their_devices(self):
        tables = self.tables()
        self.assertEqual([(t["device"], t["mass_kg"], t["size_mm"]) for t in tables], [("product", 4.4, [305.0, 320.0, 120.0]), ("station", 5.1, [272.0, 416.0, 544.0])])
        self.assertEqual((tables[0]["size_note_mm"], tables[0]["block_heading"], tables[1]["block_heading"]), (136.5, "Серия VR50T95****", "Название Станция очистки"))

    def test_only_rows_whose_value_a_named_device_table_carries_are_assigned(self):
        assigned, records, unassigned = assign_devices(self.ITEMS, self.tables())
        by = {(r["group"], r["row"], r["value"]): r["device"] for r in records}
        self.assertEqual(by[("Обзор", "Вес", "4.4 кг")], "product")
        self.assertEqual(by[("Обзор", "Размеры (ШxВxГ)", "305x136.5x320 мм")], "product")
        self.assertEqual(by[("Детали Станции очистки (Аксессуары)", "Вес", "5.1 кг")], "station")
        self.assertEqual(by[("Детали Станции очистки (Аксессуары)", "Размеры (ШxВxГ)", "272x544x416 мм")], "station")
        self.assertEqual(sorted((u["group"], u["row"], u["value"]) for u in unassigned), sorted([("Обзор", "Вес", "9.5 кг"), ("Обзор", "Размеры (ШxВxГ)", "305x544x450 мм"), ("Физические характеристики", "Размеры (ШxВxГ)", "305x544x450 мм")]))
        for record in records:
            self.assertTrue(record["basis"])                                                     # every assignment states its basis

    def test_row_order_is_never_the_evidence(self):
        forward = assign_devices(self.ITEMS, self.tables())
        backward_items = list(reversed(self.ITEMS))
        assigned, records, unassigned = assign_devices(backward_items, self.tables())
        key = lambda r: (r["group"], r["row"], r["value"], r["device"])
        self.assertEqual(sorted(map(key, records)), sorted(map(key, forward[1])))
        self.assertEqual(sorted((u["group"], u["row"], u["value"]) for u in unassigned), sorted((u["group"], u["row"], u["value"]) for u in forward[2]))

    def test_without_two_named_device_tables_nothing_is_assigned(self):
        self.assertEqual(assign_devices(self.ITEMS, self.tables()[:1])[0], {})
        self.assertEqual(assign_devices(self.ITEMS, [])[0], {})
        twin = [dict(self.tables()[0]), dict(self.tables()[0], device="station", block_heading="Название X")]
        assigned, records, unassigned = assign_devices([SpecItem("Обзор", "Вес", "4.4 кг")], twin)
        self.assertEqual((assigned, len(unassigned)), ({}, 1))                                # two tables carry the same value: no assignment

    def test_a_page_group_that_names_a_part_is_explicit_for_that_part(self):
        self.assertTrue(PART_GROUP.search("Детали Станции очистки (Аксессуары)"))
        names = [a.name for a in spec_attributes([SpecItem("Детали Станции очистки (Аксессуары)", "Вес", "5.1 кг")])]
        self.assertEqual(names, ["Вес (Детали Станции очистки (Аксессуары))"])

    def test_the_card_keeps_every_source_value_and_asks_for_a_check_instead_of_asking_you(self):
        with TemporaryDirectory() as tmp:
            run = R.run_products(Path(tmp), cards=[("Роботы-пылесосы", "VR50T95735W/EV")])
            pid = run["outcomes"][0]["product_id"]
            facts = {(f["raw_name"], f["raw_value"]): f["normalized_name"] for f in jobs.get_facts(run["database"], pid) if f["source_key"] == "samsung"}
            self.assertEqual(facts[("Вес [основное изделие]", "4.4 кг")], "product_weight__main_unit")
            self.assertEqual(facts[("Вес [станция очистки] (Детали Станции очистки (Аксессуары))", "5.1 кг")], "product_weight__cleaning_station")
            self.assertEqual(facts[("Вес", "9.5 кг")], "product_weight")                        # unassigned: kept as the source printed it
            self.assertEqual(facts[("Вес Комплекта", "4.4 кг")], "product_weight")
            self.assertIn(("Размеры (ШxВxГ) (Обзор)", "305x544x450 мм"), facts)
            r = samsung_readiness.card_readiness(run["database"], pid)
            self.assertIn("device_values_link_not_established", r["blocking_gaps"])
            self.assertEqual(r["conflict_fields"], ["product_weight"])
            self.assertEqual(len(r["device_values_unassigned"]), 3)
            self.assertIn("samsung_device_values_check", r["open_reviews"])
            self.assertEqual(run["outcomes"][0]["status"], "needs_review")
            self.assertEqual(r["verdict"], "export_ready_with_gaps")
            evidence = card_evidence.load(run["database"], pid, "samsung_page")["device_split"]
            self.assertEqual(len(evidence["assigned"]), 5)
            self.assertTrue(all(row["basis"] for row in evidence["assigned"]))

    def test_the_arithmetic_hint_is_not_used(self):
        # 4.4 kg + 5.1 kg = 9.5 kg would suggest the 9.5 kg row is the whole set; that is an inference, not a link in the data, so the row stays unassigned
        assigned, records, unassigned = assign_devices(self.ITEMS, self.tables())
        self.assertIn("9.5 кг", [u["value"] for u in unassigned])


class RouteToTheNextCategories(unittest.TestCase):
    STUDY = load("route_study_result.json")
    DECLARATION = load("route_study_declaration.json")
    MATCH = load("route_match.json")

    def test_the_route_was_declared_first_observed_and_inside_its_budget(self):
        self.assertLess(self.DECLARATION["declared_at"], self.STUDY["started_at"])
        self.assertEqual(self.DECLARATION["requests"]["max_real_requests"], 4)
        self.assertLessEqual(self.STUDY["budget"]["spent"], 4)
        self.assertEqual(self.STUDY["stopped_hosts"], [])
        urls = [e["url"] for e in self.STUDY["budget"]["log"]]
        self.assertEqual(urls, [r["url"] for r in self.DECLARATION["requests"]["planned"]])
        self.assertTrue(all(u.endswith(".xml") for u in urls))                                   # no product page, no file
        observed = json.loads((ROOT / "reports/source_census_2026-09-22_stage8_2/raw/samsung_step1.json").read_text(encoding="utf-8"))["step1_b2c_sitemap"]["sample_links"]
        for url in urls[1:]:
            self.assertIn(url, observed)                                                        # every sub-sitemap is one the official index listed in Stage 8.2...
            self.assertIn(url, self.STUDY["index_listed_now"])                                   # ...and lists today

    def test_every_proposed_page_is_an_address_a_saved_sitemap_lists(self):
        listed = {}
        for url in R.PAGES:
            if url.endswith(".xml") and not url.endswith("b2c-sitemap.xml"):
                listed[url.rsplit("/", 1)[-1]] = set(sitemap_locs(R.PAGES[url][1]))
        proposed = {c: e["proposed"] for c, e in self.MATCH["categories"].items() if "proposed" in e}
        self.assertEqual(sorted(proposed), sorted(["Внутренние SSD-накопители", "Смарт-часы", "Кабели", "Flash-накопители", "Внешние SSD-накопители", "Карты памяти", "Фитнес-браслеты"]))
        for category, p in proposed.items():
            self.assertIn(p["page_url"], listed[p["sitemap"]], category)
            self.assertIn(samsung.norm(p["article"]), samsung.norm(p["page_url"].rsplit("/kz_ru/", 1)[-1]))

    def test_the_adapters_route_finds_each_proposed_page_from_the_saved_sitemap(self):
        for category, entry in self.MATCH["categories"].items():
            if "proposed" not in entry:
                continue
            with TemporaryDirectory() as tmp:
                replay = R.Replay()
                adapter = default_samsung_adapter(Path(tmp), clock=lambda: 0.0, underlying=replay, min_interval_seconds=0.0, pages_reader=replay.pages_reader)
                report = {"steps": [], "route": {}}
                page = adapter._locate(entry["proposed"]["article"], category, report, 1e9)
                self.assertEqual(page, entry["proposed"]["page_url"], category)
                self.assertEqual(replay.refused, [])
                self.assertLessEqual(len(replay.calls), 2)

    def test_the_eight_categories_without_a_page_are_reported_and_nothing_is_guessed(self):
        without = sorted(c for c, e in self.MATCH["categories"].items() if "proposed" not in e)
        self.assertEqual(without, sorted(["Зарядные устройства", "Оперативная память", "Гарнитуры", "GPS-трекеры", "Наушники беспроводные", "МФУ", "Музыкальные проигрыватели", "Проекторы"]))
        for category in without:
            self.assertEqual(self.MATCH["categories"][category]["rows_with_exact_page"], 0)

    def test_routes_use_the_sitemaps_the_official_index_lists(self):
        self.assertEqual([a.rsplit("/", 1)[-1] for a in route_for("MZ-77E500BW", "Внутренние SSD-накопители")[1]], ["memory-sitemap.xml", "im-sitemap.xml"])
        self.assertEqual([a.rsplit("/", 1)[-1] for a in route_for("EP-DA705BBRGRU", "Кабели")[1]], ["im-sitemap.xml", "assorted-sitemap.xml"])
        self.assertEqual([a.rsplit("/", 1)[-1] for a in route_for("SM-L300NZEACIS", "Смарт-часы")[1]], ["im-sitemap.xml", "assorted-sitemap.xml"])
        self.assertEqual(route_for("SM-A376EZAGINS", "Смартфоны")[0], "hub")
        self.assertEqual(route_for("RB31FERNDSA", "Холодильники")[1][0].rsplit("/", 1)[-1], "da-sitemap.xml")


class BatchFiveIsOnlyProposed(unittest.TestCase):
    PROPOSAL = load("batch5_proposal.json")

    def test_one_product_per_category_in_small_groups_with_a_declared_budget_and_stop_rules(self):
        self.assertTrue(self.PROPOSAL["status"].startswith("PROPOSAL"))
        seen = []
        for name, group in self.PROPOSAL["groups"].items():
            self.assertLessEqual(len(group["products"]), 4, name)
            seen += list(group["products"])
            budget = group["request_budget"]
            self.assertEqual(budget["per_row_cap"], 7)
            self.assertLessEqual(budget["total_cap"], 13)
            self.assertIn("401/403/429", group["stop_rules"])
            self.assertEqual(group["dealer_requests"], 0)
        self.assertEqual(len(seen), len(set(seen)), "a category appears once")
        self.assertEqual(len(seen), 7)
        for category in seen:
            self.assertNotIn(category, self.PROPOSAL["categories_still_without_a_route"])

    def test_the_planner_offers_memory_and_checked_cable_but_waits_on_wearables(self):
        from product_tool.coverage.facts import load_config
        selected = {i["category"] for i in load_config()["selected_products"]["samsung"]["products"]}
        groups = self.PROPOSAL["groups"]
        memory = next(group for name, group in groups.items() if name.startswith("5A"))
        remaining = next(group for name, group in groups.items() if name.startswith("5B"))
        self.assertTrue(set(memory["products"]) <= selected)
        self.assertEqual(selected & set(remaining["products"]), {"Кабели"})


if __name__ == "__main__":
    unittest.main()
