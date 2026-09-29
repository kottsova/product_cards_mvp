"""General resolution policy with source authority and variant isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .identity import VerificationLevel
from .sources import SourceRole


@dataclass(frozen=True)
class SourceValue:
    field_name: str
    value: Any
    source_id: str
    role: SourceRole
    verification: VerificationLevel
    variant_key: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class ResolvedField:
    field_name: str
    value: Any
    source_id: str
    reason: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class ResolutionResult:
    fields: tuple[ResolvedField, ...]
    reviews: tuple[dict[str, Any], ...]


class ResolutionPolicy:
    """Prefer exact first-party evidence and never cross variant boundaries."""

    _role_rank = {
        SourceRole.MANUFACTURER: 0,
        SourceRole.SUPPORT: 1,
        SourceRole.DEALER: 2,
        SourceRole.RETAILER: 3,
    }
    _verification_rank = {
        VerificationLevel.EXACT_VARIANT: 0,
        VerificationLevel.EXACT_MODEL: 1,
        VerificationLevel.FAMILY_ONLY: 8,
        VerificationLevel.INSUFFICIENT: 9,
        VerificationLevel.CONFLICT: 10,
    }

    def resolve(self, candidates: Iterable[SourceValue], *, target_variant_key: str) -> ResolutionResult:
        usable = [
            item for item in candidates
            if item.verification in {VerificationLevel.EXACT_VARIANT, VerificationLevel.EXACT_MODEL}
            and item.variant_key == target_variant_key
        ]
        grouped: dict[str, list[SourceValue]] = {}
        for item in usable:
            grouped.setdefault(item.field_name, []).append(item)
        resolved: list[ResolvedField] = []
        reviews: list[dict[str, Any]] = []
        for field_name, values in sorted(grouped.items()):
            values.sort(key=lambda item: (self._verification_rank[item.verification], self._role_rank[item.role], item.source_id))
            manufacturers = [item for item in values if item.role in {SourceRole.MANUFACTURER, SourceRole.SUPPORT}]
            exact_manufacturers = [item for item in manufacturers if item.verification == VerificationLevel.EXACT_VARIANT]
            authoritative = exact_manufacturers or [item for item in manufacturers if item.verification == VerificationLevel.EXACT_MODEL]
            if authoritative:
                unique = {str(item.value) for item in authoritative}
                if len(unique) > 1:
                    reviews.append({
                        "field_name": field_name,
                        "reason": "Conflicting first-party values",
                        "provenance": [item.provenance for item in authoritative],
                    })
                    continue
                chosen = authoritative[0]
                resolved.append(ResolvedField(field_name, chosen.value, chosen.source_id, "Exact first-party evidence has priority.", chosen.provenance))
                continue
            chosen = values[0]
            resolved.append(ResolvedField(
                field_name, chosen.value, chosen.source_id,
                "Exact dealer/retailer evidence supplements a missing first-party field.",
                chosen.provenance,
            ))
        return ResolutionResult(tuple(resolved), tuple(reviews))
