"""LG selections from the uploaded batch: at most one row per category."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import jobs, readiness, storage

DEFAULT_STAGES = (1, 2, 3, 4, 6)


def is_lg(product: dict) -> bool:
    from .worker import LG_BRAND_ALIASES
    return product["brand"].strip().casefold() in LG_BRAND_ALIASES


def initialize(path: Path) -> None:
    with storage._connection(path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS lg_batch_selection (
            batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            PRIMARY KEY (batch_id, product_id)
        )""")


def selected_ids(path: Path, batch_id: str) -> set[int]:
    with storage._connection(path) as connection:
        return {row[0] for row in connection.execute(
            "SELECT product_id FROM lg_batch_selection WHERE batch_id=?", (batch_id,)
        )}


def default_ids(products: list[dict]) -> set[int]:
    chosen: dict[str, int] = {}
    for product in products:
        if is_lg(product):
            category = (product["category"] or "Категория не определена").strip().casefold()
            chosen.setdefault(category, product["id"])
    return set(chosen.values())


def queue_selected(path: Path, batch_id: str, product_ids: list[int], stages: list[int]) -> dict:
    if not product_ids:
        raise ValueError("Выберите хотя бы один товар LG.")
    if not stages or any(stage not in jobs.STAGE_NAMES for stage in stages):
        raise ValueError("Выберите этапы проверки.")
    if len(set(product_ids)) != len(product_ids):
        raise ValueError("Товар в выборе повторяется.")
    now = storage._now()
    with storage._connection(path) as connection:
        rows = connection.execute(
            "SELECT id,brand,category,search_code FROM products WHERE batch_id=?", (batch_id,)
        ).fetchall()
        by_id = {p["id"]: dict(p) for p in rows}
        if any(pid not in by_id or not is_lg(by_id[pid]) for pid in product_ids):
            raise ValueError("Выбор содержит строку вне этой партии LG.")
        categories = [by_id[pid]["category"].strip().casefold() for pid in product_ids]
        if len(categories) != len(set(categories)):
            raise ValueError("Выберите не более одного товара LG в каждой категории.")
        # A single transaction keeps the selection and queue in sync. The
        # existing partial unique index is the final guard against a race.
        connection.execute("DELETE FROM lg_batch_selection WHERE batch_id=?", (batch_id,))
        connection.executemany(
            "INSERT INTO lg_batch_selection(batch_id,product_id) VALUES (?,?)",
            [(batch_id, pid) for pid in product_ids],
        )
        queued = skipped = 0
        for pid in product_ids:
            active = connection.execute(
                "SELECT 1 FROM search_jobs WHERE product_id=? AND status IN ('queued','running') LIMIT 1", (pid,)
            ).fetchone()
            if active:
                skipped += 1
                continue
            job_id = uuid4().hex
            try:
                connection.execute(
                    "INSERT INTO search_jobs(id,product_id,stages_json,status,message,created_at,updated_at) "
                    "VALUES (?,?,?,'queued',?,?,?)",
                    (job_id, pid, json.dumps(sorted(set(stages))), "Ожидает worker.", now, now),
                )
            except sqlite3.IntegrityError:
                skipped += 1
                continue
            connection.execute(
                "INSERT INTO job_events(job_id,level,message,created_at) VALUES (?,'info',?,?)",
                (job_id, "Задание добавлено в очередь из партии LG.", now),
            )
            queued += 1
    return {"selected": len(product_ids), "new_jobs": queued, "already_active": skipped}


JOB_LABELS = {
    "queued": "В очереди", "running": "Выполняется", "done": "Завершено",
    "needs_review": "Нужна проверка", "error": "Ошибка", "not_found": "Не найдено",
}
VERDICT_LABELS = {
    "not_checked": "Не проверялась", "not_ready": "Не готова",
    "export_ready_with_gaps": "Есть пробелы", "export_ready": "Готова к выгрузке",
}


GAP_LABELS = {
    "no_official_full_sku_page": "Нет официальной товарной страницы с полным артикулом каталога.",
    "no_official_specifications": "Характеристики с официальной страницы не получены.",
    "no_official_gallery_photo": "Фото с точной официальной страницы не подтверждено.",
    "unresolved_conflicts": "Есть неразрешённый конфликт характеристик в официальных источниках LG.",
    "instruction_missing": "Русская инструкция не подтверждена.",
    "instruction_language_not_russian": "Найденный документ не подтверждён как русская инструкция.",
    "instruction_variant_link_unconfirmed": "Русский PDF проверен, но страница поддержки не подтверждает его связь с точным вариантом каталога.",
    "dealer_cross_check_missing": "Дилерская сверка отсутствует; она справочная.",
}


_UNSET = object()


def card_summary(path: Path, product_id: int, latest: dict | None | object = _UNSET) -> dict:
    if latest is _UNSET:
        latest = next(iter(jobs.list_jobs(path, product_id)), None)
    if latest is None:
        return {"verdict": "not_checked", "label": VERDICT_LABELS["not_checked"], "reasons": ["Проверка ещё не запускалась."]}
    card = readiness.card_readiness(path, product_id)
    reasons = []
    stage_by_gap = {"no_official_specifications": 3, "no_official_gallery_photo": 4}
    deferred = {3: "Характеристики не проверялись: этап не выбран.",
                4: "Фото не проверялись: этап не выбран."}
    for code in card["blocking_gaps"]:
        if code == "instruction_missing" and 6 not in latest["stages"]:
            reasons.append("Инструкция не проверялась: этап отложен.")
        elif code in stage_by_gap and stage_by_gap[code] not in latest["stages"]:
            reasons.append(deferred[stage_by_gap[code]])
        else:
            reasons.append(GAP_LABELS.get(code, code))
    if card["instruction"]["russian"] and not card["official_exact_regions"]:
        reasons.append("Официальная поддержка связывает русскую инструкцию с артикулом; эта связь не подтверждает характеристики и фото товара.")
    official = [source for source in jobs.get_source_pages(path, product_id)
                if source["source_key"] in {"lg_kz", "lg_ru"} and source["match_level"] == "full_sku" and not source["error"]]
    if 2 not in latest["stages"]:
        reasons.append("Описание не проверялось: этап не выбран.")
    elif official and not any(source["description"].strip() for source in official):
        reasons.append("Описание с точной официальной страницы не получено.")
    events = jobs.list_events(path, latest["id"])
    if not card["instruction"]["russian"] and any("PDF не удалось прочитать" in event["message"] for event in events):
        reasons = [reason for reason in reasons if reason != GAP_LABELS["instruction_missing"]]
        reasons.append("Полученный PDF не удалось прочитать; русская инструкция не подтверждена.")
    if 6 in latest["stages"] and "instruction_missing" in card["blocking_gaps"]:
        for event in events:
            message = event["message"].casefold()
            if any(word in message for word in ("превыш", "слишком большой", "больше лимита", "размер")) and any(word in message for word in ("файл", "pdf", "инструкц", "мб")):
                reasons.append("Файл инструкции слишком большой для установленного лимита; содержимое не проверено.")
                break
    for source in jobs.get_source_pages(path, product_id):
        if source["source_key"] == "sulpak" and "policy_host_stopped" in source["error"]:
            reasons.append(source["evidence"] or "Доступ к Sulpak остановлен после страницы проверки для другого товара; кандидат не запрашивался.")
    for source in jobs.get_source_pages(path, product_id):
        if source["source_key"] == "lg_ru" and "PDF проверен по содержимому" in source["evidence"] and "instruction_missing" in card["blocking_gaps"]:
            reasons = [reason for reason in reasons if reason != GAP_LABELS["instruction_missing"]]
            reasons.append("Найден русскоязычный PDF со страницы поддержки базовой модели; его текст не называет модель и полный артикул, поэтому связь инструкции с этим вариантом пока не подтверждена.")
            break
    color = next((row for row in jobs.get_resolved(path, product_id) if row["normalized_name"] == "color" or row["normalized_name"].startswith("color__") or row["normalized_name"].startswith("\u043e\u0442\u0434\u0435\u043b\u043a\u0430_")), None)
    if color and not color["selected_value"] and color["status"] == "official_base_only":
        reasons.append("\u0426\u0432\u0435\u0442 \u043f\u043e\u043b\u043d\u043e\u0433\u043e \u0430\u0440\u0442\u0438\u043a\u0443\u043b\u0430 \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d; \u043d\u0430\u0439\u0434\u0435\u043d \u0442\u043e\u043b\u044c\u043a\u043e \u0446\u0432\u0435\u0442 \u0431\u0430\u0437\u043e\u0432\u043e\u0439 \u043c\u043e\u0434\u0435\u043b\u0438.")
    # Include every raw fact in a conflict, even when one page repeats the label.
    conflict_names = {}
    conflict_status = {}
    for row in jobs.comparison_rows(path, product_id):
        resolved = row.get("resolved") or {}
        if resolved.get("conflict"):
            conflict_names[row["normalized_name"]] = row["display_name"]
            conflict_status[row["normalized_name"]] = resolved.get("display_status") or resolved.get("status") or ""
    pages = {source["source_key"]: source for source in jobs.get_source_pages(path, product_id)}
    conflict_facts: dict[str, list[str]] = {name: [] for name in conflict_names}
    for fact in jobs.get_facts(path, product_id):
        name = fact["normalized_name"]
        if name not in conflict_facts:
            continue
        page = pages.get(fact["source_key"], {})
        match = {
            "full_sku": "точный артикул",
            "base_model": "только базовая модель",
        }.get(page.get("match_level"), "связь с вариантом не подтверждена")
        section = fact.get("section") or "без раздела"
        detail = (f"{fact['site_name']} · раздел «{section}» · "
                  f"{fact['raw_name']}: {fact['raw_value']} · "
                  f"статус: {conflict_status[name]}; связь: {match}")
        if detail not in conflict_facts[name]:
            conflict_facts[name].append(detail)
    conflicts = [{"key": name, "name": conflict_names[name], "values": values}
                 for name, values in conflict_facts.items()]
    return {"verdict": card["verdict"], "label": VERDICT_LABELS.get(card["verdict"], card["verdict"]),
            "reasons": reasons, "conflicts": conflicts,
            "advisories": [GAP_LABELS.get(code, code) for code in card["advisory_gaps"]]}


def batch_rows(path: Path, products: list[dict], selected: set[int]) -> tuple[dict[int, dict], dict]:
    rows = {}
    counts = {"selected": len(selected), "queued": 0, "running": 0, "completed": 0, "review": 0}
    latest_by_id = {}
    if products:
        with storage._connection(path) as connection:
            job_rows = connection.execute(
                "SELECT j.* FROM search_jobs j JOIN products p ON p.id=j.product_id "
                "WHERE p.batch_id=? AND j.rowid=(SELECT MAX(j2.rowid) FROM search_jobs j2 WHERE j2.product_id=j.product_id)",
                (products[0]["batch_id"],),
            ).fetchall()
        for row in job_rows:
            item = dict(row)
            item["stages"] = json.loads(item.pop("stages_json"))
            latest_by_id[item["product_id"]] = item
    for product in products:
        if not is_lg(product):
            continue
        latest = latest_by_id.get(product["id"])
        summary = card_summary(path, product["id"], latest)
        rows[product["id"]] = {"job": latest, "job_label": JOB_LABELS.get(latest["status"], latest["status"]) if latest else "Не запускалось", "card": summary}
        if product["id"] not in selected or latest is None:
            continue
        if latest["status"] in ("queued", "running"):
            counts[latest["status"]] += 1
        else:
            counts["completed"] += 1
            if latest["status"] != "done" or summary["verdict"] != "export_ready":
                counts["review"] += 1
    return rows, counts
