"""Declarative brand normalization registry for census stage 3."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_BRAND_NORMALIZATION = Path(__file__).resolve().parents[1] / "config" / "brand_normalization.v1.json"
RELATIONSHIPS = frozenset({"exact", "spelling_variant", "alias", "regional_name", "subbrand", "product_line", "category_dependent", "possible_typo", "unresolved"})
REVIEW_STATUSES = frozenset({"confirmed_exact_label", "confirmed_mapping", "requires_human_review"})


@dataclass(frozen=True)
class BrandMapping:
    original_brand_label: str
    normalized_label: str
    canonical_brand: str
    source_family_id: str
    relationship: str
    confidence: float
    category_scope: tuple[str, ...]
    evidence: tuple[Mapping[str, Any], ...]
    review_status: str
    notes: str
    source_family_routes: tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BrandMapping":
        required = {"original_brand_label", "normalized_label", "canonical_brand", "source_family_id", "relationship", "confidence", "category_scope", "evidence", "review_status", "notes"}
        allowed = required | {"source_family_routes"}
        missing = required - set(value)
        unknown = set(value) - allowed
        if missing or unknown:
            raise ValueError(f"Invalid brand mapping fields: missing={sorted(missing)}, unknown={sorted(unknown)}")
        relationship = str(value["relationship"])
        review_status = str(value["review_status"])
        confidence = float(value["confidence"])
        if relationship not in RELATIONSHIPS or review_status not in REVIEW_STATUSES:
            raise ValueError("Unsupported relationship or review_status")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if relationship in {"possible_typo", "unresolved"} and review_status != "requires_human_review":
            raise ValueError("Ambiguous mappings require human review")
        evidence = tuple(value["evidence"])
        if not evidence:
            raise ValueError("Every mapping requires evidence")
        return cls(
            original_brand_label=str(value["original_brand_label"]),
            normalized_label=str(value["normalized_label"]),
            canonical_brand=str(value["canonical_brand"]),
            source_family_id=str(value["source_family_id"]),
            relationship=relationship,
            confidence=confidence,
            category_scope=tuple(str(item) for item in value["category_scope"]),
            evidence=evidence,
            review_status=review_status,
            notes=str(value["notes"]),
            source_family_routes=tuple(value.get("source_family_routes") or ()),
        )

    def family_for(self, category_group: str) -> str:
        for route in self.source_family_routes:
            if category_group in route.get("category_scope", ()):
                return str(route["source_family_id"])
        return self.source_family_id


class BrandNormalizationRegistry:
    def __init__(self, records: Iterable[BrandMapping]):
        self.records = tuple(records)
        labels = [item.original_brand_label for item in self.records]
        if len(labels) != len(set(labels)):
            raise ValueError("Duplicate original_brand_label")
        self._by_label = {item.original_brand_label: item for item in self.records}

    def get(self, label: str) -> BrandMapping:
        try:
            return self._by_label[label]
        except KeyError as exc:
            raise KeyError(f"Brand label is not registered: {label}") from exc

    def validate_catalog_labels(self, labels: Iterable[str]) -> None:
        expected = set(labels)
        actual = set(self._by_label)
        if expected != actual:
            raise ValueError(f"Brand registry/catalog mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")

    @property
    def canonical_brands(self) -> frozenset[str]:
        return frozenset(item.canonical_brand for item in self.records)

    @property
    def source_families(self) -> frozenset[str]:
        values = {item.source_family_id for item in self.records}
        for item in self.records:
            values.update(str(route["source_family_id"]) for route in item.source_family_routes)
        values.discard("bosch_category_routed")
        return frozenset(values)


def load_brand_normalization(path: str | Path = DEFAULT_BRAND_NORMALIZATION) -> BrandNormalizationRegistry:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("brands"), list):
        raise ValueError("Unsupported brand normalization registry")
    policy = payload.get("normalization_policy") or {}
    if policy.get("fuzzy_merge_allowed") is not False:
        raise ValueError("Fuzzy-only brand merging must remain disabled")
    return BrandNormalizationRegistry(BrandMapping.from_dict(item) for item in payload["brands"])

