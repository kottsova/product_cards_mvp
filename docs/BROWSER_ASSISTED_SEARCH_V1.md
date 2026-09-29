# Stage 6: bounded browser-assisted first-party search

`BrowserAssistedSearchStrategy` is research-only and disabled by default. No production worker, LG workflow or earlier census runner imports or invokes it. Use `browser_assisted=True` with a confirmed source family, ProductIdentity, eligible static evidence and BrowserBudget, or invoke the dedicated research command.

The installed-runtime detector checks the current Python and existing adjacent project environment for a usable Playwright/Chromium pair. It never installs packages/binaries. This environment provides Playwright 1.59.0 and Chromium 147.0.7727.15 through `A:/work/dev/.venv`. Without that pair the opt-in strategy returns browser_runtime_unavailable, while fixture tests remain runnable.

Eligibility is fail-closed: search_route_not_found, search_javascript_required, search_no_results with affirmative JS-search-UI evidence, or unsafe_search_route caused only by undeclared query parameters/JS handlers. Prior 403/429/challenge, access prohibition, foreign redirect, login/token requirements and unverified sources prohibit browser launch. A bare search_no_results is insufficient.

Hard caps are enforced by BrowserBudget and the worker: one ephemeral context, two queries, six main-frame first-party navigations, three candidates, three target validations, 60 seconds, bounded DOM and bounded operation waits. Counts larger than the hard caps are rejected. There is at most one retry of a technical navigation/observation error; submits are not retried. No networkidle wait is used. A protection signal ends the host run and closes its context.

The worker launches Chromium headless without profile/cookie/storage/credential imports, custom UA, proxies, extensions or stealth flags. Request interception validates navigation hosts before forwarding them, rejects foreign resource requests, blocks transaction/login/contact paths, and observes first-party 403/429 responses. Cookie handling is limited to a uniquely identified rejection/necessary-only choice. If safe dismissal is unavailable, interaction_blocked is returned.

Search fields require type=search, role=searchbox, explicit associated/ARIA search label, form role=search, or a supplied declarative selector. Arbitrary text/placeholder-only fields are rejected. Password/file/token/contact/account forms are rejected. The worker revalidates the selected input immediately before typing. Evidence contains a semantic selector description, never session IDs or raw selectors.

The first safe Stage 5 query is submitted; one normalized form may follow only if no candidates were found. Stage 5.1 ranking is reused after removing navigation/footer/header/aside subtrees and all service-path candidates. Search result text/cards never establish identity. Only rendered JSON-LD Product or local Product microdata identifiers pass to IdentityVerifier. No embedded-state or general attribute/media/manual extractor is included.

Snapshots use the existing FetchAttempt/SourceSnapshot tables in a new diagnostic DB. Stored HTML is sanitized; scripts except identity/discovery JSON-LD, IDs, comments, secrets, storage, headers and irrelevant attributes are omitted. Explicit search roles and Product microdata are retained for reprocessing. Checkpoints contain snapshot references/content hashes, counters and semantic evidence, not raw DOM.

Compatibility includes strategy/UI/parser/ranking/sanitizer/runtime/browser versions, source/product identity, allowlists, selectors and budget. A mismatch returns checkpoint_incompatible. Explicit `reprocess=True` with a snapshot loader rebuilds discovery and identity without launching a browser; missing snapshots return snapshot_missing. A compatible complete checkpoint alone returns checkpoint_complete. Incomplete runs do not silently restart browser work.

```text
.venv\Scripts\python.exe -m product_tool.census.runner_v6
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

The research runner is restricted to LG 27ART10AKPL, Bosch Home SBV45FX01R and Dreame HHR12A and never rechecks HyperX. Its eligibility gate still applies to each listed family. Existing attempts are checkpointed; invocation does not bypass version incompatibility or protection stops. See the Stage 6 report for the measured outcomes and coverage limits of this environment.
