"""Excel export with resolved category data and source audit sheets."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

from openpyxl import Workbook
from openpyxl.styles import Font

from . import jobs, storage


def _title(value: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", value or "Категория не определена").strip()[:31]
    base = base or "Категория"
    candidate, counter = base, 2
    while candidate in used:
        suffix = f" {counter}"
        candidate = base[:31 - len(suffix)] + suffix
        counter += 1
    used.add(candidate)
    return candidate


def _headers(sheet, values: list[str]) -> None:
    sheet.append(values)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def export_batch(database: Path, batch_id: str) -> bytes:
    batch = storage.get_batch(database, batch_id)
    if batch is None:
        raise ValueError("Партия не найдена.")
    book = Workbook()
    book.remove(book.active)
    used: set[str] = set()

    groups: dict[str, list[dict]] = {}
    for product in batch["products"]:
        groups.setdefault(product["category"] or "Категория не определена", []).append(product)
    for category, products in groups.items():
        sheet = book.create_sheet(_title(category, used))
        names = sorted({
            item["normalized_name"]
            for product in products for item in jobs.get_resolved(database, product["id"])
        })
        _headers(sheet, ["Строка", "Название", "Бренд", "Полный артикул", "Базовая модель", *names])
        for product in products:
            resolved = {
                item["normalized_name"]: (
                    f"{item['selected_value']} {item['selected_unit']}".strip()
                    if item["selected_value"] else ""
                )
                for item in jobs.get_resolved(database, product["id"])
            }
            from .adapters.lg import lg_base_model
            sheet.append([
                product["row_number"], product["name"], product["brand"],
                product["search_code"],
                lg_base_model(product["search_code"])
                if product["brand"].strip().upper() == "LG" else "",
                *[resolved.get(name, "") for name in names],
            ])

    check = book.create_sheet(_title("Проверка источников", used))
    _headers(check, [
        "Товар", "Полный артикул", "Характеристика", "LG", "Mechta", "Sulpak",
        "Итог", "Единица", "Причина", "Статус",
    ])
    for product in batch["products"]:
        for row in jobs.comparison_rows(database, product["id"]):
            sources = row["sources"]
            resolved = row.get("resolved") or {}
            check.append([
                product["name"], product["search_code"], row["normalized_name"],
                sources.get("lg", {}).get("raw_value", ""),
                sources.get("mechta", {}).get("raw_value", ""),
                sources.get("sulpak", {}).get("raw_value", ""),
                resolved.get("selected_value", ""), resolved.get("selected_unit", ""),
                resolved.get("reason", ""), resolved.get("status", ""),
            ])

    sources_sheet = book.create_sheet(_title("Источники", used))
    _headers(sources_sheet, [
        "Товар", "Полный артикул", "Сайт", "Найденная модель",
        "Уровень совпадения", "Доказательство", "Дата получения", "Ошибка", "URL",
    ])
    for product in batch["products"]:
        for source in jobs.get_source_pages(database, product["id"]):
            sources_sheet.append([
                product["name"], product["search_code"], source["site_name"],
                source["found_model"], source["match_level"], source["evidence"],
                source["fetched_at"], source["error"], source["url"],
            ])

    for sheet in book.worksheets:
        for column in sheet.columns:
            width = min(60, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[column[0].column_letter].width = width
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()
