"""Route facts for the offline coverage planner.

Everything is read from files already in the repository (brand normalization,
adapter profiles, the executable source registry, the Stage 13-16 facts in
coverage_planner.v1.json, saved fetch logs) plus the adapter modules
themselves. No function here opens a socket.

"Working adapter" means exactly one thing: a class the real worker.run_once()
dispatches to. Research scripts under product_tool/census/ never qualify.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.parse import urlsplit

from ..census.brands import BrandMapping, load_brand_normalization
from ..adapters.policy_fetch import stopped_hosts_from_fetch_log

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "product_tool" / "config"
PLANNER_CONFIG = CONFIG_DIR / "coverage_planner.v1.json"
ADAPTER_PROFILES = CONFIG_DIR / "adapter_profiles.v1.json"

FIXTURE_LEVELS = ("none", "structural_partial", "structural_sufficient", "full_value")
_REQUIRED_LAYERS = ("identity", "specifications", "media")
_PROFILE_STATUS_RANK = {"structure_partial": 0, "product_page_not_found": 1, "javascript_only": 2, "manual_review_required": 3, "http_blocked": 4}


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_config(path: Path = PLANNER_CONFIG) -> dict:
    config = read_json(path)
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported coverage planner config")
    ids = {item["id"] for item in config["statuses"]}
    if set(config["pair_tiebreak_order"]) != ids:
        raise ValueError("pair_tiebreak_order must list every status exactly once")
    return config


# ---------------------------------------------------------------- adapters


@dataclass(frozen=True)
class WorkingRoute:
    """An official adapter that worker.run_once() really dispatches to."""
    route_id: str
    family: str
    adapter_keys: tuple[str, ...]
    brand_aliases: frozenset[str]
    hosts: tuple[str, ...]
    url_basis: str  # "adapter_discovery" (adapter resolves the URL itself) | "known_url_map" (exact URL required)
    known_urls: Callable[[], Mapping[str, str]]
    dispatch_constant: str  # the worker.py constant that gates this branch

    def known_url(self, seller_sku: str) -> str:
        return self.known_urls().get((seller_sku or "").strip().upper(), "")


@dataclass(frozen=True)
class SupplementaryRoute:
    """Dealer fallbacks: never an official source, always exact-URL-only."""
    route_id: str
    source_key: str
    host: str
    known_urls: Callable[[], Mapping[str, str]]
    scope: str

    def known_url(self, seller_sku: str) -> str:
        return self.known_urls().get((seller_sku or "").strip().upper(), "")


def working_routes() -> tuple[WorkingRoute, ...]:
    """Read from the worker/adapter modules at call time so a patched
    KNOWN_URLS (tests) or a newly wired brand shows up immediately."""
    from .. import worker
    from ..adapters import bosch_home, hyperx

    return (
        WorkingRoute(
            "lg_official", "lg", ("lg_kz", "lg_ru"), frozenset(worker.LG_BRAND_ALIASES), ("www.lg.com",),
            "adapter_discovery", lambda: {}, "LG_BRAND_ALIASES",
        ),
        WorkingRoute(
            "hyperx_official", "hyperx", (hyperx.HyperXAdapter.source_key,), frozenset(worker.HYPERX_BRAND_ALIASES),
            tuple(sorted(hyperx.ALLOWED_HOSTS)), "known_url_map", lambda: dict(hyperx.KNOWN_URLS), "HYPERX_BRAND_ALIASES",
        ),
        WorkingRoute(
            "bosch_home_official", "bosch_home", (bosch_home.SOURCE_KEY,), frozenset(worker.BOSCH_HOME_BRAND_ALIASES),
            bosch_home.ALLOWED_HOSTS, "selected_one_per_category", lambda: {}, "BOSCH_HOME_BRAND_ALIASES",
        ),
        # Stage 27: the Samsung adapter is wired into run_once(); by the owner's rule (one product per category, small declared batches) the queue offers only the products
        # listed in the planner config's `selected_products`, never the whole brand.
        WorkingRoute(
            "samsung_official", "samsung", ("samsung",), frozenset(worker.SAMSUNG_BRAND_ALIASES), ("www.samsung.com",),
            "selected_one_per_category", lambda: {}, "SAMSUNG_BRAND_ALIASES",
        ),
    )


def selected_products(config: dict) -> dict[str, frozenset]:
    """family -> {(category casefolded, seller sku upper-cased)}: the products the owner's one-per-category rule has selected for a route whose url_basis is selected_one_per_category."""
    return {family: frozenset((item["category"].casefold(), item["seller_sku"].upper()) for item in block["products"]) for family, block in config.get("selected_products", {}).items()}


def supplementary_routes() -> tuple[SupplementaryRoute, ...]:
    from ..adapters import dns, sulpak

    return (
        SupplementaryRoute("dns_dealer", "dns", dns.PAGE_HOST, lambda: dict(dns.KNOWN_URLS), "any brand, exact known URL only"),
        SupplementaryRoute("sulpak_lg_supplier", "sulpak", "www.sulpak.kz", lambda: dict(sulpak.KNOWN_LG_URLS), "LG only, exact known URL only"),
    )


def route_for_brand(routes: Iterable[WorkingRoute], brand_label: str) -> WorkingRoute | None:
    key = (brand_label or "").strip().casefold()
    return next((route for route in routes if key in route.brand_aliases), None)


# --------------------------------------------------------------- host stops


def _log_entries(path: Path) -> list[dict]:
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return []
    return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []


def recorded_blocked_hosts(config: dict, root: Path = ROOT, extra_logs: Iterable[Path] = ()) -> dict[str, list[str]]:
    """host -> the fetch logs that recorded a 401/403/429 for it."""
    logs = [root / rel for rel in config["host_stop_logs"]["static"]]
    logs += [root / rel for rel in config["host_stop_logs"]["runtime_optional"]]
    logs += [Path(path) for path in extra_logs]
    blocked: dict[str, list[str]] = {}
    for path in logs:
        for host in stopped_hosts_from_fetch_log(_log_entries(path)):
            blocked.setdefault(host, []).append(_display(path, root))
    return {host: sorted(set(paths)) for host, paths in sorted(blocked.items())}


def _display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def host_matches(host: str, blocked: Iterable[str]) -> bool:
    host = (host or "").casefold()
    return any(host == item or host.endswith("." + item) or item.endswith("." + host) for item in blocked)


# ------------------------------------------------------------ family facts


@dataclass(frozen=True)
class ScopeFacts:
    """What one observed Product page proves: its host, market, catalog
    categories and page template -- nothing about the rest of the brand."""
    scope_id: str
    family: str
    label: str
    categories: tuple[str, ...]
    hosts: tuple[str, ...]
    market: str
    market_matches_catalog: bool
    market_reason: str
    page_template: str
    layers: tuple[tuple[str, str], ...]
    declared_level: str
    discovery_status: str  # confirmed | structural_only | no_crawl | none
    discovery_route: str
    evidence: tuple[str, ...]
    observed_urls: tuple[str, ...]
    note: str
    caveat: str

    @property
    def missing_layers(self) -> tuple[str, ...]:
        layers = dict(self.layers)
        return tuple(name for name in _REQUIRED_LAYERS if layers.get(name) != "observed")

    @property
    def level(self) -> str:
        if self.declared_level == "full_value":
            return "full_value"
        return "structural_sufficient" if not self.missing_layers else "structural_partial"

    def covers(self, category: str) -> bool:
        return (category or "").strip().casefold() in {item.casefold() for item in self.categories}

    def to_dict(self) -> dict:
        return {
            "scope_id": self.scope_id, "family": self.family, "label": self.label, "categories": list(self.categories),
            "hosts": list(self.hosts), "market": self.market, "market_matches_catalog": self.market_matches_catalog,
            "market_reason": self.market_reason, "page_template": self.page_template, "layers": dict(self.layers),
            "fixture_level": self.level, "missing_layers": list(self.missing_layers),
            "discovery_status": self.discovery_status, "discovery_route": self.discovery_route,
            "evidence": list(self.evidence), "observed_urls": list(self.observed_urls), "note": self.note, "caveat": self.caveat,
        }


@dataclass(frozen=True)
class FamilyFacts:
    family: str
    official_route_known: bool
    hosts: tuple[str, ...]
    fixture_level: str  # "category_scoped" when the family declares scopes: read them, never this
    fixture_missing_layers: tuple[str, ...]
    discovery_status: str  # confirmed | structural_only | no_crawl | none | category_scoped
    discovery_route: str
    profile_status: str
    host_blocked: bool
    blocked_reason: str
    template_group: str
    evidence: tuple[str, ...]
    note: str
    scopes: tuple[ScopeFacts, ...] = ()

    def scope_for(self, category: str) -> ScopeFacts | None:
        return next((scope for scope in self.scopes if scope.covers(category)), None)

    def to_dict(self) -> dict:
        return {
            "family": self.family, "official_route_known": self.official_route_known, "hosts": list(self.hosts),
            "fixture_level": self.fixture_level, "fixture_missing_layers": list(self.fixture_missing_layers),
            "discovery_status": self.discovery_status, "discovery_route": self.discovery_route,
            "profile_status": self.profile_status, "host_blocked": self.host_blocked,
            "blocked_reason": self.blocked_reason, "template_group": self.template_group,
            "evidence": list(self.evidence), "note": self.note, "scopes": [scope.to_dict() for scope in self.scopes],
        }


def _scope_from_config(family: str, raw: dict) -> ScopeFacts:
    return ScopeFacts(
        scope_id=raw["scope_id"], family=family, label=raw["label"], categories=tuple(raw["categories"]),
        hosts=tuple(raw["hosts"]), market=raw["market"], market_matches_catalog=bool(raw["market_matches_catalog"]),
        market_reason=raw["market_reason"], page_template=raw["page_template"], layers=tuple(sorted(raw["layers"].items())),
        declared_level=raw.get("fixture_level", ""), discovery_status=raw["discovery"]["status"],
        discovery_route=raw["discovery"]["route"], evidence=tuple(raw["evidence"]), observed_urls=tuple(raw.get("observed_urls", ())),
        note=raw.get("note", ""), caveat=raw.get("caveat", ""),
    )


def _profile_is_blocked(profile: dict) -> bool:
    return profile.get("completeness_status") == "http_blocked" or profile.get("access_status") == "blocked"


def build_family_facts(config: dict, profiles: list[dict], blocked_hosts: Mapping[str, list[str]]) -> dict[str, FamilyFacts]:
    by_family: dict[str, list[dict]] = {}
    for profile in profiles:
        by_family.setdefault(profile["source_family"], []).append(profile)
    group_of = {family: group["group_id"] for group in config["template_groups"] for family in group["families"]}
    overrides = config["family_facts"]
    facts: dict[str, FamilyFacts] = {}
    for family in sorted(set(by_family) | set(overrides)):
        all_profiles = by_family.get(family, [])
        # A support-portal mirror never decides the family's status: the product
        # page host does. (Gigabyte: page host blocked, support mirror unreviewed.)
        family_profiles = [p for p in all_profiles if p.get("division") != "support_portal"] or all_profiles
        override = overrides.get(family, {})
        hosts = sorted({h for p in family_profiles for h in (*p.get("allowed_hosts", ()), *p.get("support_hosts", ()))} | set(override.get("hosts", ())))
        # Best structural evidence across the family's profiles.
        level, missing = "none", ()
        for profile in family_profiles:
            if not profile.get("sample_product_page"):
                continue
            layers = profile.get("layers", {})
            absent = tuple(name for name in _REQUIRED_LAYERS if not layers.get(name, {}).get("observed"))
            candidate = "structural_sufficient" if not absent else "structural_partial"
            if FIXTURE_LEVELS.index(candidate) > FIXTURE_LEVELS.index(level) or (candidate == level and len(absent) < len(missing)):
                level, missing = candidate, absent
        if override.get("product_page_fixture"):
            level, missing = override["product_page_fixture"], ()
        scopes = tuple(_scope_from_config(family, raw) for raw in override.get("scopes", ()))
        statuses = sorted((p.get("completeness_status", "") for p in family_profiles), key=lambda s: _PROFILE_STATUS_RANK.get(s, 9))
        profile_status = statuses[0] if statuses else "no_profile"
        discovery_status = override.get("discovery_status") or (config["discovery_status_for_structural_only"] if level.startswith("structural") else "none")
        if scopes:
            # A family with declared scopes has no family-wide fixture or route claim.
            level, missing, discovery_status = "category_scoped", (), "category_scoped"
        blocked_reason = ""
        if override.get("host_blocked"):
            blocked_reason = "recorded_block_in_evidence"
        elif family_profiles and all(_profile_is_blocked(p) for p in family_profiles):
            blocked_reason = "every_profile_http_blocked"
        else:
            stopped = [h for h in hosts if host_matches(h, blocked_hosts)]
            if hosts and len(stopped) == len(hosts):
                blocked_reason = "fetch_log_block_recorded"
        facts[family] = FamilyFacts(
            family=family, official_route_known=bool(family_profiles), hosts=tuple(hosts), fixture_level=level,
            fixture_missing_layers=tuple(missing), discovery_status=discovery_status,
            discovery_route=override.get("discovery_route", ""), profile_status=profile_status,
            host_blocked=bool(blocked_reason), blocked_reason=blocked_reason,
            template_group=group_of.get(family, ""),
            evidence=tuple(override.get("evidence", ())), note=override.get("note", ""), scopes=scopes,
        )
    return facts


def load_profiles(path: Path = ADAPTER_PROFILES) -> list[dict]:
    return read_json(path)["profiles"]


def load_brand_registry():
    return load_brand_normalization()


def mapping_family(mapping: BrandMapping, category_group: str) -> str:
    return mapping.family_for(category_group)


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold()
