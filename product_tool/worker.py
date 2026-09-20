"""Separate worker for queued product searches. Run with python -m product_tool.worker."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import time
from typing import Callable

from . import jobs
from .adapters.lg import LGAdapter, LGSourceError, match_kind


LOGGER = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parents[1]
STAGE_START = {
    1: "Ищем точную страницу LG.",
    2: "Читаем описание с официальной страницы.",
    3: "Читаем характеристики с официальной страницы.",
    4: "Читаем фото с официальной страницы.",
}


def run_once(database: Path, adapter_factory: Callable[[], LGAdapter] = LGAdapter) -> bool:
    """Process one queued job; return False when the queue is empty."""
    job = jobs.claim_next(database)
    if job is None:
        return False
    job_id = job["id"]
    product_id = job["product_id"]
    try:
        product = jobs.get_product(database, product_id)
        if product is None:
            jobs.finish(database, job_id, "error", "Подтверждённый товар не найден.")
            return True
        article = product["search_code"]
        adapter = adapter_factory()
        existing = jobs.get_result(database, product_id)
        url = existing["page_url"]
        needs_link = 1 in job["stages"] or existing["match_status"] != "exact" or not url
        if needs_link:
            jobs.progress(database, job_id, 1, STAGE_START[1])
            found = adapter.find_page(article)
            if found.status == "needs_review":
                jobs.save_review(database, product_id, found.candidate_urls)
                jobs.progress(
                    database, job_id, 1, found.message, level="warning",
                    source_url=found.candidate_urls[0] if found.candidate_urls else "",
                )
                jobs.finish(database, job_id, "needs_review", found.message)
                return True
            if found.status == "not_found":
                jobs.finish(database, job_id, "not_found", found.message)
                return True
            if found.status != "exact" or not found.page_url:
                raise LGSourceError("LG не подтвердил точную страницу модели.")
            url = found.page_url
            jobs.save_link(database, product_id, url, found.candidate_urls)
            jobs.progress(database, job_id, 1, found.message, source_url=url)

        data_stages = [stage for stage in job["stages"] if stage in (2, 3, 4)]
        if not data_stages:
            jobs.finish(database, job_id, "done", "Ссылка на точную карточку LG сохранена.")
            return True

        page = adapter.fetch_page(url)
        if match_kind(page, article) != "exact":
            jobs.save_review(database, product_id, (url,))
            jobs.finish(
                database, job_id, "needs_review",
                "Сохранённая страница больше не подтверждает полный артикул. Нужна проверка.",
            )
            return True

        incomplete = False
        for stage in data_stages:
            jobs.progress(database, job_id, stage, STAGE_START[stage], source_url=url)
            if stage == 2:
                field, value = "description", adapter.extract_description(page.soup)
            elif stage == 3:
                field, value = "attributes", adapter.extract_attributes(page.soup)
            else:
                field, value = "photos", adapter.extract_photos(page.soup, url)
            if not value:
                incomplete = True
                jobs.progress(
                    database, job_id, stage,
                    f"{jobs.STAGE_NAMES[stage]}: на странице LG данных не найдено.",
                    level="warning", source_url=url,
                )
                continue
            jobs.save_field(database, product_id, field, value, url)
            jobs.progress(
                database, job_id, stage,
                f"{jobs.STAGE_NAMES[stage]} сохранены ({len(value)}).",
                source_url=url,
            )
        if incomplete:
            jobs.finish(
                database, job_id, "needs_review",
                "Точная страница найдена, но часть выбранных данных отсутствует. Нужна проверка.",
            )
        else:
            jobs.finish(database, job_id, "done", "Выбранные этапы LG завершены.")
    except LGSourceError as exc:
        jobs.finish(database, job_id, "error", str(exc))
    except Exception:
        LOGGER.exception("Unexpected LG worker failure for job %s", job_id)
        jobs.finish(
            database, job_id, "error",
            "Ошибка обработки LG. Подробности смотрите в консоли worker.",
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker поиска товаров LG")
    parser.add_argument("--data-dir", type=Path, help="Папка с batches.sqlite3")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="Ожидание между проверками очереди")
    parser.add_argument("--once", action="store_true", help="Обработать одно задание и завершить работу")
    args = parser.parse_args()
    if args.poll_interval <= 0:
        parser.error("--poll-interval должен быть больше нуля")
    root = (args.data_dir or Path(os.environ.get("PRODUCT_CARDS_DATA_DIR") or PROJECT_DIR / "data")).resolve()
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