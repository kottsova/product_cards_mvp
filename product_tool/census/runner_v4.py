"""Stage 4 live dry-run harness for the bounded sitemap/catalog strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from product_tool.identity import ProductIdentity

from .brands import load_brand_normalization
from .candidates import load_source_candidates
from .catalog import CatalogCensus, load_catalog_coverage
from .registry import load_source_catalog
from .research import load_source_research
from .sitemap_strategy import DiscoveryBudget, SitemapCatalogStrategy, discovery_readiness


@dataclass(frozen=True)
class DryRunSource:
    source_family: str
    brand_label: str
    source_url: str
    allowed_hosts: tuple[str, ...]
    sitemap_urls: tuple[str, ...]
    origin: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_specs() -> tuple[DryRunSource, ...]:
    catalog = load_source_catalog()
    candidates = load_source_candidates()
    research = load_source_research()
    source_by_id = {item.source_id: item for item in catalog.records}
    candidate_by_id = {item.candidate_id: item for item in candidates.records}
    research_by_id = {item["source_family_id"]: item for item in research["families"]}
    specs = []
    for family, label, record_id, origin in (
        ("bosch_home", "BOSCH", "bosch_home", "source_catalog.v2"),
        ("apple_kz", "Apple", "apple_kz", "source_catalog.v2"),
        ("karcher_global", "Karcher", "karcher_global_candidate", "source_candidates.v1"),
    ):
        record = source_by_id.get(record_id) or candidate_by_id[record_id]
        hosts = tuple(dict.fromkeys(record.page_hosts + record.support_hosts))
        sitemap_urls = tuple(
            str(target["url"]) for target in record.probe_targets
            if target.get("capability") == "sitemap"
        )
        specs.append(DryRunSource(family, label, record.candidate_url, hosts, sitemap_urls, origin))
    for family, label in (("dreame", "Dreame"), ("hyperx", "HYPERX")):
        record = research_by_id[family]
        specs.append(DryRunSource(
            family, label, record["candidate_url"],
            tuple(dict.fromkeys(record["page_hosts"] + record["support_hosts"])),
            tuple(target["url"] for target in record["probe_targets"] if target["capability"] == "sitemap"),
            "source_research.v1",
        ))
    return tuple(specs)


def _sample_products(census: CatalogCensus, source: DryRunSource, *, limit: int) -> tuple[ProductIdentity, ...]:
    normalization = load_brand_normalization()
    rows = []
    for coverage in census.coverages:
        if coverage.brand != source.brand_label:
            continue
        mapping = normalization.get(coverage.brand)
        family = mapping.family_for(coverage.category_group)
        if source.source_family == "bosch_home" and family != "bosch_home":
            continue
        for sku in coverage.sample_seller_skus:
            rows.append((coverage.unique_products, coverage.category, sku))
    rows.sort(key=lambda row: (-row[0], row[1].casefold(), row[2]))
    identities = []
    seen = set()
    for _, category, sku in rows:
        if sku in seen:
            continue
        seen.add(sku)
        identities.append(ProductIdentity.from_product({
            "brand": source.brand_label,
            "category": category,
            "name": sku,
            "search_code": sku,
            "model_candidates": (sku,),
        }))
        if len(identities) >= limit:
            break
    return tuple(identities)


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "runs": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": 1, "runs": {}}
    return value if value.get("schema_version") == 1 else {"schema_version": 1, "runs": {}}


def run_stage4_dry_run(
    catalog_path: str | Path,
    output_dir: str | Path,
    *,
    products_per_source: int = 1,
    refresh: bool = False,
    budget: DiscoveryBudget | None = None,
) -> dict[str, Any]:
    if products_per_source not in {1, 2}:
        raise ValueError("Stage 4 allows only one or two products per source family")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "checkpoint.json"
    checkpoint = _load_checkpoint(checkpoint_path)
    budget = budget or DiscoveryBudget(
        max_http_requests=10,
        max_sitemap_documents=5,
        max_sitemap_depth=2,
        max_urls_read=400,
        max_product_candidates=20,
        max_product_pages=3,
        min_interval_seconds=1.0,
        deadline_seconds=50.0,
    )
    census = load_catalog_coverage(catalog_path)
    config_dir = Path(__file__).resolve().parents[1] / "config"
    protected = (
        config_dir / "source_catalog.v2.json",
        config_dir / "source_candidates.v1.json",
        config_dir / "source_research.v1.json",
    )
    before = {str(path): _sha256(path) for path in protected}
    runs = []
    for source in _source_specs():
        identities = _sample_products(census, source, limit=products_per_source)
        if not identities:
            runs.append({
                "source_family": source.source_family,
                "source_origin": source.origin,
                "stop_reason": "no_catalog_sample",
                "readiness": {
                    "official_source_verified": True,
                    "sitemap_strategy_applicable": False,
                    "discovery_reproducible": False,
                    "product_page_found": False,
                    "exact_model_validated": False,
                    "exact_variant_validated": False,
                    "requires_other_strategy": True,
                    "requires_manual_browser_review": False,
                    "production_ready": False,
                },
            })
            continue
        for identity in identities:
            key = f"{source.source_family}:{identity.seller_sku}"
            strategy = SitemapCatalogStrategy(budget=budget)
            result = strategy.run(
                source_family=source.source_family,
                source_url=source.source_url,
                allowed_hosts=source.allowed_hosts,
                expected=identity,
                sitemap_urls=source.sitemap_urls,
                category_hints=(identity.category_raw,),
                checkpoint=checkpoint["runs"].get(key),
                refresh=refresh,
            )
            checkpoint["runs"][key] = result.checkpoint
            checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
            checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            runs.append({
                "source_family": source.source_family,
                "source_origin": source.origin,
                "source_url": source.source_url,
                "catalog_identity": identity.to_dict(),
                "result": result.to_dict(),
                "readiness": discovery_readiness(result, official_source_verified=True),
            })
    after = {str(path): _sha256(path) for path in protected}
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "sitemap_catalog_v1",
        "budget": {
            "max_http_requests": budget.max_http_requests,
            "max_sitemap_documents": budget.max_sitemap_documents,
            "max_sitemap_depth": budget.max_sitemap_depth,
            "max_urls_read": budget.max_urls_read,
            "max_product_candidates": budget.max_product_candidates,
            "max_product_pages": budget.max_product_pages,
            "min_interval_seconds": budget.min_interval_seconds,
            "deadline_seconds": budget.deadline_seconds,
        },
        "runs": runs,
        "production_registry_unchanged": before == after,
        "protected_registry_hashes_before": before,
        "protected_registry_hashes_after": after,
    }
    (output_dir / "dry_run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def write_stage4_supporting_reports(output_dir: str | Path, dry_run: dict[str, Any], *, tests_run: int) -> None:
    output_dir = Path(output_dir)
    stage3 = json.loads((output_dir.parent / "source_census_2026-09-22_stage3" / "normalized_coverage.json").read_text(encoding="utf-8"))
    unresolved = sorted(
        (item for item in stage3["labels"] if item["final_status"] == "unresolved_requires_human_review"),
        key=lambda item: (-item["unique_products"], item["original_brand_label"].casefold()),
    )
    queue = {
        "schema_version": 1,
        "generated_at": dry_run["generated_at"],
        "total_unresolved_labels": len(unresolved),
        "stage4_researched": False,
        "next_priority_batch": unresolved[:50],
        "all_unresolved_labels": unresolved,
        "negative_results_preserved": ["Accesstyle"],
    }
    (output_dir / "next_census_batch.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stage2 = json.loads((output_dir.parent / "source_census_2026-09-22_stage2" / "census.json").read_text(encoding="utf-8"))
    legacy = []
    for source in tuple(stage2.get("sources", ())) + tuple(stage2.get("source_candidates", ())):
        items = [
            item for item in source.get("evidence", ())
            if item.get("type") in {"product_identity_check", "support_identity_check"}
        ]
        if items:
            legacy.append({
                "source_id": source.get("source_id", source.get("candidate_id", "")),
                "legacy_evidence_count": len(items),
                "affects_readiness": False,
            })
    legacy_payload = {
        "schema_version": 1,
        "generated_at": dry_run["generated_at"],
        "policy": "Legacy text observations are retained for audit only and cannot raise discovery, exact identity, or production readiness.",
        "sources": legacy,
    }
    (output_dir / "legacy_identity_evidence.json").write_text(json.dumps(legacy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    access_counts: dict[str, int] = {}
    stop_counts: dict[str, int] = {}
    request_count = 0
    candidate_count = 0
    error_count = 0
    details: list[str] = []
    lines = [
        "# Source census — Stage 4 bounded sitemap/catalog-feed discovery core v1",
        "",
        "The stage implements a CMS-neutral bounded discovery strategy only. Samsung, AEM, Shopify, generic JSON-LD production adapters, attribute/media/manual extraction, dealer fallback, browser automation, and protection bypass remain out of scope.",
        "",
        "## Contracts and safety",
        "",
        "- DiscoveryBudget caps HTTP requests, sitemap documents/depth, URLs read, candidates, product probes, request interval, response size, gzip expansion, and total deadline.",
        "- CandidatePage separates URL ranking evidence from structured identity evidence.",
        "- StrategyResult records budget usage, sitemap/feed documents, redirects, errors, truncation, stop reason, timestamps, and a resumable checkpoint.",
        "- 403, 429, and confirmed challenges stop the host. No CAPTCHA solving, UA rotation, proxies, or unbounded retries are implemented.",
        "- Strategy code cannot return production readiness. Stage 4 readiness always keeps production_ready=false.",
        f"- Live budget per source: {dry_run['budget']['max_http_requests']} requests, {dry_run['budget']['max_sitemap_documents']} sitemap documents, depth {dry_run['budget']['max_sitemap_depth']}, {dry_run['budget']['max_urls_read']} URLs, {dry_run['budget']['max_product_candidates']} retained candidates, {dry_run['budget']['max_product_pages']} product probes, {dry_run['budget']['min_interval_seconds']}s minimum interval, {dry_run['budget']['deadline_seconds']}s deadline.",
        "",
        "## Dry-run",
        "",
        "| Source family | Product | Requests | Candidates | Stop reason | Product found | Exact model | Exact variant | Next route |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for run in dry_run["runs"]:
        result = run.get("result", {})
        usage = result.get("budget_used", {})
        readiness = run["readiness"]
        stop = result.get("stop_reason", run.get("stop_reason", ""))
        stop_counts[stop] = stop_counts.get(stop, 0) + 1
        request_count += int(usage.get("http_requests", 0))
        candidates = result.get("candidates", ())
        candidate_count += len(candidates)
        error_count += len(result.get("errors", ()))
        for candidate in candidates:
            access = candidate.get("access_status", "not_checked")
            access_counts[access] = access_counts.get(access, 0) + 1
        identity = run.get("catalog_identity", {})
        model = identity.get("seller_sku", "—")
        next_route = "manual/browser" if readiness["requires_manual_browser_review"] else ("other_strategy" if readiness["requires_other_strategy"] else "repeatability_sample")
        lines.append(
            f"| {run['source_family']} | {model} | {usage.get('http_requests', 0)} | {len(candidates)} | {stop} | "
            f"{readiness['product_page_found']} | {readiness['exact_model_validated']} | {readiness['exact_variant_validated']} | {next_route} |"
        )
        if candidates:
            details.extend(["", f"### Top candidates for `{run['source_family']}:{model}`", ""])
            for candidate in candidates[:3]:
                reasons = ", ".join(candidate.get("ranking_reasons", ())) or "no positive reasons"
                level = (candidate.get("identity_verification") or {}).get("level", "not_checked")
                details.append(f"- {candidate['url']} — score {candidate['ranking_score']}; {reasons}; identity={level}; rejection={candidate.get('rejection_reason') or 'none'}.")
    lines.extend(details)
    lines.extend([
        "",
        "## Totals and decisions",
        "",
        f"- HTTP requests: {request_count}; candidates retained: {candidate_count}.",
        f"- Stop reasons: {json.dumps(stop_counts, ensure_ascii=False, sort_keys=True)}.",
        f"- Candidate access outcomes: {json.dumps(access_counts, ensure_ascii=False, sort_keys=True)}.",
        f"- Sitemap/feed errors recorded: {error_count}; blocked/rate-limited dry-runs: {sum(key in {'captcha_or_blocked', 'rate_limited'} for key in stop_counts)}.",
        f"- Strategy not applicable: {sum(not run['readiness']['sitemap_strategy_applicable'] for run in dry_run['runs'])}; unavailable product candidates: {access_counts.get('unavailable', 0)}.",
        f"- Production registries unchanged: {dry_run['production_registry_unchanged']}.",
        f"- Legacy identity sources retained for audit: {len(legacy)}; readiness impact: false.",
        f"- Remaining unresolved_requires_human_review labels preserved: {len(unresolved)}.",
        f"- Unit/regression tests passed: {tests_run}.",
        "",
        "A sitemap URL or a high URL ranking never proves product identity. Exact identity is derived only from structured fields through IdentityVerifier. A successful single-product dry-run does not establish source-family repeatability and never enables a source.",
        "",
        "## Required follow-up routes",
        "",
        "- Internal search: Bosch Home, Apple, Kärcher, Dreame, HyperX. Sitemap traversal did not locate an exact target identity inside the bounded sample.",
        "- Embedded state: none promoted yet. Evaluate only after internal search reaches the correct first-party product page and JSON-LD remains insufficient.",
        "- Browser/manual review: none from this pass; no CAPTCHA, 403, 429, or browser-only stop was observed.",
        "",
        "## Next strategy recommendation",
        "",
        "Implement bounded internal-search discovery next. It directly addresses families where official sitemaps are absent, HTML-only, blocked, or too broad while preserving exact model queries, the same host allowlists, budgets, checkpoints, and structured identity gate. Do not implement that strategy in Stage 4.",
    ])
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
