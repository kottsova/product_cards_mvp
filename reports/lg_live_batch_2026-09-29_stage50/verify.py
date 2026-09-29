"""Stage 50 offline check through ordinary product and export routes."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from product_tool import attribute_projection, jobs, storage
from product_tool.lg_identity import photo_tied_to_article
from product_tool.web import create_app

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "batches.sqlite3"
BATCH = "ae3d2cb381744ba8a811e54231233254"
OUT = Path(__file__).with_name("stage50.xlsx")


def main() -> None:
    original_hash = hashlib.sha256(DB.read_bytes()).hexdigest()
    batch = storage.get_batch(DB, BATCH)
    products = [p for p in batch["products"] if p["brand"].strip().upper() == "LG"]
    assert len(products) == 12
    app = create_app(ROOT / "data", start_worker=False)
    with TestClient(app) as client:
        pages = {}
        for p in products:
            response = client.get(f"/products/{p['id']}")
            assert response.status_code == 200
            soup = BeautifulSoup(response.text, "html.parser")
            assert p["search_code"] in soup.get_text(" ", strip=True)
            assert soup.select_one("#lg-readiness")
            assert soup.select_one("#comparison")
            pages[p["search_code"]] = soup
        response = client.get(f"/batches/{BATCH}/export.xlsx")
        assert response.status_code == 200
        content = response.content
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    special = {"Проверка источников", "Источники", "Инструкции", "Фотографии", "Фото-кандидаты", "Готовность LG"}
    main_sheets = [sheet for sheet in book if sheet.title not in special]
    assert len(main_sheets) == 12
    by_article = {}
    for sheet in main_sheets:
        header = next(sheet.values)
        for row in list(sheet.values)[1:]:
            by_article[row[3]] = (header, row)
    assert set(by_article) == {p["search_code"] for p in products}
    confirmed_cells = 0
    blanked_candidate_cells = 0
    for p in products:
        header, row = by_article[p["search_code"]]
        projected = attribute_projection.final_attribute_rows(DB, p["id"])
        keys = sorted({r["normalized_name"] for r in projected},
                      key=lambda key: next(r["display_name"] for r in projected if r["normalized_name"] == key))
        assert len(row) == len(keys) + 5
        lookup = {r["normalized_name"]: r.get("resolved") or {} for r in projected}
        for i, key in enumerate(keys, 5):
            value = lookup[key]
            expected = value.get("display_value", "") if value.get("full_sku_confirmed") and not value.get("conflict") else ""
            assert (row[i] or "") == expected, (p["search_code"], key, row[i], expected)
            if expected:
                confirmed_cells += 1
            elif value.get("display_value"):
                blanked_candidate_cells += 1
            assert str(row[i] or "").strip() not in {"●", "•", "○", "-", "—", "O"}
    photo_rows = list(book["Фотографии"].values)
    candidate_rows = list(book["Фото-кандидаты"].values)
    assert all(row[-1] == "Подтверждён" for row in photo_rows[1:])
    assert len(candidate_rows) - 1 == 10
    assert all(row[-1] == "Связь с артикулом не подтверждена" for row in candidate_rows[1:])
    assert len(photo_rows) - 1 == 311
    ready = list(book["Готовность LG"].values)
    assert len(ready) - 1 == 12
    assert ready[0][2:4] == ("Статус задания", "Готовность карточки")
    p12 = pages["P12ED.NSAR + P12ED.USAR"].get_text(" ", strip=True)
    assert "P12ED.NSAR" in p12 and "P12ED.USAR" in p12
    assert "Русский" in p12
    assert "Характеристики с официальной страницы не получены" in p12
    assert "не отправлялся" in p12
    s3 = pages["S3WER.ALWPCOM"]
    assert "Фото-кандидаты: вариант не подтверждён" in s3.get_text(" ", strip=True)
    assert len(s3.select("#photos .photo-grid")) == 2
    tw = pages["TW4V7EB1W"].get_text(" ", strip=True)
    assert "TurboWash" in tw and "ДОПОЛНИТЕЛЬНЫЕ ОПЦИИ" in tw and "ФУНКЦИИ" in tw
    assert "137.0" in pages["W4W8LVPKZHM.APBPCOM"].get_text(" ", strip=True)
    OUT.write_bytes(content)
    with sqlite3.connect(DB) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        job_count = conn.execute("SELECT COUNT(*) FROM search_jobs").fetchone()[0]
        source_count = conn.execute("SELECT COUNT(*) FROM source_pages").fetchone()[0]
    assert integrity == "ok" and fk == 0
    assert hashlib.sha256(DB.read_bytes()).hexdigest() == original_hash
    result = {"pages": len(pages), "product_sheets": len(main_sheets), "ready_rows": len(ready)-1,
              "confirmed_cells": confirmed_cells, "candidate_cells_removed_from_main": blanked_candidate_cells,
              "confirmed_photo_rows": len(photo_rows)-1, "candidate_photo_rows": len(candidate_rows)-1,
              "db_sha256_unchanged": original_hash, "integrity": integrity, "foreign_key_violations": fk,
              "jobs": job_count, "source_pages": source_count,
              "xlsx_sha256": hashlib.sha256(content).hexdigest()}
    Path(__file__).with_name("verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

