# Internal-search discovery v1 (Stage 5)

`InternalSearchStrategy` is a diagnostic discovery strategy. It cannot enable sources or set production readiness. It shares Stage 4 `DiscoveryBudget`, `BudgetUsage`, `CandidatePage`, `StrategyResult`, URL normalization, AccessProbe and structured identity verification.

```python
from product_tool.census.internal_search_strategy import InternalSearchStrategy

result = InternalSearchStrategy().run(
    source_family="example",
    source_url="https://example.com/",
    allowed_hosts=("example.com",),
    expected=product_identity,
    configured_endpoints=({"url": "https://example.com/search", "query_parameter": "q"},),
    checkpoint=previous_checkpoint,
    checkpoint_callback=save_checkpoint,
)
```

Only pass configured endpoints backed by registry/configuration evidence. Without configuration, the strategy fetches the supplied first-party source page and detects declared HTML GET forms or search links. It does not invent search paths or run scripts. `detect_internal_search()` returns `SearchRoute` objects; `.to_dict()` serializes them, and legacy `["action"]` reads remain supported.

SearchRoute includes action URL, method, query parameter, static parameters, discovery source, originating page, allowed host, confidence, rejection reason and timestamp. Rejected routes have `disposition=manual_or_future_strategy`. HTML constants outside a small search/locale allowlist are rejected; token/session values are discarded. API/GraphQL routes require explicit configuration. POST, login/account/cart/checkout, password/file, submission overrides, JS handlers and foreign hosts are never executed.

Query generation uses at most three model-shaped codes: seller/manufacturer SKU, primary model candidate and conservative punctuation normalization. WB SKU, titles, personal strings and generic sizes are excluded. Dots, slash/revision/service suffixes remain significant; Bosch base E-Nr is a separate bounded query.

Hard ceilings remain 3 queries, 20 candidates, 3 target probes and 10 HTTP requests even when a caller supplies larger budgets. Smaller budgets apply. AccessProbe's `request_guard` mode disables automatic redirects and charges/validates every hop before GET. It shares the rate limiter, response byte cap, remaining request timeout and deadline. Network/stream failures become diagnostics, not retries. Protection stops terminate the family, including redirected hosts, and survive checkpoints.

Result anchors, canonical links, structured cards and JSON-LD ItemList provide ranking evidence only. Navigation, foreign hosts, tracking, account flows, assets, PDFs, categories, blog/news and generic support links are excluded. A title/URL/body model match cannot establish identity. Target-page structured Product identity passes through `validate_structured_product_identity()` and IdentityVerifier; all explicitly expected variant fields must match for exact_variant. No general product-data adapter or attribute/media/document extraction is added.

The checkpoint binds source, hosts, identity and configured routes. It stores routes, planned/completed queries, request/probe records, final URLs, candidates, identities, counters, events, stop reason and timestamps. Persist the callback atomically. A completed checkpoint returns checkpoint_complete without requests. Pending snapshots skip completed queries/probes; a persisted blocking query prevents further requests. `refresh=True` explicitly starts a fresh budget and search. A terminal budget/deadline stop also requires explicit refresh. Do not mix checkpoints across strategies or products.

Future orchestration can run sitemap first, inspect exact identity/readiness, then invoke internal_search with a separate checkpoint. A production orchestrator is outside Stage 5.

Run offline regression:

```text
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Run the opt-in six-source diagnostic (one sample each; recorded checkpoints avoid repetition):

```text
.venv\Scripts\python.exe -m product_tool.census.runner_v5
```

It accepts only `data/catalog_2026-09-21_filtered.xlsx`, writes a dated report/checkpoint, verifies replay and hashes configuration, LG/Sulpak rules and Stage 2–4 reports. It never modifies registries, the remaining census labels or the next census batch. The live report preserves executed probe evidence; see its audit note for filtering refinements made after that run.
