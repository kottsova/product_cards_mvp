# Bounded discovery orchestration plan

This is an architecture contract, not a production implementation.

## Pipeline

`CatalogCoverage -> BrandNormalization -> SourceCandidate -> OfficialDomainEvidence -> AccessProbe -> DiscoveryStrategy -> StructuredIdentityValidation -> ReadinessDecision`.

The orchestrator consumes only canonical v2 source records plus the non-executable normalization and research registries. It must never promote a research candidate into the runtime registry automatically.

## Strategy contracts

- `SitemapStrategy.discover(source, budget) -> CandidatePage[]`: reuse `parse_sitemap` and `bounded_sitemap_discovery`; enforce host allowlists, depth/item caps, robots evidence, checkpointing, and 1–3 product candidates.
- `InternalSearchStrategy.discover(source, identity, budget) -> CandidatePage[]`: reuse `detect_internal_search`; submit only explicitly discovered first-party forms/endpoints; record the query and result route.
- `EmbeddedStateStrategy.extract(page) -> StructuredCandidate[]`: reuse `detect_embedded_state`; retain JSON paths and field provenance, never tokens or cookie values.
- `JsonLdStrategy.extract(page) -> PageIdentity`: reuse `json_ld_products` and field coverage; exactness must go through `IdentityVerifier`.
- `SupportStrategy.discover(source, identity, budget) -> CandidatePage[]`: bounded support/manual lookup with product-code evidence and document-host allowlists.
- `BrowserAssistedStrategy`: opt-in/manual queue only; no CAPTCHA solving, stealth, or protection bypass.

Every strategy returns evidence, confidence, redirects, final URL, access/protection status, and a stop reason. It cannot return `production_ready`.

## Orchestrator responsibilities

The missing orchestration layer owns a per-source request budget, low-rate scheduling, immediate host stop on 403/429/confirmed challenge, resumable checkpoints, deduplication, and deterministic strategy order. It selects at most three real product samples per family and passes only structured fields to `IdentityVerifier`.

Readiness is a monotonic evidence decision: official domain, access checked, reproducible discovery, structured exact identity including significant variants, then adapter readiness. One successful URL is insufficient.

## Existing primitives and gaps

Reusable now: access/protection classification, endpoint records, sitemap parsing/caps, search-form detection, embedded-state detection, JSON-LD field coverage, platform fingerprinting, `ProductIdentity`, and `IdentityVerifier`.

Still missing: a shared budget/checkpoint coordinator, safe internal-search execution contract, sitemap candidate ranking, embedded-state JSON-path extraction, support/manual strategy, browser/manual work queue, cross-strategy candidate deduplication, and readiness adjudication.

## Non-goals

No SamsungAdapter, AEM adapter/discovery, generic production JSON-LD adapter, mass extraction, protection bypass, or automatic mutation of the production source registry.

