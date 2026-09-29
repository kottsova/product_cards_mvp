"""Stage 3 normalization-aware coverage; stage 2 files are read-only inputs."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from .brands import load_brand_normalization
from .catalog import load_catalog_coverage
from .research import load_source_research


def build_stage3(
    catalog_path: str | Path,
    stage2_dir: str | Path,
    output_dir: str | Path,
    *,
    research_results_path: str | Path | None = None,
) -> dict:
    catalog = load_catalog_coverage(catalog_path)
    registry = load_brand_normalization()
    registry.validate_catalog_labels(catalog.brands)
    stage2 = json.loads((Path(stage2_dir) / "discovery_queue.json").read_text(encoding="utf-8"))
    stage2_by_label = {item["brand"]: item for item in stage2["brands"]}
    research = load_source_research()
    if research_results_path and Path(research_results_path).exists():
        research_results = json.loads(Path(research_results_path).read_text(encoding="utf-8"))
    else:
        research_results = {"families": research["families"]}
    researched_by_family = {x["source_family_id"]: x for x in research_results["families"]}

    existing_verified = set()
    for label, record in stage2_by_label.items():
        if record["verification_status"] not in {"research_pending", "candidate"}:
            mapping = registry.get(label)
            if mapping.review_status != "requires_human_review":
                existing_verified.add(mapping.source_family_id)
                existing_verified.update(str(route["source_family_id"]) for route in mapping.source_family_routes)
    new_verified = {k for k, v in researched_by_family.items() if v["research_status"] == "official_verified"}
    verified_families = existing_verified | new_verified

    family_labels = defaultdict(set)
    for mapping in registry.records:
        family_labels[mapping.source_family_id].add(mapping.original_brand_label)
        for route in mapping.source_family_routes:
            family_labels[str(route["source_family_id"])].add(mapping.original_brand_label)

    label_products = Counter()
    family_products = Counter()
    category_family_products = Counter()
    for row in catalog.coverages:
        if not row.brand:
            continue
        mapping = registry.get(row.brand)
        family = mapping.family_for(row.category_group)
        label_products[row.brand] += row.unique_products
        family_products[family] += row.unique_products
        category_family_products[(row.category_group, family)] += row.unique_products

    labels = []
    covered_products = 0
    for mapping in registry.records:
        routed = {mapping.source_family_id} | {str(x["source_family_id"]) for x in mapping.source_family_routes}
        safe_mapping = mapping.review_status != "requires_human_review"
        covered = safe_mapping and bool(routed & verified_families)
        research_items = [researched_by_family[x] for x in routed if x in researched_by_family]
        negative = any(x["research_status"] == "official_source_not_found" for x in research_items)
        if not safe_mapping:
            final_status = "unresolved_requires_human_review"
        elif covered:
            shared = mapping.relationship != "exact" or any(len(family_labels[x]) > 1 for x in routed if x in family_labels)
            final_status = "mapped_to_verified_source_family" if shared else "verified_independent_brand"
        elif negative:
            final_status = "official_source_not_found"
        else:
            final_status = "unresolved_requires_human_review"
        products = label_products[mapping.original_brand_label]
        if covered:
            covered_products += products
        labels.append({
            "original_brand_label": mapping.original_brand_label,
            "canonical_brand": mapping.canonical_brand,
            "source_family_id": mapping.source_family_id,
            "relationship": mapping.relationship,
            "review_status": mapping.review_status,
            "unique_products": products,
            "official_coverage_inherited": covered,
            "final_status": final_status,
        })

    total = catalog.observed_totals["unique_products"]
    relationship_counts = Counter(x.relationship for x in registry.records)
    final_counts = Counter(x["final_status"] for x in labels)
    summary = {
        "source_labels": len(registry.records),
        "canonical_brands": len(registry.canonical_brands),
        "source_families": len(registry.source_families),
        "verified_source_families": len(verified_families),
        "new_priority_families_researched": len(research["families"]),
        "new_official_sources_verified": len(new_verified),
        "official_source_not_found": sum(x["research_status"] == "official_source_not_found" for x in research["families"]),
        "covered_unique_products": covered_products,
        "total_unique_products": total,
        "official_coverage_share": round(covered_products / total, 6),
        "relationship_counts": dict(sorted(relationship_counts.items())),
        "final_status_counts": dict(sorted(final_counts.items())),
    }
    output = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog": catalog.observed_totals,
        "summary": summary,
        "labels": sorted(labels, key=lambda x: x["original_brand_label"].casefold()),
        "families": [
            {"source_family_id": family, "unique_products": products, "verified": family in verified_families}
            for family, products in sorted(family_products.items())
        ],
        "category_groups": [
            {"category_group": category, "source_family_id": family, "unique_products": products, "verified": family in verified_families}
            for (category, family), products in sorted(category_family_products.items())
        ],
        "readiness_policy": {
            "official_domain_verified": "first-party relationship evidence",
            "access_checked": "bounded access probe completed",
            "discovery_validated": "reproducible sitemap/search/embedded-state path",
            "exact_identity_validated": "structured ProductIdentity model and significant variants",
            "production_ready": "all previous levels plus enabled adapter; never inferred from one URL",
        },
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "normalized_coverage.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "source_research.json").write_text(json.dumps(research_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "census.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    normalization_payload = json.loads((Path(__file__).resolve().parents[1] / "config" / "brand_normalization.v1.json").read_text(encoding="utf-8"))
    (out / "brand_normalization.json").write_text(json.dumps(normalization_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    clusters = defaultdict(lambda: {"families": set(), "endpoints": 0, "status_counts": Counter(), "max_confidence": 0.0})
    custom_families = set()
    manual_families = set()
    for family in research_results["families"]:
        recognized = False
        for endpoint in family.get("endpoint_results", ()):
            if endpoint.get("access_status") in {"captcha_or_blocked", "rate_limited", "javascript_required", "browser_assisted"}:
                manual_families.add(family["source_family_id"])
            for fingerprint in endpoint.get("fingerprints", ()):
                engine = fingerprint["engine"]
                if engine == "custom_unknown":
                    continue
                recognized = True
                cluster = clusters[engine]
                cluster["families"].add(family["source_family_id"])
                cluster["endpoints"] += 1
                cluster["status_counts"][fingerprint["status"]] += 1
                cluster["max_confidence"] = max(cluster["max_confidence"], float(fingerprint["confidence"]))
        if family["research_status"] == "official_verified" and not recognized:
            custom_families.add(family["source_family_id"])
        if family.get("checkpoint", {}).get("status") == "stopped":
            manual_families.add(family["source_family_id"])
    cluster_report = {
        "schema_version": 1,
        "generated_at": output["generated_at"],
        "clusters": [
            {
                "engine": engine,
                "families": sorted(value["families"]),
                "family_count": len(value["families"]),
                "endpoint_evidence_count": value["endpoints"],
                "status_counts": dict(value["status_counts"]),
                "max_confidence": value["max_confidence"],
                "adapter_recommendation": "evaluate_after_exact_identity_sampling" if len(value["families"]) >= 2 else "no_shared_adapter_case",
            }
            for engine, value in sorted(clusters.items())
        ],
        "custom_or_unknown_families": sorted(custom_families),
        "browser_or_manual_review_families": sorted(manual_families),
        "recommended_first_family": {
            "strategy": "sitemap_catalog_feed",
            "kind": "bounded_discovery_strategy_not_product_adapter",
            "reason": "Broadest multi-brand evidence and reusable existing bounded sitemap primitives; exact identity remains a separate gate.",
        },
        "platform_adapter_note": "Shopify is the first platform-adapter evaluation candidate (Dreame and HyperX), but is not implementation-ready until reproducible product discovery and structured exact identity are sampled. AEM remains explicitly out of scope.",
    }
    (out / "platform_clusters.json").write_text(json.dumps(cluster_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def write_report(output: dict, output_dir: str | Path, *, stage2_official_share: float = 0.771554) -> Path:
    s = output["summary"]
    endpoint_path = Path(output_dir) / "endpoint_results.json"
    endpoints = json.loads(endpoint_path.read_text(encoding="utf-8")) if endpoint_path.exists() else {"families": []}
    endpoint_rows = [e for f in endpoints["families"] for e in f.get("endpoint_results", ())]
    access_counts = Counter(e["access_status"] for e in endpoint_rows)
    checkpoint_counts = Counter(f.get("checkpoint", {}).get("status", "pending") for f in endpoints["families"])
    rows = [
        "# All-brand source census — stage 3",
        "",
        "Stage 2 preserved as immutable baseline. No SamsungAdapter, AEM discovery, production JSON-LD adapter, or production discovery orchestration was implemented.",
        "",
        "## Normalization and coverage",
        "",
        f"- Source labels: {s['source_labels']}; canonical brands: {s['canonical_brands']}; source families: {s['source_families']}.",
        f"- Researched priority families: {s['new_priority_families_researched']}; newly verified official sources: {s['new_official_sources_verified']}; official source not found: {s['official_source_not_found']}.",
        f"- Official coverage after safe normalization: {s['official_coverage_share']:.1%} ({s['covered_unique_products']} / {s['total_unique_products']} products); stage 2: {stage2_official_share:.1%}.",
        f"- Explicit label outcomes: {json.dumps(s['final_status_counts'], ensure_ascii=False, sort_keys=True)}.",
        "",
        "Mappings marked requires_human_review never inherit source coverage. Bosch Home and Bosch Tools remain separate routed families. POCO remains a distinct brand identity routed through the verified Xiaomi family; exact identity still requires structured model/variant evidence.",
        "",
        "## Bounded research and probes",
        "",
        "The registry contains the next 50 priority unresolved families. Accesstyle is an explicit negative result: the guessed domain is unrelated and no first-party source was accepted. Probe results are checkpointed per family, use declared allowlisted hosts only, retain redirects/status/protection/fingerprints, and stop the whole host after 403, 429, or a confirmed challenge. No bypass is attempted.",
        f"Bounded pass: {len(endpoint_rows)} endpoints; access statuses {json.dumps(dict(access_counts), sort_keys=True)}; checkpoints {json.dumps(dict(checkpoint_counts), sort_keys=True)}.",
        "",
        "A probe completing homepage/robots/sitemap is access_checked only. It is not product discovery, exact identity, or production readiness. Product samples remain incomplete where no bounded reproducible product route was found.",
        "",
        "## Readiness",
        "",
        "- Official-domain, access, discovery, exact-identity, and production-ready levels are independent.",
        "- Arbitrary body substring matches no longer qualify as exact identity in stage 3.",
        "- Existing stage-2 readiness is not promoted by the new research registry.",
        "",
        "## Recommendation",
        "",
        "Implement the bounded sitemap/catalog-feed discovery strategy described in docs/DISCOVERY_ORCHESTRATION_PLAN.md before any product adapter. Shopify (Dreame + HyperX) is the first platform-adapter evaluation candidate, but not implementation-ready until reproducible discovery and structured exact identity are sampled. Current evidence still does not justify a common JSON-LD or AEM production adapter.",
    ]
    path = Path(output_dir) / "report.md"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path
