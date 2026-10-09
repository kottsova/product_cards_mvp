"""Card readiness for export, kept apart from the job status (Stage 21).

The job status says whether the source comparison finished cleanly: for an LG row `done` means an official page whose
article matches the full row article (variant confirmed) and no real conflict between values. It says nothing about
whether the card is complete. This module computes that separately, from what is stored for the product, and names
every gap -- a missing instruction, an instruction whose language is not stated as Russian, a missing dealer
cross-check -- so none of them hides behind `done`.

Verdicts:
  export_ready            official full-article page, specifications, gallery photos, no real conflict, and a
                          Russian instruction (advisory gaps, i.e. the dealer cross-check, are still listed)
  export_ready_with_gaps  official full-article page, specifications and gallery photos, but a blocking gap remains
                          (no instruction, instruction language not Russian, a real conflict)
  not_ready               no official full-article page, or no official specifications, or no official gallery photo
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import jobs, manual_status
from .lg_identity import allows_evidence, document_tied_to_article, source_relation

OFFICIAL_KEYS = frozenset({"lg_kz", "lg_ru", "lg_global"})
DEALER_KEYS = frozenset({"sulpak", "dns"})
DEALER_CONFIRMED_LEVELS = frozenset({"full_sku", "model_and_code_confirmed"})

BLOCKING = ("no_official_full_sku_page", "no_official_specifications", "no_official_gallery_photo", "unresolved_conflicts", "instruction_missing", "instruction_language_not_russian", "instruction_variant_link_unconfirmed")
ADVISORY = ("dealer_cross_check_missing",)


def card_readiness(database: Path, product_id: int) -> dict[str, Any]:
    product = jobs.get_product(database, product_id) or {}
    from .xbox_identity import BRANDS as XBOX_BRANDS
    if product.get('brand','').strip().casefold() in XBOX_BRANDS:
        from . import xbox_pipeline
        return xbox_pipeline.card_readiness(database,product_id)
    from .playstation_identity import BRANDS as PLAYSTATION_BRANDS
    if product.get('brand','').strip().casefold() in PLAYSTATION_BRANDS:
        from . import playstation_pipeline
        return playstation_pipeline.card_readiness(database,product_id)
    if product.get('brand','').strip().upper() == 'APPLE':
        from . import apple_pipeline
        result=apple_pipeline.card_readiness(database,product_id)
        result.update(gaps=result['blocking_gaps']+result['advisory_gaps'],official_exact_regions=['apple_model'] if result['identity'].get('model')=='model_confirmed' else [],instruction={'russian':result['manual_status']=='Проверена'})
        return result
    sources = jobs.get_source_pages(database, product_id)
    facts = jobs.get_facts(database, product_id)
    photos = jobs.get_photo_candidates(database, product_id, include_excluded=False)
    product = jobs.get_product(database, product_id) or {}
    article = product.get("search_code", "")
    documents = (manual_status.effective_documents(database, product_id, article)
                 if product.get("brand", "").strip().upper() == "LG"
                 else jobs.get_documents(database, product_id))
    conflicts = jobs.result_counts(database, product_id)["conflicts"]

    exact_regions = sorted(s["source_key"] for s in sources if s["source_key"] in OFFICIAL_KEYS and s["match_level"] == "full_sku" and not s["error"])
    product_relations = {s["source_key"]: source_relation(s["source_key"], s["match_level"])
                         for s in sources if not s["error"]}
    official_facts = sum(1 for f in facts if f["source_key"] in OFFICIAL_KEYS)
    exact_facts = sum(1 for f in facts if f["source_key"] in OFFICIAL_KEYS and
                      allows_evidence(product_relations.get(f["source_key"], "unknown"), "specs"))
    gallery = sum(1 for p in photos if p["source_key"] in OFFICIAL_KEYS and p["kind"] == "product_gallery" and p["selected"])
    gallery_exact = sum(1 for p in photos if p["source_key"] in OFFICIAL_KEYS and
                        allows_evidence(product_relations.get(p["source_key"], "unknown"), "photo") and
                        p["kind"] == "product_gallery" and p["selected"])
    languages = sorted({d["language"] for d in documents if d["language"]})
    tied_documents = [d for d in documents if d.get("identity_confirmed",
                       document_tied_to_article(article, d, sources))]
    tied_languages = {d["language"] for d in tied_documents if d["language"]}
    dealer_confirmed = sorted(s["source_key"] for s in sources if s["source_key"] in DEALER_KEYS and s["match_level"] in DEALER_CONFIRMED_LEVELS and not s["error"])

    blocking: list[str] = []
    if not exact_regions:
        blocking.append("no_official_full_sku_page")
    if not exact_facts:
        blocking.append("no_official_specifications")
    if not gallery_exact:
        blocking.append("no_official_gallery_photo")
    if conflicts:
        blocking.append("unresolved_conflicts")
    if not documents:
        blocking.append("instruction_missing")
    elif "Русский" in languages and "Русский" not in tied_languages:
        blocking.append("instruction_variant_link_unconfirmed")
    elif "Русский" not in tied_languages:
        blocking.append("instruction_language_not_russian")
    advisory = [] if dealer_confirmed else ["dealer_cross_check_missing"]

    basics = not ({"no_official_full_sku_page", "no_official_specifications", "no_official_gallery_photo"} & set(blocking))
    verdict = "not_ready" if not basics else ("export_ready_with_gaps" if blocking else "export_ready")
    return {
        "verdict": verdict, "blocking_gaps": blocking, "advisory_gaps": advisory, "gaps": blocking + advisory,
        "official_exact_regions": exact_regions, "official_facts": official_facts, "official_facts_from_exact_pages": exact_facts, "official_gallery_selected": gallery, "official_gallery_from_exact_pages": gallery_exact,
        "real_conflicts": conflicts, "instruction": {"found": len(documents), "languages": languages, "russian": "Русский" in tied_languages, "russian_file_found": "Русский" in languages, "verified_for_article": len(tied_documents)},
        "dealer_confirmed": dealer_confirmed,
    }


def readiness_text(readiness: dict[str, Any]) -> str:
    gaps = ", ".join(readiness["gaps"]) or "нет"
    return f"Готовность карточки к выгрузке: {readiness['verdict']}; пробелы: {gaps}."
