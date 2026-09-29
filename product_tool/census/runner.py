"""Generate all-brand coverage and a bounded first-pass source census."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .catalog import CatalogCensus, load_catalog_coverage
from .endpoint_probe import guarded_entry_point
from .models import AccessStatus, AdapterStatus, FingerprintStatus, LifecycleStatus, SourceRecord
from .probe import AccessProbe, ProbePolicy
from .registry import SourceCatalog, load_source_catalog


def _source_recommendation(record: SourceRecord) -> str:
    if record.access_status in {AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED}:
        return "manual_or_browser_review"
    if record.access_status in {AccessStatus.JAVASCRIPT_REQUIRED, AccessStatus.BROWSER_ASSISTED}:
        return "browser_assisted_research"
    if record.presumed_engine in {"shopify", "magento", "salesforce_commerce_cloud", "woocommerce"}:
        return f"shared_{record.presumed_engine}_adapter"
    if record.presumed_engine in {"next_js", "nuxt", "adobe_experience_manager", "sitecore"}:
        return f"shared_{record.presumed_engine}_discovery_layer"
    if record.presumed_engine == "generic_json_ld_product":
        return "generic_json_ld_product_adapter"
    if record.presumed_engine == "sitemap_catalog_feed":
        return "generic_sitemap_catalog_adapter"
    return "custom_research_required"


def probe_sources(catalog: SourceCatalog, *, limit: int, policy: ProbePolicy | None = None) -> SourceCatalog:
    if limit <= 0:
        return catalog
    probe = AccessProbe(policy=policy)
    updated: list[SourceRecord] = []
    checked = 0
    for record in catalog.records:
        # Stage 16: the literal named exclusion this eligibility check used
        # to carry was redundant with the generic registry-driven filter
        # below (this legacy census registry has no such record at all --
        # official_status.value == "official_verified" already excludes
        # anything not verified in it) -- removed, not replaced.
        eligible = (
            checked < limit and record.candidate_url and record.page_hosts
            and record.official_status.value == "official_verified"
            and record.access_status == AccessStatus.NOT_CHECKED
        )
        if not eligible:
            updated.append(record)
            continue
        result = probe.probe(record.candidate_url, allowed_hosts=record.page_hosts)
        checked += 1
        fingerprints = tuple(item.to_dict() for item in result.fingerprints)
        best = result.fingerprints[0] if result.fingerprints else None
        fingerprint_status = best.status if best else FingerprintStatus.INSUFFICIENT
        lifecycle = LifecycleStatus.FINGERPRINTED if best else LifecycleStatus.ACCESS_CHECKED
        adapter_status = AdapterStatus.RECOMMENDED if best and best.engine != "custom_unknown" else record.adapter_status
        candidate = replace(
            record,
            access_status=result.access_status,
            fingerprint_status=fingerprint_status,
            adapter_status=adapter_status,
            lifecycle_status=lifecycle,
            last_checked_at=result.checked_at,
            http_status=result.http_status,
            redirect_chain=result.redirect_chain,
            robots_status=result.robots_status,
            sitemap_status=result.sitemap_status,
            javascript_required=result.javascript_required,
            protection_status=result.protection_status,
            product_search_available=result.product_search_available,
            platform_fingerprints=fingerprints,
            presumed_engine=best.engine if best else "custom_unknown",
            confidence=best.confidence if best else 0.0,
            sample_urls=(result.final_url,) if result.final_url else (),
        )
        updated.append(replace(candidate, adapter_recommendation=_source_recommendation(candidate)))
    return SourceCatalog(updated)


def _brand_records(census: CatalogCensus, sources: SourceCatalog) -> list[dict[str, Any]]:
    aggregates: dict[str, dict[str, Any]] = {}
    for coverage in census.coverages:
        if not coverage.brand:
            continue
        item = aggregates.setdefault(coverage.brand_canonical, {
            "brand": coverage.brand, "market": coverage.market,
            "unique_products": 0, "source_rows": 0,
            "categories": 0, "category_groups": set(),
        })
        item["unique_products"] += coverage.unique_products
        item["source_rows"] += coverage.source_rows
        item["categories"] += 1
        item["category_groups"].add(coverage.category_group)
    result = []
    for key, item in sorted(aggregates.items(), key=lambda pair: (-pair[1]["unique_products"], pair[0])):
        known = sources.for_brand(item["brand"])
        result.append({
            **{name: value for name, value in item.items() if name != "category_groups"},
            "category_groups": sorted(item["category_groups"]),
            "coverage_share": round(item["unique_products"] / census.expected_totals["unique_products"], 6),
            "research_status": "source_known" if known else "research_pending",
            "source_ids": [source.source_id for source in known],
        })
    return result


def _coverage_records(census: CatalogCensus, sources: SourceCatalog) -> list[dict[str, Any]]:
    records = []
    for coverage in census.coverages:
        matches = sources.match(coverage.brand, coverage.category, coverage.market) if coverage.brand else ()
        value = coverage.to_dict()
        value.update({
            "coverage_share": round(coverage.unique_products / census.expected_totals["unique_products"], 6),
            "source_ids": [item.source_id for item in matches],
            "research_status": "source_known" if matches else "research_pending",
        })
        records.append(value)
    return records


def _clusters(records: tuple[SourceRecord, ...], brand_products: dict[str, int]) -> list[dict[str, Any]]:
    grouped: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        if record.fingerprint_status == FingerprintStatus.NOT_CHECKED or record.official_status.value == "not_allowed":
            continue
        grouped[record.presumed_engine].append(record)
    clusters = []
    for engine, items in grouped.items():
        brand_map: dict[str, str] = {}
        for item in items:
            for brand in item.brands:
                brand_map.setdefault(brand.casefold(), brand)
        brands = sorted(brand_map.values(), key=str.casefold)
        product_count = sum(brand_products.get(key, 0) for key in brand_map)
        clusters.append({
            "engine": engine, "sources": [item.source_id for item in items],
            "brands": brands, "catalog_products": product_count,
            "adapter_recommendations": sorted({item.adapter_recommendation for item in items}),
        })
    return sorted(clusters, key=lambda item: (-item["catalog_products"], item["engine"]))


def _summary(census: CatalogCensus, sources: SourceCatalog, brands: list[dict[str, Any]]) -> dict[str, Any]:
    accessible = {AccessStatus.DIRECT_ACCESS, AccessStatus.STRUCTURED_API, AccessStatus.SEARCH_ONLY, AccessStatus.SUPPORT_ONLY}
    blocked = {AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED}
    known_brands = sum(item["research_status"] == "source_known" for item in brands)
    return {
        "catalog": census.expected_totals,
        "brands_researched": known_brands,
        "brands_research_pending": len(brands) - known_brands,
        "sources_total": len(sources.records),
        "sources_enabled": sum(item.enabled for item in sources.records),
        "sources_accessible": sum(item.access_status in accessible for item in sources.records),
        "sources_blocked": sum(item.access_status in blocked for item in sources.records),
        "sources_not_checked": sum(item.access_status == AccessStatus.NOT_CHECKED for item in sources.records),
        "unresolved_brand_products": sum(item.unique_products for item in census.unresolved_brand_coverages),
        "unresolved_brand_category_pairs": len(census.unresolved_brand_coverages),
    }


def _report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    top = payload["brands"][:20]
    clusters = payload["platform_clusters"]
    manual = payload["manual_or_browser_review"]
    custom = payload["custom_sites"]
    recommendations = [item for item in clusters if item["engine"] not in {"custom_unknown"} and item["catalog_products"]]
    first = recommendations[0] if recommendations else None
    lines = [
        "# All-brand source census", "",
        f"Generated: {payload['generated_at']}", "",
        "## Status", "",
        f"- Catalog brands: {summary['catalog']['brands']}",
        f"- Brand/category pairs: {summary['catalog']['brand_category_pairs']}",
        f"- Brands with at least one confirmed source record: {summary['brands_researched']}",
        f"- Brands still research_pending: {summary['brands_research_pending']}",
        f"- Sources: {summary['sources_total']} total, {summary['sources_accessible']} accessible, {summary['sources_blocked']} blocked, {summary['sources_not_checked']} not checked",
        f"- Unresolved-brand products retained separately: {summary['unresolved_brand_products']}", "",
        "## Largest brands", "", "| Brand | Products | Categories | Status | Sources |", "| --- | ---: | ---: | --- | --- |",
    ]
    lines.extend(f"| {item['brand']} | {item['unique_products']} | {item['categories']} | {item['research_status']} | {', '.join(item['source_ids']) or '—'} |" for item in top)
    lines.extend(["", "## Platform clusters", "", "| Engine | Sources | Catalog products | Recommendation |", "| --- | ---: | ---: | --- |"]) 
    lines.extend(f"| {item['engine']} | {len(item['sources'])} | {item['catalog_products']} | {', '.join(item['adapter_recommendations'])} |" for item in clusters)
    lines.extend(["", "## Custom sites", "", *(f"- {item}" for item in custom or ["None classified yet."]), "", "## Browser or manual review", "", *(f"- {item}" for item in manual or ["None in this pass."]), "", "## First platform recommendation", ""])
    if first:
        lines.append(f"Implement `{first['adapter_recommendations'][0]}` first: the current evidence cluster covers {first['catalog_products']} catalog products across {len(first['brands'])} brand labels. Validate product-search and exact-identity behavior before enabling it.")
    else:
        lines.append("No platform family has enough confirmed fingerprint evidence yet. Run another bounded access/fingerprint pass before choosing an adapter.")
    lines.extend(["", "Unknown domains were not synthesized from brand names; they remain `research_pending`.", ""])
    return "\n".join(lines)


def generate_census(
    catalog_path: str | Path,
    output_dir: str | Path,
    *,
    market: str = "KZ",
    probe_limit: int = 0,
    min_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    census = load_catalog_coverage(catalog_path, market=market)
    sources = probe_sources(load_source_catalog(), limit=probe_limit, policy=ProbePolicy(min_interval_seconds=min_interval_seconds))
    brands = _brand_records(census, sources)
    coverage = _coverage_records(census, sources)
    brand_products = {item["brand"].casefold(): item["unique_products"] for item in brands}
    clusters = _clusters(sources.records, brand_products)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_catalog": str(Path(catalog_path).resolve()),
        "market": market,
        "summary": _summary(census, sources, brands),
        "brands": brands,
        "coverage": coverage,
        "sources": [item.to_dict() for item in sources.records],
        "platform_clusters": clusters,
        "custom_sites": [item.source_id for item in sources.records if item.presumed_engine == "custom_unknown" and item.fingerprint_status == FingerprintStatus.INSUFFICIENT],
        "manual_or_browser_review": [item.source_id for item in sources.records if item.access_status in {AccessStatus.JAVASCRIPT_REQUIRED, AccessStatus.BROWSER_ASSISTED, AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED, AccessStatus.REGIONAL_REDIRECT}],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "census.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "coverage.json").write_text(json.dumps({"schema_version": 1, "coverage": coverage}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "source_registry.json").write_text(json.dumps({"schema_version": 1, "sources": payload["sources"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "platform_clusters.json").write_text(json.dumps({"schema_version": 1, "clusters": clusters}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "report.md").write_text(_report(payload), encoding="utf-8")
    return payload


@guarded_entry_point
def main() -> None:
    parser = argparse.ArgumentParser(description="Build all-brand source coverage and bounded source census")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/source_census_2026-09-21"))
    parser.add_argument("--market", "--catalog-market", dest="market", default="unknown")
    parser.add_argument("--probe-limit", type=int, default=0)
    parser.add_argument("--min-interval", type=float, default=2.0)
    parser.add_argument("--endpoint-limit-per-source", type=int, default=5)
    parser.add_argument("--brand-offset", type=int, default=0)
    parser.add_argument("--brand-batch-size", type=int, default=50)
    args = parser.parse_args()
    payload = generate_census(
        args.catalog, args.output, market=args.market, probe_limit=args.probe_limit,
        min_interval_seconds=args.min_interval,
        endpoint_limit_per_source=args.endpoint_limit_per_source,
        brand_offset=args.brand_offset, brand_batch_size=args.brand_batch_size,
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


from .runner_v2 import generate_census_v2 as generate_census  # noqa: E402


if __name__ == "__main__":
    main()
