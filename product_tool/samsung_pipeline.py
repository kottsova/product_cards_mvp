"""The Samsung stages of worker.run_once() (Stage 26), kept out of worker.py so the pinned worker only dispatches.

  official_stage   the official page: fetched through the policy session under a per-row request budget, saved as the `samsung` source (variant level, specifications, photos), its evidence stored;
                   the page's gallery is selected for the card ONLY when the article is confirmed by the page's markup or title (`full_sku`) -- never for a base-model page or a code found only in text;
  documents_stage  the instruction files the page prints: assessed by their own text into three separate facts (see samsung.py), saved with those facts, a file without extractable text queued for a person;
  gate_dealer      the dealer fallback may only add values when its match is exact model AND variant: an unconfirmed dealer page contributes nothing;
  dealer_check     dealer values are compared with the official ones field by field: a field only the dealer has is an added field with its own source; a differing value is a dispute, sent to review (the official
                   value stays);
  finish           readiness (samsung_readiness.py), review items, and the job's final status.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from . import card_evidence, jobs, samsung_readiness, storage
from .adapters.common import SourceDocument
from .adapters.policy_session import RequestBudget, request_budget
from .adapters.samsung_source import MAX_REQUESTS_PER_ROW, levels_note
from .resolution import _signature

KEY = "samsung"
REVIEW_VARIANT, REVIEW_INSTRUCTION, REVIEW_DEALER = "samsung_variant_check", "samsung_instruction_check", "dealer_dispute"
DEVICE_REVIEW = "samsung_device_values_check"
INSTRUCTION_REVIEW_GAPS = ("instruction_text_not_extractable_manual_check", "instruction_tied_by_weaker_page", "instruction_code_relation_unverified", "instruction_not_accepted", "instruction_file_not_confirmed", "instruction_russian_candidate_not_verified")


_BATCH: list[RequestBudget | None] = [None]


@contextmanager
def batch_budget(max_total: int) -> Iterator[RequestBudget]:
    """A declared budget for a whole small batch: every job started inside shares it, so the batch's total (as well as each row's) is capped before any request is made."""
    budget = RequestBudget(max_per_row=MAX_REQUESTS_PER_ROW, max_total=max_total)
    previous, _BATCH[0] = _BATCH[0], budget
    try:
        yield budget
    finally:
        _BATCH[0] = previous


def new_budget(product_id: int) -> RequestBudget:
    budget = _BATCH[0] or RequestBudget(max_per_row=MAX_REQUESTS_PER_ROW)
    budget.begin_row(str(product_id))
    return budget


def official_stage(database: Path, job_id: str, product_id: int, product: dict[str, Any], adapter, code: str, *, stages: list[int], deadline: float, clock: Callable[[], float], budget: RequestBudget,
                   documents_deadline: float | None = None) -> SourceDocument:
    if clock() >= deadline:
        document = SourceDocument(adapter.source_key, adapter.site_name, "", error="Товар не проверен: исчерпан общий 20-секундный бюджет официального поиска.")
    else:
        with request_budget(budget):
            document = adapter.find_source(code, deadline=deadline, category=product.get("category", ""), name=product.get("name", ""))
    report = adapter.reports.get(code, {})
    device_split = None
    found = bool(document.url) and not document.error
    if found and 6 in stages and documents_deadline is not None:
        # the instruction is read BEFORE the page is saved: its technical-data tables are the evidence for which size and weight belong to which part of the product
        with request_budget(budget):
            adapter.pending[code] = adapter.find_documents(document, code, deadline=documents_deadline)
    if found and hasattr(adapter, "split_devices"):
        attributes, device_split = adapter.split_devices(document, code)
        if device_split["tables"]:
            document.attributes = attributes
    jobs.save_source_document(database, product_id, document, update_description=2 in stages, update_attributes=3 in stages, update_photos=4 in stages)
    report = adapter.reports.get(code, {})
    card_evidence.save(database, product_id, "samsung_page", {**{key: report.get(key) for key in ("article", "route", "steps", "page_url", "buy_page_url", "identity", "specs", "photos", "document_links", "gaps", "missing_fields", "outcome", "halted")},
                                                              "device_split": device_split})
    if device_split and device_split["tables"]:
        jobs.progress(database, job_id, 3, f"Samsung: размер и вес разделены по устройствам только по явной связи (таблицы инструкции с названием устройства): отнесено {len(device_split['assigned'])}, без связи оставлено {len(device_split['unassigned'])} (оба исходных значения сохранены, нужна проверка).",
                      level="warning" if device_split["unassigned"] else "info")
    selected = ""
    bound = list((report.get("photos") or {}).get("bound_by_asset_path") or [])
    if 4 in stages and document.photos and not document.error:
        if document.match_level == "full_sku":
            jobs.set_photo_selection(database, product_id, [], mode="source", source_key=KEY)
            selected = "all"
        elif bound:
            # The page does not confirm the variant by its markup or title, but these photos' own asset paths name exactly the catalog code: bound to the variant by official data.
            select_photos(database, product_id, bound)
            selected = "bound"
    jobs.progress(database, job_id, 1, f"{document.site_name}: {document.match_level}. {document.error or document.evidence}", level="info" if document.match_level == "full_sku" and not document.error else "warning", source_url=document.url)
    if report.get("outcome") == "page_read":
        photos = report["photos"]
        note = ("выбраны для карточки" if selected == "all" else f"выбрано {len(bound)}: путь файла называет точно код каталога (привязка к варианту); остальные не выбраны" if selected == "bound"
                else "не выбраны: вариант не подтверждён, привязки к варианту нет — нужна ручная проверка" if document.photos else "нет")
        jobs.progress(database, job_id, 1, f"Samsung: характеристик {report['specs']}; фото {photos['full_size']} ({note}); миниатюры ({photos['thumbnails']}) и 3D-файлы ({photos['three_d_excluded']}) фото не считаются.", source_url=document.url)
    if report.get("halted"):
        jobs.progress(database, job_id, 1, f"Samsung: запросы остановлены политикой доступа: {report['halted']}", level="warning")
    return document


def select_photos(database: Path, product_id: int, asset_keys: list[str]) -> None:
    """Select these Samsung gallery photos for the card (the others, and a person's own choice for other photos, stay as they are)."""
    with storage._connection(database) as connection:
        connection.executemany("UPDATE photo_candidates SET selected=1 WHERE product_id=? AND source_key=? AND kind='product_gallery' AND asset_key=?", [(product_id, KEY, key) for key in asset_keys])


def documents_stage(database: Path, job_id: str, product_id: int, adapter, document: SourceDocument, code: str, *, deadline: float, budget: RequestBudget) -> None:
    if document.url and not document.error:
        pending = getattr(adapter, "pending", {}).pop(code, None)
        if pending is None:
            with request_budget(budget):
                pending = adapter.find_documents(document, code, deadline=deadline)
        documents, reason = pending
        jobs.save_documents(database, product_id, adapter.source_key, documents)
        report = adapter.reports.get(code, {})
        card_evidence.save(database, product_id, "samsung_documents", {"documents": report.get("documents", []), "document_links_on_page": (card_evidence.load(database, product_id, "samsung_page") or {}).get("document_links", []),
                                                                       "page_model_data": report.get("page_model_data") or {}, "outcome": report.get("documents_outcome", ""), "halted": report.get("halted", ""), "steps": [s for s in report.get("steps", []) if s["step"] == "document"]})
        russian = sum(1 for d in documents if d.language == "Русский")
        message = (f"Samsung: инструкций сохранено {len(documents)}; русских по тексту: {russian}." + ("" if russian else " " + reason)) if documents else reason
        jobs.progress(database, job_id, 6, message, level="info" if russian else "warning", source_url=document.url)
        for entry in report.get("documents", []):
            facts = entry.get("facts")
            if facts:
                jobs.progress(database, job_id, 6, f"Файл {entry.get('file', '')}: {entry['state']}; {levels_note(facts)}.", level="info" if entry["state"] == "instruction_saved" else "warning", source_url=entry.get("final_url", ""))
    else:
        jobs.save_documents(database, product_id, adapter.source_key, [])
        card_evidence.save(database, product_id, "samsung_documents", {"documents": [], "document_links_on_page": [], "outcome": "official_page_unavailable", "halted": ""})
        jobs.progress(database, job_id, 6, "Инструкции Samsung не проверены: официальная страница не получена.", level="warning")


def dealer_missing_fields(database: Path, product_id: int, stages: list[int]) -> list[str]:
    """What the dealer link request asks for (Stage 30). Same as the generic per-row check for characteristics and photos; the instruction counts as missing until a FULL RUSSIAN instruction is
    confirmed -- a saved English file or a brief multilingual guide with a Russian section does not close it. A request is only text for a person: no dealer request is made without a verified exact URL."""
    missing = []
    if 3 in stages and not jobs.get_facts(database, product_id):
        missing.append("характеристики")
    if 4 in stages and not jobs.get_photo_candidates(database, product_id, include_excluded=False):
        missing.append("фото")
    if 6 in stages and not samsung_readiness.full_russian_instruction_confirmed(database, product_id):
        missing.append("полная русская инструкция")
    return missing


def gate_dealer(dealer_document: SourceDocument) -> SourceDocument:
    """A dealer page that is not an exact model-and-code match contributes no values at all (it may only be reported)."""
    if dealer_document.match_level != "model_and_code_confirmed" and (dealer_document.attributes or dealer_document.photos or dealer_document.photo_candidates):
        dealer_document.evidence = (dealer_document.evidence + " Значения дилера не используются: точное совпадение модели и варианта не подтверждено.").strip()
        dealer_document.attributes, dealer_document.photos, dealer_document.photo_candidates = [], [], []
    return dealer_document


def dealer_check(database: Path, product_id: int, dealer_document: SourceDocument) -> dict[str, Any]:
    facts = jobs.get_facts(database, product_id)
    official: dict[str, set] = {}
    dealer: dict[str, dict] = {}
    for fact in facts:
        if fact["source_key"] == KEY:
            official.setdefault(fact["normalized_name"], set()).add(_signature(fact))
        elif fact["source_key"] == "dns":
            dealer.setdefault(fact["normalized_name"], fact)
    added, disputes, agreed = [], [], 0
    for name, fact in dealer.items():
        if name not in official:
            added.append({"field": name, "value": fact["normalized_value"], "source": "dns", "url": dealer_document.url})
        elif _signature(fact) in official[name]:
            agreed += 1
        else:
            disputes.append({"field": name, "dealer_value": fact["normalized_value"], "dealer_source": "dns", "official_values": sorted(str(s[0]) for s in official[name]), "resolution": "official value kept; sent to review"})
    payload = {"dns_match_level": dealer_document.match_level, "dns_url": dealer_document.url, "added_fields": added, "disputes": disputes, "agreements": agreed, "note": dealer_document.evidence[:400]}
    card_evidence.save(database, product_id, "dealer", payload)
    if disputes:
        card_evidence.replace_review(database, product_id, REVIEW_DEALER, f"Дилер расходится с официальным Samsung по полям: {', '.join(d['field'] for d in disputes[:8])}.", {"disputes": disputes})
    else:
        card_evidence.clear_review(database, product_id, REVIEW_DEALER)
    return payload


def finish(database: Path, job_id: str, product_id: int, stages: list[int], document: SourceDocument, dealer_document: SourceDocument, dealer_summary: str, budget: RequestBudget | None = None) -> str:
    if budget is not None:
        card_evidence.save(database, product_id, "samsung_requests", {"max_per_row": budget.max_per_row, "spent": budget.row, "batch_spent_so_far": budget.total, "max_total": budget.max_total, "log": [e for e in budget.log if e["row"] == budget.row_key]})
    readiness = samsung_readiness.card_readiness(database, product_id)
    text = " " + samsung_readiness.readiness_text(readiness)
    counts = jobs.result_counts(database, product_id)
    gaps = set(readiness["blocking_gaps"])
    page = card_evidence.load(database, product_id, "samsung_page") or {}
    if readiness["page_match_level"] not in ("full_sku", "none"):
        card_evidence.replace_review(database, product_id, REVIEW_VARIANT, "Вариант каталога не подтверждён содержимым страницы: " + ("; ".join(readiness["open_variant_differences"]) or readiness["page_match_level"]), {"page_match_level": readiness["page_match_level"], "identity": page.get("identity")})
    else:
        card_evidence.clear_review(database, product_id, REVIEW_VARIANT)
    if gaps & set(INSTRUCTION_REVIEW_GAPS):
        card_evidence.replace_review(database, product_id, REVIEW_INSTRUCTION, "Инструкция требует ручной проверки: " + ", ".join(sorted(gaps & set(INSTRUCTION_REVIEW_GAPS))), {"instruction": readiness["instruction"]})
    else:
        card_evidence.clear_review(database, product_id, REVIEW_INSTRUCTION)
    if "device_values_link_not_established" in gaps:
        card_evidence.replace_review(database, product_id, DEVICE_REVIEW, "Размер/вес без явной связи с устройством (оба исходных значения сохранены): " + "; ".join(f"{u['row']} {u['value']} ({u['group']})" for u in readiness["device_values_unassigned"][:6]), {"unassigned": readiness["device_values_unassigned"]})
    else:
        card_evidence.clear_review(database, product_id, DEVICE_REVIEW)
    jobs.progress(database, job_id, max(stages), text.strip(), level="info" if readiness["verdict"] == "export_ready" else "warning")
    summary = f" Реальных конфликтов: {counts['conflicts']}; расхождений с дилером: {len(readiness['dealer_disputes'])}."
    found = bool(document.url) and not document.error
    identity = document.error or document.evidence
    request_text = f" {dealer_document.evidence}" if dealer_document.match_level == "dealer_url_needed" else ""
    if not found:
        if document.error:
            jobs.finish(database, job_id, "error", f"Официальная страница Samsung недоступна: {document.error}" + summary + dealer_summary + request_text)
        else:
            jobs.finish(database, job_id, "needs_review", "Официальная страница Samsung не найдена: " + identity + summary + dealer_summary + request_text + text)
        return "not_found" if not document.error else "error"
    if counts["conflicts"] or readiness["dealer_disputes"] or document.match_level != "full_sku":
        jobs.finish(database, job_id, "needs_review", "Samsung: " + identity + summary + dealer_summary + request_text + text)
        return "needs_review"
    jobs.finish(database, job_id, "done", "Samsung: " + identity + summary + dealer_summary + text)
    return "done"
