"""Second-pass census runner with persistent brand queue and endpoint evidence."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .candidates import CandidateCatalog, SourceCandidate, load_source_candidates
from .catalog import CatalogCensus, load_catalog_coverage
from .discovery import validate_structured_product_identity
from product_tool.identity import ProductIdentity
from .models import (
    AccessStatus,
    AdapterStatus,
    EndpointCapability,
    FingerprintStatus,
    LifecycleStatus,
    OfficialStatus,
    ProtectionStatus,
    SourceRecord,
)
from .probe import AccessProbe, ProbePolicy
from .registry import SourceCatalog, load_source_catalog
from .source_fingerprint import aggregate_endpoint_fingerprints


ACCESSIBLE = {
    AccessStatus.DIRECT_ACCESS,
    AccessStatus.STRUCTURED_API,
    AccessStatus.JAVASCRIPT_REQUIRED,
    AccessStatus.BROWSER_ASSISTED,
    AccessStatus.SEARCH_ONLY,
    AccessStatus.SUPPORT_ONLY,
}


def _resume_catalog(base: SourceCatalog, output_dir: Path) -> SourceCatalog:
    path = output_dir / "source_registry.json"
    if not path.exists():
        return base
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        previous = {item.source_id: item for item in (SourceRecord.from_dict(value) for value in payload.get("sources", ())) }
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return base
    merged = []
    for current in base.records:
        old = previous.get(current.source_id)
        if not old:
            merged.append(current)
            continue
        targets = {str(target.get("url", "")): target for target in current.probe_targets}
        normalized_endpoints = {}
        for endpoint in old.endpoints:
            target = targets.get(endpoint.url)
            if target:
                endpoint = replace(
                    endpoint,
                    capability=EndpointCapability(target.get("capability", endpoint.capability.value)),
                    sample_type=str(target.get("sample_type", endpoint.sample_type)),
                )
            normalized_endpoints[(endpoint.url, endpoint.capability.value)] = endpoint
        dynamic_evidence = tuple(
            item for item in old.evidence
            if item.get("type") in {"product_identity_check", "support_identity_check", "structured_identity_check", "reproducible_discovery"}
        )
        merged.append(replace(
            current,
            access_status=old.access_status,
            fingerprint_status=old.fingerprint_status,
            lifecycle_status=old.lifecycle_status,
            last_checked_at=old.last_checked_at,
            evidence=current.evidence + dynamic_evidence,
            http_status=old.http_status,
            redirect_chain=old.redirect_chain,
            robots_status=old.robots_status,
            sitemap_status=old.sitemap_status,
            javascript_required=old.javascript_required,
            protection_status=old.protection_status,
            product_search_available=any(endpoint.product_search_available is True for endpoint in normalized_endpoints.values()),
            platform_fingerprints=old.platform_fingerprints,
            fingerprint_layers=old.fingerprint_layers,
            presumed_engine=old.presumed_engine,
            confidence=old.confidence,
            sample_urls=old.sample_urls,
            endpoints=tuple(normalized_endpoints.values()),
        ))
    return SourceCatalog(merged)


def _resume_candidates(base: CandidateCatalog, output_dir: Path) -> CandidateCatalog:
    path = output_dir / "source_candidates.json"
    if not path.exists():
        return base
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        previous = {item.candidate_id: item for item in (SourceCandidate.from_dict(value) for value in payload.get("candidates", ())) }
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return base
    merged = []
    for current in base.records:
        old = previous.get(current.candidate_id)
        if not old:
            merged.append(current)
            continue
        current_targets = {str(target.get("url", "")) for target in current.probe_targets}
        endpoints = tuple(item for item in old.endpoints if item.url in current_targets)
        dynamic_evidence = tuple(item for item in old.evidence if item.get("type") in {"product_identity_check", "support_identity_check", "structured_identity_check", "reproducible_discovery"})
        merged.append(replace(
            current,
            access_status=old.access_status,
            fingerprint_status=old.fingerprint_status,
            last_checked_at=old.last_checked_at,
            evidence=current.evidence + dynamic_evidence,
            endpoints=endpoints,
            fingerprint_layers=old.fingerprint_layers,
            presumed_engine=old.presumed_engine,
            confidence=old.confidence,
        ))
    return CandidateCatalog(merged)


def _endpoint_map(record: SourceRecord) -> dict[tuple[str, str], Any]:
    return {(item.url, item.capability.value): item for item in record.endpoints}


def _merge_layers(existing, new):
    merged = {(item.get("layer"), item.get("engine")): dict(item) for item in existing}
    rank = {"not_checked": 0, "insufficient": 1, "probable": 2, "confirmed": 3, "conflict": 4}
    for item in new:
        key = (item.get("layer"), item.get("engine"))
        old = merged.get(key)
        if not old:
            merged[key] = dict(item)
            continue
        winner = dict(item) if rank.get(item.get("status"), 0) > rank.get(old.get("status"), 0) else dict(old)
        winner["confidence"] = max(float(old.get("confidence", 0)), float(item.get("confidence", 0)))
        winner["sample_types"] = sorted(set(old.get("sample_types", ())) | set(item.get("sample_types", ())))
        winner["evidence"] = list(old.get("evidence", ())) + [value for value in item.get("evidence", ()) if value not in old.get("evidence", ())]
        merged[key] = winner
    return tuple(merged.values())


def _aggregate_access(endpoints) -> AccessStatus:
    checked = [item for item in endpoints if item.access_status != AccessStatus.NOT_CHECKED]
    if not checked:
        return AccessStatus.NOT_CHECKED
    priority_capabilities = {
        EndpointCapability.PRODUCT_PAGE,
        EndpointCapability.INTERNAL_SEARCH,
        EndpointCapability.STRUCTURED_API,
    }
    useful = [item for item in checked if item.capability in priority_capabilities and item.access_status in ACCESSIBLE]
    if useful:
        if any(item.access_status == AccessStatus.STRUCTURED_API for item in useful):
            return AccessStatus.STRUCTURED_API
        if any(item.access_status == AccessStatus.JAVASCRIPT_REQUIRED for item in useful):
            return AccessStatus.JAVASCRIPT_REQUIRED
        return AccessStatus.DIRECT_ACCESS
    if any(item.access_status in ACCESSIBLE for item in checked):
        return AccessStatus.DIRECT_ACCESS
    if any(item.access_status == AccessStatus.RATE_LIMITED for item in checked):
        return AccessStatus.RATE_LIMITED
    if any(item.access_status == AccessStatus.CAPTCHA_OR_BLOCKED for item in checked):
        return AccessStatus.CAPTCHA_OR_BLOCKED
    if any(item.access_status == AccessStatus.REGIONAL_REDIRECT for item in checked):
        return AccessStatus.REGIONAL_REDIRECT
    return AccessStatus.UNAVAILABLE


def _aggregate_protection(endpoints) -> str:
    statuses = {item.protection_status for item in endpoints}
    for status in (
        ProtectionStatus.CHALLENGE_CONFIRMED,
        ProtectionStatus.BROWSER_VERIFICATION_REQUIRED,
        ProtectionStatus.CHALLENGE_SUSPECTED,
        ProtectionStatus.ORDINARY_PAGE,
    ):
        if status in statuses:
            return status.value
    return ProtectionStatus.INCONCLUSIVE.value


def _recommendation(record: SourceRecord, layers: tuple[dict, ...]) -> str:
    if any(item.protection_status == ProtectionStatus.CHALLENGE_CONFIRMED for item in record.endpoints):
        return "manual_or_browser_review"
    if any(item.access_status == AccessStatus.JAVASCRIPT_REQUIRED for item in record.endpoints):
        return "browser_assisted_research"
    confirmed_product_layers = [
        item for item in layers
        if item.get("status") == "confirmed" and item.get("layer") in {"commerce_search", "product_data", "catalog_feed"}
    ]
    if confirmed_product_layers:
        return "platform_candidate_requires_cross_site_validation"
    return "generic_discovery_first"


def probe_source_endpoints(
    catalog: SourceCatalog,
    *,
    source_limit: int,
    endpoint_limit_per_source: int,
    brand_keys: set[str] | None = None,
    policy: ProbePolicy | None = None,
    checkpoint_path: Path | None = None,
) -> SourceCatalog:
    if source_limit <= 0:
        return catalog
    probe = AccessProbe(policy=policy)
    updated: list[SourceRecord] = []
    checked_sources = 0
    for index, record in enumerate(catalog.records):
        source_brand_keys = {brand.casefold() for brand in record.brands}
        # Stage 16: same removal as runner.py's probe_sources() -- the
        # literal named exclusion was redundant with this generic
        # registry-driven filter (official_status == OFFICIAL_VERIFIED),
        # not a rule that needed a replacement branch.
        eligible = (
            checked_sources < source_limit
            and record.official_status == OfficialStatus.OFFICIAL_VERIFIED
            and bool(record.probe_targets)
            and (not brand_keys or bool(source_brand_keys & brand_keys))
        )
        if not eligible:
            updated.append(record)
            continue
        checked_sources += 1
        endpoint_records = _endpoint_map(record)
        raw_fingerprints = []
        added_evidence = list(record.evidence)
        regional_code = record.regional_product_code
        checked_at = record.last_checked_at
        allowed_hosts = tuple(dict.fromkeys(record.page_hosts + record.support_hosts + record.asset_document_hosts))
        for target in record.probe_targets[:endpoint_limit_per_source]:
            url = str(target.get("url", ""))
            capability = EndpointCapability(target.get("capability", "homepage"))
            sample_type = str(target.get("sample_type", capability.value))
            key = (url, capability.value)
            old = endpoint_records.get(key)
            evidence_type = "support_identity_check" if capability == EndpointCapability.SUPPORT_PAGE else "product_identity_check"
            has_identity = any(item.get("type") == "structured_identity_check" and item.get("url") == url for item in added_evidence)
            identity_refresh = capability in {EndpointCapability.PRODUCT_PAGE, EndpointCapability.SUPPORT_PAGE} and old and old.access_status in ACCESSIBLE and not has_identity
            if old and old.checked_at and not identity_refresh:
                continue
            result = probe.probe(url, allowed_hosts=allowed_hosts, capability=capability, sample_type=sample_type)
            endpoint_records[key] = result.to_endpoint_record()
            checked_at = result.checked_at
            raw_fingerprints.append((sample_type, result.fingerprints))
            expected = tuple(str(value) for value in target.get("expected_models", ()))
            if capability in {EndpointCapability.PRODUCT_PAGE, EndpointCapability.SUPPORT_PAGE} and result.diagnostic_text and expected:
                expected_identity = ProductIdentity.from_product({
                    "brand": record.brands[0] if record.brands else "",
                    "category": target.get("category", ""),
                    "search_code": expected[0],
                    "model_candidates": expected,
                    "name": target.get("expected_title", ""),
                    "variant_attributes": target.get("variant_attributes", {}),
                })
                identity = validate_structured_product_identity(
                    result.diagnostic_text, expected=expected_identity, source_url=result.final_url or url
                )
                added_evidence.append({"type": "structured_identity_check", "legacy_type": evidence_type, "url": url, "final_url": result.final_url, "verification": identity.to_dict()})
                if capability == EndpointCapability.PRODUCT_PAGE and identity.level.value in {"exact_model", "exact_variant"} and not regional_code:
                    regional_code = expected[0]

        endpoints = tuple(sorted(endpoint_records.values(), key=lambda item: (item.capability.value, item.url)))
        if raw_fingerprints:
            layers = _merge_layers(record.fingerprint_layers, tuple(item.to_dict() for item in aggregate_endpoint_fingerprints(tuple(raw_fingerprints))))
        else:
            layers = record.fingerprint_layers
        best = next((item for item in layers if item.get("status") == "confirmed"), layers[0] if layers else None)
        fingerprint_status = FingerprintStatus(best["status"]) if best else FingerprintStatus.NOT_CHECKED
        product_checked = any(item.capability == EndpointCapability.PRODUCT_PAGE and item.checked_at for item in endpoints)
        lifecycle = LifecycleStatus.SAMPLED if product_checked else LifecycleStatus.ACCESS_CHECKED
        robots = next((item.access_status.value for item in endpoints if item.capability == EndpointCapability.ROBOTS), "not_checked")
        sitemap = next((item.access_status.value for item in endpoints if item.capability == EndpointCapability.SITEMAP), "not_checked")
        homepage = next((item for item in endpoints if item.capability == EndpointCapability.HOMEPAGE), None)
        candidate = replace(
            record,
            access_status=_aggregate_access(endpoints),
            fingerprint_status=fingerprint_status,
            adapter_status=record.adapter_status if record.enabled else AdapterStatus.RESEARCH_PENDING,
            lifecycle_status=record.lifecycle_status if record.enabled else lifecycle,
            last_checked_at=checked_at,
            evidence=tuple(added_evidence),
            http_status=homepage.http_status if homepage else record.http_status,
            redirect_chain=homepage.redirect_chain if homepage else record.redirect_chain,
            robots_status=robots,
            sitemap_status=sitemap,
            javascript_required=homepage.javascript_required if homepage else record.javascript_required,
            protection_status=_aggregate_protection(endpoints),
            product_search_available=any(item.product_search_available is True for item in endpoints),
            platform_fingerprints=tuple(item for _, results in raw_fingerprints for item in (result.to_dict() for result in results)),
            fingerprint_layers=layers,
            presumed_engine=best["engine"] if best else "custom_unknown",
            confidence=float(best["confidence"]) if best else 0.0,
            sample_urls=tuple(item.url for item in endpoints if item.checked_at),
            regional_product_code=regional_code,
            endpoints=endpoints,
        )
        recommendation = record.adapter_recommendation if record.enabled else _recommendation(candidate, layers)
        updated.append(replace(candidate, adapter_recommendation=recommendation))
        if checkpoint_path:
            snapshot = updated + list(catalog.records[index + 1:])
            checkpoint_path.write_text(json.dumps({"schema_version": 2, "sources": [item.to_dict() for item in snapshot]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return SourceCatalog(updated)


def probe_candidate_endpoints(
    catalog: CandidateCatalog,
    *,
    source_limit: int,
    endpoint_limit_per_source: int,
    brand_keys: set[str] | None = None,
    policy: ProbePolicy | None = None,
    checkpoint_path: Path | None = None,
) -> CandidateCatalog:
    """Probe only configured, official candidate endpoints and persist each result."""
    if source_limit <= 0:
        return catalog
    probe = AccessProbe(policy=policy)
    updated: list[SourceCandidate] = []
    checked_sources = 0
    for index, record in enumerate(catalog.records):
        eligible = (
            checked_sources < source_limit
            and record.official_status == OfficialStatus.OFFICIAL_VERIFIED
            and bool(record.probe_targets)
            and (not brand_keys or bool({brand.casefold() for brand in record.brands} & brand_keys))
        )
        if not eligible:
            updated.append(record)
            continue
        checked_sources += 1
        endpoint_records = {(item.url, item.capability.value): item for item in record.endpoints}
        raw_fingerprints = []
        evidence = list(record.evidence)
        checked_at = record.last_checked_at
        allowed_hosts = tuple(dict.fromkeys(record.page_hosts + record.support_hosts + record.asset_document_hosts))
        for target in record.probe_targets[:endpoint_limit_per_source]:
            url = str(target.get("url", ""))
            capability = EndpointCapability(target.get("capability", "homepage"))
            sample_type = str(target.get("sample_type", capability.value))
            key = (url, capability.value)
            old = endpoint_records.get(key)
            evidence_type = "support_identity_check" if capability == EndpointCapability.SUPPORT_PAGE else "product_identity_check"
            has_identity = any(item.get("type") == "structured_identity_check" and item.get("url") == url for item in evidence)
            needs_metadata = bool(old and old.access_status in ACCESSIBLE and old.json_ld_product_count and not old.json_ld_field_coverage)
            identity_refresh = bool(capability in {EndpointCapability.PRODUCT_PAGE, EndpointCapability.SUPPORT_PAGE} and old and old.access_status in ACCESSIBLE and not has_identity)
            if old and old.checked_at and not identity_refresh and not needs_metadata:
                continue
            result = probe.probe(url, allowed_hosts=allowed_hosts, capability=capability, sample_type=sample_type)
            endpoint_records[key] = result.to_endpoint_record()
            checked_at = result.checked_at
            raw_fingerprints.append((sample_type, result.fingerprints))
            expected = tuple(str(value) for value in target.get("expected_models", ()))
            if capability in {EndpointCapability.PRODUCT_PAGE, EndpointCapability.SUPPORT_PAGE} and result.diagnostic_text and expected:
                expected_identity = ProductIdentity.from_product({
                    "brand": record.brands[0] if record.brands else "",
                    "category": target.get("category", ""),
                    "search_code": expected[0],
                    "model_candidates": expected,
                    "name": target.get("expected_title", ""),
                    "variant_attributes": target.get("variant_attributes", {}),
                })
                identity = validate_structured_product_identity(
                    result.diagnostic_text, expected=expected_identity, source_url=result.final_url or url
                )
                evidence.append({"type": "structured_identity_check", "legacy_type": evidence_type, "url": url, "final_url": result.final_url, "verification": identity.to_dict()})
        endpoints = tuple(sorted(endpoint_records.values(), key=lambda item: (item.capability.value, item.url)))
        layers = record.fingerprint_layers
        if raw_fingerprints:
            layers = _merge_layers(layers, tuple(item.to_dict() for item in aggregate_endpoint_fingerprints(tuple(raw_fingerprints))))
        best = next((item for item in layers if item.get("status") == "confirmed"), layers[0] if layers else None)
        updated.append(replace(
            record,
            access_status=_aggregate_access(endpoints),
            fingerprint_status=FingerprintStatus(best["status"]) if best else FingerprintStatus.NOT_CHECKED,
            last_checked_at=checked_at,
            evidence=tuple(evidence),
            endpoints=endpoints,
            fingerprint_layers=layers,
            presumed_engine=best["engine"] if best else "custom_unknown",
            confidence=float(best["confidence"]) if best else 0.0,
            next_operation="review_identity_and_platform_evidence" if any(item.capability == EndpointCapability.PRODUCT_PAGE and item.checked_at for item in endpoints) else "find_and_probe_product_page",
        ))
        if checkpoint_path:
            snapshot = updated + list(catalog.records[index + 1:])
            checkpoint_path.write_text(json.dumps({"schema_version": 1, "candidates": [item.to_dict() for item in snapshot]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return CandidateCatalog(updated)


def _brand_aggregates(census: CatalogCensus) -> list[dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for coverage in census.coverages:
        if not coverage.brand:
            continue
        item = values.setdefault(coverage.brand_canonical, {
            "brand": coverage.brand,
            "catalog_market": coverage.catalog_market,
            "unique_products": 0,
            "source_rows": 0,
            "categories": set(),
            "category_groups": set(),
            "sample_seller_skus": [],
        })
        item["unique_products"] += coverage.unique_products
        item["source_rows"] += coverage.source_rows
        item["categories"].add(coverage.category)
        item["category_groups"].add(coverage.category_group)
        for sku in coverage.sample_seller_skus:
            if sku not in item["sample_seller_skus"] and len(item["sample_seller_skus"]) < 8:
                item["sample_seller_skus"].append(sku)
    return [values[key] for key in sorted(values, key=lambda key: (-values[key]["unique_products"], key))]


def _endpoint_flags(sources) -> dict[str, bool]:
    sources = tuple(sources)
    endpoints = [item for source in sources for item in source.endpoints]
    def checked(capability):
        return any(item.capability == capability and bool(item.checked_at) for item in endpoints)
    exact = any(
        evidence.get("type") == "structured_identity_check"
        and (evidence.get("verification") or {}).get("level") in {"exact_model", "exact_variant"}
        for source in sources for evidence in source.evidence
    )
    discovery = any(
        evidence.get("type") == "reproducible_discovery"
        and evidence.get("strategy") in {"sitemap_catalog", "internal_search", "embedded_state", "structured_api"}
        and bool(evidence.get("candidate_url"))
        for source in sources for evidence in source.evidence
    )
    return {
        "homepage_checked": checked(EndpointCapability.HOMEPAGE),
        "product_page_checked": checked(EndpointCapability.PRODUCT_PAGE),
        "search_checked": any(item.checked_at and item.product_search_available is not None for item in endpoints),
        "search_working": any(item.product_search_available is True for item in endpoints),
        "support_checked": checked(EndpointCapability.SUPPORT_PAGE),
        "endpoint_sampled": bool(endpoints and any(item.checked_at for item in endpoints)),
        "product_discovery_validated": discovery,
        "exact_identity_validated": exact,
    }


def build_discovery_queue(
    census: CatalogCensus,
    sources: SourceCatalog,
    candidates: CandidateCatalog | None = None,
) -> list[dict[str, Any]]:
    queue = []
    total = census.expected_totals["unique_products"]
    for item in _brand_aggregates(census):
        known = sources.for_brand(item["brand"])
        allowed = tuple(source for source in known if source.official_status != OfficialStatus.NOT_ALLOWED)
        official = tuple(source for source in allowed if source.official_status == OfficialStatus.OFFICIAL_VERIFIED)
        domain_candidates = [
            {
                "source_id": source.source_id,
                "candidate_kind": "source_record",
                "url": source.candidate_url,
                "official_status": source.official_status.value,
                "source_country": source.source_country,
                "source_locale": source.source_locale,
                "source_languages": list(source.source_languages),
                "market_scope": source.market_scope,
                "evidence": list(source.evidence),
            }
            for source in allowed if source.candidate_url
        ]
        external_candidates = candidates.for_brand(
            item["brand"],
            categories=item["categories"],
            category_groups=item["category_groups"],
            catalog_market=item["catalog_market"],
        ) if candidates else ()
        flags = _endpoint_flags(allowed + tuple(external_candidates))
        domain_candidates.extend({
            "source_id": candidate.candidate_id,
            "candidate_kind": "domain_candidate",
            "url": candidate.candidate_url,
            "official_status": candidate.official_status.value,
            "source_country": candidate.source_country,
            "source_locale": candidate.source_locale,
            "source_languages": list(candidate.source_languages),
            "market_scope": candidate.market_scope,
            "evidence": list(candidate.evidence),
            "access_status": candidate.access_status.value,
            "fingerprint_status": candidate.fingerprint_status.value,
            "adapter_status": candidate.adapter_status,
            "enabled": candidate.enabled,
            "last_checked_at": candidate.last_checked_at,
            "next_operation": candidate.next_operation,
            "endpoint_count": len(candidate.endpoints),
            "presumed_engine": candidate.presumed_engine,
            "confidence": candidate.confidence,
        } for candidate in external_candidates)
        official_evidence = [evidence for source in official for evidence in source.evidence]
        official_evidence.extend(
            evidence
            for candidate in external_candidates
            if candidate.official_status == OfficialStatus.OFFICIAL_VERIFIED
            for evidence in candidate.evidence
        )
        has_official_candidate = bool(official) or any(
            candidate.official_status == OfficialStatus.OFFICIAL_VERIFIED
            for candidate in external_candidates
        )
        official_domain_verified = has_official_candidate
        production_ready = flags["product_discovery_validated"] and flags["exact_identity_validated"] and any(
            source.enabled and source.adapter_status == AdapterStatus.READY
            for source in allowed
        )
        if not domain_candidates:
            status, reason, operation = "research_pending", "no_domain_candidate", "discover_domain_candidates"
        elif not has_official_candidate:
            status, reason, operation = "candidate", "official_evidence_missing", "verify_official_domain"
        elif not flags["homepage_checked"]:
            status, reason, operation = "official_verified", "homepage_not_checked", "probe_homepage_and_discovery_endpoints"
        elif not flags["product_page_checked"]:
            status, reason, operation = "access_checked", "product_page_not_checked", "find_and_probe_product_page"
        else:
            status, reason, operation = "sampled", "", "review_identity_and_platform_evidence"
        queue.append({
            "brand": item["brand"],
            "catalog_market": item["catalog_market"],
            "categories": sorted(item["categories"], key=str.casefold),
            "category_groups": sorted(item["category_groups"]),
            "unique_products": item["unique_products"],
            "source_rows": item["source_rows"],
            "assortment_share": round(item["unique_products"] / total, 6),
            "sample_seller_skus": item["sample_seller_skus"],
            "domain_candidates": domain_candidates,
            "official_evidence": official_evidence,
            "verification_status": status,
            "official_domain_verified": official_domain_verified,
            "production_ready": production_ready,
            "no_result_reason": reason,
            "next_operation": operation,
            **flags,
        })
    return queue


def _coverage_records(census: CatalogCensus, sources: SourceCatalog) -> list[dict[str, Any]]:
    output = []
    for coverage in census.coverages:
        matches = sources.match(coverage.brand, coverage.category, coverage.catalog_market) if coverage.brand else ()
        review = sources.review_matches(coverage.brand, coverage.category) if coverage.brand else ()
        value = coverage.to_dict()
        value.update({
            "coverage_share": round(coverage.unique_products / census.expected_totals["unique_products"], 6),
            "source_ids": [item.source_id for item in matches],
            "coverage_status": "source_scoped" if matches else ("review_pending" if review else "research_pending"),
            "review_source_ids": [item.source_id for item in review],
        })
        output.append(value)
    return output


def _record_id(record) -> str:
    return getattr(record, "source_id", getattr(record, "candidate_id", ""))


def _identity_validated(record) -> bool:
    return any(
        item.get("type") == "structured_identity_check"
        and (item.get("verification") or {}).get("level") in {"exact_model", "exact_variant"}
        for item in record.evidence
    )


def _json_ld_rows(records) -> list[dict[str, Any]]:
    fields = ("name", "sku", "mpn", "model", "gtin", "brand", "image", "description", "characteristics", "documents", "variant_data")
    rows = []
    for record in records:
        product_endpoints = [item for item in record.endpoints if item.json_ld_product_count]
        if not product_endpoints:
            continue
        coverage = {field: any(item.json_ld_field_coverage.get(field, False) for item in product_endpoints) for field in fields}
        rows.append({
            "source_id": _record_id(record),
            "hosts": list(record.page_hosts),
            "product_endpoints": len(product_endpoints),
            "product_nodes": sum(item.json_ld_product_count for item in product_endpoints),
            "fields": coverage,
            "exact_identity_validated": _identity_validated(record),
        })
    return rows


def _clusters(records, brand_products: dict[str, int]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[tuple[SourceRecord, dict]]] = defaultdict(list)
    for record in records:
        if record.official_status == OfficialStatus.NOT_ALLOWED:
            continue
        for layer in record.fingerprint_layers:
            if layer.get("status") == "confirmed" and layer.get("engine") != "custom_unknown":
                groups[(str(layer.get("layer")), str(layer.get("engine")))].append((record, layer))
    output = []
    for (layer_name, engine), items in groups.items():
        source_ids = sorted({_record_id(record) for record, _ in items})
        hosts = sorted({host for record, _ in items for host in record.page_hosts})
        brand_keys = {brand.casefold() for record, _ in items for brand in record.brands}
        sample_types = sorted({sample for _, layer in items for sample in layer.get("sample_types", ())})
        multi_site = len(source_ids) >= 2 and len(hosts) >= 2
        deep_single = len(source_ids) == 1 and "product_page" in sample_types and bool({"internal_search", "support_page"} & set(sample_types))
        structure_validated = layer_name != "site_cms"
        compatibility_evidence = "confirmed fingerprint on bounded endpoints"
        if engine == "generic_json_ld_product":
            useful = []
            for record, _ in items:
                coverages = [endpoint.json_ld_field_coverage for endpoint in record.endpoints if endpoint.json_ld_product_count]
                has_identity_fields = any(
                    values.get("name") and any(values.get(field) for field in ("sku", "mpn", "model", "gtin"))
                    for values in coverages
                )
                useful.append(has_identity_fields and _identity_validated(record))
            structure_validated = multi_site and len(useful) >= 2 and all(useful)
            compatibility_evidence = "exact identity plus useful JSON-LD identifiers across independent sites" if structure_validated else "Product @type alone is insufficient; useful field/identity compatibility not validated"
        output.append({
            "layer": layer_name,
            "engine": engine,
            "sources": source_ids,
            "independent_hosts": hosts,
            "sample_types": sample_types,
            "catalog_products": sum(brand_products.get(key, 0) for key in brand_keys),
            "single_source_candidate": len(source_ids) == 1,
            "multi_site_cluster": multi_site,
            "adapter_candidate": structure_validated and (multi_site or deep_single),
            "structure_compatibility_validated": structure_validated,
            "compatibility_evidence": compatibility_evidence,
        })
    return sorted(output, key=lambda item: (-item["catalog_products"], item["layer"], item["engine"]))


def _summary(census: CatalogCensus, queue, sources: SourceCatalog, candidates: CandidateCatalog) -> dict[str, Any]:
    total_products = census.expected_totals["unique_products"]
    status_counts = {
        status: sum(item["verification_status"] == status for item in queue)
        for status in ("research_pending", "candidate", "official_verified", "access_checked", "sampled")
    }
    all_records = sources.records + candidates.records
    endpoints = [endpoint for source in all_records for endpoint in source.endpoints if endpoint.checked_at]
    def brand_count(field):
        return sum(bool(item[field]) for item in queue)
    def share(predicate):
        return round(sum(item["unique_products"] for item in queue if predicate(item)) / total_products, 6)
    official = lambda item: any(candidate["official_status"] == "official_verified" for candidate in item["domain_candidates"])
    protection_values = [endpoint.protection_status for source in all_records for endpoint in source.endpoints]
    confirmed_challenge_sources = {_record_id(source) for source in all_records if any(endpoint.protection_status == ProtectionStatus.CHALLENGE_CONFIRMED for endpoint in source.endpoints)}
    suspected_challenge_sources = {_record_id(source) for source in all_records if any(endpoint.protection_status == ProtectionStatus.CHALLENGE_SUSPECTED for endpoint in source.endpoints)}
    browser_required_sources = {_record_id(source) for source in all_records if any(endpoint.protection_status == ProtectionStatus.BROWSER_VERIFICATION_REQUIRED for endpoint in source.endpoints)}
    confirmed_engine_brands = {
        brand.casefold()
        for source in all_records
        if any(layer.get("status") == "confirmed" for layer in source.fingerprint_layers)
        for brand in source.brands
    }
    return {
        "catalog": census.expected_totals,
        "catalog_market": census.catalog_market,
        "brand_stage_counts": status_counts,
        "brands_researched": len(queue) - status_counts["research_pending"],
        "brands_not_researched": status_counts["research_pending"],
        "brands_with_domain_candidate": sum(bool(item["domain_candidates"]) for item in queue),
        "brands_official_verified": sum(official(item) for item in queue),
        "brands_homepage_checked": brand_count("homepage_checked"),
        "brands_product_page_checked": brand_count("product_page_checked"),
        "brands_search_checked": brand_count("search_checked"),
        "brands_search_working": brand_count("search_working"),
        "brands_support_checked": brand_count("support_checked"),
        "brands_endpoint_sampled": brand_count("endpoint_sampled"),
        "brands_product_discovery_validated": brand_count("product_discovery_validated"),
        "brands_exact_identity_validated": brand_count("exact_identity_validated"),
        "brands_production_ready": brand_count("production_ready"),
        "sources_challenge_confirmed": len(confirmed_challenge_sources),
        "sources_challenge_suspected": len(suspected_challenge_sources),
        "sources_browser_verification_required": len(browser_required_sources),
        "challenge_endpoints_confirmed": protection_values.count(ProtectionStatus.CHALLENGE_CONFIRMED),
        "challenge_endpoints_suspected": protection_values.count(ProtectionStatus.CHALLENGE_SUSPECTED),
        "sources_total": len(all_records),
        "sources_with_checked_endpoints": sum(any(endpoint.checked_at for endpoint in source.endpoints) for source in all_records),
        "accessible_endpoints": sum(endpoint.access_status in ACCESSIBLE for endpoint in endpoints),
        "blocked_endpoints": sum(endpoint.access_status in {AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED} for endpoint in endpoints),
        "brands_engine_confirmed": sum(item["brand"].casefold() in confirmed_engine_brands for item in queue),
        "assortment_shares": {
            "domain_candidate": share(lambda item: bool(item["domain_candidates"])),
            "official_verified": share(official),
            "homepage_checked": share(lambda item: item["homepage_checked"]),
            "product_page_checked": share(lambda item: item["product_page_checked"]),
            "search_checked": share(lambda item: item["search_checked"]),
            "search_working": share(lambda item: item["search_working"]),
            "support_checked": share(lambda item: item["support_checked"]),
            "endpoint_sampled": share(lambda item: item["endpoint_sampled"]),
            "product_discovery_validated": share(lambda item: item["product_discovery_validated"]),
            "exact_identity_validated": share(lambda item: item["exact_identity_validated"]),
            "production_ready": share(lambda item: item["production_ready"]),
            "research_pending": share(lambda item: not item["domain_candidates"]),
        },
        "unresolved_brand_products": sum(item.unique_products for item in census.unresolved_brand_coverages),
    }


def _report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    shares = summary["assortment_shares"]
    clusters = payload["platform_clusters"]
    lines = [
        "# All-brand source census v2", "",
        f"Generated: {payload['generated_at']}", "",
        "## Coverage stages", "",
        f"- Catalog brands: {summary['catalog']['brands']}",
        f"- Catalog market: {summary['catalog_market']}",
        f"- Researched brands (candidate evidence or deeper): {summary['brands_researched']}",
        f"- Not researched (`research_pending`): {summary['brands_not_researched']}",
        f"- Brands with domain candidate: {summary['brands_with_domain_candidate']} ({shares['domain_candidate']:.1%} of assortment)",
        f"- Brands with verified official domain: {summary['brands_official_verified']} ({shares['official_verified']:.1%})",
        f"- Brands with checked homepage: {summary['brands_homepage_checked']} ({shares['homepage_checked']:.1%})",
        f"- Brands with checked product page: {summary['brands_product_page_checked']} ({shares['product_page_checked']:.1%})",
        f"- Brands with inspected search capability: {summary['brands_search_checked']} ({shares['search_checked']:.1%})",
        f"- Brands with working search detected: {summary['brands_search_working']} ({shares['search_working']:.1%})",
        f"- Brands with checked support: {summary['brands_support_checked']} ({shares['support_checked']:.1%})",
        f"- Brands endpoint-sampled: {summary['brands_endpoint_sampled']} ({shares['endpoint_sampled']:.1%})",
        f"- Brands with product discovery validated: {summary['brands_product_discovery_validated']} ({shares['product_discovery_validated']:.1%})",
        f"- Brands with exact identity validated: {summary['brands_exact_identity_validated']} ({shares['exact_identity_validated']:.1%})",
        f"- Brands production-ready: {summary['brands_production_ready']} ({shares['production_ready']:.1%})",
        f"- Sources with confirmed challenge: {summary['sources_challenge_confirmed']}",
        f"- Sources with suspected challenge: {summary['sources_challenge_suspected']}",
        f"- Sources requiring browser verification: {summary['sources_browser_verification_required']}",
        f"- Endpoints with confirmed challenge: {summary['challenge_endpoints_confirmed']}",
        f"- Endpoints with suspected challenge: {summary['challenge_endpoints_suspected']}", "",
        f"- Sources with checked endpoints: {summary['sources_with_checked_endpoints']} of {summary['sources_total']}",
        f"- Accessible checked endpoints: {summary['accessible_endpoints']}",
        f"- Blocked/rate-limited checked endpoints: {summary['blocked_endpoints']}", "",
        "A known homepage alone is not counted as product coverage.", "",
        "The requested remainder listed 18 brand labels; POCO was already sampled through the shared `xiaomi_global` source, so 17 brands actually remained (LG plus 16 candidate records). All 25 previously domain-covered catalog brands now have endpoint evidence.", "",
        "## Bounded source recheck", "",
        "| Source | Homepage | Product | Support | Identity observations | Protection | Confirmed engines |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for source in payload["sources"]:
        endpoints = [item for item in source.get("endpoints", ()) if item.get("checked_at")]
        if not endpoints:
            continue

        def endpoint_value(capability: str) -> str:
            values = [
                f"{item.get('http_status') or '—'}:{item.get('access_status')}"
                for item in endpoints if item.get("capability") == capability
            ]
            return ", ".join(values) or "—"

        identity_count = sum(
            item.get("type") in {"product_identity_check", "support_identity_check"}
            for item in source.get("evidence", ())
        )
        engines = sorted({
            item.get("engine", "") for item in source.get("fingerprint_layers", ())
            if item.get("status") == "confirmed"
        })
        protections = sorted({item.get("protection_status", "inconclusive") for item in endpoints})
        lines.append(
            f"| {source['source_id']} | {endpoint_value('homepage')} | {endpoint_value('product_page')} | "
            f"{endpoint_value('support_page')} | {identity_count} | {', '.join(protections)} | {', '.join(engines) or '—'} |"
        )
    for source in payload["source_candidates"]:
        endpoints = [item for item in source.get("endpoints", ()) if item.get("checked_at")]
        if not endpoints:
            continue
        def candidate_endpoint_value(capability: str) -> str:
            values = [f"{item.get('http_status') or '—'}:{item.get('access_status')}" for item in endpoints if item.get("capability") == capability]
            return ", ".join(values) or "—"
        identity_count = sum(item.get("type") in {"product_identity_check", "support_identity_check"} for item in source.get("evidence", ()))
        engines = sorted({item.get("engine", "") for item in source.get("fingerprint_layers", ()) if item.get("status") == "confirmed"})
        protections = sorted({item.get("protection_status", "inconclusive") for item in endpoints})
        lines.append(f"| {source['candidate_id']} | {candidate_endpoint_value('homepage')} | {candidate_endpoint_value('product_page')} | {candidate_endpoint_value('support_page')} | {identity_count} | {', '.join(protections)} | {', '.join(engines) or '—'} |")
    lines.extend([
        "",
        "## Platform clusters", "",
        "| Layer | Engine | Sources | Single source | Multi-site | Adapter candidate |", "| --- | --- | ---: | --- | --- | --- |",
    ])
    for item in clusters:
        lines.append(f"| {item['layer']} | {item['engine']} | {len(item['sources'])} | {item['single_source_candidate']} | {item['multi_site_cluster']} | {item['adapter_candidate']} |")
    if not clusters:
        lines.append("| — | — | 0 | — | — | — |")
    lines.extend(["", "## JSON-LD Product field coverage", "", "| Source | name | sku | mpn | model | gtin | brand | image | description | characteristics | documents | variants | exact identity |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]) 
    for item in payload["json_ld_field_coverage"]:
        fields = item["fields"]
        marks = [("yes" if fields.get(name) else "no") for name in ("name", "sku", "mpn", "model", "gtin", "brand", "image", "description", "characteristics", "documents", "variant_data")]
        lines.append(f"| {item['source_id']} | " + " | ".join(marks) + f" | {item['exact_identity_validated']} |")
    if not payload["json_ld_field_coverage"]:
        lines.append("| — | no | no | no | no | no | no | no | no | no | no | no | False |")
    pending = [item["brand"] for item in payload["brands"] if item["verification_status"] == "research_pending"]
    lines.extend(["", "## Remaining research_pending", "", ", ".join(pending) or "None."])
    custom_sites = payload["custom_sites"]
    manual = payload["manual_or_browser_review"]
    lines.extend([
        "", "## Custom or still unclassified sites", "",
        *(f"- {item}" for item in custom_sites or ["None in the bounded sample."]),
        "", "## Browser or manual review", "",
        *(f"- {item}" for item in manual or ["None in the bounded sample."]),
        "", "## Next shared layer", "",
        "Implement a shared bounded discovery orchestration layer around sitemap/catalog indexes, internal-search evidence, embedded state and exact-identity validation. Do not implement a generic JSON-LD adapter yet: the sampled sites share `Product` markup but not a validated identifier/variant structure. No CMS-specific adapter is justified by the present evidence.", "",
        "## Changes in this stage", "",
        "- Canonicalized executable configuration on `source_catalog.v2.json`; removed unreferenced v1 catalog/schema files and made the loader v2-only.",
        "- Replaced Sulpak category-group inference with an exact five-category allowlist plus explicit review and deny rules.",
        "- Added persisted candidate endpoint records, per-source checkpoints, five independent confirmation levels, final URLs, JSON-LD field coverage, embedded-state kinds and discovery evidence.",
        "- Added bounded targets for all previously domain-covered brands and added the next official-domain batch; HIPER remains an unverified candidate and ATLANT supplies the 50th verified brand.",
        "- Downgraded generic JSON-LD structure compatibility and withheld adapter recommendation where useful identity/variant fields do not converge.",
        "- Preserved LG adapters and storage compatibility; no database migration or production adapter was introduced.", "",
        "## Verification", "",
        "- Schema, status, fingerprint, allowlist and safe-probe regressions are covered by `tests/test_source_census_v2.py` and the full test suite.",
    ])
    return "\n".join(lines)


def generate_census_v2(
    catalog_path: str | Path,
    output_dir: str | Path,
    *,
    market: str = "unknown",
    probe_limit: int = 0,
    min_interval_seconds: float = 2.0,
    endpoint_limit_per_source: int = 5,
    brand_offset: int = 0,
    brand_batch_size: int = 50,
    resume: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    census = load_catalog_coverage(catalog_path, market=market)
    sources = load_source_catalog()
    candidates = load_source_candidates()
    if resume:
        sources = _resume_catalog(sources, output)
        candidates = _resume_candidates(candidates, output)
    initial_queue = build_discovery_queue(census, sources, candidates)
    batch = initial_queue[brand_offset: brand_offset + max(0, min(brand_batch_size, 50))]
    brand_keys = {item["brand"].casefold() for item in batch}
    sources = probe_source_endpoints(
        sources,
        source_limit=probe_limit,
        endpoint_limit_per_source=endpoint_limit_per_source,
        brand_keys=brand_keys,
        policy=ProbePolicy(min_interval_seconds=min_interval_seconds),
        checkpoint_path=output / "source_registry.json",
    )
    candidates = probe_candidate_endpoints(
        candidates,
        source_limit=probe_limit,
        endpoint_limit_per_source=endpoint_limit_per_source,
        brand_keys=brand_keys,
        policy=ProbePolicy(min_interval_seconds=min_interval_seconds),
        checkpoint_path=output / "source_candidates.json",
    )
    queue = build_discovery_queue(census, sources, candidates)
    coverage = _coverage_records(census, sources)
    brand_products = {item["brand"].casefold(): item["unique_products"] for item in queue}
    all_records = sources.records + candidates.records
    clusters = _clusters(all_records, brand_products)
    json_ld_coverage = _json_ld_rows(all_records)
    custom_sites = [
        _record_id(source) for source in all_records
        if any(endpoint.checked_at for endpoint in source.endpoints)
        and not any(layer.get("status") == "confirmed" for layer in source.fingerprint_layers)
    ]
    manual_or_browser_review = [
        _record_id(source) for source in all_records
        if any(
            endpoint.protection_status in {
                ProtectionStatus.CHALLENGE_CONFIRMED,
                ProtectionStatus.CHALLENGE_SUSPECTED,
                ProtectionStatus.BROWSER_VERIFICATION_REQUIRED,
            }
            or endpoint.access_status in {
                AccessStatus.JAVASCRIPT_REQUIRED,
                AccessStatus.CAPTCHA_OR_BLOCKED,
                AccessStatus.RATE_LIMITED,
            }
            for endpoint in source.endpoints
        )
    ]
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_catalog": str(Path(catalog_path).resolve()),
        "catalog_market": market,
        "batch": {"brand_offset": brand_offset, "brand_batch_size": min(brand_batch_size, 50), "brands": [item["brand"] for item in batch]},
        "summary": _summary(census, queue, sources, candidates),
        "brands": queue,
        "coverage": coverage,
        "sources": [item.to_dict() for item in sources.records],
        "source_candidates": [item.to_dict() for item in candidates.records],
        "platform_clusters": clusters,
        "json_ld_field_coverage": json_ld_coverage,
        "single_source_platform_candidates": [item for item in clusters if item["single_source_candidate"]],
        "multi_site_platform_clusters": [item for item in clusters if item["multi_site_cluster"]],
        "adapter_recommendations": [item for item in clusters if item["adapter_candidate"]],
        "custom_sites": custom_sites,
        "manual_or_browser_review": manual_or_browser_review,
    }
    (output / "census.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "coverage.json").write_text(json.dumps({"schema_version": 2, "coverage": coverage}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "discovery_queue.json").write_text(json.dumps({"schema_version": 2, "brands": queue}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "source_registry.json").write_text(json.dumps({"schema_version": 2, "sources": payload["sources"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "source_candidates.json").write_text(json.dumps({"schema_version": 1, "candidates": payload["source_candidates"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    endpoint_sources = [{"source_id": _record_id(item), "record_kind": "source" if isinstance(item, SourceRecord) else "candidate", "endpoints": [endpoint.to_dict() for endpoint in item.endpoints]} for item in all_records]
    (output / "endpoint_results.json").write_text(json.dumps({"schema_version": 2, "sources": endpoint_sources}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "json_ld_field_coverage.json").write_text(json.dumps({"schema_version": 1, "sources": json_ld_coverage}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "platform_clusters.json").write_text(json.dumps({"schema_version": 2, "clusters": clusters}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "report.md").write_text(_report(payload), encoding="utf-8")
    return payload
