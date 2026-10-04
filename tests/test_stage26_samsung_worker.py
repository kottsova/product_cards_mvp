"""Stage 26: the Samsung adapter inside the ordinary worker.run_once() path, replayed offline on the pages and document texts saved in Stages 24-25.

One shared run puts the eleven cards of the earlier batches (one per category) through run_once(); the tests read what was stored (source rows, facts, photos, documents, evidence, reviews, job
status, readiness, export). No socket is opened: the transport is tests/_samsung_replay.Replay and the dealer's session refuses every call.
"""
from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import load_workbook

import _samsung_replay as R
from product_tool import card_evidence, display, exporter, jobs, samsung_readiness, worker
from product_tool.adapters.common import RawAttribute, SourceDocument
from product_tool.adapters.dns import DnsAdapter
from product_tool.adapters.policy_session import RequestBudget, request_budget
from product_tool.adapters.samsung import PAGE_TIES, buy_page_url
from product_tool.adapters.samsung_source import MAX_REQUESTS_PER_ROW, default_samsung_adapter, levels_note, match_level_of, route_for
from product_tool.normalization import normalize_name

EXPECTED = {  # category: (article, page level, specification items, gallery photos)
    "Телевизоры": ("QE48S85HAEXCE", "full_sku", 117, 8), "Смартфоны": ("SM-A376EZAGINS", "base_model", 64, 9), "Пылесосы": ("VC18M21D0VG/EV", "full_sku", 28, 15),
    "Стиральные машины": ("WD10T754CBX/LD", "full_sku", 85, 11), "Микроволновые печи": ("MS23K3614AK/BW", "full_sku", 59, 11), "Холодильники": ("RB31FERNDSA", "code_in_page_text", 55, 9),
    "Духовые шкафы": ("NV7B4120ZAS/WT", "full_sku", 45, 8), "Сплит-системы": ("AR80F09CABWNER", "full_sku", 83, 18), "Варочные панели": ("NZ64T3506AK/WT", "full_sku", 25, 1),   # Stage 30: the page's own single product-data code equals the catalog code (was code_in_page_text)
    
    "Мониторы": ("LS24D300GAIXCI", "full_sku", 64, 11), "Саундбары": ("HW-Q800D", "full_sku", 57, 17),
}


class OrdinaryWorkerPath(unittest.TestCase):
    """The eleven checked categories through worker.run_once()."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = TemporaryDirectory()
        cls.batch = R.run_products(Path(cls._tmp.name))
        cls.db = cls.batch["database"]
        cls.by_category = {o["category"]: o for o in cls.batch["outcomes"]}
        cls.readiness = {c: samsung_readiness.card_readiness(cls.db, o["product_id"]) for c, o in cls.by_category.items()}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def source(self, category, key="samsung"):
        return next(s for s in jobs.get_source_pages(self.db, self.by_category[category]["product_id"]) if s["source_key"] == key)

    def test_every_checked_category_goes_through_run_once_and_finishes(self):
        self.assertEqual(len(self.by_category), 11)
        for category, outcome in self.by_category.items():
            self.assertIn(outcome["status"], ("done", "needs_review"), (category, outcome["message"]))

    def test_variant_levels_specifications_and_photo_counts_are_the_saved_ones(self):
        for category, (article, level, specs, photos) in EXPECTED.items():
            with self.subTest(category):
                product_id = self.by_category[category]["product_id"]
                self.assertEqual(self.source(category)["match_level"], level)
                self.assertEqual(sum(1 for f in jobs.get_facts(self.db, product_id) if f["source_key"] == "samsung"), specs)
                gallery = [p for p in jobs.get_photo_candidates(self.db, product_id, include_excluded=False) if p["source_key"] == "samsung"]
                self.assertEqual(len(gallery), photos)

    def test_a_code_found_only_in_page_text_is_never_an_unconditionally_exact_variant(self):
        for category in ("Холодильники",):     # Stage 30: the hob is no longer a text-only case -- its own product data names the exact code
            with self.subTest(category):
                self.assertEqual(self.source(category)["match_level"], "code_in_page_text")
                self.assertNotEqual(self.by_category[category]["status"], "done")
                self.assertEqual(self.readiness[category]["verdict"], "needs_verification")
                self.assertIn("variant_code_only_in_page_text", self.readiness[category]["blocking_gaps"])
                photos = [p for p in jobs.get_photo_candidates(self.db, self.by_category[category]["product_id"], include_excluded=False) if p["source_key"] == "samsung"]
                selected = sum(1 for p in photos if p["selected"])
                # only a photo whose OWN asset path names exactly the catalog code is bound to the variant (the hob's), never one chosen because the page's text mentions the code
                self.assertEqual(selected, 0)
                self.assertIn("samsung_variant_check", self.readiness[category]["open_reviews"])

    def test_the_phone_keeps_region_and_colour_open_and_has_more_gaps_than_the_missing_instruction(self):
        r = self.readiness["Смартфоны"]
        self.assertEqual(r["page_match_level"], "base_model")
        self.assertEqual(self.by_category["Смартфоны"]["status"], "needs_review")
        self.assertTrue(any("региональный код" in d and "INS" in d and "SKZ" in d for d in r["open_variant_differences"]))
        self.assertTrue(any("код цвета" in d and "ZA" in d and "DG" in d for d in r["open_variant_differences"]))
        self.assertIn("variant_base_model_only", r["blocking_gaps"])
        self.assertIn("photos_not_selected_variant_open", r["blocking_gaps"])
        self.assertIn("instruction_missing", r["blocking_gaps"])
        self.assertGreater(len([g for g in r["blocking_gaps"] if g != "instruction_missing"]), 1)
        self.assertEqual(r["verdict"], "needs_verification")
        self.assertEqual(r["official_photos"], 9)
        self.assertEqual(r["official_photos_selected"], 0)
        self.assertEqual(jobs.get_documents(self.db, self.by_category["Смартфоны"]["product_id"]), [])

    def test_a_gallery_is_selected_for_the_card_only_when_the_page_content_confirms_the_article(self):
        for category, (article, level, specs, photos) in EXPECTED.items():
            with self.subTest(category):
                selected = self.readiness[category]["official_photos_selected"]
                self.assertEqual(selected, photos if level == "full_sku" else 0)

    def test_thumbnails_and_3d_files_are_never_photos(self):
        for category, outcome in self.by_category.items():
            with self.subTest(category):
                rows = jobs.get_photo_candidates(self.db, outcome["product_id"], include_excluded=True)
                for row in rows:
                    if row["source_key"] != "samsung":
                        continue
                    if row["kind"] == "product_gallery":
                        self.assertNotRegex(row["url"], r"-thumb-|104_104|\.(?:glb|usdz)")
                    else:
                        self.assertIn(row["excluded_reason"], ("thumbnail", "3d_model"))
                keys = [r["asset_key"] for r in rows if r["kind"] == "product_gallery"]
                self.assertEqual(len(keys), len(set(keys)))  # one asset once (no size duplicates)

    def test_tv_and_vacuum_keep_the_three_document_facts_apart_and_the_owner_rule_is_applied(self):
        tv = self.readiness["Телевизоры"]["instruction"]
        vacuum = self.readiness["Пылесосы"]["instruction"]
        self.assertEqual((tv["russian_by_text"], tv["tied_by_official_page"], tv["names_catalog_code_exactly"], tv["names_family_mask"], tv["names_link_model_only"]), (True, "exact_page", False, [], False))
        self.assertEqual((vacuum["russian_by_text"], vacuum["tied_by_official_page"], vacuum["names_catalog_code_exactly"], vacuum["names_family_mask"], vacuum["names_link_model_only"]), (True, "exact_page", False, [], True))
        # TV: the exact page prints the link, the text is a Russian instruction, no model is named at all -> accepted with the owner's mark
        self.assertEqual((tv["acceptance_basis"], tv["accepted"]), ("exact_page_link_only", True))
        self.assertEqual(tv["mark"], "связь с моделью подтверждена точной официальной страницей; точный код в PDF не назван")
        # vacuum: the PDF names ANOTHER code; accepted only because this page's own data declares that code as its model name next to the catalog code as its model code
        self.assertEqual((vacuum["acceptance_basis"], vacuum["accepted"]), ("code_relation_declared_by_page_data", True))
        self.assertEqual((vacuum["code_relation"]["link_model_name"], vacuum["code_relation"]["page_model_name"], vacuum["code_relation"]["page_model_code"]), ("SC18M21D0VG", "SC18M21D0VG", "VC18M21D0VG/EV"))
        for category in ("Телевизоры", "Пылесосы"):
            self.assertEqual(self.readiness[category]["blocking_gaps"], [])
            self.assertIn("instruction_exact_code_not_in_pdf", self.readiness[category]["advisory_gaps"])
            self.assertEqual(self.readiness[category]["verdict"], "export_ready")
        vacuum_doc = jobs.get_documents(self.db, self.by_category["Пылесосы"]["product_id"])[0]
        self.assertEqual(vacuum_doc["support_model"], "SC18M21D0VG")           # the model the page's own link declares...
        self.assertEqual(vacuum_doc["product_model"], "VC18M21D0VG")           # ...is stored apart from the catalog model: no SC = VC rule
        self.assertIn("код каталога не назван", vacuum_doc["title"])
        self.assertIn("принята с пометкой", vacuum_doc["title"])
        self.assertIn("связь с моделью подтверждена точной официальной страницей", jobs.get_documents(self.db, self.by_category["Телевизоры"]["product_id"])[0]["title"])

    def test_no_code_equality_rule_is_applied_to_sc_and_vc(self):
        from product_tool.adapters.samsung import instruction_acceptance
        evidence = card_evidence.load(self.db, self.by_category["Пылесосы"]["product_id"], "samsung_documents")
        facts = next(d["facts"] for d in evidence["documents"] if d.get("facts"))
        self.assertFalse(facts["names_catalog_model"]["exact"])
        self.assertTrue(facts["names_link_model"]["exact"])
        self.assertEqual(facts["conflicting_models"], [])
        # the same PDF facts on a page whose data does NOT declare the link's model as its model name: not accepted, left for a person
        no_data = instruction_acceptance(facts, {}, "VC18M21D0VG/EV", "SC18M21D0VG")
        self.assertEqual((no_data["basis"], no_data["accepted"]), ("link_code_relation_unverified", False))
        other_name = instruction_acceptance(facts, {"model_code": "VC18M21D0VG/EV", "model_name": "SOMETHING_ELSE", "source": "test"}, "VC18M21D0VG/EV", "SC18M21D0VG")
        self.assertEqual((other_name["basis"], other_name["accepted"]), ("link_code_relation_unverified", False))
        # a page that declares the model name but for ANOTHER catalog code does not tie it either
        wrong_code = instruction_acceptance(facts, {"model_code": "VC99X99X9X/EV", "model_name": "SC18M21D0VG", "source": "test"}, "VC18M21D0VG/EV", "SC18M21D0VG")
        self.assertEqual((wrong_code["basis"], wrong_code["accepted"]), ("link_code_relation_unverified", False))

    def test_the_monitor_is_accepted_on_its_own_page_data_not_on_a_rule(self):
        monitor = self.readiness["Мониторы"]["instruction"]
        self.assertEqual((monitor["acceptance_basis"], monitor["accepted"]), ("code_relation_declared_by_page_data", True))
        self.assertEqual((monitor["code_relation"]["link_model_name"], monitor["code_relation"]["page_model_code"]), ("S24D300GAI", "LS24D300GAIXCI"))

    def test_a_scanned_instruction_stays_a_manual_check_and_is_not_saved(self):
        hob = self.by_category["Варочные панели"]["product_id"]
        self.assertEqual(jobs.get_documents(self.db, hob), [])
        self.assertIn("instruction_text_not_extractable_manual_check", self.readiness["Варочные панели"]["blocking_gaps"])
        entry = card_evidence.load(self.db, hob, "samsung_documents")["documents"][0]
        self.assertEqual(entry["state"], "manual_check_text_not_extractable")
        self.assertIsNone(entry["facts"]["russian_by_text"])
        self.assertIn("samsung_instruction_check", self.readiness["Варочные панели"]["open_reviews"])

    def test_family_masks_are_accepted_and_always_carry_the_mark(self):
        for category in ("Стиральные машины", "Духовые шкафы", "Сплит-системы"):
            with self.subTest(category):
                i = self.readiness[category]["instruction"]
                self.assertIn("instruction_exact_code_not_in_pdf", self.readiness[category]["advisory_gaps"])
                self.assertTrue(i["names_family_mask"])
                self.assertFalse(i["names_catalog_code_exactly"])
                self.assertEqual((i["acceptance_basis"], i["accepted"]), ("family_mask_in_pdf", True))
                self.assertIn("точный код в PDF не назван", i["mark"])
                self.assertIn("точный код в PDF не назван", jobs.get_documents(self.db, self.by_category[category]["product_id"])[0]["title"])
        soundbar = self.readiness["Саундбары"]["instruction"]
        self.assertEqual(soundbar["acceptance_basis"], "exact_code_in_pdf")
        self.assertNotIn("instruction_exact_code_not_in_pdf", self.readiness["Саундбары"]["advisory_gaps"])

    def test_the_microwave_instruction_is_taken_from_the_recorded_stage_8_6_evidence_without_a_download(self):
        r = self.readiness["Микроволновые печи"]
        i = r["instruction"]
        self.assertEqual((i["acceptance_basis"], i["accepted"], i["assessed_from"]), ("exact_code_in_pdf", True, "recorded"))
        self.assertEqual(r["blocking_gaps"], [])
        self.assertEqual(r["verdict"], "export_ready")
        self.assertEqual(self.batch["replay"].refused, [])
        self.assertFalse(any("MS23K3614AK" in c and "ContentsFile" in c for c in self.batch["replay"].calls))       # the PDF was not requested
        evidence = card_evidence.load(self.db, self.by_category["Микроволновые печи"]["product_id"], "samsung_documents")
        entry = evidence["documents"][0]
        self.assertTrue(entry["recorded"])
        self.assertEqual(entry["facts"]["tied_by_official_page"], "exact_page")                 # the tie to the CURRENT page is read live
        self.assertIn("reports/source_census_2026-09-22_stage8_6/content_verification.json", entry["facts"]["evidence_report"])
        log = card_evidence.load(self.db, self.by_category["Микроволновые печи"]["product_id"], "samsung_requests")
        self.assertEqual(log["spent"], 1)                                                       # the product page only

    def test_no_real_conflicts_and_no_same_source_false_conflicts(self):
        for category, outcome in self.by_category.items():
            self.assertEqual(jobs.result_counts(self.db, outcome["product_id"])["conflicts"], 0, category)

    def test_job_status_is_kept_apart_from_card_readiness(self):
        done = sorted(c for c, o in self.by_category.items() if o["status"] == "done")
        self.assertEqual(done, sorted(c for c, (a, level, s, p) in EXPECTED.items() if level == "full_sku"))
        self.assertEqual(self.by_category["Телевизоры"]["status"], "done")
        self.assertEqual(self.readiness["Телевизоры"]["verdict"], "export_ready")
        verdicts = {}
        for category, r in self.readiness.items():
            verdicts.setdefault(r["verdict"], []).append(category)
        self.assertEqual(sorted(verdicts), ["export_ready", "export_ready_with_gaps", "needs_verification"])
        self.assertEqual(sorted(verdicts["needs_verification"]), sorted(["Смартфоны", "Холодильники"]))
        self.assertEqual(verdicts["export_ready_with_gaps"], ["Варочные панели"])           # Stage 30: variant confirmed by the page's own product data; the scanned instruction stays a manual check
        self.assertEqual(len(verdicts["export_ready"]), 8)

    def test_dealer_fallback_makes_no_request_without_a_verified_url_and_yields_the_ready_request(self):
        self.assertEqual(self.batch["dealer_session"].calls, [])
        phone = self.source("Смартфоны", "dns")
        self.assertEqual(phone["match_level"], "dealer_url_needed")
        self.assertIn("SM-A376EZAGINS", phone["evidence"])
        self.assertIn("инструкция", phone["evidence"])
        self.assertEqual(self.source("Телевизоры", "dns")["match_level"], "not_needed")

    def test_requests_stay_inside_the_per_row_budget_and_are_all_logged(self):
        total = 0
        for category, outcome in self.by_category.items():
            log = card_evidence.load(self.db, outcome["product_id"], "samsung_requests")
            self.assertLessEqual(log["spent"], MAX_REQUESTS_PER_ROW, category)
            self.assertEqual(log["spent"], len(log["log"]))
            total += log["spent"]
        # every request that reached the transport and was answered is a logged one; a refusal of the replay (the unsaved microwave manual, asked twice: one retry) is not a round trip
        self.assertEqual(total, len(self.batch["replay"].calls) - len(self.batch["replay"].refused))
        self.assertEqual(sum(1 for c in self.batch["replay"].calls if c.endswith("sitemap.xml")), 2)   # each sitemap once for the whole batch

    def test_only_official_routes_are_requested(self):
        for url in self.batch["replay"].calls:
            self.assertRegex(url, r"^https://(?:www\.samsung\.com/kz_ru/|org\.downloadcenter\.samsung\.com/downloadfile/ContentsFile\.aspx\?)")

    def test_export_carries_the_levels_photos_and_documents(self):
        self.assertEqual(load_workbook(io.BytesIO(exporter.export_batch(self.db, self.batch["batch_id"]))).sheetnames, load_workbook(io.BytesIO(self.batch["export"])).sheetnames)
        book = load_workbook(io.BytesIO(self.batch["export"]))                 # the file the web route served
        self.assertIn("Готовность Samsung", book.sheetnames)
        rows = list(book["Готовность Samsung"].iter_rows(values_only=True))
        self.assertEqual(len(rows) - 1, 11)
        by_article = {r[1]: r for r in rows[1:]}
        self.assertEqual(by_article["SM-A376EZAGINS"][2], "needs_verification")
        self.assertIn("региональный код", by_article["SM-A376EZAGINS"][4])
        self.assertIn("точный код в PDF не назван", by_article["QE48S85HAEXCE"][9])
        self.assertEqual(by_article["QE48S85HAEXCE"][rows[0].index("\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f: \u043e\u0441\u043d\u043e\u0432\u0430\u043d\u0438\u0435 \u043f\u0440\u0438\u043d\u044f\u0442\u0438\u044f")], "exact_page_link_only: принята")
        self.assertEqual(by_article["VC18M21D0VG/EV"][rows[0].index("\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f: \u043e\u0441\u043d\u043e\u0432\u0430\u043d\u0438\u0435 \u043f\u0440\u0438\u043d\u044f\u0442\u0438\u044f")], "code_relation_declared_by_page_data: принята")
        self.assertEqual(by_article["MS23K3614AK/BW"][9], "точный код")
        self.assertEqual(by_article["NZ64T3506AK/WT"][2], "export_ready_with_gaps")
        exported_photos = list(book["Фотографии"].iter_rows(min_row=2, values_only=True))
        expected = sum(photos for (a, level, s, photos) in EXPECTED.values() if level == "full_sku")
        self.assertEqual(len(exported_photos), expected)
        self.assertFalse(any(r[3] and ("-thumb-" in r[3] or r[3].endswith((".glb", ".usdz"))) for r in exported_photos))
        levels = {r[3]: r[4] for r in book["Источники"].iter_rows(min_row=2, values_only=True) if r[2] == "Samsung Казахстан"}
        self.assertEqual(sorted(set(levels.values())), ["Артикул только в тексте страницы", "Базовая модель", "Полный артикул"])
        self.assertIn("Samsung", [c.value for c in book["Проверка источников"][1]])
        self.assertEqual(len(list(book["Инструкции"].iter_rows(min_row=2, values_only=True))), 9)  # the phone and the hob have none saved; the fridge's is saved but not accepted

    def test_the_card_page_labels_the_evidence_levels(self):
        from fastapi.testclient import TestClient
        from product_tool.web import create_app
        with TemporaryDirectory() as tmp:
            import shutil
            shutil.copy(self.db, Path(tmp) / "batches.sqlite3")
            with TestClient(create_app(tmp)) as client:
                hob = client.get(f"/products/{self.by_category['Холодильники']['product_id']}")
                self.assertEqual(hob.status_code, 200)
                self.assertIn("Артикул только в тексте страницы", hob.text)
                self.assertIn("Samsung Казахстан", hob.text)
                self.assertIn("Артикул найден только в тексте страницы Samsung", hob.text)
                phone = client.get(f"/products/{self.by_category['Смартфоны']['product_id']}")
                self.assertIn("Найдена только базовая модель Samsung", phone.text)
                tv = client.get(f"/products/{self.by_category['Телевизоры']['product_id']}")
                self.assertIn("Полный артикул найден на Samsung", tv.text)
                self.assertNotIn("Найдено только у базовой модели LG", tv.text)


class SamsungRoutesAndLevels(unittest.TestCase):
    def test_routes_are_the_observed_ones_and_wearables_have_none(self):
        self.assertEqual(route_for("SM-A376EZAGINS", "Смартфоны")[0], "hub")
        self.assertEqual(route_for("SM-X826BZARSKZ", "Планшеты")[1], ("https://www.samsung.com/kz_ru/tablets/all-tablets/",))
        self.assertEqual(route_for("SM-L320NZKACIS", "Прочее")[0], "none")
        self.assertEqual(route_for("RB31FERNDSA", "Холодильники")[1][0], "https://www.samsung.com/kz_ru/da-sitemap.xml")
        self.assertEqual(route_for("QE48S85HAEXCE", "Телевизоры")[1][0], "https://www.samsung.com/kz_ru/vd-sitemap.xml")

    def test_a_wearable_row_requests_nothing(self):
        with TemporaryDirectory() as tmp:
            replay = R.Replay()
            adapter = default_samsung_adapter(Path(tmp), clock=lambda: 0.0, underlying=replay, min_interval_seconds=0.0, pages_reader=replay.pages_reader)
            document = adapter.find_source("SM-L320NZKACIS", deadline=1e9, category="Прочее")
            self.assertEqual((document.match_level, document.url, replay.calls), ("unknown", "", []))
            self.assertIn("маршрут", document.evidence)

    def test_a_blank_or_stub_code_requests_nothing(self):
        with TemporaryDirectory() as tmp:
            replay = R.Replay()
            adapter = default_samsung_adapter(Path(tmp), clock=lambda: 0.0, underlying=replay, min_interval_seconds=0.0, pages_reader=replay.pages_reader)
            for code in ("", "  ", "X1"):
                document = adapter.find_source(code, deadline=1e9, category="Телевизоры")
                self.assertEqual((document.match_level, document.url), ("unknown", ""))
            self.assertEqual(replay.calls, [])

    def test_the_buy_page_is_the_one_the_products_own_markup_names(self):
        url = R.page_url("a376edggskz/")
        self.assertTrue(url.endswith("a376edggskz/"))
        html = R.PAGES[url][1]
        self.assertEqual(buy_page_url(html, url), url + "buy/")
        self.assertEqual(buy_page_url("<html></html>", url), "")

    def test_page_ties_are_kept_as_three_levels(self):
        self.assertEqual(PAGE_TIES, {"full_sku": "exact_page", "code_in_page_text": "page_with_code_in_text_only", "base_model": "base_model_page"})

    def test_levels_note_states_the_three_facts_in_words(self):
        facts = {"content_status": "readable", "russian_by_text": True, "tied_by_official_page": "exact_page", "names_catalog_model": {"exact": False, "family_mask": [], "tokens": ["X"]},
                 "names_link_model": {"model_name": "Y1", "exact": True, "family_mask": []}}
        self.assertEqual(levels_note(facts), "русский по тексту; связь с товаром: страница показывает полный артикул; в тексте назван только код из ссылки страницы (Y1), код каталога не назван")
        self.assertIn("проверяются вручную", levels_note({"content_status": "text_not_extractable"}))

    def test_match_level_of_separates_markup_from_text(self):
        class Identity:
            level, evidence_strength = "full_sku", "strong"
        self.assertEqual(match_level_of(Identity), "full_sku")
        Identity.evidence_strength = "text_only"
        self.assertEqual(match_level_of(Identity), "code_in_page_text")


class StopsAndBudget(unittest.TestCase):
    def test_a_403_stops_the_host_and_the_stop_outlives_the_run(self):
        with TemporaryDirectory() as tmp:
            first = R.run_products(Path(tmp), cards=[("Телевизоры", "QE48S85HAEXCE")], blocked_hosts=("www.samsung.com",))
            self.assertEqual(first["outcomes"][0]["status"], "error")
            self.assertEqual(len(first["replay"].calls), 1)
            log = json.loads((Path(tmp) / "samsung_fetch_log.json").read_text(encoding="utf-8"))
            self.assertEqual([e["status_code"] for e in log], [403])
            page = card_evidence.load(first["database"], first["outcomes"][0]["product_id"], "samsung_page")
            self.assertIn("HTTP 403", page["halted"])
            # a NEW run over the same directory: the stopped host is refused without any request
            second = R.run_products(Path(tmp), cards=[("Телевизоры", "QE48S85HAEXCE")], replay=R.Replay())
            self.assertEqual(second["replay"].calls, [])
            self.assertEqual(second["outcomes"][0]["status"], "error")
            self.assertIn("policy_host_stopped", card_evidence.load(second["database"], second["outcomes"][0]["product_id"], "samsung_page")["halted"])

    def test_the_row_budget_refuses_the_request_before_it_is_made(self):
        with TemporaryDirectory() as tmp:
            replay = R.Replay()
            adapter = default_samsung_adapter(Path(tmp), clock=lambda: 0.0, underlying=replay, min_interval_seconds=0.0, pages_reader=replay.pages_reader)
            budget = RequestBudget(max_per_row=1)
            budget.begin_row("t")
            with request_budget(budget):
                document = adapter.find_source("QE48S85HAEXCE", deadline=1e9, category="Телевизоры")
            self.assertEqual(len(replay.calls), 1)                 # the sitemap; the page request was refused
            self.assertTrue(document.error or document.match_level == "unknown")
            self.assertEqual(budget.row, 1)
            self.assertIn("policy_budget_exhausted", json.dumps(adapter.reports["QE48S85HAEXCE"]["steps"]))

    def test_without_an_injected_transport_the_test_process_still_opens_no_socket(self):
        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "batches.sqlite3"
            jobs.initialize(database)
            from product_tool.coverage.executor import _ensure_product
            unit = R.catalog_units({"QE48S85HAEXCE"})["QE48S85HAEXCE"]
            product_id = _ensure_product(database, unit, "guard")
            job_id = jobs.enqueue(database, product_id, [1, 2, 3, 4, 6])
            with self.assertLogs("product_tool.worker", level="ERROR"):     # the blocked attempt is logged by run_once as an unexpected failure
                worker.run_once(database, clock=lambda: 0.0, dns_adapter_factory=lambda: DnsAdapter(R.NoNetworkSession(), clock=lambda: 0.0))
            job = next(j for j in jobs.list_jobs(database, product_id) if j["id"] == job_id)
            self.assertEqual(job["status"], "error")


class DealerFallback(unittest.TestCase):
    """A dealer adds only what the official page lacks, only on an exact model and variant, with its own source; a difference goes to review; an unconfirmed page adds nothing."""

    def run_with(self, tmp, level, attributes):
        class Dealer:
            source_key, site_name, document_urls = "dns", "DNS", {}

            def find_source(self, code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
                return SourceDocument("dns", "DNS", "https://www.dns-shop.ru/product/verified/", found_model=code, match_level=level, evidence="test dealer", attributes=list(attributes))

            def find_documents(self, code, *, model_tokens=None, deadline):
                return [], "нет"

        run = R.run_products(Path(tmp), cards=[("Телевизоры", "QE48S85HAEXCE")], dealer_factory=lambda: Dealer())
        return run, run["outcomes"][0]["product_id"]

    def test_a_confirmed_dealer_fills_a_missing_field_with_its_own_source_and_a_difference_goes_to_review(self):
        with TemporaryDirectory() as tmp:
            probe = R.run_products(Path(tmp) / "probe", cards=[("Телевизоры", "QE48S85HAEXCE")])
            official = next(f for f in jobs.get_facts(probe["database"], probe["outcomes"][0]["product_id"]) if f["source_key"] == "samsung" and f["raw_value"].strip())
            run, product_id = self.run_with(Path(tmp) / "dealer", "model_and_code_confirmed", [RawAttribute("Особенность только у дилера", "да, есть"), RawAttribute(official["raw_name"], official["raw_value"] + " и ещё что-то")])
            payload = card_evidence.load(run["database"], product_id, "dealer")
            self.assertEqual([a["field"] for a in payload["added_fields"]], ["особенность_только_у_дилера"])
            self.assertEqual(payload["added_fields"][0]["source"], "dns")
            self.assertEqual([d["field"] for d in payload["disputes"]], [official["normalized_name"]])
            resolved = {r["normalized_name"]: r for r in jobs.get_resolved(run["database"], product_id)}
            self.assertEqual(resolved[official["normalized_name"]]["selected_value"], official["normalized_value"])      # the official value stays
            self.assertEqual(resolved[official["normalized_name"]]["selected_source"], "samsung")
            self.assertEqual(resolved["особенность_только_у_дилера"]["selected_source"], "dns")
            self.assertEqual(resolved["особенность_только_у_дилера"]["status"], "needs_review")                        # never silently trusted
            self.assertEqual(run["outcomes"][0]["status"], "needs_review")
            r = samsung_readiness.card_readiness(run["database"], product_id)
            self.assertIn("dealer_dispute", r["blocking_gaps"])
            self.assertIn("dealer_dispute", r["open_reviews"])
            self.assertEqual(r["dealer_confirmed"], ["dns"])
            self.assertNotIn("dealer_cross_check_missing", r["advisory_gaps"])

    def test_a_dealer_page_that_is_not_an_exact_match_adds_nothing(self):
        with TemporaryDirectory() as tmp:
            run, product_id = self.run_with(tmp, "model_confirmed", [RawAttribute("Особенность только у дилера", "да, есть")])
            self.assertEqual([f for f in jobs.get_facts(run["database"], product_id) if f["source_key"] == "dns"], [])
            self.assertEqual(card_evidence.load(run["database"], product_id, "dealer")["added_fields"], [])
            self.assertIn("Значения дилера не используются", self.dealer_source(run, product_id)["evidence"])
            self.assertEqual(run["outcomes"][0]["status"], "done")

    def dealer_source(self, run, product_id):
        return next(s for s in jobs.get_source_pages(run["database"], product_id) if s["source_key"] == "dns")


class DisplayAndNormalization(unittest.TestCase):
    def test_labels_name_samsung_not_lg(self):
        self.assertEqual(display.display_source("samsung"), "Samsung Казахстан")
        self.assertIn("Samsung", display.display_status("official_base_only", "samsung"))
        self.assertEqual(display.display_status("official_base_only", "lg_kz"), "Найдено только у базовой модели LG")
        self.assertEqual(display.display_status("official_base_only"), "Найдено только у базовой модели LG")

    def test_samsung_wording_that_named_other_quantities_no_longer_shares_one_name(self):
        # the collisions the eleven cards showed: phone (display size vs product size), microwave (turntable vs product), monitor (screen class vs the "image size" mode)
        self.assertEqual(len({normalize_name(n) for n in ("Размер (Основной Дисплей)", "Размеры (В x Ш x Г, мм)")}), 2)
        self.assertEqual(len({normalize_name(n) for n in ("Размеры вращающегося столика", "Размеры изделия (ШxВxГ)")}), 2)
        self.assertEqual(len({normalize_name(n) for n in ("Размер экрана (класс)", "Размер изображения")}), 2)
        self.assertEqual(normalize_name("Размер (Основной Дисплей)"), normalize_name("Размер экрана (класс)"))           # the same quantity on two pages still shares one name
        self.assertEqual(len({normalize_name(n) for n in ("Глубина корпуса с дверной ручкой (мм)", "Глубина корпуса без дверной ручки", "Глубина корпуса без дверей", "Глубина упаковки")}), 4)
        self.assertEqual(normalize_name("Глубина корпуса с дверной ручкой (мм) (Обзор)"), normalize_name("Глубина корпуса с дверной ручкой (мм) (Физические характеристики)"))
        self.assertNotEqual(normalize_name("Высота корпуса с учетом петель"), normalize_name("Высота корпуса без учета петель"))

    def test_names_that_were_already_package_quantities_keep_their_name(self):
        self.assertEqual(normalize_name("Вес упаковки"), "package_weight")
        self.assertEqual(normalize_name("Размеры упаковки"), "package_dimensions")
        self.assertEqual(normalize_name("Ширина"), "product_dimensions__width")


if __name__ == "__main__":
    unittest.main()
