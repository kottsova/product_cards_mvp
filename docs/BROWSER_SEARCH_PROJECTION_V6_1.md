# Bounded search projection, Stage 6.1

`BrowserAssistedSearchStrategy` remains the same opt-in research strategy. It is not registered in production and always reports `production_ready=false`.

## Modes

- `render_existing_search_result`: requires an officially verified source, a completed safe GET matching `generate_search_queries(expected)`, an available ordinary 200 response, and no historical protection or foreign redirect. The route's action, parameter and constants must match the exact saved request. The worker opens that string, skips input inspection and rejects submit commands.
- `interactive_search_ui`: a live run requires the already observed first-party search action with undeclared query parameter/JavaScript handler. The worker inspects visible semantic search controls, rejects ambiguous/unsafe forms, and revalidates the descriptor before filling and pressing Enter. No new search endpoint is synthesized.

## Projection contract

`browser_projection.js` executes in the page. It returns URL/title, bounded visible search descriptors, local result links, whitelisted Product/ItemList JSON-LD, Product microdata, protection booleans, cookie-dialog presence and counters. It never serializes the document HTML, copies arbitrary scripts/styles/SVG, reads cookies/storage or exports hidden input values/IDs.

Inputs include type/role, normalized Search label, form presence/action host/path/method, visibility and password/file/security flags. The ephemeral index exists only in worker memory and is removed before persistence.

Defaults: 120,000 UTF-8 bytes per projection, 12,000 per fragment/descriptor, 100 fragments, 20 search descriptors; configurable hard maxima are 200,000/20,000 bytes and 200 fragments. Relevant JSON-LD source parsing has an additional 200,000-character guard. Excess relevant projection returns `projection_budget_exhausted`. Unrelated DOM size is not the projection budget. The legacy `max_dom_bytes` setting is only the existing parser input cap, not a DOM capture operation.

`projection_html` builds whitelisted semantic markup for Stage 5.1 candidate parsing and the existing structured identity verifier. Result text only ranks candidates. Exact identity requires target Product JSON-LD or Product microdata; at most three targets are validated.

## Resource and operation limits

One ephemeral context; at most two safe generated queries, six main-frame navigations, three candidates/target validations and one idempotent technical retry. No submit retry. Wall-clock deadline is 60 seconds, operation timeout five seconds.

`max_network_requests` defaults to 200 and cannot exceed 200. It counts requests admitted for forwarding, before `route.continue_`; blocked requests do not consume network bandwidth and are recorded separately. Document, script/XHR/fetch, stylesheet and other admitted counts sum to `network_requests`. Images/fonts/media and known download paths are aborted. Runtime downloads are disabled/cancelled. Existing first-party restrictions also apply to scripts and XHR. 403/429 or a visible challenge stop the source; further requests are aborted. No bypass, external fallback or permission expansion exists.

## Persistence and replay

Only sanitized typed projection JSON enters existing immutable SourceSnapshot tables. Metadata includes source/product scope, phase, final/request URL, query, mode, content hash, fragment types, network counts, browser/runtime/parser/ranking/projection versions. Storage performs a second schema whitelist and removes ephemeral indices.

Final semantics: strategy 6.1.1, projection 2, checkpoint schema 3, UI detector 3, sanitizer projection2, Stage 5.1 result parser/ranking unchanged. A version change makes a checkpoint incompatible. Compatible complete resume performs no browser work. Reprocessing verifies hashes/scope/projection version and cannot launch a browser. Historical HTML conversion is explicitly offline-only; it is not a live worker path.

## Research artifacts

`python -m product_tool.census.runner_v61` is limited to LG 27ART10AKPL and Dreame HHR12A live, plus Bosch SBV45FX01R offline. Attempt markers prevent repeat live runs, including after an incomplete attempt. Existing completed artifacts are returned without launching a browser. HyperX is excluded.

`python -m product_tool.census.reprocess_v61` performs the explicit captured-snapshot migration and final offline checks. The recorded live run used projection 1; final projection 2 was verified locally and offline, not by repeating protected LG or the completed Dreame run.

See `reports/source_census_2026-09-22_stage6_1/report.md`. Decision: `manual_review_only`.
