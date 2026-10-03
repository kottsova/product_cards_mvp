"""Stage 57: no invented axes, no source promotion, stable manual evidence."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from product_tool import jobs, manual_status, readiness, storage
from product_tool.adapters.common import ProductDocument, SourceDocument
from product_tool.adapters.lg_support import verified_russian_archive
from product_tool.lg_presentation import canonical_label, canonical_section, classify, safe_composite_dimensions, split_dimensions


def dimension_row(name: str, raw_name: str, raw_value: str, value: str) -> dict:
    fact = {"raw_name": raw_name, "raw_value": raw_value, "section": "",
            "normalized_value": value, "unit": "mm", "site_name": "LG",
            "source_key": "lg_kz"}
    return {"normalized_name": name, "display_name": raw_name, "raw_names": [raw_name],
            "sources": {"lg_kz": fact}, "resolved": {
                "selected_source": "lg_kz", "selected_value": value,
                "selected_unit": "mm", "full_sku_confirmed": True, "conflict": False}}


class Stage57ProjectionTests(unittest.TestCase):
    def test_explicit_axis_order_and_cm_normalization(self):
        row = dimension_row("product_dimensions", "Размеры (В × Ш × Г, см)",
                            "85 × 60 × 56,5", "w=600;h=850;d=565")
        axes = split_dimensions(row)
        self.assertEqual(
            {r["normalized_name"]: r["resolved"]["display_value"] for r in axes},
            {"product_w_mm": "600 мм", "product_h_mm": "850 мм", "product_d_mm": "565 мм"})
        self.assertEqual(axes[0]["sources"]["lg_kz"]["raw_value"], "85 × 60 × 56,5")

    def test_glued_axis_unit_on_official_label(self):
        row = dimension_row("package_dimensions", "\u0420\u0430\u0437\u043c\u0435\u0440\u044b \u043a\u043e\u0440\u043e\u0431\u043a\u0438 (\u0428x\u0412x\u0413\u043c\u043c)",
                            "325 x 331 x 612", "w=325;h=331;d=612")
        self.assertEqual([r["normalized_name"] for r in split_dimensions(row)],
                         ["package_w_mm", "package_h_mm", "package_d_mm"])

    def test_unproven_order_or_unit_stays_composite(self):
        row = dimension_row("product_dimensions", "Размеры товара", "720 x 63 x 87",
                            "w=720;h=63;d=87")
        self.assertIsNone(split_dimensions(row))
        row["sources"]["lg_kz"]["raw_name"] = "Размеры (Ш × В × Г)"
        self.assertIsNone(split_dimensions(row))

    def test_uppercase_english_section_is_russian(self):
        self.assertEqual(canonical_section("ACCESSORIES"), "\u041a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u0430\u0446\u0438\u044f")

    def test_inferred_mm_is_not_shown_without_source_unit(self):
        row = dimension_row("product_dimensions__without_stand",
                            "\u0420\u0430\u0437\u043c\u0435\u0440 \u0431\u0435\u0437 \u043f\u043e\u0434\u0441\u0442\u0430\u0432\u043a\u0438 (\u0428x\u0412x\u0413)",
                            "1927 x 1104 x 59.9", "w=1927;h=1104;d=59.9")
        row["resolved"]["display_value"] = "1927 x 1104 x 59.9 \u043c\u043c"
        self.assertIsNone(split_dimensions(row))
        shown = safe_composite_dimensions(row)
        self.assertEqual(shown["resolved"]["display_value"], "1927 x 1104 x 59.9")
        self.assertEqual(shown["resolved"]["selected_unit"], "")
        self.assertEqual(row["sources"]["lg_kz"]["raw_value"], "1927 x 1104 x 59.9")

    def test_product_package_and_junk_are_separate(self):
        product = dimension_row("product_dimensions", "Размеры товара (Ш × В × Г, мм)",
                                "600 x 850 x 565", "w=600;h=850;d=565")
        package = dimension_row("package_dimensions", "Размеры упаковки (Ш × В × Г, мм)",
                                "610 x 870 x 600", "w=610;h=870;d=600")
        self.assertEqual(split_dimensions(product)[0]["normalized_name"], "product_w_mm")
        self.assertEqual(split_dimensions(package)[0]["normalized_name"], "package_w_mm")
        self.assertEqual(classify({"normalized_name": "container_q_ty_40ft", "resolved": {}}),
                         "logistics/internal metadata")
        self.assertEqual(canonical_label({"normalized_name": "completion_beeper", "sources": {}}),
                         "Звуковой сигнал окончания работы")


class Stage57ManualTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "db.sqlite3"
        jobs.initialize(self.path)
        with storage._connection(self.path) as c:
            for batch in ("a", "b"):
                c.execute("INSERT INTO batches VALUES (?,?,?,?,?)",
                          (batch, "x.xlsx", "Items", "{}", "2026-01-01"))
            self.ids = []
            for batch, code in (("a", "P12ED.NSAR + P12ED.USAR"),
                                ("b", "P12ED.NSAR + P12ED.USAR"),
                                ("b", "P12ED.NSAR + P12ED.DIFFERENT")):
                self.ids.append(c.execute(
                    "INSERT INTO products (batch_id,row_number,name,brand,search_code,"
                    "alternate_code,category,needs_confirmation,issues_json,original_values_json)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (batch, len(self.ids)+2, "AC", "LG", code, "", "AC", 0, "[]", "{}")
                ).lastrowid)

    def test_exact_duplicate_inherits_official_pdf_only(self):
        url = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"
        jobs.save_source_document(self.path, self.ids[0],
                                  SourceDocument("lg_kz_support", "LG", url,
                                                 match_level="full_sku"))
        jobs.save_documents(
            self.path, self.ids[0], "lg_kz_support",
            [ProductDocument("Russian manual", "Русский", "", "",
                             "https://gscs-b2c.lge.com/open/downloadFile?fileId=proof",
                             url, "P12ED", "P12ED.NSAR, P12ED.USAR", url, True)])
        self.assertEqual(manual_status.russian_status(self.path, self.ids[1],
                                                       "P12ED.NSAR + P12ED.USAR"),
                         manual_status.VERIFIED)
        self.assertEqual(len(manual_status.effective_documents(
            self.path, self.ids[1], "P12ED.NSAR + P12ED.USAR")), 1)
        self.assertTrue(readiness.card_readiness(self.path, self.ids[1])["instruction"]["russian"])
        self.assertNotIn("instruction_missing", readiness.card_readiness(self.path, self.ids[1])["blocking_gaps"])
        self.assertEqual(manual_status.russian_status(self.path, self.ids[2],
                                                       "P12ED.NSAR + P12ED.DIFFERENT"),
                         manual_status.UNCHECKED)

    def test_archive_requires_real_russian_manual_pages(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("ru-ru/main.html", "<html lang='ru'>Инструкция</html>")
            for n in range(3):
                z.writestr(f"ru-ru/topics/{n}.html", "Эксплуатация устройства. " * 100)
        verified = verified_russian_archive(buffer.getvalue())
        self.assertEqual(verified["kind"], "russian_html_manual_archive")
        self.assertGreater(verified["cyrillic_characters"], 1000)
        self.assertIsNone(verified_russian_archive(b"%PDF-fake"))


if __name__ == "__main__":
    unittest.main()
