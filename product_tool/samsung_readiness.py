"""Card readiness for a Samsung row, kept apart from the job status (Stage 26). Modelled on readiness.py (LG), with the evidence levels Samsung needs kept separate:

  * variant: `full_sku` (the article in the page's markup or title) is the only level that confirms a variant unconditionally. `code_in_page_text` (the article only in the visible text) and
    `base_model` (same base model, another regional/colour code) are reported as their own gaps; the open differences (region, colour) are listed as they are;
  * instruction, three facts kept apart for the best saved instruction: its language by TEXT; its tie to the product by the official page (exact page / code-in-text page / base-model page);
    and what the TEXT names (the exact catalog code / a family mask / only the code the page's link declares / nothing). Nothing here treats the codes SC and VC (or any two codes) as equal;
  * a file whose text cannot be extracted is a manual check, never an accepted instruction;
  * a dealer dispute with an official value is a blocking gap (the official value stays).

Verdicts: `export_ready` | `export_ready_with_gaps` | `needs_verification` (an official page and its data exist, the variant is not confirmed by the page's content) | `not_ready` (no official
page, no specifications or no photo at all). The owner has not adopted a Samsung rule for an instruction whose text does not name the model, so that case stays a blocking gap, listed openly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import card_evidence, jobs
from .adapters.samsung import brief_guide_note, is_brief_guide

KEY = "samsung"
BLOCKING_ORDER = ("no_official_page", "no_official_specifications", "no_official_photo", "variant_base_model_only", "variant_code_only_in_page_text", "variant_not_shown_on_page", "photos_not_selected_variant_open",
                  "unresolved_conflicts", "device_values_link_not_established", "dealer_dispute", "instruction_not_checked", "instruction_no_exact_page", "instruction_missing", "instruction_file_not_confirmed", "instruction_russian_candidate_not_verified", "instruction_language_not_russian", "instruction_full_russian_manual_missing", "instruction_text_not_extractable_manual_check", "instruction_tied_by_weaker_page",
                  "instruction_code_relation_unverified", "instruction_not_accepted")
# An accepted Russian instruction whose PDF does not name the exact catalog code always keeps this mark (a family mask, the page's own link, or the page's own model data is the basis).
ADVISORY_ORDER = ("instruction_exact_code_not_in_pdf", "instruction_only_non_russian_file_saved", "instruction_brief_guide_russian_section", "dealer_cross_check_missing")


def _best_instruction(documents: list[dict[str, Any]], evidence: dict[str, Any] | None) -> dict[str, Any]:
    """The Russian instruction to judge (the primary one), with its three facts read from the stored evidence, or a description of why there is none."""
    facts_by_url = {d.get("final_url"): d.get("facts") for d in (evidence or {}).get("documents", []) if d.get("facts")}
    samsung_docs = [d for d in documents if d["source_key"] == KEY]
    russian = [d for d in samsung_docs if d["language"] == "Русский"]
    accepted = [d for d in russian if (facts_by_url.get(d["direct_url"]) or {}).get("acceptance", {}).get("accepted")]
    chosen = (accepted or russian or samsung_docs or [None])[0]
    entries = (evidence or {}).get("documents", [])
    manual = [d for d in entries if d.get("state") == "manual_check_text_not_extractable"]
    not_obtained = [d for d in entries if d.get("state") in ("reachable_but_not_a_complete_pdf", "candidate_link_unreachable", "pdf_unreadable") and d.get("language_hint_from_file_name") == "RU"]
    brief = [d for d in samsung_docs if is_brief_guide(facts_by_url.get(d["direct_url"]) or {})]
    result = {"saved": len(samsung_docs), "russian_saved": len(russian), "brief_guides": [{"direct_url": d["direct_url"], "pages": (facts_by_url[d["direct_url"]].get("russian_section") or {}).get("pages", []), "note": brief_guide_note(facts_by_url[d["direct_url"]])} for d in brief], "manual_check_files": len(manual), "russian_named_file_not_obtained": len(not_obtained), "links_on_page": len((evidence or {}).get("document_links_on_page", [])) if evidence else 0, "facts": None, "direct_url": ""}
    if chosen:
        result["facts"] = facts_by_url.get(chosen["direct_url"])
        result["direct_url"] = chosen["direct_url"]
    return result


def full_russian_instruction_confirmed(database: Path, product_id: int) -> bool:
    """True only for a saved instruction that is Russian by its text AND accepted by the rules: a file in another language, a brief multilingual guide with a Russian section, a file whose text
    cannot be read and a Russian file left to a person do not count."""
    instruction = _best_instruction(jobs.get_documents(database, product_id), card_evidence.load(database, product_id, "samsung_documents"))
    return bool(instruction["russian_saved"] and ((instruction["facts"] or {}).get("acceptance") or {}).get("accepted"))


GAP_TEXT = {
    "no_official_page": "официальная страница Samsung не найдена или недоступна",
    "no_official_specifications": "на официальной странице нет таблицы характеристик",
    "no_official_photo": "на официальной странице нет галереи товара",
    "variant_base_model_only": "страница той же базовой модели, но другого варианта; различия остаются открытыми",
    "variant_code_only_in_page_text": "артикул каталога виден на странице только в произвольном тексте, а не в разметке товара и не в заголовке",
    "variant_not_shown_on_page": "страница найдена, но артикул каталога на ней не показан",
    "photos_not_selected_variant_open": "фото найдены, но ни одно не привязано к варианту (путь файла не называет код каталога) и человек их не подтверждал",
    "unresolved_conflicts": "у источника два разных значения под одним именем поля",
    "device_values_link_not_established": "размер или вес относятся к нескольким устройствам, а явной связи значения с устройством нет (порядок строк не считается связью)",
    "dealer_dispute": "значение дилера расходится с официальным",
    "instruction_not_checked": "этап инструкций не запрашивался",
    "instruction_no_exact_page": "ссылка на инструкцию для кода каталога не проверена: точная официальная страница не найдена или недоступна",
    "instruction_missing": "на официальной странице нет ссылки на руководство",
    "instruction_file_not_confirmed": "ссылка на руководство есть, но файл не получен и не подтверждён",
    "instruction_russian_candidate_not_verified": "кандидат на русскую инструкцию (по имени файла в ссылке) не получен целиком или не прочитан; это не значит, что русской инструкции нет; файл на другом языке её не заменяет",
    "instruction_language_not_russian": "все прочитанные файлы по тексту не русские, русского раздела в них нет",
    "instruction_full_russian_manual_missing": "полной русской инструкции нет: сохранена только краткая памятка, в которой есть русский раздел; она полным руководством не считается",
    "instruction_text_not_extractable_manual_check": "текст файла не извлекается (скан или нарисованный текст): язык и модель проверяются вручную",
    "instruction_tied_by_weaker_page": "файл связан страницей, которая подтверждает артикул только текстом (или только базовую модель)",
    "instruction_code_relation_unverified": "PDF называет другой код, а данные страницы не объявляют его названием модели этого товара",
    "instruction_not_accepted": "инструкция не принята по правилам этапа 27",
    "instruction_exact_code_not_in_pdf": "точный код каталога в PDF не назван (принято по пометке: маска семейства, связь точной страницы или данные страницы)",
    "instruction_only_non_russian_file_saved": "сохранён файл не на русском языке; он не подменяет русский",
    "instruction_brief_guide_russian_section": "сохранена краткая памятка (краткое руководство) с русским разделом; она не закрывает пробел по полной русской инструкции",
    "dealer_cross_check_missing": "проверенного точного адреса у дилера нет, DNS запросов не делает; сверка с дилером не выполнялась",
}


def card_readiness(database: Path, product_id: int) -> dict[str, Any]:
    sources = jobs.get_source_pages(database, product_id)
    page = next((s for s in sources if s["source_key"] == KEY), None)
    facts = [f for f in jobs.get_facts(database, product_id) if f["source_key"] == KEY]
    photos = [p for p in jobs.get_photo_candidates(database, product_id, include_excluded=False) if p["source_key"] == KEY and p["kind"] == "product_gallery"]
    documents = jobs.get_documents(database, product_id)
    conflicts = jobs.result_counts(database, product_id)["conflicts"]
    page_evidence = card_evidence.load(database, product_id, "samsung_page") or {}
    document_evidence = card_evidence.load(database, product_id, "samsung_documents")
    dealer = card_evidence.load(database, product_id, "dealer") or {}
    level = page["match_level"] if page and not page["error"] else ""
    open_differences = (page_evidence.get("identity") or {}).get("open_differences", [])
    dealer_confirmed = [s["source_key"] for s in sources if s["source_key"] == "dns" and s["match_level"] == "model_and_code_confirmed" and not s["error"]]

    blocking: list[str] = []
    advisory: list[str] = []
    if not page or page["error"] or not page["url"]:
        blocking.append("no_official_page")
    else:
        if not facts:
            blocking.append("no_official_specifications")
        if not photos:
            blocking.append("no_official_photo")
        if level != "full_sku":
            blocking.append({"base_model": "variant_base_model_only", "code_in_page_text": "variant_code_only_in_page_text"}.get(level, "variant_not_shown_on_page"))
            if photos and not any(p["selected"] for p in photos):
                blocking.append("photos_not_selected_variant_open")
        elif photos and not any(p["selected"] for p in photos):
            blocking.append("photos_not_selected_variant_open")
    if conflicts:
        blocking.append("unresolved_conflicts")
    device_split = page_evidence.get("device_split") or {}
    if device_split.get("unassigned"):
        blocking.append("device_values_link_not_established")      # size / weight rows of a product with named parts whose device no explicit evidence gives: both source values stay, a person checks
    if dealer.get("disputes"):
        blocking.append("dealer_dispute")

    instruction = _best_instruction(documents, document_evidence)
    if not page or page["error"] or not page["url"]:
        blocking.append("instruction_no_exact_page")
    else:
        if not instruction["saved"]:
            blocking.append("instruction_not_checked" if document_evidence is None else "instruction_text_not_extractable_manual_check" if instruction["manual_check_files"]
                            else "instruction_russian_candidate_not_verified" if instruction["russian_named_file_not_obtained"] else "instruction_file_not_confirmed" if instruction["links_on_page"] else "instruction_missing")
        elif not instruction["russian_saved"]:
            if instruction["russian_named_file_not_obtained"]:
                # a file whose link name says Russian could not be read: a CANDIDATE for the Russian instruction, not proof that none exists; a saved file in another language does not stand in for it
                blocking.append("instruction_russian_candidate_not_verified")
                advisory.append("instruction_only_non_russian_file_saved")
            elif instruction["brief_guides"]:
                blocking.append("instruction_full_russian_manual_missing")
                advisory.append("instruction_brief_guide_russian_section")
            else:
                blocking.append("instruction_language_not_russian")
        else:
            acceptance = (instruction["facts"] or {}).get("acceptance") or {}
            if not acceptance:
                blocking.append("instruction_not_accepted")     # evidence without an acceptance decision is never accepted
            elif not acceptance["accepted"]:
                blocking.append({"page_tie_not_exact": "instruction_tied_by_weaker_page", "link_code_relation_unverified": "instruction_code_relation_unverified"}.get(acceptance["basis"], "instruction_not_accepted"))
            elif acceptance["basis"] != "exact_code_in_pdf":
                advisory.append("instruction_exact_code_not_in_pdf")
    if not dealer_confirmed:
        advisory.append("dealer_cross_check_missing")

    basics = not ({"no_official_page", "no_official_specifications", "no_official_photo"} & set(blocking))
    identity_open = level != "full_sku"
    verdict = "not_ready" if not basics else "needs_verification" if identity_open else "export_ready_with_gaps" if blocking else "export_ready"
    facts_doc = instruction["facts"] or {}
    all_gaps = [g for g in BLOCKING_ORDER if g in blocking] + [g for g in ADVISORY_ORDER if g in advisory]
    detail = {"variant_base_model_only": "; ".join(open_differences), "unresolved_conflicts": ", ".join(sorted(r["normalized_name"] for r in jobs.get_resolved(database, product_id) if r["conflict"])),
              "device_values_link_not_established": "; ".join(f"{u['row']} {u['value']} ({u['group']})" for u in device_split.get("unassigned", [])[:4]),
              "instruction_exact_code_not_in_pdf": (facts_doc.get("acceptance") or {}).get("note", ""), "photos_not_selected_variant_open": f"найдено {len(photos)}",
              "instruction_brief_guide_russian_section": "; ".join(b["note"] for b in instruction["brief_guides"])}
    reasons = {g: GAP_TEXT[g] + (f": {detail[g]}" if detail.get(g) else "") for g in all_gaps}
    return {
        "gap_reasons": reasons,
        "verdict": verdict, "blocking_gaps": [g for g in BLOCKING_ORDER if g in blocking], "advisory_gaps": [g for g in ADVISORY_ORDER if g in advisory], "gaps": [g for g in BLOCKING_ORDER if g in blocking] + [g for g in ADVISORY_ORDER if g in advisory],
        "page_match_level": level or "none", "open_variant_differences": open_differences, "official_facts": len(facts), "official_photos": len(photos), "official_photos_selected": sum(1 for p in photos if p["selected"]),
        "real_conflicts": conflicts, "conflict_fields": sorted(r["normalized_name"] for r in jobs.get_resolved(database, product_id) if r["conflict"]), "device_values_unassigned": device_split.get("unassigned", []), "device_values_assigned": len(device_split.get("assigned", [])), "dealer_disputes": dealer.get("disputes", []), "open_reviews": [r["review_type"] for r in card_evidence.open_reviews(database, product_id)],
        "instruction": {"saved": instruction["saved"], "russian_saved": instruction["russian_saved"], "manual_check_files": instruction["manual_check_files"], "brief_guides": instruction["brief_guides"],
                        "russian_by_text": facts_doc.get("russian_by_text") if facts_doc else None, "tied_by_official_page": facts_doc.get("tied_by_official_page") if facts_doc else None,
                        "names_catalog_code_exactly": (facts_doc.get("names_catalog_model") or {}).get("exact") if facts_doc else None, "names_family_mask": (facts_doc.get("names_catalog_model") or {}).get("family_mask") if facts_doc else None,
                        "names_link_model_only": bool(facts_doc and not (facts_doc.get("names_catalog_model") or {}).get("exact") and not (facts_doc.get("names_catalog_model") or {}).get("family_mask")
                                                     and ((facts_doc.get("names_link_model") or {}).get("exact") or (facts_doc.get("names_link_model") or {}).get("family_mask"))),
                        "acceptance_basis": (facts_doc.get("acceptance") or {}).get("basis") if facts_doc else None, "accepted": (facts_doc.get("acceptance") or {}).get("accepted") if facts_doc else None,
                        "mark": (facts_doc.get("acceptance") or {}).get("note", "") if facts_doc else "", "code_relation": (facts_doc.get("acceptance") or {}).get("code_relation", {}) if facts_doc else {},
                        "assessed_from": facts_doc.get("assessed_from", "file") if facts_doc else None},
        "dealer_confirmed": dealer_confirmed,
    }


def readiness_text(readiness: dict[str, Any]) -> str:
    gaps = ", ".join(readiness["gaps"]) or "нет"
    opened = f" Открыто по варианту: {'; '.join(readiness['open_variant_differences'])}." if readiness["open_variant_differences"] else ""
    return f"Готовность карточки Samsung к выгрузке: {readiness['verdict']}; пробелы: {gaps}.{opened}"
