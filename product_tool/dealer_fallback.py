"""Dealer-fallback provenance helpers.

Why this module does NOT reimplement attribute-merge priority
------------------------------------------------------------
resolve_attributes() (resolution.py) already resolves each attribute name
independently:
  1. If SUPPLIERS (sulpak) confirm the full SKU, their value wins.
  2. Else if OFFICIAL (lg/lg_kz/lg_ru) has a value for that exact attribute
     name, it wins -- and a dealer-only fact for the SAME name is never
     even considered, because the official branch returns before reaching
     the generic fallback branch below.
  3. Only when NEITHER of the above has anything for that attribute name
     does the function fall through to its generic branch, which treats a
     single unconfirmed source (any source_key not in SUPPLIERS/OFFICIAL,
     including "dns") as "needs_review" -- found, but not silently trusted.

This is exactly "official first, dealer fills only genuinely missing
fields, never silently overwrites, conflicting dealer values go to review"
-- with zero changes to resolution.py, as long as a dealer source's
source_key is never added to SUPPLIERS or OFFICIAL. See source_types.py for
the classification used everywhere else (display/export/provenance).

What this module DOES provide: a clean, explicit provenance record per
accepted field, carrying source_type='dealer' literally (not just implied
by a source_key lookup), the field's own URL, evidence text, and the
identity/variant verification level that produced it -- for use in exports,
the review UI, and reports.

Scope of the DNS rule, precisely (Stage 11.5)
----------------------------------------------
"DNS is a secondary source for any brand/category" describes what the RULE
covers, not what it does automatically. A network request only ever
happens when adapters/dns.py already has a pre-verified exact URL for that
product's search code (see its KNOWN_URLS/KNOWN_DOCUMENT_URLS -- explicit
maps, never a crawl or search). For every catalog row without such an
entry -- which is virtually all of them -- find_source() returns a
'dealer_url_needed' status instead of guessing or searching. See
`dealer_url_needed_request()` below, which turns that into a ready-to-ask
question: brand, model/variant, and which fields are actually missing.

Two dealer roles, not one (user preference, Stage 11.5)
---------------------------------------------------------
Once an exact Technopark page is available for a product, its role differs
from DNS's: Technopark is used to CROSS-CHECK disputed/conflicting
characteristics and variant identity against the official source (a
verification role) -- DNS is used to FILL IN characteristics, photos, and
instructions the official source never supplied at all (a supplementation
role). Both are dealer-type sources; official sources always have
priority over either. No Technopark adapter exists yet -- there is no
verified URL to build one against, and none is guessed. When a URL is
supplied, it must go through the same verify_document()/check_identity()
content rules as DNS, with the SAME never-claim-a-document-exists-without-
reading-it discipline.
"""
from __future__ import annotations

from dataclasses import dataclass

from .source_types import source_type as classify_source_type


@dataclass(frozen=True)
class FieldProvenance:
    field: str
    value: str
    unit: str
    source_key: str
    source_type: str  # 'official' | 'dealer' | 'unknown'
    url: str
    evidence: str
    identity_match_level: str
    site_name: str = ""


def build_provenance(
    *, field: str, value: str, unit: str, source_key: str, url: str,
    evidence: str, identity_match_level: str, site_name: str = "",
) -> FieldProvenance:
    """Builds one field's provenance record. Never called for a field whose
    value came from an official source claiming a dealer origin, and vice
    versa -- source_type is derived from source_key, not asserted freely."""
    return FieldProvenance(
        field=field, value=value, unit=unit, source_key=source_key,
        source_type=classify_source_type(source_key), url=url, evidence=evidence,
        identity_match_level=identity_match_level, site_name=site_name,
    )


@dataclass(frozen=True)
class DealerUrlNeeded:
    status: str  # always 'dealer_url_needed'
    brand: str
    model_variant_hint: str
    seller_code: str
    missing_fields: tuple[str, ...]
    message: str


def dealer_url_needed_request(
    *, brand: str, name: str, seller_code: str, missing_fields: list[str] | None = None,
) -> DealerUrlNeeded:
    """Builds an explicit, ready-to-ask request for a human: which product,
    which fields are missing, and that a verified dealer URL is needed --
    never a guessed one. Called whenever adapters/dns.py (or a future
    Technopark adapter) has no pre-verified URL for a search code."""
    missing = tuple(missing_fields or ())
    fields_text = ", ".join(missing) if missing else "характеристики/фото/инструкция (не уточнено)"
    message = (
        f"Нет проверенного дилерского URL для «{brand} {name}» (артикул {seller_code}). "
        f"Не хватает: {fields_text}. Нужна точная ссылка на карточку товара у дилера "
        f"(DNS и/или Технопарк) -- не будет угадана и не будет запущен общий поиск."
    )
    return DealerUrlNeeded(
        status="dealer_url_needed", brand=brand, model_variant_hint=name,
        seller_code=seller_code, missing_fields=missing, message=message,
    )


def resolved_row_provenance(resolved_row: dict, source_pages_by_key: dict[str, dict]) -> FieldProvenance | None:
    """Builds a FieldProvenance from one row of jobs.get_resolved() output,
    looking up the winning source's page (URL, evidence, match_level) from
    jobs.get_source_pages() (keyed by source_key). Returns None for manual
    or empty selections, which have no single dealer/official page behind
    them."""
    source_key = resolved_row.get("selected_source") or ""
    if not source_key or source_key == "manual" or "+" in source_key:
        return None
    page = source_pages_by_key.get(source_key)
    if not page:
        return None
    return build_provenance(
        field=resolved_row["normalized_name"],
        value=resolved_row.get("selected_value", ""),
        unit=resolved_row.get("selected_unit", ""),
        source_key=source_key,
        url=page.get("url", ""),
        evidence=page.get("evidence", ""),
        identity_match_level=page.get("match_level", "unknown"),
        site_name=page.get("site_name", ""),
    )
