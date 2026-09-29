"""One status per unit of work. Pure functions; no I/O, no network.

Order of the decision (first match wins):
  1. catalog-level problems: missing/unresolved brand, missing or malformed
     article -> manual_review; article shared by several catalog units ->
     a risk flag (identity_conflict only if the units' own titles contradict
     each other); a confirmed product fact (config) -> its status
  2. brand -> source family (category-routed for Bosch)
  3. family has a working adapter (worker.run_once() dispatch):
       stopped host -> host_blocked; exact URL on record or confirmed adapter
       discovery -> ready_to_run; otherwise adapter_url_missing
  4. no working adapter: blocked -> host_blocked; no verified official route
     -> manual_review; then the Product page evidence *for this unit's own
     category*: a scope whose layers are complete and whose market matches
     the catalog -> official_route_no_adapter; anything else (no scope for
     the category, a foreign market, missing layers) ->
     needs_product_page_fixture. Evidence never spreads across a brand.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..census.brands import BrandNormalizationRegistry
from ..census.catalog import category_group
from .catalog_units import CatalogUnit
from .facts import FamilyFacts, ScopeFacts, SupplementaryRoute, WorkingRoute, host_matches, route_for_brand

READY = "ready_to_run"
URL_MISSING = "adapter_url_missing"
ROUTE_NO_ADAPTER = "official_route_no_adapter"
NEEDS_FIXTURE = "needs_product_page_fixture"
HOST_BLOCKED = "host_blocked"
IDENTITY_CONFLICT = "identity_conflict"
MANUAL = "manual_review"

ADDRESSABLE_STATUSES_FOR_RUN = frozenset({READY, URL_MISSING})  # run_once() is safe (and informative) for these

NEXT_ACTION = {
    READY: "run_once",
    URL_MISSING: "supply_exact_official_url",
    ROUTE_NO_ADAPTER: "build_adapter",
    NEEDS_FIXTURE: "capture_product_page_fixture",
    HOST_BLOCKED: "wait_for_human_host_decision",
    IDENTITY_CONFLICT: "settle_identity_with_catalog_owner",
    MANUAL: "manual_decision",
}


@dataclass(frozen=True)
class Classification:
    status: str
    reason: str
    family: str = ""
    route_id: str = ""
    url_basis: str = ""
    exact_url: str = ""
    hosts: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    dealer_exact_urls: tuple[tuple[str, str], ...] = ()
    detail: str = ""
    sku_risk: str = ""
    scope_id: str = ""
    url_finding: str = ""

    @property
    def next_action(self) -> str:
        return NEXT_ACTION[self.status]


@dataclass
class ClassifierContext:
    brands: BrandNormalizationRegistry
    facts: dict[str, FamilyFacts]
    routes: tuple[WorkingRoute, ...]
    supplementary: tuple[SupplementaryRoute, ...]
    blocked_hosts: dict[str, list[str]]
    product_facts: list[dict]
    product_flags: list[dict] = field(default_factory=list)
    url_findings: dict[str, dict] = field(default_factory=dict)  # family -> seller sku -> what the URL-discovery wave found
    selected: dict[str, frozenset] = field(default_factory=dict)  # family -> {(category, sku)} chosen under the one-product-per-category rule (routes with url_basis selected_one_per_category)
    sku_owners: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    sku_units: dict[str, list[CatalogUnit]] = field(default_factory=dict)

    @classmethod
    def build(cls, units, **kwargs) -> "ClassifierContext":
        context = cls(**kwargs)
        for unit in units:
            if unit.brand and unit.seller_sku:
                key = unit.seller_sku.casefold()
                context.sku_owners.setdefault(key, set()).add((unit.brand.casefold(), unit.category))
                context.sku_units.setdefault(key, []).append(unit)
        return context


_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+")
_QUANTITY = re.compile(r"^\d+(?:MM|CM|KG|GB|TB|MB|MAH|HZ|GHZ|W|V|A|L|M|G|ШТ|ММ|СМ|КГ|Л|ВТ)$")


def model_tokens(title: str) -> frozenset[str]:
    """Model-like tokens of a catalog title: alphanumeric, a digit and a letter, 3+ characters, not a bare quantity."""
    tokens = set()
    for raw in _TOKEN_SPLIT.split(title or ""):
        token = raw.upper()
        if len(token) < 3 or not any(c.isdigit() for c in token) or not any(c.isalpha() for c in token) or _QUANTITY.match(token):
            continue
        tokens.add(token)
    return frozenset(tokens)


def title_check(units) -> str:
    """agrees: every title names a model and they share one; contradicts: every
    title names a model and none is shared; uninformative: some title names none."""
    token_sets = [model_tokens(unit.title) for unit in units]
    if not all(token_sets):
        return "uninformative"
    return "agrees" if frozenset.intersection(*token_sets) else "contradicts"


def repeated_halves(sku: str) -> bool:
    """`X-BX-B`: the same token twice with nothing between (catalog concatenation artefact)."""
    half, remainder = divmod(len(sku), 2)
    return remainder == 0 and half >= 4 and sku[:half] == sku[half:]


def unit_flags(unit: CatalogUnit) -> tuple[str, ...]:
    flags = []
    if unit.alternate_titles:
        flags.append("has_alternate_titles")
    if repeated_halves(unit.seller_sku):
        flags.append("sku_repeated_halves")
    if unit.importer_brand_source == "name":
        flags.append("importer_brand_inferred_from_title")
    if unit.importer_needs_confirmation:
        flags.append("importer_needs_confirmation")
    return tuple(flags)


def _dealer_urls(context: ClassifierContext, unit: CatalogUnit, brand_is_lg: bool) -> tuple[tuple[str, str], ...]:
    found = []
    for route in context.supplementary:
        if route.source_key == "sulpak" and not brand_is_lg:
            continue
        url = route.known_url(unit.seller_sku)
        if url:
            found.append((route.source_key, url))
    return tuple(found)


def classify(unit: CatalogUnit, context: ClassifierContext) -> Classification:
    flags = unit_flags(unit)
    risk = ""
    flag_detail = ""

    def done(status, reason, **kw):
        if flag_detail:
            kw["detail"] = " ".join(part for part in (kw.get("detail", ""), flag_detail) if part)
        return Classification(status, reason, flags=flags, sku_risk=risk, **kw)

    if not unit.brand:
        return done(MANUAL, "brand_missing", detail="Brand column is empty" + ("; the importer would infer it from the title." if unit.importer_brand_source == "name" else "."))
    if not unit.seller_sku:
        return done(MANUAL, "seller_sku_missing")

    try:
        mapping = context.brands.get(unit.brand)
    except KeyError:
        return done(MANUAL, "brand_label_not_registered")
    if mapping.review_status == "requires_human_review" or mapping.relationship in {"unresolved", "possible_typo"}:
        return done(MANUAL, "brand_mapping_unresolved", family=mapping.source_family_id)

    owners = context.sku_owners.get(unit.seller_sku.casefold(), set())
    if len(owners) > 1:
        # A repeated seller article is a risk to verify together with title, model and
        # variant -- not by itself an identity conflict.
        differing = "brand" if len({brand for brand, _ in owners}) > 1 else "category"
        check = title_check(context.sku_units.get(unit.seller_sku.casefold(), [unit]))
        risk = f"shared_across_{differing};titles_{check}"
        flags += (f"seller_sku_shared_across_{differing}",)
        flag_detail = f"Article {unit.seller_sku!r} is a separate catalog unit in {len(owners)} brand/category combinations; catalog titles {check.replace('_', ' ')}."
        if check == "contradicts":
            return done(IDENTITY_CONFLICT, "seller_sku_shared_titles_contradict", family=mapping.source_family_id)

    family = mapping.family_for(category_group(unit.category))
    if family == "bosch_category_routed":
        return done(MANUAL, "category_routing_ambiguous", family=family,
                    detail="Bosch home and Bosch tools are separate sources; this category is in neither route.")

    for fact in context.product_facts:
        if fact["brand_family"] == family and fact["seller_sku"].casefold() == unit.seller_sku.casefold():
            return done(fact["status"], fact["reason"], family=family, detail=fact["detail"])

    for item in context.product_flags:
        if item["brand_family"] == family and item["seller_sku"].casefold() == unit.seller_sku.casefold():
            flags += (item["flag"],)
            flag_detail = " ".join(part for part in (flag_detail, item["detail"]) if part)

    route = route_for_brand(context.routes, unit.brand)
    facts = context.facts.get(family)
    brand_is_lg = bool(route and route.family == "lg")
    dealer = _dealer_urls(context, unit, brand_is_lg)

    if route is not None:
        if route.family != family:
            return done(MANUAL, "worker_dispatch_and_brand_family_disagree", family=family, route_id=route.route_id)
        stopped = [h for h in route.hosts if host_matches(h, context.blocked_hosts)]
        if stopped or (facts and facts.host_blocked):
            return done(HOST_BLOCKED, "host_stop_recorded", family=family, route_id=route.route_id, hosts=tuple(stopped or route.hosts), dealer_exact_urls=dealer)
        if repeated_halves(unit.seller_sku):
            return done(MANUAL, "seller_sku_not_a_manufacturer_code", family=family, route_id=route.route_id,
                        detail="The article repeats itself; the adapter searches by manufacturer code and would not find it.")
        if route.url_basis == "selected_one_per_category":
            if (unit.category.casefold(), unit.seller_sku.upper()) in context.selected.get(family, frozenset()):
                return done(READY, "selected_one_per_category", family=family, route_id=route.route_id, url_basis=route.url_basis, hosts=route.hosts, dealer_exact_urls=dealer)
            return done(MANUAL, "not_selected_one_card_per_category", family=family, route_id=route.route_id, hosts=route.hosts, dealer_exact_urls=dealer,
                        detail="Owner rule: one product per category, in small declared batches. This row is queued, not selected; it is not offered to run_once().")
        url = route.known_url(unit.seller_sku)
        if url:
            return done(READY, "exact_url_on_record", family=family, route_id=route.route_id, url_basis="known_url_map", exact_url=url, hosts=route.hosts, dealer_exact_urls=dealer)
        if route.url_basis == "adapter_discovery":
            return done(READY, "adapter_discovery_route", family=family, route_id=route.route_id, url_basis="adapter_discovery", hosts=route.hosts, dealer_exact_urls=dealer)
        finding = context.url_findings.get(family, {}).get(unit.seller_sku.upper(), {})
        return done(URL_MISSING, "no_confirmed_exact_url", family=family, route_id=route.route_id, url_basis=route.url_basis, hosts=route.hosts, dealer_exact_urls=dealer,
                    url_finding=finding.get("outcome", ""), detail=finding.get("detail", ""))

    if facts is None or not facts.official_route_known:
        return done(MANUAL, "official_source_not_verified", family=family, dealer_exact_urls=dealer)
    if facts.host_blocked:
        return done(HOST_BLOCKED, facts.blocked_reason, family=family, hosts=facts.hosts, dealer_exact_urls=dealer)
    if facts.profile_status in {"manual_review_required", "javascript_only"} and facts.fixture_level == "none":
        return done(MANUAL, f"official_route_{facts.profile_status}", family=family, hosts=facts.hosts, dealer_exact_urls=dealer)
    if facts.scopes:
        return _scoped_status(done, facts, unit, family, dealer)
    if facts.fixture_level in {"full_value", "structural_sufficient"}:
        # Family-wide evidence is never enough: it has to be declared as a scope.
        return done(NEEDS_FIXTURE, "fixture_scope_not_declared", family=family, hosts=facts.hosts, dealer_exact_urls=dealer,
                    detail="The saved Product page is not tied to any catalog category, host and market, so it is not applied to this unit.")
    reason = "no_product_page_evidence" if facts.fixture_level == "none" else "structural_missing_" + "_".join(facts.fixture_missing_layers)
    return done(NEEDS_FIXTURE, reason, family=family, hosts=facts.hosts, dealer_exact_urls=dealer)


def _scoped_status(done, facts: FamilyFacts, unit: CatalogUnit, family: str, dealer) -> Classification:
    scope: ScopeFacts | None = facts.scope_for(unit.category)
    if scope is None:
        proven = "; ".join(f"{item.label} ({', '.join(item.categories)})" for item in facts.scopes)
        return done(NEEDS_FIXTURE, "no_product_page_evidence_for_category", family=family, hosts=facts.hosts, dealer_exact_urls=dealer,
                    detail=f"No Product page was observed for the category {unit.category!r}. Fixtures exist only for: {proven}.")
    if not scope.market_matches_catalog:
        missing = f" Layers not observed: {', '.join(scope.missing_layers)}." if scope.missing_layers else ""
        return done(NEEDS_FIXTURE, "fixture_market_differs_from_catalog", family=family, hosts=scope.hosts, dealer_exact_urls=dealer,
                    scope_id=scope.scope_id, detail=f"{scope.label}: {scope.market_reason}{missing}")
    if scope.level in {"full_value", "structural_sufficient"}:
        return done(ROUTE_NO_ADAPTER, f"fixture_{scope.level}_in_scope", family=family, hosts=scope.hosts, dealer_exact_urls=dealer, scope_id=scope.scope_id)
    return done(NEEDS_FIXTURE, "structural_missing_" + "_".join(scope.missing_layers), family=family, hosts=scope.hosts, dealer_exact_urls=dealer,
                scope_id=scope.scope_id, detail=f"{scope.label}: layers not observed: {', '.join(scope.missing_layers)}.")
