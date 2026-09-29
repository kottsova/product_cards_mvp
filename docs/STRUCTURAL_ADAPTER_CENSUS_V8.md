# Stage 8: all-source structural adapter census

Stage 8 is a research-only contract census. It does not import or modify production
adapters and does not search catalog model codes. Entry points:

- `python -m product_tool.census.structural_runner_v8 --live`: bounded sampling;
  completed profile checkpoints prevent repeated work.
- `python -m product_tool.census.structural_report_v8`: offline fixture review,
  schema validation, source-family matrix, label coverage and protected-file audit.

The scope is the union of verified source/catalog/research/domain registries and
explicit support hosts. Bosch's category routing label is not an additional site.
Bosch Home and Tools remain distinct. HYPERX and HIPER remain distinct. Sulpak is
limited to its existing LG appliance scope; no other dealer is eligible.

New HTTP is capped at 500 requests including redirects, 8 per exact host, 5 per
profile, 700,000 response bytes and 35 seconds per profile. Every redirect is
checked against existing allowed hosts. No protected host retries, browser runs,
login, rotating identity or model-search expansion is allowed. HTTP access history
is separate from browser observations. Successful historical snapshots are opened
read-only and hash-checked before structural inspection.

The five independent layers are discovery, identity, specifications, media and
documents. CMS fingerprints do not enter cluster keys. Signatures exclude product
values, arbitrary CSS IDs and campaign parameters. Fixtures contain structural
contracts and content hashes, never raw new HTML or completed product cards.
Only explicitly reviewed compatible contracts can become shared/regional research
candidates; a single source or unresolved identity/variant semantics stays custom.
All declarations retain `production_ready=false`.

Outputs are in `reports/source_census_2026-09-22_stage8/`. Declarative profile and
JSON Schema copies are in `product_tool/config/adapter_profiles.v1*.json`; the
production registry does not load them. The matrix records every original brand
label, including explicit unresolved statuses with next actions. An incomplete
structural sample is not evidence that a catalog product is absent and cannot
activate dealer fallback.
