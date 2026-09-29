"""Read the catalog workbook (read-only) into one work unit per unique product.

Nothing here writes to the workbook or touches the network. A row is passed
through the importer's own `preview_row()` so brand/code/category semantics
are the ones the real import path uses (the importer's 5 000-row upload cap
does not apply to this offline census, so the sheet is iterated directly).

Unique-product key, as defined by the catalog's own "Контекст" sheet:
casefolded brand column + category + seller article. Rows with an empty brand
column stay separate units (the importer may *infer* a brand from the title;
that inference is kept as a review flag, never merged into the key).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from ..importer import detect_mapping, original_cell, preview_row

PRODUCTS_SHEET = "Товары"
PAIRS_SHEET = "Бренд_Категория"
CONTEXT_SHEET = "Контекст"

# Positions inside a "Товары" row (header: Бренд, Категория, Артикул продавца,
# Артикулы WB, Наименование, Альтернативные наименования, ТНВЭД, Повторов в выгрузках).
_WB_SKU, _ALT_TITLES, _DUPLICATES = 3, 5, 7


@dataclass(frozen=True)
class CatalogUnit:
    unit_id: str
    row_number: int
    brand: str  # catalog brand column, whitespace-normalised, may be empty
    category: str
    seller_sku: str
    wb_sku: str
    title: str
    alternate_titles: str
    source_rows: int  # "Повторов в выгрузках"
    importer_brand: str  # brand as the real import path would set it
    importer_brand_source: str
    importer_needs_confirmation: bool
    importer_issues: tuple[str, ...]

    @property
    def pair_key(self) -> tuple[str, str]:
        return (self.brand, self.category)


@dataclass(frozen=True)
class CatalogSnapshot:
    path: str
    sha256: str
    units: tuple[CatalogUnit, ...]
    pair_rows: tuple[tuple[str, str, int, int], ...]  # brand, category, unique products, source rows
    context: dict[str, object]


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def unit_id_for(brand: str, category: str, seller_sku: str) -> str:
    key = "\x1f".join((brand.casefold(), category, seller_sku))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_catalog(path: str | Path) -> CatalogSnapshot:
    path = Path(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        context = {}
        rows = workbook[CONTEXT_SHEET].iter_rows(values_only=True)
        next(rows, None)
        for key, value in rows:
            if key:
                context[str(key)] = value

        sheet = workbook[PRODUCTS_SHEET]
        mapping = detect_mapping(sheet)
        units: list[CatalogUnit] = []
        for row_number, cells in enumerate(sheet.iter_rows(values_only=True), start=1):
            if row_number <= mapping.header_row:
                continue
            raw = tuple(original_cell(value) for value in cells[:100])
            preview = preview_row(row_number, raw, mapping)
            if preview is None:
                continue
            brand = _clean(raw[0]) if len(raw) > 0 else ""
            category = _clean(raw[1]) if len(raw) > 1 else ""
            sku = _clean(raw[2]) if len(raw) > 2 else ""
            units.append(CatalogUnit(
                unit_id=unit_id_for(brand, category, sku), row_number=row_number,
                brand=brand, category=category, seller_sku=sku,
                wb_sku=_clean(raw[_WB_SKU]) if len(raw) > _WB_SKU else "",
                title=_clean(raw[4]) if len(raw) > 4 else "",
                alternate_titles=_clean(raw[_ALT_TITLES]) if len(raw) > _ALT_TITLES else "",
                source_rows=int(raw[_DUPLICATES] or 1) if len(raw) > _DUPLICATES else 1,
                importer_brand=preview.brand, importer_brand_source=preview.brand_source,
                importer_needs_confirmation=preview.needs_confirmation, importer_issues=preview.issues,
            ))

        pair_rows = []
        pairs = workbook[PAIRS_SHEET].iter_rows(values_only=True)
        next(pairs, None)
        for brand, category, unique_products, source_rows, _samples in pairs:
            if _clean(category):
                pair_rows.append((_clean(brand), _clean(category), int(unique_products or 0), int(source_rows or 0)))
    finally:
        workbook.close()
    return CatalogSnapshot(str(path), file_sha256(path), tuple(units), tuple(pair_rows), context)


def reconcile(snapshot: CatalogSnapshot) -> dict[str, object]:
    """Compare what was read with the workbook's own declared totals and its
    Бренд_Категория sheet; raises ValueError if anything disagrees."""
    units = snapshot.units
    ctx = snapshot.context
    observed = {
        "unique_products": len(units),
        "source_rows": sum(unit.source_rows for unit in units),
        "brands": len({unit.brand.casefold() for unit in units if unit.brand}),
        "categories": len({unit.category.casefold() for unit in units}),
        "brand_category_pairs": len({unit.pair_key for unit in units}),
    }
    expected = {
        "unique_products": int(ctx["Уникальных товаров после фильтра"]),
        "source_rows": int(ctx["Рабочих строк после фильтра"]),
        "brands": int(ctx["Брендов после фильтра"]),
        "categories": int(ctx["Категорий после фильтра"]),
        "brand_category_pairs": int(ctx["Связок бренд + категория после фильтра"]),
    }
    problems = [f"{key}: read {observed[key]} != declared {expected[key]}" for key in expected if observed[key] != expected[key]]
    if len({unit.unit_id for unit in units}) != len(units):
        problems.append("unit ids are not unique")
    per_pair: dict[tuple[str, str], int] = {}
    for unit in units:
        per_pair[unit.pair_key] = per_pair.get(unit.pair_key, 0) + 1
    sheet_pairs = {(brand, category): count for brand, category, count, _rows in snapshot.pair_rows}
    if per_pair != sheet_pairs:
        problems.append("per-pair unique product counts differ from the Бренд_Категория sheet")
    if problems:
        raise ValueError("Catalog does not reconcile: " + "; ".join(problems))
    return {"observed": observed, "declared": expected, "pair_sheet_matches": True}
