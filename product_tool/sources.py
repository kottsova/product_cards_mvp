"""Declarative source registry, Bosch routing, and strict host policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable
from urllib.parse import urlsplit


class SourceRole(str, Enum):
    MANUFACTURER = "manufacturer"
    SUPPORT = "support"
    DEALER = "dealer"
    RETAILER = "retailer"


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    adapter_id: str
    brands: tuple[str, ...]
    categories: tuple[str, ...]
    markets: tuple[str, ...]
    role: SourceRole
    capabilities: frozenset[str]
    identity_strategy: str
    priority: int
    page_hosts: tuple[str, ...]
    asset_hosts: tuple[str, ...] = ()
    host_verification: str = "not_checked"
    official_status: str = "research_pending"
    access_status: str = "not_checked"
    fingerprint_status: str = "not_checked"
    adapter_status: str = "not_started"
    enabled: bool = False
    last_checked_at: str = ""
    evidence: tuple[dict, ...] = ()
    support_hosts: tuple[str, ...] = ()
    category_groups: tuple[str, ...] = ()
    source_country: str = ""
    source_locale: str = ""
    source_languages: tuple[str, ...] = ()
    market_scope: str = "unknown"
    identity_scope: str = "unknown"
    category_review_patterns: tuple[str, ...] = ()
    category_allowlist: tuple[str, ...] = ()
    category_deny_patterns: tuple[str, ...] = ()

    def supports(self, brand: str, category: str, market: str, capability: str = "") -> bool:
        if not self.enabled:
            return False
        brand_ok = brand.casefold() in {x.casefold() for x in self.brands}
        category_value = category.casefold()
        from .census.catalog import category_group

        review = any(x.casefold() in category_value for x in self.category_review_patterns)
        denied = any(x.casefold() in category_value for x in self.category_deny_patterns)
        if self.category_allowlist:
            pattern_ok = category_value.strip() in {x.casefold().strip() for x in self.category_allowlist}
            group_ok = True
        else:
            pattern_ok = not self.categories or any(x.casefold() in category_value for x in self.categories)
            group_ok = not self.category_groups or category_group(category).casefold() in {x.casefold() for x in self.category_groups}
        market_value = (market or "unknown").casefold()
        source_markets = {x.casefold() for x in self.markets}
        if self.source_country:
            source_markets.add(self.source_country.casefold())
        market_ok = market_value in {"", "unknown", "any"} or self.market_scope == "global" or not source_markets or market_value in source_markets
        capability_ok = not capability or capability in self.capabilities
        return brand_ok and pattern_ok and group_ok and not review and not denied and market_ok and capability_ok

    def allows_url(self, url: str, *, asset: bool = False) -> bool:
        host = (urlsplit(url).hostname or "").rstrip(".").casefold()
        allowed = self.asset_hosts if asset else self.page_hosts
        return bool(host) and any(host == item.casefold() or host.endswith("." + item.casefold()) for item in allowed)


class UnknownSourceHost(ValueError):
    pass


@dataclass
class SourceRegistry:
    definitions: dict[str, SourceDefinition] = field(default_factory=dict)

    def register(self, definition: SourceDefinition) -> None:
        if definition.source_id in self.definitions:
            raise ValueError(f"Duplicate source id: {definition.source_id}")
        if not definition.page_hosts:
            raise ValueError(f"Source {definition.source_id} has no explicit page hosts")
        self.definitions[definition.source_id] = definition

    def get(self, source_id: str) -> SourceDefinition:
        return self.definitions[source_id]

    def select(self, *, brand: str, category: str, market: str = "", capability: str = "") -> list[SourceDefinition]:
        def rank(item: SourceDefinition) -> tuple[int, int, int, str]:
            identity_rank = {"exact_product": 0, "unknown": 1, "family_only": 2}.get(item.identity_scope, 1)
            scope_rank = 0 if item.market_scope == "global" else 1
            return identity_rank, scope_rank, item.priority, item.source_id

        return sorted(
            (item for item in self.definitions.values() if item.supports(brand, category, market, capability)),
            key=rank,
        )

    def validate_url(self, source_id: str, url: str, *, asset: bool = False) -> None:
        if not self.get(source_id).allows_url(url, asset=asset):
            raise UnknownSourceHost(f"Host is not allowed for {source_id}: {urlsplit(url).hostname or '<missing>'}")

    def validate_redirect_chain(self, source_id: str, urls: Iterable[str], *, asset: bool = False) -> None:
        chain = tuple(urls)
        if not chain:
            raise UnknownSourceHost("Redirect chain is empty")
        for url in chain:
            self.validate_url(source_id, url, asset=asset)


BOSCH_HOME_CATEGORIES = (
    "духовой", "варочная", "холодиль", "морозиль", "посудомоеч",
    "стираль", "сушиль", "вытяжк", "кофемашин", "кухонн",
)
BOSCH_TOOLS_CATEGORIES = (
    "дрель", "шуруповерт", "перфоратор", "шлифов", "лобзик", "пила",
    "фрезер", "рубанок", "инструмент", "дальномер", "нивелир",
)


def route_bosch_category(category: str) -> str:
    """Conservative routing: ambiguous/unknown categories always require review."""
    value = category.casefold()
    home = any(token in value for token in BOSCH_HOME_CATEGORIES)
    tools = any(token in value for token in BOSCH_TOOLS_CATEGORIES)
    if home == tools:
        return "review"
    return "bosch_home" if home else "bosch_tools"


def default_source_registry() -> SourceRegistry:
    """Build the active registry from the validated data-owned JSON catalog."""
    from .census.registry import load_source_catalog

    registry = SourceRegistry()
    for record in load_source_catalog().records:
        if record.official_status.value == "not_allowed":
            continue
        registry.register(SourceDefinition(
            source_id=record.source_id,
            adapter_id=record.adapter_id,
            brands=record.brands,
            categories=record.category_patterns,
            markets=record.markets,
            role=SourceRole(record.source_role),
            capabilities=frozenset(record.capabilities),
            identity_strategy=record.identity_strategy,
            priority=record.priority,
            page_hosts=record.page_hosts,
            asset_hosts=record.asset_document_hosts,
            host_verification=record.host_verification,
            official_status=record.official_status.value,
            access_status=record.access_status.value,
            fingerprint_status=record.fingerprint_status.value,
            adapter_status=record.adapter_status.value,
            enabled=record.enabled,
            last_checked_at=record.last_checked_at,
            evidence=record.evidence,
            support_hosts=record.support_hosts,
            category_groups=record.category_groups,
            source_country=record.source_country,
            source_locale=record.source_locale,
            source_languages=record.source_languages,
            market_scope=record.market_scope,
            identity_scope=record.identity_scope,
            category_review_patterns=record.category_review_patterns,
            category_allowlist=record.category_allowlist,
            category_deny_patterns=record.category_deny_patterns,
        ))
    return registry

