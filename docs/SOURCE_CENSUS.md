# All-brand source census

The census is a discovery and coverage layer. It does not extract product attributes and
does not crawl every SKU.

## Pipeline

`CatalogCoverage -> SourceCandidate -> OfficialDomainEvidence -> AccessProbe -> PlatformFingerprint -> PlatformCluster -> AdapterRecommendation`

The cleaned catalog is read from `data/catalog_2026-09-21_filtered.xlsx`. The importer
reconciles its observations against the control totals on the `Контекст` sheet before it
writes a report.

## Source catalog

Known sources live in `product_tool/config/source_catalog.v2.json`; executable Python no
longer owns the domain list. `source_catalog.v2.schema.json` documents the machine-readable
contract, while `product_tool.census.models.SourceRecord` performs strict runtime
validation, including enum values and unknown fields.
This is the only executable production catalog: the loader rejects every schema version
other than v2, and the obsolete v1 catalog/schema files have been removed after reference
checks. `default_source_registry()` and all census commands resolve this canonical v2 path.

Confirmed domain candidates that have not yet been access-probed are kept separately in
`source_candidates.v1.json`. They can advance the research queue to `official_verified`,
but they cannot be enabled and do not count as product coverage. Promotion to the source
catalog requires endpoint and identity evidence.
Candidate records may retain bounded endpoint results and fingerprints, but remain
non-executable (`enabled=false`).

Each brand queue record exposes five independent confirmation levels:
`official_domain_verified`, `endpoint_sampled`, `product_discovery_validated`,
`exact_identity_validated`, and `production_ready`. The last level is true only for an
enabled source with a ready adapter; an official domain or homepage never implies it.

Sulpak uses an exact five-category allowlist for LG. Split systems are routed to
`review_pending`; televisions, monitors, audio, computers and other electronics are denied.
This rule does not depend on the shared category-group classifier.

`host_verification` defaults to `not_checked`. A source can be selected by the active
registry only when `enabled=true`; any catalog record with `official_status=not_allowed`
is excluded from `SourceRegistry` entirely, by that generic rule alone -- no specific
source name is special-cased in code or documentation for this. Test-injected legacy
adapters remain supported.

## Safe probing

`AccessProbe` performs one bounded GET per configured endpoint, reads at most 512 KB and
uses no automatic retry. It validates the initial host and every redirect against the
source allowlist. A 403 stops that exact endpoint, so support/sitemap/product capabilities
can still be assessed independently. Persistent 429 can stop the host. There is no
protection bypass. A weak `captcha` word is only `challenge_suspected`; confirmed challenge
requires converging signals. Cookie/token values are never stored.

Default census generation is offline:

```powershell
python -m product_tool.census.runner data\catalog_2026-09-21_filtered.xlsx `
  --output reports\source_census_2026-09-22 --catalog-market unknown
```

An explicitly bounded first pass can be requested with `--probe-limit` and
`--min-interval`. Never point the probe at a URL that is absent from the verified source
catalog.

## Fingerprints

The detector uses HTML, headers, cookies, script/asset paths, JSON-LD and embedded state.
Supported initial engines are Shopify, Magento, Salesforce Commerce Cloud/Demandware,
WooCommerce, Adobe Experience Manager, Sitecore, Next.js, Nuxt, generic JSON-LD Product,
sitemap/catalog feed and custom/unknown.

One weak signal can produce only `probable`; it cannot produce `confirmed`. Each result
retains the matched signals, their sources, strengths and weights.

## Outputs

`reports/source_census_2026-09-22_stage2/` contains:

- `census.json`: complete brands, coverage, sources, probes and recommendations;
- `coverage.json`: all brand/category coverage rows;
- `source_registry.json`: source records after the bounded probe;
- `source_candidates.json`: verified but non-executable domain candidates;
- `discovery_queue.json`: persistent queue for every catalog brand;
- `endpoint_results.json`: capability-level access/protection results;
- `platform_clusters.json`: engine clusters and covered catalog volume;
- `json_ld_field_coverage.json`: per-site Product JSON-LD fields and exact-identity evidence;
- `report.md`: compact human-readable status report.

Unknown domains are never synthesized from brand names. Brands without confirmed source
evidence remain `research_pending`.
