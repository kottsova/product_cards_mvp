"""Stage 21: D2 (job status vs card readiness), D3 (different quantities keep different names, real conflicts stay),
D4 (base-model search rule never raises a match to an exact variant), D1/D5 (RU pages come from the observed RU sitemap).

Offline. The real pages are the ones the Stage 20 pilot saved.
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup

from product_tool import jobs, readiness, worker
from product_tool.adapters.common import PhotoCandidate, ProductDocument, RawAttribute, SourceDocument
from product_tool.adapters.lg import LG_KZ_SITEMAP, LG_RU_SITEMAP, LGAdapter, LGRUAdapter, lg_base_model, normalize_lg_sku
from product_tool.normalization import normalize_fact, normalize_name

from coverage_controls import FixtureSession
from test_lg_workflow import StaticAdapter, seed_product, source

ROOT = Path(__file__).resolve().parents[1]
S20 = ROOT / "reports/source_census_2026-09-24_stage20"
S21 = ROOT / "reports/source_census_2026-09-24_stage21"


def fact(name, value):
    return normalize_fact(RawAttribute(name, value))


def run_job(database, official, *, supplier=None, docs=None, photos=True, stages=(1, 3, 4, 6), sku="S3WER.ALWPCOM"):
    product = seed_product(database, sku=sku)
    jobs.enqueue(database, product, list(stages))
    lg = StaticAdapter(official)
    sulpak = StaticAdapter(supplier or SourceDocument("sulpak", "Sulpak", "", match_level="unknown", evidence="Для полного артикула нет ограниченного кандидата Sulpak."))
    worker.run_once(database, lambda: (lg, sulpak), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
    return product, jobs.list_jobs(database, product)[0]


class _NoDealer:
    source_key, site_name, document_urls = "dns", "DNS", {}

    def find_source(self, *a, **k):
        return SourceDocument("dns", "DNS", "", match_level="unknown")

    def find_documents(self, *a, **k):
        return [], "-"


def official_doc(match="full_sku", key="lg_kz", facts=(("Цвет", "Белый"),), photos=True):
    doc = source(key, match, list(facts), site_name="LG Казахстан")
    doc.match_level = match
    if photos:
        doc.photo_candidates = [PhotoCandidate(f"https://www.lg.com/img/{i}.jpg", f"k{i}", "product_gallery") for i in range(3)]
        doc.photos = [c.url for c in doc.photo_candidates]
    return doc


class D2DoneIsNotReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / "batches.sqlite3"

    def test_official_full_sku_page_without_conflict_is_done_without_a_supplier(self):
        product, job = run_job(self.database, official_doc())
        self.assertEqual(job["status"], "done")
        card = readiness.card_readiness(self.database, product)
        self.assertEqual(card["verdict"], "export_ready_with_gaps")  # done does not hide the gaps
        self.assertEqual(set(card["blocking_gaps"]), {"instruction_missing"})
        self.assertEqual(card["advisory_gaps"], ["dealer_cross_check_missing"])
        self.assertIn("Готовность карточки к выгрузке: export_ready_with_gaps", job["message"])
        self.assertIn("instruction_missing", job["message"])
        self.assertIn("dealer_cross_check_missing", job["message"])
        events = [e["message"] for e in jobs.list_events(self.database, job["id"])]
        self.assertTrue(any("Готовность карточки к выгрузке" in m for m in events))

    def test_base_model_page_alone_is_not_done(self):
        product, job = run_job(self.database, official_doc(match="base_model"))
        self.assertEqual(job["status"], "needs_review")
        self.assertIn("no_official_full_sku_page", readiness.card_readiness(self.database, product)["blocking_gaps"])

    def test_a_real_conflict_still_blocks_done(self):
        doc = official_doc(facts=(("Цвет", "Белый"),))
        ru = source("lg_ru", "full_sku", [("Цвет", "Чёрный")], site_name="LG Россия")
        product = seed_product(self.database)
        jobs.enqueue(self.database, product, [1, 3, 4])
        worker.run_once(self.database, lambda: (StaticAdapter(doc), StaticAdapter(ru), StaticAdapter(SourceDocument("sulpak", "Sulpak", "", match_level="unknown"))), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
        job = jobs.list_jobs(self.database, product)[0]
        self.assertEqual(job["status"], "needs_review")
        card = readiness.card_readiness(self.database, product)
        self.assertEqual(card["real_conflicts"], 1)
        self.assertIn("unresolved_conflicts", card["blocking_gaps"])

    def test_a_supplier_confirmed_full_article_next_to_an_official_base_page_is_still_done(self):
        product, job = run_job(self.database, official_doc(match="base_model"), supplier=source("sulpak", "full_sku", [("Цвет", "Белый")]))
        self.assertEqual(job["status"], "done")

    def test_instruction_language_and_dealer_confirmation_are_separate_gaps(self):
        product = seed_product(self.database)
        jobs.enqueue(self.database, product, [1, 3, 4])
        ru = SourceDocument("lg_ru", "LG Россия", "https://www.lg.com/ru/x/lg-s3wer", match_level="unknown")
        worker.run_once(self.database, lambda: (StaticAdapter(official_doc()), StaticAdapter(ru), StaticAdapter(source("sulpak", "full_sku", [("Цвет", "Белый")]))), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
        jobs.save_documents(self.database, product, "lg_ru", [ProductDocument("Manual", "English", "", "", "https://x/d.pdf", "https://x", "S3WER", "S3RERB", "https://x")])
        card = readiness.card_readiness(self.database, product)
        self.assertEqual((card["verdict"], card["blocking_gaps"], card["advisory_gaps"]), ("export_ready_with_gaps", ["instruction_language_not_russian"], []))
        jobs.save_documents(self.database, product, "lg_ru", [ProductDocument("Руководство", "Русский", "", "", "https://x/d.pdf", "https://x", "S3WER", "S3RERB", "https://x")])
        card = readiness.card_readiness(self.database, product)
        self.assertEqual((card["verdict"], card["blocking_gaps"], card["advisory_gaps"]),
                         ("export_ready_with_gaps", ["instruction_variant_link_unconfirmed"], []))
        support_url = "https://www.lg.com/ru/support/product/lg-S3WER.ALWPCOM"
        jobs.save_source_document(self.database, product,
            SourceDocument("lg_ru_support", "LG RU support", support_url,
                           found_model="S3WER.ALWPCOM", match_level="full_sku",
                           html='<div data-product-id="S3WER.ALWPCOM"></div>'),
            update_attributes=False, update_photos=False)
        jobs.save_documents(self.database, product, "lg_ru", [ProductDocument(
            "Russian manual", "Русский", "", "", "https://x/d.pdf", support_url,
            "S3WER", "S3WER.ALWPCOM", "https://x")])
        card = readiness.card_readiness(self.database, product)
        self.assertEqual((card["verdict"], card["blocking_gaps"], card["advisory_gaps"]), ("export_ready", [], []))

    def test_no_official_data_is_not_ready(self):
        product, job = run_job(self.database, official_doc(facts=(), photos=False))
        card = readiness.card_readiness(self.database, product)
        self.assertEqual(card["verdict"], "not_ready")
        self.assertEqual(job["status"], "done")  # the status rule is the owner's; readiness says what is missing
        self.assertIn("no_official_specifications", card["blocking_gaps"])
        self.assertIn("no_official_gallery_photo", card["blocking_gaps"])


class D3DifferentQuantitiesKeepDifferentNames(unittest.TestCase):
    PAIRS = [
        ("Вес телевизора без подставки", "Вес телевизора с подставкой"), ("Вес брутто", "Вес нетто"), ("Вес внутреннего блока (кг)", "Вес наружного блока (кг)"),
        ("Размеры внутреннего блока_ШxВxГ (мм)", "Размеры наружного блока_ШxВxГ (мм)"), ("Цвет дверцы", "Цвет корпуса"), ("Цвет корпуса", "Цвет внутри"),
        ("Масса (кг)", "Макс. вес белья для стирки (кг)"), ("Размеры ящика (ШxВxГ мм)", "Размеры продукта (ШxВxГ мм)"),
        ("Габариты внутреннего пространства (Ш x В x Г) (мм)", "Габариты продукта (Ш x В x Г) (мм)"), ("Размер поворотного стола (мм)", "Габариты продукта (Ш x В x Г) (мм)"),
        ("Сабвуфер, размер (Ш × В × Г, мм)", "Основной модуль, размер (Ш × В × Г, мм)"),
    ]

    def test_each_pair_of_different_quantities_gets_two_names(self):
        for a, b in self.PAIRS:
            self.assertNotEqual(normalize_name(a), normalize_name(b), (a, b))

    def test_the_same_quantity_in_two_regions_keeps_one_name(self):
        self.assertEqual(normalize_name("Вес (кг)"), normalize_name("Масса"))
        self.assertEqual(normalize_name("Вес телевизора без подставки"), normalize_name("Вес без подставки (кг)"))
        self.assertEqual(normalize_name("Цвет"), "color")
        self.assertEqual(fact("Размеры (ШхВхГ)", "600 x 850 x 440 мм").normalized_name, fact("Габариты", "600 × 850 × 440").normalized_name)

    def test_a_part_named_row_with_a_size_and_a_weight_is_two_quantities(self):
        self.assertNotEqual(fact("Главный", "890 x 57 x 85 mm").normalized_name, fact("Главный", "2.1 kg").normalized_name)
        self.assertEqual(fact("Мощность", "1200 Вт").normalized_name, "мощность")  # an ordinary unmapped name is untouched

    def test_values_are_still_parsed_by_the_quantity(self):
        self.assertEqual(fact("Размеры телевизора с подставкой (ШхВхГ)", "1123 x 721 x 260").normalized_value, "w=1123;h=721;d=260")
        self.assertEqual((fact("Вес брутто", "18.5 kg").normalized_value, fact("Вес брутто", "18.5 kg").unit), ("18.5", "kg"))

    def conflicts(self, kz_facts, ru_facts=()):
        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "b.sqlite3"
            product = seed_product(database)
            jobs.enqueue(database, product, [1, 3])
            kz = source("lg_kz", "full_sku", list(kz_facts), site_name="LG Казахстан")
            ru = source("lg_ru", "full_sku", list(ru_facts), site_name="LG Россия")
            worker.run_once(database, lambda: (StaticAdapter(kz), StaticAdapter(ru), StaticAdapter(SourceDocument("sulpak", "Sulpak", "", match_level="unknown"))), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
            return [r["normalized_name"] for r in jobs.get_resolved(database, product) if r["conflict"]]

    def test_different_quantities_in_one_source_are_no_conflict(self):
        self.assertEqual(self.conflicts([("Вес телевизора без подставки", "13.0"), ("Вес телевизора с подставкой", "16.8"), ("Вес брутто", "18.5 kg"), ("Вес нетто", "15.5 kg"),
                                         ("Цвет дверцы", "Черный"), ("Цвет внутри", "Серый")]), [])

    def test_a_real_conflict_between_two_values_of_the_same_quantity_stays_in_one_source(self):
        self.assertEqual(self.conflicts([("Масса (кг)", "56"), ("Масса (кг)", "57")]), ["product_weight"])
        self.assertEqual(self.conflicts([("Вес телевизора с подставкой", "16.8"), ("Вес телевизора с подставкой", "17.4")]), ["product_weight__with_stand"])

    def test_a_real_conflict_between_regions_stays(self):
        self.assertEqual(self.conflicts([("Вес (кг)", "13")], [("Масса", "14")]), ["product_weight"])
        self.assertEqual(self.conflicts([("Вес нетто", "15.5 kg")], [("Вес нетто (кг)", "16 kg")]), ["product_weight__net"])
        self.assertEqual(self.conflicts([("Вес нетто", "15.5 kg")], [("Вес нетто (кг)", "15.5 kg")]), [])

    def test_an_unrecognised_qualifier_still_ends_in_a_conflict_not_a_merge(self):
        self.assertEqual(self.conflicts([("Вес изделия в кофре", "20"), ("Вес изделия", "10")]), ["product_weight"])


class D3FormattingIsNotAConflictButValuesAre(unittest.TestCase):
    """The comparison key forgives formatting only; a different colour, size or wording of a fact stays on review."""
    conflicts = D3DifferentQuantitiesKeepDifferentNames.conflicts

    def test_the_same_value_written_two_ways_is_no_conflict(self):
        for name_a, value_a, name_b, value_b in [
            ("Диагональ [дюймы]", "23.8", "Размер диагонали (дюймы)", '23.8"'), ("Шаг Пикселя [мм]", "0.2745 x 0.2745", "Шаг пикселя (мм)", "0.2745 x 0.2745 мм"),
            ("Угол Обзора (CR≥10)", "178º(r/l), 178º(u/d)", "Угол обзора (CR≥10)", "178º(п/л), 178º(в/н)"), ("Энергопотребление (Режим Сна)", "менее 0.5 Вт", "Энергопотребление (режим сна)", "меньше 0.5 Вт"),
            ("Разрешение", "3,840 x 2,160", "Разрешение", "3840 x 2160"), ("Частота", "60Гц", "Частота", "60 Гц"), ("Количество", "1шт", "Количество", "1 шт.")]:
            self.assertEqual(self.conflicts([(name_a, value_a)], [(name_b, value_b)]), [], (name_a, value_a, value_b))

    def test_real_differences_seen_on_the_pilot_pages_stay_conflicts(self):
        for name, a, b in [("Цвет корпуса", "платиновое серебро", "темно-серебристый"), ("Пульт Magic Remote", "в комплекте", "встроенный"), ("Тип установки", "настольная", "отдельно стоящая"),
                           ("Глубина (мм)", "660", "690"), ("Диагональ [дюймы]", "23.8", "27"), ("Частота", "60 Гц", "120 Гц")]:
            self.assertEqual(len(self.conflicts([(name, a)], [(name, b)])), 1, (name, a, b))

    def test_a_dash_placeholder_is_not_a_value_and_cannot_conflict(self):
        self.assertEqual(self.conflicts([("Мощность", "1200 Вт")], [("Мощность", "-")]), [])
        self.assertEqual(self.conflicts([("Мощность", "1200 Вт")], [("Мощность", "—")]), [])

    def test_name_rules_are_anchored_to_the_start_of_the_name(self):
        self.assertEqual(normalize_name("Цвета Бит"), "цвета_бит")
        self.assertEqual(normalize_name("Глубина Цвета"), "глубина_цвета")
        self.assertEqual(normalize_name("Макс. время работы"), "макс_время_работы")
        self.assertEqual(normalize_name("Цвет"), "color")
        self.assertNotEqual(normalize_name("Макс. вес белья для стирки (кг)"), normalize_name("Макс. вес белья для сушки (кг)"))

    def test_the_replay_of_the_twelve_rows_separates_status_from_readiness(self):
        rows = {r["seller_sku"]: r for r in json.loads((S21 / "raw/replay_phase2.json").read_text(encoding="utf-8"))["rows"]}
        self.assertEqual(len(rows), 12)
        a9n = rows["A9N-MASTERX"]
        self.assertEqual((a9n["job_status"], a9n["readiness"]["verdict"]), ("done", "not_ready"))
        self.assertIn("no_official_gallery_photo", a9n["readiness"]["gaps"])
        for sku, row in rows.items():
            self.assertIn("instruction_missing", row["readiness"]["gaps"], sku)
            if row["job_status"] == "done":
                self.assertEqual(row["real_conflicts"], [], sku)
            if row["real_conflicts"]:
                self.assertEqual(row["job_status"], "needs_review", sku)
                self.assertIn("unresolved_conflicts", row["readiness"]["gaps"], sku)
        for sku in ("24MR400-B.ARUQ", "27MD5KL-B.AEU"):
            self.assertEqual(rows[sku]["job_status"], "needs_review", sku)
            self.assertIn("no_official_full_sku_page", rows[sku]["readiness"]["gaps"], sku)


def recorded_pilot():
    index = [json.loads(line) for line in (S20 / "pilot/responses/index.jsonl").read_text(encoding="utf-8").splitlines()]
    return {e["url"]: (e["status"], gz(S20 / "pilot/responses" / e["saved_as"]) if e["saved_as"] else "") for e in index}


def gz(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


class D3OnTheSavedPilotPages(unittest.TestCase):
    """The 13 false conflicts of the Stage 20 pilot came from these pages; the 9 exact rows are re-read here."""

    @classmethod
    def setUpClass(cls):
        cls.pages = recorded_pilot()
        cls.rows = json.loads((S20 / "raw/pilot_selection.json").read_text(encoding="utf-8"))["rows"]

    def facts_of(self, sku):
        session = FixtureSession(self.pages)
        doc = LGAdapter(session, clock=lambda: 0.0).find_source(sku, deadline=1e9)
        return doc, [normalize_fact(a) for a in doc.attributes]

    def test_no_name_carries_two_different_values_on_any_pilot_page(self):
        checked = 0
        for row in self.rows:
            if row["seller_sku"] in {"24MR400-B.ARUQ", "A9N-MASTERX", "27MD5KL-B.AEU"}:
                continue
            doc, facts = self.facts_of(row["seller_sku"])
            self.assertEqual(doc.match_level, "full_sku", row["seller_sku"])
            groups = {}
            for f in facts:
                groups.setdefault(f.normalized_name, set()).add((f.normalized_value, f.unit))
            clashes = {name: values for name, values in groups.items() if len(values) > 1}
            self.assertEqual(clashes, {}, row["seller_sku"])
            checked += 1
        self.assertEqual(checked, 9)

    def test_the_same_pages_did_conflict_before_the_fix(self):
        before = json.loads((S20 / "raw/conflicts_within_source.json").read_text(encoding="utf-8"))
        self.assertEqual((before["conflicts"], before["within_one_source"], before["rows_with_conflicts"]), (13, 13, 8))


class D4BaseModelSearch(unittest.TestCase):
    def test_short_and_long_regional_suffixes_are_stripped_and_others_are_not(self):
        table = {"24MR400-B.ARUQ": "24MR400-B", "27MD5KL-B.AEU": "27MD5KL-B", "S3WER.ALWPCOM": "S3WER", "OLED65C3RLA.AMAE": "OLED65C3RLA",
                 "43UR78006LK.ADGG": "43UR78006LK", "XX100.AB": "XX100.AB", "ABC.1234": "ABC.1234", "F2J3WS1W": "F2J3WS1W", "MS2032GAS": "MS2032GAS"}
        for full, base in table.items():
            self.assertEqual(lg_base_model(full), base, full)

    def kz_pages(self, page_text, slug="xx100"):
        url = f"https://www.lg.com/kz/monitors/{slug}/"
        html = f"<html><body><h1>LG {page_text}</h1><section id='pdp-overview-section'><p>{page_text}</p></section><section id='pdp-specs-section'></section></body></html>"
        sitemap = f"<urlset><url><loc>{url}</loc></url></urlset>"
        return FixtureSession({LG_KZ_SITEMAP: (200, sitemap), url: (200, html)})

    def test_a_base_code_hit_is_a_base_model_match_never_an_exact_variant(self):
        session = self.kz_pages("Монитор XX100")
        doc = LGAdapter(session, clock=lambda: 0.0).find_source("XX100.ARUQ", deadline=1e9)
        self.assertEqual((doc.match_level, doc.found_model), ("base_model", "XX100"))
        self.assertEqual(session.calls[-1], "https://www.lg.com/kz/monitors/xx100/")

    def test_the_page_must_show_the_full_article_to_be_exact(self):
        doc = LGAdapter(self.kz_pages("Монитор XX100.ARUQ"), clock=lambda: 0.0).find_source("XX100.ARUQ", deadline=1e9)
        self.assertEqual(doc.match_level, "full_sku")

    def test_a_suffix_that_distinguishes_variants_does_not_borrow_the_other_variants_confirmation(self):
        session = self.kz_pages("Монитор XX100.AAAA")  # the family page lists only the AAAA variant
        adapter = LGAdapter(session, clock=lambda: 0.0)
        self.assertEqual(adapter.find_source("XX100.AAAA", deadline=1e9).match_level, "full_sku")
        self.assertEqual(adapter.find_source("XX100.BBBB", deadline=1e9).match_level, "base_model")

    def test_a_base_model_match_alone_leaves_the_job_in_review(self):
        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "b.sqlite3"
            product = seed_product(database, sku="XX100.ARUQ")
            jobs.enqueue(database, product, [1, 3])
            doc = LGAdapter(self.kz_pages("Монитор XX100"), clock=lambda: 0.0).find_source("XX100.ARUQ", deadline=1e9)
            worker.run_once(database, lambda: (StaticAdapter(doc), StaticAdapter(SourceDocument("lg_ru", "LG Россия", "", match_level="mismatch")), StaticAdapter(SourceDocument("sulpak", "Sulpak", "", match_level="unknown"))),
                            clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
            self.assertEqual(jobs.list_jobs(database, product)[0]["status"], "needs_review")

    def test_on_the_saved_kz_sitemap_the_rule_reaches_exactly_the_estimated_rows(self):
        estimate = json.loads((S20 / "raw/estimate_578.json").read_text(encoding="utf-8"))
        self.assertEqual((estimate["reachable_by_the_current_rule"], estimate["reachable_with_a_3plus_letter_suffix_rule"], estimate["gain_of_the_suffix_correction"]), (426, 465, 39))
        pages = recorded_pilot()
        session = FixtureSession(pages)
        adapter = LGAdapter(session, clock=lambda: 0.0)
        urls = adapter.sitemap_product_urls(1e9)
        self.assertTrue(any(u.endswith("/24mr400-b/") for u in urls))
        # what the adapter would request for the monitor of the pilot is the observed sitemap URL, not a built one
        try:
            adapter.find_source("24MR400-B.ARUQ", deadline=1e9)
        except Exception:
            pass
        self.assertIn("https://www.lg.com/kz/monitors/fhd-qhd/24mr400-b/", session.calls + session.refused)


class D1RuPagesComeFromTheObservedSitemap(unittest.TestCase):
    RU_MAP = ("<urlset><url><loc>https://www.lg.com/ru/audio/lg-xl7s</loc></url><url><loc>https://www.lg.com/ru/about-lg/press-and-media/lg-2020-sounbars-in-russia</loc></url></urlset>")

    def page(self, model="XL7S"):
        return f"<html><body><h1>{model}</h1><div id='overview'><div class='text-block'><div class='title'><h2>Звук</h2></div><p class='copy'>{model} " + "описание " * 8 + "</p></div></div><div id='pdp_spec'></div></body></html>"

    def test_the_url_is_taken_from_the_sitemap_and_nothing_else_is_requested(self):
        session = FixtureSession({LG_RU_SITEMAP: (200, self.RU_MAP), "https://www.lg.com/ru/audio/lg-xl7s": (200, self.page())})
        doc = LGRUAdapter(session, clock=lambda: 0.0).find_source("XL7S", deadline=1e9)
        self.assertEqual((doc.match_level, doc.url, doc.error), ("full_sku", "https://www.lg.com/ru/audio/lg-xl7s", ""))
        self.assertEqual(session.calls, [LG_RU_SITEMAP, "https://www.lg.com/ru/audio/lg-xl7s"])

    def test_a_row_absent_from_the_sitemap_is_a_miss_and_no_url_is_built(self):
        session = FixtureSession({LG_RU_SITEMAP: (200, self.RU_MAP)})
        doc = LGRUAdapter(session, clock=lambda: 0.0).find_source("XL9Z", deadline=1e9)
        self.assertEqual((doc.match_level, doc.url, doc.error), ("mismatch", "", ""))
        self.assertEqual(session.calls, [LG_RU_SITEMAP])
        self.assertNotIn("laundry", "".join(session.calls))

    def test_the_legacy_constructed_pattern_is_never_requested(self):
        source_text = (ROOT / "product_tool/adapters/lg.py").read_text(encoding="utf-8")
        self.assertNotIn("LG_RU_PRODUCT.format", source_text)

    def test_the_saved_ru_sitemap_and_page_match_what_the_probe_found(self):
        result = json.loads((S21 / "raw/probe_result_2.json").read_text(encoding="utf-8"))
        self.assertEqual(result["requests_in_total_with_r1"], 3)
        self.assertEqual(len(result["analysis"]["r2"]["pilot_rows_matched"]), 11)
        index = [json.loads(line) for line in (S21 / "probe/responses/index.jsonl").read_text(encoding="utf-8").splitlines()]
        pages = {e["url"]: (e["status"], gz(S21 / "probe/responses" / e["saved_as"])) for e in index if e["saved_as"]}
        session = FixtureSession(pages)
        doc = LGRUAdapter(session, clock=lambda: 0.0).find_source("XL7S", deadline=1e9)
        self.assertEqual((doc.match_level, doc.url), ("full_sku", "https://www.lg.com/ru/audio/lg-xl7s"))
        self.assertGreater(len(doc.attributes), 5)


if __name__ == "__main__":
    unittest.main()
