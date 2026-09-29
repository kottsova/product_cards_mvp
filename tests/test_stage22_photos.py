"""Stage 22: LG Russia gallery photos come from the observed structure /ru/images/<category>/<md...>/gallery/ (offline, on the 11 saved pages).

Placeholders and size duplicates are dropped, and a photo never changes a page's match level.
"""
from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from product_tool.adapters.lg import LG_RU_SITEMAP, LGRUAdapter, extract_lg_photo_candidates

from coverage_controls import FixtureSession

ROOT = Path(__file__).resolve().parents[1]
S21 = ROOT / "reports/source_census_2026-09-24_stage21"


def saved(directory: Path) -> dict[str, tuple[int, str]]:
    pages = {}
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["saved_as"]:
            with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                pages[entry["url"]] = (entry["status"], handle.read())
    return pages


PAGES = {**saved(S21 / "probe/responses"), **saved(S21 / "verify/responses")}
PRODUCT_PAGES = {url: text for url, (status, text) in PAGES.items() if "/ru/" in url and not url.endswith(".xml") and "/support/" not in url}
EXPECTED = {"lg-ms2032gas": 11, "lg-24mr400-b": 7, "lg-a9n-masterx": 15, "lg-SN4": 13, "lg-27MD5KL-B": 8, "lg-ac09bk": 14, "lg-f2j3ws1w": 12, "lg-dc90v5v9s": 11, "lg-50ut91006la": 13,
            "lg-gc-b509seum": 15, "lg-xl7s": 14}


def gallery(html: str, url="https://www.lg.com/ru/x/lg-y"):
    return [c for c in extract_lg_photo_candidates(BeautifulSoup(html, "html.parser"), url, region="ru") if c.kind == "product_gallery"]


class ElevenSavedPages(unittest.TestCase):
    def test_every_page_gives_its_gallery_and_nothing_else(self):
        self.assertEqual(len(PRODUCT_PAGES), 11)
        for url, html in PRODUCT_PAGES.items():
            items = gallery(html, url)
            slug = url.rsplit("/", 1)[-1]
            self.assertEqual(len(items), EXPECTED[slug], slug)
            self.assertEqual(len({c.url for c in items}), len(items), slug)  # no duplicate of one picture
            for c in items:
                self.assertIn("/ru/images/", c.url, slug)
                self.assertIn("/gallery/", c.url, slug)
                self.assertNotIn("obj-base", c.url.lower(), slug)
                self.assertNotIn("?", c.url, slug)

    def test_the_first_picture_is_the_main_image_and_is_the_large_one(self):
        html = next(h for u, h in PRODUCT_PAGES.items() if u.endswith("lg-a9n-masterx"))
        items = gallery(html, "https://www.lg.com/ru/vacuum-cleaners/lg-a9n-masterx")
        self.assertTrue(items[0].url.endswith("/md07565054/gallery/D-01.jpg"))
        self.assertFalse(any("/S-" in c.url for c in items))  # the small thumbnails are the same pictures, taken at their large size

    def test_the_gallery_folder_belongs_to_the_page_it_was_read_from(self):
        # LG names the gallery folder by the model data id (md...); one page never mixes two ids
        for url, html in PRODUCT_PAGES.items():
            ids = {c.url.split("/gallery/")[0].rsplit("/", 1)[-1].lower() for c in gallery(html, url)}
            self.assertEqual(len(ids), 1, (url, ids))


class SyntheticShapes(unittest.TestCase):
    def test_a_thumbnail_and_its_large_picture_are_one_asset(self):
        html = ('<div id="desktop_summary_gallery"><img id="base_detail_target" src="/ru/images/a/md1/gallery/D-01.jpg">'
                '<ul><li><img data-src="/ru/images/a/md1/gallery/S-01.jpg" data-medium="/ru/images/a/md1/gallery/D-01.jpg"></li>'
                '<li><img data-src="/ru/images/a/md1/gallery/S-02.jpg" data-medium="/ru/images/a/md1/gallery/D-02.jpg"></li></ul></div>')
        self.assertEqual([c.url.rsplit("/", 1)[-1] for c in gallery(html)], ["D-01.jpg", "D-02.jpg"])

    def test_the_placeholder_and_pictures_outside_the_gallery_folder_are_dropped(self):
        html = ('<div id="mobile_summary_gallery"><img src="/ru/images/a/md1/gallery/medium01.jpg"><img class="objet-base" src="/lg5-common-gp/images/objet/obj-base.png">'
                '<img src="/ru/images/a/md1/badges/energy.png"><img src="/lg5-common-gp/images/common/header/logo-b2c.jpg"></div>')
        self.assertEqual([c.url.rsplit("/", 1)[-1] for c in gallery(html)], ["medium01.jpg"])

    def test_the_older_stylers_layout_is_still_accepted(self):
        html = '<div id="pdpGallery"><img src="/ru/images/stylers/x/large01.jpg"></div>'
        self.assertEqual(len(gallery(html)), 1)

    def test_kazakhstan_extraction_is_untouched(self):
        html = '<div class="c-summary-gallery"><img src="https://www.lg.com/kz/images/objet-collection/large01.jpg"></div>'
        items = [c for c in extract_lg_photo_candidates(BeautifulSoup(html, "html.parser"), "https://www.lg.com/kz/x/", region="kz") if c.kind == "product_gallery"]
        self.assertEqual(len(items), 1)


class TheMdFolderLayout(unittest.TestCase):
    """VC5316NNTS (found by the second pilot): the gallery pictures lie directly in /ru/images/<category>/<md...>/, with no gallery folder."""

    def test_pictures_without_a_gallery_folder_are_read_at_their_large_size(self):
        html = ('<div id="desktop_summary_gallery"><img id="base_detail_target" src="/ru/images/vacuum-cleaners/md07548417/D-1.jpg"><ul>'
                '<li><img data-src="/ru/images/vacuum-cleaners/md07548417/180-1.jpg" data-medium="/ru/images/vacuum-cleaners/md07548417/D-1.jpg"></li>'
                '<li><img data-src="/ru/images/vacuum-cleaners/md07548417/180-2.jpg" data-medium="/ru/images/vacuum-cleaners/md07548417/D-2.jpg"></li></ul></div>'
                '<div id="mobile_summary_gallery"><img src="/lg5-common-gp/images/objet/obj-base.png"></div>')
        self.assertEqual([c.url.rsplit("/", 1)[-1] for c in gallery(html)], ["D-1.jpg", "D-2.jpg"])

    def test_a_subfolder_other_than_gallery_is_still_not_a_gallery_picture(self):
        self.assertEqual(gallery('<div id="desktop_summary_gallery"><img src="/ru/images/a/md1/badges/energy.png"></div>'), [])

    def test_the_saved_vc5316nnts_page_gives_ten_pictures(self):
        pilot2 = saved(ROOT / "reports/source_census_2026-09-24_stage22/pilot2/responses")
        url = "https://www.lg.com/ru/vacuum-cleaners/lg-vc5316nnts"
        items = gallery(pilot2[url][1], url)
        self.assertEqual(len(items), 10)
        self.assertTrue(all("/md07548417/" in c.url for c in items))


class TheTwoRowsThatHadNoPhoto(unittest.TestCase):
    def find(self, article):
        session = FixtureSession(dict(PAGES))
        return LGRUAdapter(session, clock=lambda: 0.0).find_source(article, deadline=1e9)

    def test_a9n_masterx_now_has_a_gallery_from_its_exact_page(self):
        doc = self.find("A9N-MASTERX")
        self.assertEqual(doc.match_level, "full_sku")
        self.assertEqual(len(doc.photos), 15)
        self.assertTrue(all("/md07565054/gallery/" in url for url in doc.photos))

    def test_27md5kl_b_aeu_exact_sales_code_and_photos(self):
        doc = self.find("27MD5KL-B.AEU")
        self.assertEqual(doc.match_level, "full_sku")
        self.assertIn("data-adobe-salesmodelcode", doc.evidence)
        self.assertEqual(len(doc.photos), 8)
        self.assertEqual(doc.found_model, "27MD5KL-B.AEU")

    def test_24mr400_b_aruq_exact_sales_code_and_photos(self):
        doc = self.find("24MR400-B.ARUQ")
        self.assertEqual((doc.match_level, len(doc.photos)), ("full_sku", 7))
        self.assertIn("data-adobe-salesmodelcode", doc.evidence)


if __name__ == "__main__":
    unittest.main()
