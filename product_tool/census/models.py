"""Validated data contracts for the source census."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class OfficialStatus(str, Enum):
    RESEARCH_PENDING = "research_pending"
    CANDIDATE = "candidate"
    OFFICIAL_VERIFIED = "official_verified"
    THIRD_PARTY_CONFIRMED = "third_party_confirmed"
    NOT_ALLOWED = "not_allowed"
    REJECTED = "rejected"


class AccessStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    DIRECT_ACCESS = "direct_access"
    STRUCTURED_API = "structured_api"
    JAVASCRIPT_REQUIRED = "javascript_required"
    BROWSER_ASSISTED = "browser_assisted"
    SEARCH_ONLY = "search_only"
    RATE_LIMITED = "rate_limited"
    CAPTCHA_OR_BLOCKED = "captcha_or_blocked"
    REGIONAL_REDIRECT = "regional_redirect"
    SUPPORT_ONLY = "support_only"
    LEGACY_MISSING = "legacy_missing"
    UNAVAILABLE = "unavailable"


class FingerprintStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    INSUFFICIENT = "insufficient"
    PROBABLE = "probable"
    CONFIRMED = "confirmed"
    CONFLICT = "conflict"


class AdapterStatus(str, Enum):
    NOT_STARTED = "not_started"
    RESEARCH_PENDING = "research_pending"
    RECOMMENDED = "recommended"
    LEGACY_COMPATIBILITY = "legacy_compatibility"
    READY = "ready"


class LifecycleStatus(str, Enum):
    CANDIDATE = "candidate"
    OFFICIAL_VERIFIED = "official_verified"
    ACCESS_CHECKED = "access_checked"
    FINGERPRINTED = "fingerprinted"
    SAMPLED = "sampled"
    ADAPTER_READY = "adapter_ready"
    ENABLED = "enabled"
    DISABLED = "disabled"


class ProtectionStatus(str, Enum):
    CHALLENGE_CONFIRMED = "challenge_confirmed"
    CHALLENGE_SUSPECTED = "challenge_suspected"
    BROWSER_VERIFICATION_REQUIRED = "browser_verification_required"
    ORDINARY_PAGE = "ordinary_page"
    INCONCLUSIVE = "inconclusive"


class EndpointCapability(str, Enum):
    HOMEPAGE = "homepage"
    ROBOTS = "robots_txt"
    SITEMAP = "sitemap"
    CATEGORY_PAGE = "category_page"
    INTERNAL_SEARCH = "internal_search"
    PRODUCT_PAGE = "product_page"
    SUPPORT_PAGE = "support_page"
    DOCUMENT = "document_endpoint"
    ASSET_HOST = "asset_host"
    STRUCTURED_API = "structured_api"


SOURCE_ROLES = {"manufacturer", "support", "dealer", "retailer"}
HOST_VERIFICATION_STATUSES = {"not_checked", "verified", "rejected"}
MARKET_SCOPES = {"unknown", "global", "regional", "country", "local"}
IDENTITY_SCOPES = {"unknown", "family_only", "exact_product"}


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    return tuple(value)


@dataclass(frozen=True)
class EndpointRecord:
    url: str
    capability: EndpointCapability
    sample_type: str
    access_status: AccessStatus = AccessStatus.NOT_CHECKED
    http_status: int | None = None
    redirect_chain: tuple[str, ...] = ()
    final_url: str = ""
    content_type: str = ""
    protection_status: ProtectionStatus = ProtectionStatus.INCONCLUSIVE
    protection_evidence: tuple[Mapping[str, Any], ...] = ()
    javascript_required: bool | None = None
    product_search_available: bool | None = None
    json_ld_product_count: int = 0
    json_ld_field_coverage: Mapping[str, bool] = field(default_factory=dict)
    embedded_state_kinds: tuple[str, ...] = ()
    discovery_evidence: tuple[Mapping[str, Any], ...] = ()
    checked_at: str = ""
    error: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EndpointRecord":
        return cls(
            url=str(value.get("url", "")),
            capability=EndpointCapability(value.get("capability", "homepage")),
            sample_type=str(value.get("sample_type", value.get("capability", "homepage"))),
            access_status=AccessStatus(value.get("access_status", "not_checked")),
            http_status=value.get("http_status"),
            redirect_chain=_strings(value.get("redirect_chain"), "redirect_chain"),
            final_url=str(value.get("final_url", "")),
            content_type=str(value.get("content_type", "")),
            protection_status=ProtectionStatus(value.get("protection_status", "inconclusive")),
            protection_evidence=tuple(value.get("protection_evidence") or ()),
            javascript_required=value.get("javascript_required"),
            product_search_available=value.get("product_search_available"),
            json_ld_product_count=int(value.get("json_ld_product_count", 0)),
            json_ld_field_coverage=dict(value.get("json_ld_field_coverage") or {}),
            embedded_state_kinds=_strings(value.get("embedded_state_kinds"), "embedded_state_kinds"),
            discovery_evidence=tuple(value.get("discovery_evidence") or ()),
            checked_at=str(value.get("checked_at", "")),
            error=str(value.get("error", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["capability"] = self.capability.value
        result["access_status"] = self.access_status.value
        result["protection_status"] = self.protection_status.value
        result["redirect_chain"] = list(self.redirect_chain)
        result["protection_evidence"] = list(self.protection_evidence)
        result["embedded_state_kinds"] = list(self.embedded_state_kinds)
        result["discovery_evidence"] = list(self.discovery_evidence)
        return result


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    adapter_id: str
    brands: tuple[str, ...]
    category_groups: tuple[str, ...]
    category_patterns: tuple[str, ...]
    markets: tuple[str, ...]
    source_role: str
    candidate_url: str
    page_hosts: tuple[str, ...]
    support_hosts: tuple[str, ...]
    asset_document_hosts: tuple[str, ...]
    capabilities: tuple[str, ...]
    identity_strategy: str
    priority: int
    official_status: OfficialStatus
    access_status: AccessStatus
    fingerprint_status: FingerprintStatus
    adapter_status: AdapterStatus
    lifecycle_status: LifecycleStatus
    host_verification: str = "not_checked"
    enabled: bool = False
    last_checked_at: str = ""
    evidence: tuple[Mapping[str, Any], ...] = ()
    http_status: int | None = None
    redirect_chain: tuple[str, ...] = ()
    robots_status: str = "not_checked"
    sitemap_status: str = "not_checked"
    javascript_required: bool | None = None
    protection_status: str = "none_observed"
    product_search_available: bool | None = None
    platform_fingerprints: tuple[Mapping[str, Any], ...] = ()
    presumed_engine: str = "custom_unknown"
    confidence: float = 0.0
    sample_urls: tuple[str, ...] = ()
    adapter_recommendation: str = "research_pending"
    fallback_sources: tuple[str, ...] = ()
    source_country: str = ""
    source_locale: str = ""
    source_languages: tuple[str, ...] = ()
    market_scope: str = "unknown"
    identity_scope: str = "unknown"
    regional_product_code: str = ""
    category_review_patterns: tuple[str, ...] = ()
    category_allowlist: tuple[str, ...] = ()
    category_deny_patterns: tuple[str, ...] = ()
    probe_targets: tuple[Mapping[str, Any], ...] = ()
    endpoints: tuple[EndpointRecord, ...] = ()
    fingerprint_layers: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id or not self.adapter_id:
            raise ValueError("source_id and adapter_id are required")
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"Unsupported source_role: {self.source_role}")
        if self.host_verification not in HOST_VERIFICATION_STATUSES:
            raise ValueError(f"Unsupported host_verification: {self.host_verification}")
        if self.enabled and self.lifecycle_status not in {LifecycleStatus.ENABLED, LifecycleStatus.ADAPTER_READY}:
            raise ValueError("Enabled sources must be adapter_ready or enabled")
        if self.enabled and self.official_status not in {OfficialStatus.OFFICIAL_VERIFIED, OfficialStatus.THIRD_PARTY_CONFIRMED}:
            raise ValueError("Enabled sources require verified official or confirmed third-party status")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.market_scope not in MARKET_SCOPES:
            raise ValueError(f"Unsupported market_scope: {self.market_scope}")
        if self.identity_scope not in IDENTITY_SCOPES:
            raise ValueError(f"Unsupported identity_scope: {self.identity_scope}")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceRecord":
        known = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = set(value) - known
        if unknown:
            raise ValueError(f"Unknown source fields: {', '.join(sorted(unknown))}")
        return cls(
            source_id=str(value.get("source_id", "")),
            adapter_id=str(value.get("adapter_id", "")),
            brands=_strings(value.get("brands"), "brands"),
            category_groups=_strings(value.get("category_groups"), "category_groups"),
            category_patterns=_strings(value.get("category_patterns"), "category_patterns"),
            markets=_strings(value.get("markets"), "markets"),
            source_role=str(value.get("source_role", "")),
            candidate_url=str(value.get("candidate_url", "")),
            page_hosts=_strings(value.get("page_hosts"), "page_hosts"),
            support_hosts=_strings(value.get("support_hosts"), "support_hosts"),
            asset_document_hosts=_strings(value.get("asset_document_hosts"), "asset_document_hosts"),
            capabilities=_strings(value.get("capabilities"), "capabilities"),
            identity_strategy=str(value.get("identity_strategy", "")),
            priority=int(value.get("priority", 100)),
            official_status=OfficialStatus(value.get("official_status", "research_pending")),
            access_status=AccessStatus(value.get("access_status", "not_checked")),
            fingerprint_status=FingerprintStatus(value.get("fingerprint_status", "not_checked")),
            adapter_status=AdapterStatus(value.get("adapter_status", "not_started")),
            lifecycle_status=LifecycleStatus(value.get("lifecycle_status", "candidate")),
            host_verification=str(value.get("host_verification", "not_checked")),
            enabled=value.get("enabled", False),
            last_checked_at=str(value.get("last_checked_at", "")),
            evidence=tuple(value.get("evidence") or ()),
            http_status=value.get("http_status"),
            redirect_chain=_strings(value.get("redirect_chain"), "redirect_chain"),
            robots_status=str(value.get("robots_status", "not_checked")),
            sitemap_status=str(value.get("sitemap_status", "not_checked")),
            javascript_required=value.get("javascript_required"),
            protection_status=str(value.get("protection_status", "none_observed")),
            product_search_available=value.get("product_search_available"),
            platform_fingerprints=tuple(value.get("platform_fingerprints") or ()),
            presumed_engine=str(value.get("presumed_engine", "custom_unknown")),
            confidence=float(value.get("confidence", 0.0)),
            sample_urls=_strings(value.get("sample_urls"), "sample_urls"),
            adapter_recommendation=str(value.get("adapter_recommendation", "research_pending")),
            fallback_sources=_strings(value.get("fallback_sources"), "fallback_sources"),
            source_country=str(value.get("source_country", "")),
            source_locale=str(value.get("source_locale", "")),
            source_languages=_strings(value.get("source_languages"), "source_languages"),
            market_scope=str(value.get("market_scope", "unknown")),
            identity_scope=str(value.get("identity_scope", "unknown")),
            regional_product_code=str(value.get("regional_product_code", "")),
            category_review_patterns=_strings(value.get("category_review_patterns"), "category_review_patterns"),
            category_allowlist=_strings(value.get("category_allowlist"), "category_allowlist"),
            category_deny_patterns=_strings(value.get("category_deny_patterns"), "category_deny_patterns"),
            probe_targets=tuple(value.get("probe_targets") or ()),
            endpoints=tuple(EndpointRecord.from_dict(item) for item in (value.get("endpoints") or ())),
            fingerprint_layers=tuple(value.get("fingerprint_layers") or ()),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("official_status", "access_status", "fingerprint_status", "adapter_status", "lifecycle_status"):
            result[key] = getattr(self, key).value
        for key, value in tuple(result.items()):
            if isinstance(value, tuple):
                result[key] = list(value)
        result["endpoints"] = [item.to_dict() for item in self.endpoints]
        return result
