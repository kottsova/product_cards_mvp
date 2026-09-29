"""Apply the saved official support candidate to product 4 without HTTP."""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from product_tool import jobs
from product_tool.adapters.lg_support import LGSupportAdapter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DB = ROOT / "data/batches.sqlite3"
BACKUP = OUT / "batches_before_support.sqlite3"
SAVED = next((OUT / "official_support").glob("001_*.gz"))
ARTICLE = "P12ED.NSAR + P12ED.USAR"
PRODUCT_ID = 4


class Response:
    status_code = 200
    url = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"

    def __init__(self):
        with gzip.open(SAVED, "rt", encoding="utf-8") as stream:
            self.text = stream.read()
        self.content = self.text.encode()

    def raise_for_status(self):
        pass


class ReplayHttp:
    def get(self, url, **_):
        if url != Response.url:
            raise AssertionError(f"Unrecorded URL: {url}")
        return Response()


def main():
    with sqlite3.connect(DB) as source:
        active = source.execute("SELECT count(*) FROM search_jobs WHERE status IN ('queued','running')").fetchone()[0]
        product = source.execute("SELECT id,search_code,batch_id FROM products WHERE id=?", (PRODUCT_ID,)).fetchone()
        before = source.execute("SELECT id,status,message FROM search_jobs WHERE product_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (PRODUCT_ID,)).fetchone()
        if active or product is None or product[1] != ARTICLE:
            raise RuntimeError(f"Unsafe batch state: active={active}, product={product}")
        if BACKUP.exists():
            raise RuntimeError("Backup already exists; refusing a second application")
        with sqlite3.connect(BACKUP) as target:
            source.backup(target)
    adapter = LGSupportAdapter(http=ReplayHttp())
    document = adapter.find_source(ARTICLE, deadline=10**10)
    if document.match_level != "support_candidate" or document.attributes or document.photos:
        raise RuntimeError("Saved response no longer has the expected limited evidence")
    jobs.save_source_document(DB, PRODUCT_ID, document)
    new_message = (
        "Официальная страница поддержки LG открыта как кандидат: содержимое сохранённого ответа "
        "не подтвердило оба полных кода комплекта. Русская инструкция, характеристики и фото "
        "ещё не проверены. Статус задания: нужна проверка; карточка к выгрузке не готова."
    )
    with sqlite3.connect(DB) as connection:
        connection.execute("UPDATE search_jobs SET message=? WHERE id=? AND status='needs_review'", (new_message, before[0]))
        connection.execute(
            "INSERT INTO job_events(job_id,level,message,created_at) VALUES (?, 'warning', ?, CURRENT_TIMESTAMP)",
            (before[0], "Offline evidence update: " + new_message),
        )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        row_count = connection.execute("SELECT count(*) FROM products WHERE batch_id=?", (product[2],)).fetchone()[0]
    result = {"product_id": PRODUCT_ID, "batch_id": product[2], "existing_job_id": before[0],
              "old_status": before[1], "old_message": before[2], "new_message": new_message,
              "source_url": document.url, "match_level": document.match_level,
              "batch_products": row_count, "integrity_check": integrity}
    (OUT / "applied_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
