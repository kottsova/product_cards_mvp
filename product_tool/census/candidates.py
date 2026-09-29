"""Validated, non-executable domain candidates for the all-brand census."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import AccessStatus, EndpointRecord, FingerprintStatus, OfficialStatus


DEFAULT_CANDIDATES = Path(__file__).resolve().parents[1] / "config" / "source_candidates.v1.json"
MARKET_SCOPES = {"unknown", "global", "regional", "country", "local"}
SOURCE_ROLES = {"manufacturer", "support", "dealer", "retailer"}


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    return tuple(value)


@dataclass(frozen=True)
class SourceCandidate:
    candidate_id: str
    brands: tuple[str, ...]
    category_groups: tuple[str, ...]
    category_patterns: tuple[str, ...]
    market: str
    market_scope: str
    source_country: str
    source_locale: str
    source_languages: tuple[str, ...]
    source_role: str
    candidate_url: str
    page_hosts: tuple[str, ...]
    support_hosts: tuple[str, ...]
    asset_document_hosts: tuple[str, ...]
    official_status: OfficialStatus
    access_status: AccessStatus
    fingerprint_status: FingerprintStatus
    adapter_status: str
    enabled: bool
    last_checked_at: str
    evidence: tuple[Mapping[str, Any], ...]
    next_operation: str
    probe_targets: tuple[Mapping[str, Any], ...] = ()
    endpoints: tuple[EndpointRecord, ...] = ()
    fingerprint_layers: tuple[Mapping[str, Any], ...] = ()
    presumed_engine: str = "custom_unknown"
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.brands or not self.candidate_url:
            raise ValueError("candidate_id, brands and candidate_url are required")
        if self.market_scope not in MARKET_SCOPES:
            raise ValueError(f"Unsupported market_scope: {self.market_scope}")
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"Unsupported source_role: {self.source_role}")
        if self.enabled:
            raise ValueError("Source candidates cannot be enabled")
        if self.official_status == OfficialStatus.OFFICIAL_VERIFIED and not self.evidence:
            raise ValueError("official_verified candidates require evidence")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceCandidate":
        known = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = set(value) - known
        if unknown:
            raise ValueError(f"Unknown candidate fields: {', '.join(sorted(unknown))}")
        return cls(
            candidate_id=str(value.get("candidate_id", "")),
            brands=_strings(value.get("brands"), "brands"),
            category_groups=_strings(value.get("category_groups"), "category_groups"),
            category_patterns=_strings(value.get("category_patterns"), "category_patterns"),
            market=str(value.get("market", "unknown")),
            market_scope=str(value.get("market_scope", "unknown")),
            source_country=str(value.get("source_country", "")),
            source_locale=str(value.get("source_locale", "")),
            source_languages=_strings(value.get("source_languages"), "source_languages"),
            source_role=str(value.get("source_role", "manufacturer")),
            candidate_url=str(value.get("candidate_url", "")),
            page_hosts=_strings(value.get("page_hosts"), "page_hosts"),
            support_hosts=_strings(value.get("support_hosts"), "support_hosts"),
            asset_document_hosts=_strings(value.get("asset_document_hosts"), "asset_document_hosts"),
            official_status=OfficialStatus(value.get("official_status", "candidate")),
            access_status=AccessStatus(value.get("access_status", "not_checked")),
            fingerprint_status=FingerprintStatus(value.get("fingerprint_status", "not_checked")),
            adapter_status=str(value.get("adapter_status", "research_pending")),
            enabled=bool(value.get("enabled", False)),
            last_checked_at=str(value.get("last_checked_at", "")),
            evidence=tuple(value.get("evidence") or ()),
            next_operation=str(value.get("next_operation", "probe_homepage_and_discovery_endpoints")),
            probe_targets=tuple(value.get("probe_targets") or ()),
            endpoints=tuple(EndpointRecord.from_dict(item) for item in (value.get("endpoints") or ())),
            fingerprint_layers=tuple(value.get("fingerprint_layers") or ()),
            presumed_engine=str(value.get("presumed_engine", "custom_unknown")),
            confidence=float(value.get("confidence", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["official_status"] = self.official_status.value
        result["access_status"] = self.access_status.value
        result["fingerprint_status"] = self.fingerprint_status.value
        for key, value in tuple(result.items()):
            if isinstance(value, tuple):
                result[key] = list(value)
        result["endpoints"] = [item.to_dict() for item in self.endpoints]
        return result


class CandidateCatalog:
    def __init__(self, records: Iterable[SourceCandidate]):
        self.records = tuple(records)
        ids = [item.candidate_id for item in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate_id in source candidate catalog")

    def for_brand(
        self,
        brand: str,
        *,
        categories: Iterable[str] = (),
        category_groups: Iterable[str] = (),
        catalog_market: str = "unknown",
    ) -> tuple[SourceCandidate, ...]:
        key = brand.casefold().strip()
        category_values = tuple(value.casefold() for value in categories)
        group_values = {value.casefold() for value in category_groups}
        requested_market = (catalog_market or "unknown").casefold()
        result = []
        for item in self.records:
            if key not in {value.casefold() for value in item.brands}:
                continue
            if item.category_groups and not group_values.intersection(value.casefold() for value in item.category_groups):
                continue
            if item.category_patterns and not any(
                pattern.casefold() in category
                for pattern in item.category_patterns
                for category in category_values
            ):
                continue
            if requested_market not in {"", "unknown", "any"} and item.market_scope != "global":
                if requested_market not in {item.market.casefold(), item.source_country.casefold()}:
                    continue
            result.append(item)
        return tuple(result)


def load_source_candidates(path: str | Path = DEFAULT_CANDIDATES) -> CandidateCatalog:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("candidates"), list):
        raise ValueError("Unsupported source candidate catalog")
    return CandidateCatalog(SourceCandidate.from_dict(item) for item in payload["candidates"])
