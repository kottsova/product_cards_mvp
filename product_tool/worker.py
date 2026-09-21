"""Separate bounded worker for LG official and trusted fallback sources."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import time
from typing import Callable

from . import jobs
from .adapters.common import SourceDocument
from .adapters.lg import LGAdapter, lg_base_model, normalize_lg_sku
from .adapters.mechta import MechtaAdapter
from .adapters.sulpak import SulpakAdapter


LOGGER = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parents[1]
TOTAL_BUDGET_SECONDS = 60
FALLBACK_BUDGET_SECONDS = 30


def run_once(
    database: Path,
    adapter_factory: Callable[[], tuple[LGAdapter, SulpakAdapter, MechtaAdapter]] | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Process one job. No fallback adapters are created for non-LG products."""
    job = jobs.claim_next(database)
    if job is None:
        return False
    job_id, product_id = job["id"], job["product_id"]
    try:
        product = jobs.get_product(database, product_id)
        if product is None:
            jobs.finish(database, job_id, "error", "Подтверждённый товар не найден.")
            return True
        if product["brand"].strip().casefold() not in {"lg", "lg electronics", "лджи", "элджи"}:
            jobs.finish(database, job_id, "error", "Fallback Mechta и Sulpak разрешён только для LG.")
            return True

        start = clock()
        total_deadline = start + TOTAL_BUDGET_SECONDS
        full_sku = normalize_lg_sku(product["search_code"])
        base_model = lg_base_model(full_sku)
        jobs.progress(
            database, job_id, 1,
            f"LG: ищем полный артикул {full_sku}, затем базовую модель {base_model}.",
        )
        adapters = adapter_factory() if adapter_factory else (
            LGAdapter(clock=clock), SulpakAdapter(clock=clock), MechtaAdapter(clock=clock)
        )
        lg, sulpak, mechta = adapters

        official = lg.find_source(full_sku, deadline=total_deadline)
        jobs.save_source_document(
            database, product_id, official,
            update_description=2 in job["stages"],
            update_attributes=3 in job["stages"],
            update_photos=4 in job["stages"],
        )
        jobs.progress(
            database, job_id, 1,
            f"{official.site_name}: {official.match_level}. "
            f"{official.error or official.evidence}",
            level="warning" if official.error or official.match_level in {"mismatch", "unknown"} else "info",
            source_url=official.url,
        )

        # LG-specific fallback. Suppliers always receive the original full SKU.
        fallback_start = clock()
        fallback_deadline = min(total_deadline, fallback_start + FALLBACK_BUDGET_SECONDS)
        for adapter in (sulpak, mechta):
            if clock() >= fallback_deadline:
                document = SourceDocument(
                    adapter.source_key, adapter.site_name, "",
                    match_level="unknown",
                    error="Источник не проверен: исчерпан 30-секундный бюджет fallback.",
                )
            else:
                document = adapter.find_source(full_sku, deadline=fallback_deadline)
            jobs.save_source_document(
                database, product_id, document,
                update_description=2 in job["stages"],
                update_attributes=3 in job["stages"],
                update_photos=4 in job["stages"],
            )
            jobs.progress(
                database, job_id, 1,
                f"{document.site_name}: {document.match_level}. "
                f"{document.error or document.evidence}",
                level="warning" if document.error or document.match_level != "full_sku" else "info",
                source_url=document.url,
            )

        if 3 in job["stages"]:
            jobs.progress(database, job_id, 3, "Нормализуем и сравниваем характеристики.")
            jobs.resolve_product(database, product_id)

        sources = jobs.get_source_pages(database, product_id)
        identity = jobs.identification_status(sources)
        conflicts = [row for row in jobs.get_resolved(database, product_id) if row["conflict"]]
        full_confirmed = any(
            page["source_key"] in {"sulpak", "mechta"} and page["match_level"] == "full_sku"
            for page in sources
        )
        all_errors = sources and all(page["error"] for page in sources)
        if all_errors:
            jobs.finish(database, job_id, "error", "Все источники недоступны. " + identity)
        elif conflicts or not full_confirmed:
            suffix = f" Конфликтов характеристик: {len(conflicts)}." if conflicts else ""
            jobs.finish(database, job_id, "needs_review", identity + "." + suffix)
        else:
            jobs.finish(database, job_id, "done", identity + ". Сравнение завершено.")
    except Exception:
        LOGGER.exception("Unexpected source comparison failure for job %s", job_id)
        jobs.finish(
            database, job_id, "error",
            "Ошибка сравнения источников. Подробности смотрите в консоли worker.",
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker сравнения источников LG")
    parser.add_argument("--data-dir", type=Path, help="Папка с batches.sqlite3")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_interval <= 0:
        parser.error("--poll-interval должен быть больше нуля")
    root = (
        args.data_dir
        or Path(os.environ.get("PRODUCT_CARDS_DATA_DIR") or PROJECT_DIR / "data")
    ).resolve()
    database = root / "batches.sqlite3"
    jobs.initialize(database)
    recovered = jobs.recover_interrupted(database)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if recovered:
        LOGGER.warning("Возвращено в очередь после перезапуска: %s", recovered)
    LOGGER.info("Worker LG запущен; база: %s", database)
    try:
        while True:
            processed = run_once(database)
            if args.once:
                break
            if not processed:
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        LOGGER.info("Worker остановлен.")


if __name__ == "__main__":
    main()
