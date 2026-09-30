"""Stage 53 card presentation regression: evidence remains independent."""
from __future__ import annotations

import gc
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from product_tool import attribute_projection, card_presentation, jobs
from product_tool.adapters.common import PhotoCandidate, RawAttribute, SourceDocument
from product_tool.web import create_app


def source(key: str, attributes: list[RawAttribute]) -> SourceDocument:
    names = {"lg_ru": "LG Россия", "lg_kz": "LG Казахстан"}
    return SourceDocument(
        key, names[key], "https://example.test/p", found_model="86NANO81A6A",
        match_level="full_sku", evidence="fixture", attributes=attributes,
        photo_candidates=[PhotoCandidate("https://example.test/image.jpg", "fixture", "product_gallery")]
        if key == "lg_ru" else [],
    )


class CardUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "batches.sqlite3"
        jobs.initialize(self.db)
        with sqlite3.connect(self.db) as connection:
            connection.execute("INSERT INTO batches VALUES ('b1','fixture.xlsx','Товары','{}','2026-01-01')")
            self.product_id = connection.execute(
                "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,"
                "category,needs_confirmation,issues_json,original_values_json) "
                "VALUES ('b1',2,'TV','LG','86NANO81A6A','','Телевизор',0,'[]','{}')"
            ).lastrowid
        jobs.save_source_document(self.db, self.product_id, source("lg_ru", [
            RawAttribute("Адаптивное управление звуком (ИИ)", "Да", "АУДИО"),
            RawAttribute("Разрешение экрана", "3840 x 2160", "ЭКРАН"),
            RawAttribute("Операционная система (ОС)", "webOS 25", "SMART TV"),
            RawAttribute("TurboWash", "Нет", "ДОПОЛНИТЕЛЬНЫЕ ОПЦИИ"),
            RawAttribute("TurboWash", "Да", "ФУНКЦИИ"),
        ]))
        jobs.save_source_document(self.db, self.product_id, source("lg_kz", [
            RawAttribute("AI Звук (*AI - искусственный интеллект)", "Да", "АУДИО"),
            RawAttribute("Разрешение экрана", "3840 x 2160", "ЭКРАН"),
        ]))
        jobs.resolve_product(self.db, self.product_id)

    def tearDown(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            gc.collect()
        self.tmp.cleanup()

    def test_grouped_names_compact_status_and_dealer_visibility(self) -> None:
        rows = attribute_projection.final_attribute_rows(self.db, self.product_id)
        pages = jobs.get_source_pages(self.db, self.product_id)
        presented = card_presentation.present_card_rows(
            rows, jobs.get_facts(self.db, self.product_id), pages, "Телевизор"
        )
        self.assertEqual(presented["columns"], [("lg_ru", "LG Россия"), ("lg_kz", "LG Казахстан")])
        flattened = [row for sections in presented["groups"].values() for group in sections.values() for row in group]
        sound = next(row for row in flattened if row["display_name"] == "Адаптивное управление звуком (ИИ)")
        self.assertEqual(sound["role"], "feature")
        screen = next(row for row in flattened if row["display_name"] == "Разрешение экрана")
        self.assertEqual(screen["section_name"], "Экран")
        self.assertEqual(screen["role"], "core")
        self.assertEqual(screen["compact_status"], "Совпадает")
        conflict = next(row for row in flattened if row["display_name"] == "TurboWash")
        self.assertEqual(conflict["compact_status"], "Есть расхождение")
        self.assertEqual(len(conflict["conflict_sides"]), 2)
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "INSERT INTO source_pages (product_id,source_key,site_name,url,match_level,"
                "found_model,evidence,description,photos_json,error,fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (self.product_id, "sulpak", "Sulpak", "", "unknown", "", "", "", "[]", "", "2026-01-01")
            )
        presented = card_presentation.present_card_rows(
            rows, jobs.get_facts(self.db, self.product_id),
            jobs.get_source_pages(self.db, self.product_id), "Телевизор"
        )
        self.assertEqual(len(presented["columns"]), 2)
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "UPDATE source_pages SET url='https://example.test/dealer', "
                "match_level='unknown' WHERE product_id=? AND source_key='sulpak'",
                (self.product_id,),
            )
        presented = card_presentation.present_card_rows(
            rows, jobs.get_facts(self.db, self.product_id),
            jobs.get_source_pages(self.db, self.product_id), "Телевизор"
        )
        self.assertIn(("sulpak", "Sulpak"), presented["columns"])

    def test_unknown_photo_metadata_is_not_invented(self) -> None:
        with TestClient(create_app(self.root, start_worker=False)) as client:
            page = BeautifulSoup(client.get(f"/products/{self.product_id}").text, "html.parser")
        photo = page.select_one(".photo-open")
        self.assertEqual(photo["data-resolution"], "Не определено")
        self.assertEqual(photo["data-size"], "не определено")
        self.assertEqual(photo["data-format"], "Не определено")

    def test_page_lightbox_and_single_value_override_preserve_evidence(self) -> None:
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "UPDATE photo_candidates SET verified_width=2000,verified_height=2000,"
                "verified_bytes=1887437,verified_format='JPG' WHERE product_id=?",
                (self.product_id,),
            )
        with TestClient(create_app(self.root, start_worker=False)) as client:
            page = client.get(f"/products/{self.product_id}")
            self.assertEqual(page.status_code, 200)
            soup = BeautifulSoup(page.text, "html.parser")
            self.assertIsNone(soup.find("th", string="Итог"))
            self.assertIsNone(soup.find("th", string="Sulpak"))
            self.assertIsNotNone(soup.find("dialog", id="photo-lightbox"))
            photo = soup.select_one(".photo-open")
            self.assertEqual(photo["data-resolution"], "2000 × 2000 px")
            self.assertEqual(photo["data-format"], "JPG")
            self.assertEqual(photo["data-size"], "1.8 MB")
            self.assertTrue(soup.select(".attribute-group[data-role=core]"))
            self.assertTrue(soup.select(".attribute-group[data-role=feature]"))
            self.assertIn("Есть расхождение", page.text)
            self.assertIn("Только LG Россия", page.text)
            self.assertIn("Совпадает", page.text)
            conflict_row = soup.find("th", string="TurboWash").find_parent("tr")
            form = conflict_row.find("form", action=lambda x: x and "/attributes/" in x)
            self.assertEqual([field["name"] for field in form.find_all("input")], ["value"])
            self.assertIn("Свое значение", form.parent.text)
            before = len(jobs.get_facts(self.db, self.product_id))
            result = client.post(form["action"], data={"value": "проверено вручную"}, follow_redirects=False)
            self.assertEqual(result.status_code, 303)
            self.assertEqual(len(jobs.get_facts(self.db, self.product_id)), before)
            decisions = jobs.get_manual_decisions(self.db, self.product_id)
            self.assertEqual(len(decisions), 1)
            self.assertEqual(next(iter(decisions.values()))["reason"], "manual_user_override")
            self.assertEqual(next(iter(decisions.values()))["selected_value"], "проверено вручную")
            updated = BeautifulSoup(client.get(f"/products/{self.product_id}").text, "html.parser")
            evidence = updated.find("th", string="TurboWash").find_parent("tr").select_one(".evidence-detail")
            self.assertIn("Нет", evidence.text)
            self.assertIn("Да", evidence.text)


if __name__ == "__main__":
    unittest.main()
