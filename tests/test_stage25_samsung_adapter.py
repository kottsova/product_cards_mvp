"""Stage 25: the limited Samsung adapter (adapters/samsung.py), tested on the SAVED official pages of Stage 24 batch 1/1b and Stage 25 batch 2 (offline).

Facts kept apart: identity level; specification table; photos (no size duplicates, no thumbnails, no 3D files); document links; and, for a document, three separate facts --
Russian by the text / tied to the product by the official page / the exact model named inside. No general SC = VC (or LS = S) code equality is assumed.
"""
from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path

import requests

from product_tool.adapters import samsung as S
from product_tool.adapters.dns import DnsAdapter

ROOT = Path(__file__).resolve().parents[1]
S24 = ROOT / "reports/source_census_2026-09-25_stage24"
S25 = ROOT / "reports/source_census_2026-09-25_stage25"


def index(directory: Path):
    result = {}
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        entry["dir"] = directory
        result[entry["url"]] = entry
    return result


ALL = {**index(S24 / "batch1/responses"), **index(S24 / "batch1b/responses"), **index(S25 / "batch2/responses")}
EXTRACT = {r["url"]: r for r in json.loads((S24 / "docs_extract/index.json").read_text(encoding="utf-8")) if r.get("text_file")}


def html(fragment: str) -> tuple[str, str]:
    url = next(u for u in ALL if fragment in u and u.startswith("https://www.samsung.com/kz_ru") and ALL[u]["saved_as"])
    entry = ALL[url]
    with gzip.open(entry["dir"] / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
        return url, handle.read()


def text_pages(fragment: str) -> list[str]:
    url = next(u for u in EXTRACT if fragment in u)
    with gzip.open(S24 / "docs_extract" / EXTRACT[url]["text_file"], "rt", encoding="utf-8") as handle:
        return handle.read().split("\n\f\n")


CASES = {
    "tv": ("qe48s85haexce/", "QE48S85HAEXCE"), "vacuum": ("vc18m21d0vg-ev/", "VC18M21D0VG/EV"), "washer": ("wd10t754cbx-ld/", "WD10T754CBX/LD"), "a37": ("a376edggskz/", "SM-A376EZAGINS"),
    "fridge": ("rb31ferndsa-wt/", "RB31FERNDSA"), "oven": ("nv7000b-4series-single-fan-4series-single-fan-nv7b4120zas-wt/", "NV7B4120ZAS/WT"), "hob": ("hob-nz64t3506ak-wt/", "NZ64T3506AK/WT"),
    "monitor": ("ls24d300gaixci/", "LS24D300GAIXCI"), "soundbar": ("q800d-black-hw-q800d-ru/", "HW-Q800D"), "microwave": ("ms23k3614akbw/", "MS23K3614AK/BW"),
}


def card(name):
    fragment, article = CASES[name]
    url, page = html(fragment)
    return S.parse_product_page(page, url, article)


class SpecificationTable(unittest.TestCase):
    def test_the_table_is_in_the_static_html_and_read_group_by_group(self):
        expected = {"tv": (117, 16), "vacuum": (28, 10), "washer": (85, 10), "a37": (64, 15), "fridge": (55, 10), "monitor": (64, 13), "microwave": (59, 10)}
        for name, (items, groups) in expected.items():
            c = card(name)
            self.assertEqual((len(c.specs), len({i.group for i in c.specs})), (items, groups), name)
        tv = card("tv")
        self.assertIn(("Дисплей", "Размер экрана", '48"'), [(i.group, i.name, i.value) for i in tv.specs])
        self.assertIn(("Тип продукта", "Тип продукта", "OLED"), [(i.group, i.name, i.value) for i in tv.specs])  # an item without a title carries its group's value

    def test_the_family_marketing_page_has_no_table_and_is_not_a_product_page(self):
        url, page = html("galaxy-s25-ultra/")
        c = S.parse_product_page(page, url, "SM-S938BZKBSKZ")
        self.assertEqual((c.identity.is_product_page, c.identity.level, len(c.specs), len(c.photos.photos)), (False, "unknown", 0, 0))
        self.assertIn("характеристики", c.missing_fields)

    def test_pipeline_rows_repeat_a_name_with_its_group_and_never_invent_a_value(self):
        attributes = S.spec_attributes(card("vacuum").specs)
        names = [a.name for a in attributes]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("Вес", names)
        self.assertNotIn("", [a.value for a in attributes])


class Photos(unittest.TestCase):
    def test_one_asset_once_no_thumbnails_no_3d(self):
        for name, photos in {"tv": 8, "vacuum": 15, "washer": 11, "fridge": 9, "oven": 8, "monitor": 11, "soundbar": 17, "microwave": 11}.items():
            p = card(name).photos
            self.assertEqual(len(p.photos), photos, name)
            self.assertEqual(len({x.asset_key for x in p.photos}), photos, name)  # a size variant is not a second photo
            for x in p.photos:
                self.assertNotIn("-thumb-", x.url)
                self.assertNotRegex(x.url, r"104_104|\.glb|\.usdz")
                self.assertEqual(x.kind, "product_gallery")
            self.assertEqual(len(p.thumbnails), photos, name)  # every full-size photo has its own thumbnail: the gallery is complete

    def test_the_largest_size_of_each_asset_is_kept(self):
        for x in card("tv").photos.photos:
            self.assertEqual(x.width, 2052, x.url)

    def test_the_tv_3d_model_is_not_a_photo(self):
        p = card("tv").photos
        self.assertFalse(any(x.url.endswith((".glb", ".usdz")) for x in p.photos))

    def test_the_phone_product_page_has_no_gallery_only_a_thumbnail_named_candidate(self):
        p = card("a37").photos
        self.assertEqual((len(p.photos), len(p.candidate_thumbnail_only)), (0, 1))
        self.assertTrue(p.gap)
        self.assertIn("фото", card("a37").missing_fields)

    def test_the_phone_buy_page_carries_the_gallery(self):
        url, page = html("a376edggskz/buy/")
        c = S.parse_product_page(page, url, "SM-A376EZAGINS")
        self.assertEqual((len(c.photos.photos), len(c.specs)), (9, 0))


class ExactVariantByContent(unittest.TestCase):
    def test_exact_articles_are_confirmed_by_page_content(self):
        for name in ("tv", "vacuum", "washer", "oven", "monitor", "soundbar", "microwave"):
            c = card(name)
            self.assertEqual((c.identity.level, c.identity.evidence_strength), ("full_sku", "strong"), name)
            self.assertNotIn("url_only_not_counted", [e for e in c.identity.evidence if e not in ("url_only_not_counted",)])

    def test_a_code_only_in_the_visible_text_is_marked_as_weaker(self):
        self.assertEqual((card("fridge").identity.level, card("fridge").identity.evidence_strength), ("full_sku", "text_only"))
        # Stage 30 (owner decision): the hob's page also declares exactly its catalog code in its own product data (modelCode/shopSKU), which is strong evidence; the fridge's data says RB31FERNDSA/WT
        self.assertEqual((card("hob").identity.level, card("hob").identity.evidence_strength), ("full_sku", "strong"))
        self.assertIn("product_data_code", card("hob").identity.evidence)

    def test_the_address_alone_never_confirms(self):
        page = "<html><head><title>Смартфон</title></head><body><p>нет кода</p></body></html>"
        identity = S.extract_identity(page, "https://www.samsung.com/kz_ru/x/abc-qe48s85haexce/", "QE48S85HAEXCE")
        self.assertEqual(identity.level, "unknown")
        self.assertIn("url_only_not_counted", identity.evidence)

    def test_regional_codes_stay_open_on_the_phone(self):
        identity = card("a37").identity
        self.assertEqual(identity.level, "base_model")
        self.assertEqual(identity.jsonld_sku, "SM-A376EDGGSKZ")
        self.assertTrue(any("региональный код: каталог INS, страница SKZ" in d for d in identity.open_differences))
        self.assertTrue(any("код цвета: каталог ZA, страница DG" in d for d in identity.open_differences))
        self.assertFalse(any("память" in d for d in identity.open_differences))  # the memory code G is the same
        self.assertEqual(S.sm_code_parts("SM-A376EZAGINS"), {"base": "SM-A376E", "colour": "ZA", "memory": "G", "region": "INS"})

    def test_the_same_region_and_colour_would_be_exact(self):
        page = '<script type="application/ld+json">{"@type":"Product","name":"Galaxy A37 5G","sku":"SM-A376EDGGSKZ"}</script><title>x</title>'
        self.assertEqual(S.extract_identity(page, "u", "SM-A376EDGGSKZ").level, "full_sku")


class DocumentsThreeSeparateFacts(unittest.TestCase):
    def test_the_tv_russian_and_tied_by_the_page_but_no_model_named_inside(self):
        c = card("tv")
        link = next(x for x in c.documents if x.language_hint == "RU")
        facts = S.assess_samsung_document(text_pages("RUS_260828"), "QE48S85HAEXCE", link.model_name, c.identity.level)
        self.assertEqual(link.model_name, "QE48S85HAE")
        self.assertTrue(facts["russian_by_text"])
        self.assertEqual(facts["tied_by_official_page"], "exact_page")
        self.assertEqual((facts["names_catalog_model"]["exact"], facts["names_catalog_model"]["family_mask"]), (False, []))
        self.assertEqual((facts["names_link_model"]["exact"], facts["names_link_model"]["family_mask"]), (False, []))
        self.assertEqual(S.rule4_analog(facts), "accepted_tied_by_page_not_by_text")

    def test_the_vacuum_names_the_model_its_link_declares_not_the_catalog_model(self):
        c = card("vacuum")
        ru = next(x for x in c.documents if x.language_hint == "RU")
        facts = S.assess_samsung_document(text_pages("_RU_251001"), "VC18M21D0VG/EV", ru.model_name, c.identity.level)
        self.assertEqual(ru.model_name, "SC18M21D0VG")
        self.assertTrue(facts["russian_by_text"])
        self.assertEqual(facts["tied_by_official_page"], "exact_page")
        self.assertFalse(facts["names_catalog_model"]["exact"])   # VC18M21D0VG is not in the text ...
        self.assertTrue(facts["names_link_model"]["exact"])        # ... SC18M21D0VG, declared by the page's link, is
        self.assertEqual(S.rule4_analog(facts), "accepted_only_the_model_declared_by_the_pages_link_is_named_in_text")

    def test_the_kazakh_vacuum_file_is_not_russian_by_text(self):
        c = card("vacuum")
        kk = next(x for x in c.documents if x.language_hint == "KK")
        facts = S.assess_samsung_document(text_pages("_KK_251001"), "VC18M21D0VG/EV", kk.model_name, c.identity.level)
        self.assertFalse(facts["russian_by_text"])
        self.assertEqual(facts["languages_by_text"], ["kk"])
        self.assertEqual(S.rule4_analog(facts), "not_accepted")

    def test_sc_and_vc_are_not_declared_equal(self):
        text = ("Руководство пользователя. Меры предосторожности и безопасность. Перед использованием внимательно прочитайте инструкцию. Нажмите кнопку и подключите. " * 40) + " SC18M21D0VG"
        facts = S.assess_samsung_document([text], "VC18M21D0VG/EV", "", "full_sku")
        self.assertFalse(facts["names_catalog_model"]["exact"])
        self.assertEqual(facts["names_link_model"]["exact"], False)  # no link model was given: nothing to compare
        facts = S.assess_samsung_document([text], "VC18M21D0VG/EV", "SC18M21D0VG", "full_sku")
        self.assertEqual((facts["names_catalog_model"]["exact"], facts["names_link_model"]["exact"]), (False, True))

    def test_a_base_model_page_does_not_tie_a_document_exactly(self):
        text = ("Руководство пользователя. Меры предосторожности и безопасность. Перед использованием внимательно прочитайте инструкцию. Нажмите кнопку и подключите. " * 40)
        facts = S.assess_samsung_document([text], "SM-A376EZAGINS", "SM-A376E", "base_model")
        self.assertEqual(facts["tied_by_official_page"], "base_model_page")
        self.assertEqual(S.rule4_analog(facts), "not_accepted")

    def test_a_declaration_is_never_an_instruction(self):
        text = "ДЕКЛАРАЦИЯ О СООТВЕТСТВИИ\n" + "Изделие QE48S85HAE соответствует техническому регламенту. " * 60
        facts = S.assess_samsung_document([text], "QE48S85HAEXCE", "QE48S85HAE", "full_sku")
        self.assertEqual((facts["regulatory"], facts["russian_by_text"]), (True, False))
        self.assertEqual(S.rule4_analog(facts), "not_accepted")

    def test_a_conflicting_model_blocks_acceptance(self):
        text = ("Руководство пользователя. Меры предосторожности и безопасность. Перед использованием внимательно прочитайте инструкцию. Нажмите кнопку и подключите. " * 40) + " NV7B4120ZBS"
        facts = S.assess_samsung_document([text], "NV7B4120ZAS/WT", "", "full_sku")
        self.assertIn("NV7B4120ZBS", facts["conflicting_models"])
        self.assertEqual(S.rule4_analog(facts), "not_accepted")

    def test_positional_masks_name_a_family_and_a_mask_of_stars_names_nothing(self):
        self.assertEqual(S.positional_masks("WD1*T******/WD9*T******", "WD10T754CBX/LD"), ["WD1*T******"])
        self.assertEqual(S.positional_masks("WD9*T******", "WD10T754CBX/LD"), [])
        self.assertEqual(S.positional_masks("***********", "WD10T754CBX"), [])

    def test_a_file_without_extractable_text_is_a_manual_check_not_a_verdict(self):
        pages = ["PNg 16166000A24139"] + [""] * 83  # the hob manual: 80 of 84 pages carry no text
        facts = S.assess_samsung_document(pages, "NZ64T3506AK/WT", "NZ64T3506AK", "full_sku")
        self.assertEqual(facts["content_status"], "text_not_extractable")
        self.assertIsNone(facts["russian_by_text"])
        self.assertEqual(facts["conflicting_models"], [])
        self.assertEqual(S.rule4_analog(facts), "manual_check_text_not_extractable")

    def test_the_file_name_language_is_only_an_ordering_hint(self):
        links = S.extract_document_links(html("wd10t754cbx-ld/")[1], "https://www.samsung.com/kz_ru/x/")
        self.assertEqual([x.language_hint for x in links], ["UZ"])  # the name says UZ; the text is Russian and Kazakh (see the Stage 25 report)
        vacuum = S.order_for_request(card("vacuum").documents)
        self.assertEqual([x.language_hint for x in vacuum], ["RU", "KK"])

    def test_document_links_are_the_pages_own_manual_links_only(self):
        for name in ("tv", "vacuum", "washer", "oven"):
            for link in card(name).documents:
                self.assertIn("CDCttType=UM", link.href)
                self.assertNotIn("Delivery-Service", link.href)
                self.assertTrue(link.model_name)


class FindingThePage(unittest.TestCase):
    def test_hub_links_are_pages_not_images_and_a_neighbouring_model_is_not_a_match(self):
        url = "https://www.samsung.com/kz_ru/tablets/all-tablets/"
        links = S.hub_product_links(html("all-tablets/")[1], url)
        self.assertTrue(links)
        for link in links:
            self.assertNotIn("/gallery/", link)
            self.assertTrue(link.endswith("/"))
        self.assertTrue(any("sm-x406" in link for link in links))          # Galaxy Tab S10 Lite is on the current list ...
        self.assertEqual(S.find_on_hub(links, "SM-X826BZARSKZ"), "")        # ... the catalog's S10+ (SM-X826) is not, and S10 Lite is not a match for it
        self.assertEqual(S.find_on_hub(links, "SM-X926BZARSKZ"), "")

    def test_the_phone_row_is_found_on_the_hub_by_its_base_model_code(self):
        phone_links = []
        for fragment in ("all-smartphones/", "galaxy-a/"):
            url, page = html(fragment)
            phone_links += S.hub_product_links(page, url)
        found = S.find_on_hub(sorted(set(phone_links)), "SM-A376EZAGINS")
        self.assertTrue(found.endswith("sm-a376edggskz/"))

    def test_sitemap_match_uses_the_article_substring_and_builds_nothing(self):
        urls = ["https://www.samsung.com/kz_ru/vacuum-cleaners/canister/canister-2100v-vc18m21d0vg-ev/", "https://www.samsung.com/kz_ru/a/b-other-model/"]
        self.assertEqual(S.find_in_sitemap(urls, "VC18M21D0VG/EV"), urls[0])
        self.assertEqual(S.find_in_sitemap(urls, "NOSUCH123456"), "")


class DealerFallback(unittest.TestCase):
    def test_a_dealer_value_fills_only_a_missing_field_with_its_own_source_and_never_replaces_an_official_one(self):
        official = {"характеристики": "таблица", "фото": "", "инструкция": ""}
        dealer = {"фото": {"value": "dns-photo", "source": "DNS", "exact_model": True, "exact_variant": True},
                  "инструкция": {"value": "dns-manual", "source": "DNS", "exact_model": True, "exact_variant": False},
                  "характеристики": {"value": "другая таблица", "source": "DNS", "exact_model": True, "exact_variant": True}}
        merged = S.merge_dealer_fields(official, dealer)
        self.assertEqual(merged["характеристики"], {"value": "таблица", "source": "official"})
        self.assertEqual(merged["фото"], {"value": "dns-photo", "source": "DNS"})
        self.assertNotIn("инструкция", merged)
        outcomes = {n["field"]: n["outcome"] for n in merged["_notes"]["value"]}
        self.assertIn("not exact model and variant", outcomes["инструкция"])
        self.assertIn("official value kept", outcomes["характеристики"])

    def test_dns_knows_no_samsung_url_so_it_makes_no_request_and_names_what_it_needs(self):
        class Refusing:
            headers: dict = {}
            calls = 0

            def get(self, url, **kw):
                Refusing.calls += 1
                raise requests.ConnectionError("offline")

        document = DnsAdapter(Refusing(), clock=lambda: 0.0).find_source("SM-A376EZAGINS", deadline=1e9, brand="Samsung", name="Galaxy A37 8+256GB", missing_fields=["инструкция"])
        self.assertEqual((document.match_level, Refusing.calls), ("dealer_url_needed", 0))
        self.assertIn("инструкция", document.evidence)
        none_needed = DnsAdapter(Refusing(), clock=lambda: 0.0).find_source("SM-A376EZAGINS", deadline=1e9, brand="Samsung", name="x", missing_fields=[])
        self.assertEqual(none_needed.match_level, "not_needed")

    def test_only_the_phone_has_a_missing_field_among_the_ten_cards(self):
        cards = json.loads((S25 / "raw/cards.json").read_text(encoding="utf-8"))["cards"]
        self.assertEqual(len(cards), 11)
        missing = {c["category"]: c["missing_fields"] for c in cards if c["missing_fields"]}
        self.assertEqual(missing, {"Смартфоны": ["инструкция"]})
        for c in cards:
            self.assertEqual(c["dealer_fallback"]["requests_made"], 0)


if __name__ == "__main__":
    unittest.main()
