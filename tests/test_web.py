"""Browser workflow checks using only temporary Excel books and databases."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
from openpyxl import Workbook

from product_tool import storage
from product_tool.web import create_app


def workbook_bytes(rows: list[list[str | None]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Товары"
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class WebWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data_dir = Path(temporary.name)
        self.client = TestClient(create_app(self.data_dir))
        self.addCleanup(self.client.close)

    def upload(self, contents: bytes, filename: str = "items.xlsx") -> str:
        response = self.client.post(
            "/upload",
            files={"file": (filename, contents, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)
        return response.headers["location"]

    def test_review_correct_confirm_and_reopen_after_restart(self) -> None:
        path = self.upload(workbook_bytes([
            ["Предмет", "Бренд", "Наименование", "Артикул продавца", "Модель"],
            ["Стиральная машина", "LG", "Стиральная машина LG F2V5HG1W", "F2V5HG1W", "F2V5HG1W"],
            [None, None, "Смартфон Samsung SM-A566ELIHINS"],
        ]))
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200)
        for label in ("Номер", "Название", "Бренд", "Основной артикул", "Запасная модель", "Категория", "Нужно проверить"):
            self.assertIn(label, page.text)
        self.assertIn('name="brand" type="number" min="1" max="100" value="2"', page.text)

        response = self.client.post(
            f"{path}/confirm",
            data={
                "brand_2": "LG", "search_code_2": "F2V5HG1W",
                "alternate_code_2": "", "category_2": "Стиральная машина",
                "brand_3": "Samsung", "search_code_3": "SM-A566ELIHINS",
                "alternate_code_3": "SM-A566", "category_3": "Телефоны",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)
        batch_path = response.headers["location"]
        batch_id = batch_path.rsplit("/", 1)[-1]
        saved = storage.get_batch(self.data_dir / "batches.sqlite3", batch_id)
        self.assertEqual(len(saved["products"]), 2)
        self.assertEqual(saved["products"][1]["category"], "Телефоны")
        self.assertEqual(saved["products"][1]["alternate_code"], "SM-A566")
        self.assertIn("SM-A566ELIHINS", saved["products"][1]["original_values_json"])
        self.assertTrue((self.data_dir / "uploads" / f"{batch_id}.xlsx").is_file())

        with TestClient(create_app(self.data_dir)) as restarted:
            self.assertIn("items.xlsx", restarted.get("/").text)
            page = restarted.get(batch_path)
            self.assertEqual(page.status_code, 200)
            self.assertIn("Стиральная машина", page.text)
            self.assertIn("Телефоны", page.text)
            self.assertIn("SM-A566ELIHINS", page.text)

    def test_headerless_book_can_be_mapped_manually(self) -> None:
        path = self.upload(workbook_bytes([
            ["Ноутбук Lenovo 83M0003YRK", "Lenovo", "83M0003YRK", "Ноутбук"],
        ]))
        self.assertIn("Укажите лист и номера колонок", self.client.get(path).text)
        mapping = self.client.post(
            f"{path}/mapping",
            data={
                "sheet_name": "Товары", "header_row": "0",
                "name": "1", "brand": "2", "search_code": "3",
                "fallback_code": "", "category": "4",
            },
            follow_redirects=False,
        )
        self.assertEqual(mapping.status_code, 303)
        page = self.client.get(path)
        self.assertIn("Ноутбук Lenovo 83M0003YRK", page.text)
        self.assertIn('name="search_code" type="number" min="1" max="100" value="3"', page.text)

    def test_missing_required_product_values_are_shown_on_page(self) -> None:
        path = self.upload(workbook_bytes([["Наименование"], ["Неизвестный товар"]]))
        response = self.client.post(
            f"{path}/confirm",
            data={"brand_2": "", "search_code_2": "", "alternate_code_2": "", "category_2": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Строка 2: заполните бренд и основной артикул", response.text)
        self.assertEqual(storage.list_batches(self.data_dir / "batches.sqlite3"), [])

    def test_invalid_upload_and_mapping_show_readable_errors(self) -> None:
        response = self.client.post("/upload", files={"file": ("items.csv", b"a,b", "text/csv")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Поддерживаются только файлы .xlsx", response.text)

        response = self.client.post("/upload", files={"file": ("broken.xlsx", b"not a workbook", "application/octet-stream")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Не удалось открыть Excel", response.text)

        path = self.upload(workbook_bytes([["Наименование"], ["Ноутбук Lenovo 83M0003YRK"]]))
        response = self.client.post(
            f"{path}/mapping",
            data={"sheet_name": "Товары", "header_row": "1", "name": "101", "brand": "", "search_code": "", "fallback_code": "", "category": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("номер колонки должен быть от 1 до 100", response.text)

    def test_uploaded_text_is_escaped_in_html(self) -> None:
        path = self.upload(workbook_bytes([
            ["Наименование", "Бренд", "Артикул"],
            ["<script>alert(1)</script>", "LG", "F2V5HG1W"],
        ]))
        page = self.client.get(path)
        self.assertIn("&lt;script&gt;", page.text)
        self.assertNotIn("<script>alert(1)</script>", page.text)


if __name__ == "__main__":
    unittest.main()