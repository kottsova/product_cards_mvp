# Stage 7.1 — catalog-backed identity reconciliation

The research entry point is `python -m product_tool.census.runner_v71 --live`.
It first writes a completely offline baseline replay and only then allows new HTTP
for high-confidence candidates from real original titles that Stage 7 did not query.
A completed run refuses accidental repetition. `--replay-saved` reconstructs the
result exclusively from hash-checked baseline and Stage 7.1 snapshots, without HTTP.
The report renderer is `python -m product_tool.census.report_v71`.

`catalog_identity.py` streams the original `Товары` sheet read-only and preserves
all columns, row references, raw titles/codes, alternative titles and duplicates.
Ambiguity prevents final identity/dealer decisions and new HTTP. Rules live in
`product_tool/config/identity_reconciliation.v1.json`; seller and internal codes
are separate from manufacturer/regional/marketing models. WB identifiers never
become queries. Plans contain at most three distinct queries, retain punctuation,
and record role, source, confidence, normalization and extraction reason.

`PageIdentity.structured_product_name` is optional. Existing positional constructor
arguments and legacy verifier behavior remain supported. Stage 7.1 opts into strict
punctuation/model consistency and structured marketing-name verification. Product
JSON-LD/microdata is allowed; arbitrary page text is not. Source ownership, category,
token boundaries, model qualifiers and significant variants constrain exactness.

Scopes hash the complete reconciled identity, catalog hash, rules, domains and
parser/ranking semantics. Stage 7 absence/checkpoints never authorize Stage 7.1
dealers. Query response receipt is distinct from verified search evidence; missing,
truncated or unvalidated evidence leaves the official search incomplete. The existing
Sulpak gate is only consulted after all new completeness conditions pass.

Budgets remain 10 requests/domain/product, 40/product, three target pages/domain,
40 seconds/domain/product, three sitemap documents/800 URLs and at most three
queries/product; Stage 7.1 additionally caps all new HTTP at 24, counting redirects.
Only saved declared routes on existing official domains are executable. HTTP
protection is host/endpoint/method scoped, with no browser-to-HTTP inheritance.
No browser imports/runs, production integration, dealer expansion, attributes,
photos or instruction-document extraction are part of this stage.

The completed 11-product audit is in
`reports/source_census_2026-09-22_stage7_1/report.md`.
