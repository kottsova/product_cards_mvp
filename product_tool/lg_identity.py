"""LG identity relations and evidence-specific acceptance.

The graph records what an official source *represents*. A route or search hit
never creates an exact edge; only a main PDP sales-code field or support-page
content does.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class IdentityEdge:
    source_key: str
    source_url: str
    represented_model: str
    requested_article: str
    relation: str
    basis: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _code(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def _components(article: str) -> tuple[str, ...]:
    return tuple(_code(part) for part in re.split(r"\s*\+\s*", article) if _code(part))


def structured_sales_relation(requested_article: str, printed_sales_code: str) -> str:
    """Compare a main PDP sales-code field with the requested article.

    A missing dot at the model/suffix boundary is accepted only when the two
    *whole* structured tokens concatenate to the whole requested article.
    Extra dot-separated LG market/channel tokens may follow. The rule never
    applies to URL slugs, search snippets, image filenames, or body text.
    """
    requested = _code(requested_article)
    observed = _code(printed_sales_code)
    if not requested or not observed:
        return "unknown"
    components = _components(requested_article)
    if len(components) > 1:
        return "component_of" if any(
            structured_sales_relation(part, observed) == "exact" for part in components
        ) else "unknown"
    if observed == requested or observed.startswith(requested + "."):
        return "exact"
    if "." not in observed and requested.startswith(observed) and len(requested) > len(observed) + 2:
        return "family_of"
    parts = observed.split(".")
    if "." not in requested and len(parts) >= 2 and parts[0] + parts[1] == requested:
        return "exact"
    requested_base = requested.split(".", 1)[0]
    if len(parts) >= 2 and parts[0] == requested_base:
        return "family_of" if "." not in requested else "regional_variant_of"
    if "." in requested and observed == requested_base:
        return "family_of"
    # The catalog may print a model and suffix without a dot. This gives a
    # regional-variant relation, never an exact one, when the suffix differs.
    if "." not in requested and len(parts) >= 2 and requested.startswith(parts[0]):
        suffix = requested[len(parts[0]):]
        if len(suffix) >= 3 and re.fullmatch(r"[A-Z0-9]+", suffix):
            return "regional_variant_of"
    return "unknown"


def product_edges(source_key: str, source_url: str, requested_article: str,
                  main_sales_codes: Iterable[str]) -> tuple[IdentityEdge, ...]:
    return tuple(IdentityEdge(source_key, source_url, _code(code),
                              _code(requested_article),
                              structured_sales_relation(requested_article, code),
                              "main_pdp_structured_sales_code")
                 for code in dict.fromkeys(main_sales_codes) if _code(code))


def support_edges(source_key: str, source_url: str, requested_article: str,
                  content_sales_codes: Iterable[str]) -> tuple[IdentityEdge, ...]:
    """Link an official support page to each component printed in its content."""
    components = _components(requested_article)
    codes = tuple(dict.fromkeys(_code(code) for code in content_sales_codes if _code(code)))
    edges = []
    matched = set()
    for code in codes:
        relations = [structured_sales_relation(component, code) for component in components]
        for component, relation in zip(components, relations):
            if relation == "exact":
                matched.add(component)
                edges.append(IdentityEdge(source_key, source_url, code, _code(requested_article),
                                          "component_of" if len(components) > 1 else "support_for",
                                          "official_support_content_sales_code"))
            elif relation in {"family_of", "regional_variant_of"}:
                edges.append(IdentityEdge(source_key, source_url, code, _code(requested_article),
                                          relation, "official_support_content_sales_code"))
    if components and len(matched) == len(components):
        edges.append(IdentityEdge(source_key, source_url, ", ".join(sorted(matched)),
                                  _code(requested_article), "support_for",
                                  "all_requested_components_on_official_support_page"))
    return tuple(edges)


def source_relation(source_key: str, match_level: str) -> str:
    if source_key in {"lg_kz_support", "lg_ru_support"}:
        return {"full_sku": "support_for", "component_only": "component_of",
                "base_model": "family_of"}.get(match_level, "unknown")
    if source_key in {"lg_kz", "lg_ru"}:
        return {"full_sku": "exact", "base_model": "family_of",
                "component_only": "component_of"}.get(match_level, "unknown")
    return "unknown"


def allows_evidence(relation: str, evidence_type: str, *,
                    official_family_shared: bool = False) -> bool:
    if evidence_type == "manual":
        return relation in {"exact", "support_for"}
    if evidence_type in {"specs", "photo"}:
        return relation == "exact" or (relation == "family_of" and official_family_shared)
    raise ValueError(f"Unknown evidence type: {evidence_type}")


def article_has_variant(article: str, linked_sales_codes: Iterable[str] = ()) -> bool:
    """A catalog suffix may be dotted or printed joined to model+suffix."""
    requested = _code(article)
    if "." in requested or "+" in requested:
        return True
    for linked in linked_sales_codes:
        parts = _code(linked).split(".")
        if len(parts) >= 2 and parts[0] + parts[1] == requested:
            return True
    return False


def document_tied_to_article(article: str, document: dict, source_pages: Iterable[dict]) -> bool:
    """A verified PDF still needs an official support tie for a specified variant."""
    pages = {p["source_key"]: p for p in source_pages if not p.get("error")}
    key = document.get("source_key", "")
    if key == "lg_kz_support":
        page = pages.get(key, {})
        return (document.get("source_url") == page.get("url") and
                source_relation(key, page.get("match_level", "")) == "support_for")
    if key == "lg_ru" and article_has_variant(article, (document.get("support_model", ""),)):
        page = pages.get("lg_ru_support", {})
        return (document.get("source_url") == page.get("url") and
                source_relation("lg_ru_support", page.get("match_level", "")) == "support_for")
    return True


def photo_tied_to_article(photo: dict, source_pages: Iterable[dict]) -> bool:
    pages = {p["source_key"]: p for p in source_pages if not p.get("error")}
    key = photo.get("source_key", "")
    page = pages.get(key, {})
    if key in {"lg_kz", "lg_ru"}:
        return allows_evidence(source_relation(key, page.get("match_level", "")), "photo")
    if key in {"dns", "sulpak"}:
        return page.get("match_level") in {"full_sku", "model_and_code_confirmed"}
    return False
