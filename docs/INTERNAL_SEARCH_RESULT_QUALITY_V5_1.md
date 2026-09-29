# Stage 5.1: internal-search result quality and versioned reprocessing

Stage 5 reports remain the immutable historical baseline. Stage 5.1 outputs are in `reports/source_census_2026-09-22_stage5_1/`.

`SearchHTMLParser` attributes a card marker to the nearest local product container. Exact class tokens `product-card`, `product-item`, `product-result`, schema.org/Product itemtype and product-specific data markers qualify. Generic results/layout wrappers do not qualify; navigation boundaries stop inherited card evidence.

`search_results.path_signals()` uses complete path segments. `/products/item` qualifies; `/support/product-support/item` does not. Service/navigation paths require explicit exact model evidence and a recorded exception reason. Search pages, transaction/account flows and assets remain excluded. Query echoes in `q` are not product-model evidence. First-party host and category matches cannot independently admit a candidate. Declarative source patterns are explicit complete path prefixes, supplied as `configured_product_patterns=("/devices/detail/",)`.

Ranking evidence distinguishes `html_product_card`, `json_ld_itemlist_product`, `exact_model_in_result_title`, `exact_model_in_result_url`, `configured_product_pattern` and `generic_first_party_anchor`. ItemList navigation entries receive no Product bonus. Candidate identity is still established only from the target page through the existing structured IdentityVerifier.

Checkpoints carry checkpoint schema 2, strategy 5.1, route detector 2, result parser 3 and ranking 3. Versions, product/source configuration, category hints and product patterns enter the compatibility key. Incompatible or unversioned checkpoints return `checkpoint_incompatible` with zero candidates and no network activity. They cannot establish readiness for the current parser. Compatible complete checkpoints alone return `checkpoint_complete`.

Pass `snapshot_writer=store.writer(expected, source_family)` during a bounded live run to persist successful responses through the existing FetchAttempt/SourceSnapshot functions. The dry-run uses its own SQLite database, never the user's existing database. The checkpoint contains only snapshot IDs, store references and content hashes, not HTML. Snapshot HTML is a sanitized discovery/identity projection: non-JSON-LD scripts, irrelevant attributes, private URL parameters and form/meta secrets are omitted; JSON-LD retains only fields needed by discovery and identity. This is not an embedded-state extractor or production adapter.

To rebuild routes, candidates, rankings, rejection reasons and target identities without network:

```python
result = strategy.run(
    **source_and_identity_arguments,
    checkpoint=old_checkpoint,
    reprocess=True,
    snapshot_loader=store.load,
)
```

Reprocessing verifies content hashes and scope and does not reuse old derived data. Missing or invalid snapshots return `snapshot_missing`; they cannot silently fall back to network. `refresh=True` is an explicit fresh bounded run and cannot be combined with `reprocess=True`.

The Stage 5.1 harness is restricted to LG 27ART10AKPL and HyperX 4P5D4AA. It first tries snapshot reprocessing. `--refresh-missing` permits one marked bounded refresh per source if snapshots are insufficient. Subsequent runs without that flag only reprocess snapshots. The final report distinguishes historical refresh HTTP counts from current zero-network replay.

```text
.venv\Scripts\python.exe -m product_tool.census.runner_v5_1
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

No new discovery strategy, browser execution, Shopify adapter, embedded-state extraction, production orchestrator, registry promotion or census relabeling is included.
