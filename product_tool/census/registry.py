"""Load and validate the data-owned source catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .catalog import category_group
from .models import SourceRecord


CANONICAL_SOURCE_CATALOG = Path(__file__).resolve().parents[1] / "config" / "source_catalog.v2.json"
DEFAULT_CATALOG = CANONICAL_SOURCE_CATALOG


class SourceCatalog:
    def __init__(self, records: Iterable[SourceRecord]):
        values = tuple(records)
        ids = [item.source_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source_id in source catalog")
        self.records = values

    def active(self) -> tuple[SourceRecord, ...]:
        return tuple(item for item in self.records if item.enabled)

    def for_brand(self, brand: str, *, include_disabled: bool = True) -> tuple[SourceRecord, ...]:
        records = self.records if include_disabled else self.active()
        value = brand.casefold().strip()
        return tuple(
            item for item in records
            if item.official_status.value != "not_allowed"
            and value in {candidate.casefold() for candidate in item.brands}
        )

    @staticmethod
    def _market_allowed(item: SourceRecord, catalog_market: str) -> bool:
        requested = (catalog_market or "unknown").casefold()
        if requested in {"", "unknown", "any"}:
            return True
        if item.market_scope == "global":
            return True
        values = {value.casefold() for value in item.markets}
        if item.source_country:
            values.add(item.source_country.casefold())
        return not values or requested in values

    @staticmethod
    def _rank(item: SourceRecord, catalog_market: str) -> tuple[int, int, int, str]:
        identity_rank = {"exact_product": 0, "unknown": 1, "family_only": 2}[item.identity_scope]
        scope_rank = 0 if item.market_scope == "global" else 1
        return identity_rank, scope_rank, item.priority, item.source_id

    def match(self, brand: str, category: str, market: str = "unknown", *, include_disabled: bool = True) -> tuple[SourceRecord, ...]:
        category_value = category.casefold()
        group_value = category_group(category)
        result = []
        for item in self.for_brand(brand, include_disabled=include_disabled):
            if not self._market_allowed(item, market):
                continue
            if item.category_review_patterns and any(pattern.casefold() in category_value for pattern in item.category_review_patterns):
                continue
            if item.category_deny_patterns and any(pattern.casefold() in category_value for pattern in item.category_deny_patterns):
                continue
            if item.category_allowlist:
                if category_value.strip() not in {value.casefold().strip() for value in item.category_allowlist}:
                    continue
                result.append(item)
                continue
            if item.category_groups and group_value.casefold() not in {value.casefold() for value in item.category_groups}:
                continue
            if item.category_patterns and not any(pattern.casefold() in category_value for pattern in item.category_patterns):
                continue
            result.append(item)
        return tuple(sorted(result, key=lambda item: self._rank(item, market)))

    def review_matches(self, brand: str, category: str) -> tuple[SourceRecord, ...]:
        value = category.casefold()
        return tuple(
            item for item in self.for_brand(brand)
            if item.category_review_patterns
            and any(pattern.casefold() in value for pattern in item.category_review_patterns)
        )


def load_source_catalog(path: str | Path = CANONICAL_SOURCE_CATALOG) -> SourceCatalog:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != 2:
        raise ValueError("Only canonical source catalog schema_version=2 is executable")
    if not isinstance(value.get("sources"), list):
        raise ValueError("source catalog must contain a sources array")
    return SourceCatalog(SourceRecord.from_dict(item) for item in value["sources"])
