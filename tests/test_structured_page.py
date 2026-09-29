"""Stage 14: offline tests for the reusable, source-agnostic Product-page
extraction primitives in product_tool/adapters/structured_page.py.

Includes boundary tests against synthetic Bosch/Cudy fixtures -- these
exist ONLY to prove where the shared low-level components do and do not
generalize across brands. No Bosch/Cudy identity check or adapter is built
here or anywhere this stage; structural similarity is never treated as
proof of an exact product match. No network access is used anywhere in
this file.
"""
from __future__ import annotations

from pathlib import Path
import unittest

from product_tool.adapters.structured_page import (
    CONFIRMED,
    PARTIAL,
    ROLE_DESCRIPTION_IMAGE,
    ROLE_DOM_TABLE,
    ROLE_GALLERY,
    ROLE_JSON_LD,
    ROLE_VIDEO,
    extract_description_images,
    extract_dom_spec_table,
    extract_json_ld_product,
    extract_main_gallery,
    extract_video,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage14_hyperx"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


QUADCAST_HTML = read("quadcast_2s_black_9a273aa_synthetic.html")
QUADCAST_URL = "https://hyperx.com/products/hyperx-quadcast-2s-black"


class ExtractedFieldShapeTests(unittest.TestCase):
    """Every field, from every extractor, must carry all four required
    properties -- never a bare value."""

    def test_every_json_ld_field_has_url_evidence_role_and_confirmation(self):
        fields = extract_json_ld_product(QUADCAST_HTML, QUADCAST_URL)
        self.assertTrue(fields)
        for field in fields:
            self.assertTrue(field.url)
            self.assertTrue(field.evidence)
            self.assertEqual(field.role, ROLE_JSON_LD)
            self.assertEqual(field.confirmation, CONFIRMED)

    def test_every_gallery_field_has_url_evidence_role_and_confirmation(self):
        fields = extract_main_gallery(QUADCAST_HTML, QUADCAST_URL)
        self.assertTrue(fields)
        for field in fields:
            self.assertTrue(field.url)
            self.assertTrue(field.evidence)
            self.assertEqual(field.role, ROLE_GALLERY)
            self.assertEqual(field.confirmation, CONFIRMED)


class JsonLdProductTests(unittest.TestCase):
    def test_identity_and_spec_fields_are_extracted(self):
        fields = extract_json_ld_product(QUADCAST_HTML, QUADCAST_URL)
        by_name = {f.name: f.value for f in fields}
        self.assertEqual(by_name["sku"], "9A273AA")
        self.assertEqual(by_name["productID"], "9A273AA")
        self.assertEqual(by_name["Sensor"], "Electret condenser")
        self.assertEqual(by_name["Sample rate"], "48kHz")

    def test_non_product_json_ld_blocks_are_ignored(self):
        html = '''<script type="application/ld+json">
        {"@context":"https://schema.org/","@type":"WebSite","name":"HyperX"}
        </script>'''
        self.assertEqual(extract_json_ld_product(html, "https://example.test/"), [])

    def test_malformed_json_ld_is_skipped_not_raised(self):
        html = '<script type="application/ld+json">{not valid json</script>'
        self.assertEqual(extract_json_ld_product(html, "https://example.test/"), [])


class DomSpecTableTests(unittest.TestCase):
    def test_dl_dt_dd_pairs_are_confirmed(self):
        fields = extract_dom_spec_table(QUADCAST_HTML, QUADCAST_URL)
        by_name = {f.name: f for f in fields}
        self.assertEqual(by_name["Interface"].value, "USB-C")
        self.assertEqual(by_name["Interface"].confirmation, CONFIRMED)
        self.assertEqual(by_name["Interface"].role, ROLE_DOM_TABLE)

    def test_accordion_details_summary_is_partial_not_confirmed(self):
        fields = extract_dom_spec_table(QUADCAST_HTML, QUADCAST_URL)
        box_contents = next(f for f in fields if f.name == "What's in the box")
        self.assertEqual(box_contents.confirmation, PARTIAL)
        self.assertIn("Quick Start Guide", box_contents.value)

    def test_box_contents_text_is_never_treated_as_a_document_link(self):
        # The literal requirement: mentioning a Quick Start Guide as an
        # included accessory must never become a document/manual URL.
        fields = extract_dom_spec_table(QUADCAST_HTML, QUADCAST_URL)
        box_contents = next(f for f in fields if f.name == "What's in the box")
        self.assertNotIn("http", box_contents.value)


class GalleryTests(unittest.TestCase):
    def test_full_gallery_found_via_data_media_id_and_data_fancybox(self):
        fields = extract_main_gallery(QUADCAST_HTML, QUADCAST_URL)
        urls = {f.value for f in fields}
        self.assertEqual(len(fields), 3)
        self.assertIn("https://hyperx.com/cdn/shop/products/quadcast-2s-black-front.jpg", urls)
        self.assertIn("https://hyperx.com/cdn/shop/products/quadcast-2s-black-side.jpg", urls)
        self.assertIn("https://hyperx.com/cdn/shop/products/quadcast-2s-black-rgb.jpg", urls)

    def test_logo_srcset_is_never_counted_as_gallery(self):
        # The logo sits inside a data-fancybox anchor AND itself carries a
        # data-media-id and a multi-width srcset -- every superficial
        # signal a naive gallery scan might use. It must still be excluded
        # because it is marked as a logo.
        fields = extract_main_gallery(QUADCAST_HTML, QUADCAST_URL)
        for field in fields:
            self.assertNotIn("logo", field.value.lower())

    def test_plain_img_srcset_alone_is_not_gallery_evidence(self):
        html = '<img src="https://example.test/a.jpg" srcset="https://example.test/a-320.jpg 320w">'
        self.assertEqual(extract_main_gallery(html, "https://example.test/"), [])


class DescriptionImageAndVideoTests(unittest.TestCase):
    def test_description_image_is_found_and_distinct_from_gallery(self):
        fields = extract_description_images(QUADCAST_HTML, QUADCAST_URL)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].role, ROLE_DESCRIPTION_IMAGE)
        self.assertIn("desk-lifestyle", fields[0].value)
        gallery_urls = {f.value for f in extract_main_gallery(QUADCAST_HTML, QUADCAST_URL)}
        self.assertNotIn(fields[0].value, gallery_urls)

    def test_video_element_source_is_found(self):
        fields = extract_video(QUADCAST_HTML, QUADCAST_URL)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].role, ROLE_VIDEO)
        self.assertTrue(fields[0].value.endswith(".mp4"))

    def test_a_page_with_no_video_yields_no_video_field_not_a_guess(self):
        mouse_html = read("pulsefire_fuse_a1ky6aa_synthetic.html")
        self.assertEqual(extract_video(mouse_html, "https://hyperx.com/products/pulsefire-fuse"), [])


class BoschCudyBoundaryTests(unittest.TestCase):
    """Boundary tests only -- no Bosch/Cudy adapter or identity check
    exists, and none is implied by these passing. They exist to show
    exactly where a brand-agnostic component generalizes (JSON-LD, DOM
    tables) and where it correctly does not (the Shopify-specific gallery
    attribute pattern)."""

    def test_json_ld_extraction_generalizes_to_bosch_shape(self):
        html = read("bosch_boundary_synthetic.html")
        fields = extract_json_ld_product(html, "https://www.bosch-home.com/twk7203")
        by_name = {f.name: f.value for f in fields}
        self.assertEqual(by_name["gtin13"], "4242002948291")
        self.assertEqual(by_name["mpn"], "TWK7203")
        self.assertEqual(by_name["Capacity"], "1.7 L")

    def test_json_ld_extraction_generalizes_to_cudy_shape(self):
        html = read("cudy_boundary_synthetic.html")
        fields = extract_json_ld_product(html, "https://www.cudy.com/wr6500h")
        by_name = {f.name: f.value for f in fields}
        self.assertEqual(by_name["sku"], "WR6500H-1.0")
        self.assertEqual(by_name["Wi-Fi standard"], "Wi-Fi 6")

    def test_dom_table_extraction_generalizes_to_both(self):
        bosch_fields = extract_dom_spec_table(read("bosch_boundary_synthetic.html"), "https://www.bosch-home.com/twk7203")
        cudy_fields = extract_dom_spec_table(read("cudy_boundary_synthetic.html"), "https://www.cudy.com/wr6500h")
        self.assertIn("Colour", {f.name for f in bosch_fields})
        self.assertIn("Antennas", {f.name for f in cudy_fields})

    def test_data_media_id_gallery_extractor_correctly_finds_nothing_on_either(self):
        # This is the actual boundary: Bosch/Cudy's own confirmed structural
        # contract never used the Shopify data-media-id/data-fancybox
        # pattern, so the extractor must not invent gallery hits for them --
        # finding zero here is the CORRECT, honest result, not a failure.
        bosch_gallery = extract_main_gallery(read("bosch_boundary_synthetic.html"), "https://www.bosch-home.com/twk7203")
        cudy_gallery = extract_main_gallery(read("cudy_boundary_synthetic.html"), "https://www.cudy.com/wr6500h")
        self.assertEqual(bosch_gallery, [])
        self.assertEqual(cudy_gallery, [])


if __name__ == "__main__":
    unittest.main()
