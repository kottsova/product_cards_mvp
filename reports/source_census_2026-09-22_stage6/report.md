# Stage 6 — bounded browser-assisted first-party search v1

Live diagnostic timestamp: 2026-09-22T15:25:51.933421+00:00

## Runtime and opt-in

Existing runtime: **playwright-1.59.0**, Chromium **147.0.7727.15**, interpreter `A:\work\dev\.venv\Scripts\python.exe`. The project venv lacks Playwright, but the adjacent existing project environment has it and the matching Chromium binaries. An ephemeral about:blank launch confirmed usability. No package or browser download was performed.

BrowserAssistedSearchStrategy is disabled by default. It requires browser_assisted=True, a verified official source, explicit source/product identity, bounded budget and eligible static evidence. The dedicated runner_v6 research command is the only new live entry point. Existing LG workflows, census runners and production workers were not connected to it.

## Safety and budgets

- Per source: one fresh ephemeral context, at most two queries, six first-party navigations, three candidate URLs, three target identity validations, 60 seconds, 600,000-byte DOM limit and 5-second operation timeout. Bounds above the hard limits are rejected.
- No persistent profile, credentials, imported cookies/storage, extensions, stealth, proxy changes, custom User-Agent, fingerprint spoofing or automatic login. Contexts are closed in finally blocks.
- Main-frame requests are checked against host allowlists before forwarding; third-party requests and account/cart/contact flows are blocked. First-party 403/429 and visible challenge signals stop the host without retry.
- Only declared search inputs and normal Enter submission are permitted. The input/form is revalidated immediately before typing. Cookie interactions are restricted to a unique rejection/necessary-only choice; other banners stop with interaction_blocked.
- At most one ordinary technical retry is allowed for observation/navigation. Submits are not retried. No networkidle waits or arbitrary button clicks are used.

## Static versus browser-assisted diagnostic

| Family / catalog model | Static result | Browser result | Contexts | Queries | Navigations | Allowed network requests | Candidates | Target validations |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lg_kz / 27ART10AKPL | search_no_results | browser_strategy_not_eligible | 0 | 0 | 0 | 0 | 0 | 0 |
| bosch_home / SBV45FX01R | search_route_not_found | browser_search_ui_not_found | 1 | 0 | 2 | 30 | 0 | 0 |
| dreame / HHR12A | unsafe_search_route | budget_exhausted | 1 | 0 | 1 | 147 | 0 | 0 |

**LG was not launched.** Its static result is search_no_results, but the saved sanitized static snapshot contains neither an explicit search input nor a retained JavaScript search handler. Therefore the required affirmative JS-search-UI evidence is unavailable. This is browser_strategy_not_eligible, not browser_runtime_unavailable. The explicit eligibility requirement takes precedence over attempting every named source; no JS dependency was invented.

**Bosch Home:** the confirmed first-party homepage was opened. One ordinary technical navigation retry was used (two navigations total). No eligible visible search input was found within the bounded DOM. One sanitized homepage snapshot was saved; the context closed. This does not claim that Bosch has no search functionality outside the permitted interaction surface.

**Dreame:** the first-party search page came directly from the observed Stage 5 search-link evidence, not a guessed URL. One navigation was issued. The rendered DOM exceeded the byte cap before interaction/snapshot persistence, causing budget_exhausted; the context closed. No search query was entered and no target URL was supplied manually.

Measured totals: **2 contexts, 3 navigations, 177 allowed first-party network requests** including page resources. Network totals are not product probes; no separate HTTP-count cap was specified for Stage 6. Blocked resource totals were not retained in this live artifact. Both contexts closed within 60 seconds (Bosch approximately 9.7 seconds, Dreame approximately 2.8 seconds).

No CAPTCHA/challenge, 403/429, foreign-redirect or cookie-consent stop was returned in this live pass. No candidates or target-page identities were established live. HyperX was not reopened because static search already validated it.

## Actions and snapshots

### lg_kz

- No browser action executed (eligibility gate).
- No usable rendered snapshot saved.

### bosch_home

- {"action": "open_homepage", "elapsed_seconds": 8.894, "query": "", "url": "https://www.bosch-home.com/"}
- {"action": "close_context", "closed": true}
- SourceSnapshot `1` in `source_snapshots.sqlite3`, phase `homepage`, content SHA-256 `0b01565be7c4a641d703b03086cb338d8e92a512d62a52be1aae0a6cf91b3cdb`.

### dreame

- {"action": "close_context", "closed": true}
- No usable rendered snapshot saved.

Snapshots reuse the existing FetchAttempt/SourceSnapshot tables in an isolated Stage 6 DB. They retain sanitized DOM, final URL, content hash and narrow discovery metadata. IDs, raw selectors, storage, cookies, headers, security values, full HAR, unrelated scripts and personal URL parameters are not persisted. Product microdata/search-role semantics survive sanitization. Only snapshot references/hashes appear in checkpoints.

## Versioned checkpoint and offline verification

| Component | Final version |
| --- | --- |
| checkpoint_schema_version | 2 |
| strategy_version | 6.0.1 |
| ui_detector_version | 2 |
| result_parser_version | browser1-stage5.1-3 |
| ranking_version | 3 |
| sanitizer_version | browser1 |
| Browser runtime | playwright-1.59.0 |
| Browser binary | 147.0.7727.15 |

Compatibility also includes source/product identity, host allowlists, declarative selectors and budget. Final input revalidation changed strategy/UI semantics after the live attempt; the final versions are therefore different from the original live checkpoints. Old candidates are not silently accepted.

| Family | Original checkpoint under final code | Offline reprocessing | Compatible resume of rebuilt checkpoint | New contexts / requests |
| --- | --- | --- | --- | --- |
| lg_kz | browser_strategy_not_eligible | browser_strategy_not_eligible | not_applicable | 0 / 0 |
| bosch_home | checkpoint_incompatible | browser_search_ui_not_found | checkpoint_complete | 0 / 0 |
| dreame | checkpoint_incompatible | snapshot_missing | not_applicable | 0 / 0 |

Bosch reprocessing reproduced browser_search_ui_not_found from its hash-checked DOM without launching a browser, and its rebuilt compatible checkpoint returned checkpoint_complete with zero requests. Dreame has snapshot_missing, so the final parser is not claimed to have been verified against a Dreame rendered snapshot. LG remains ineligible and has no browser snapshot. Final offline verification preserved the snapshot DB hash. See final_reprocessing.json and reprocessed_checkpoint.json.

## Regression and preservation

**196 tests passed; exit code 0.** See tests.txt. The mandatory suite uses fake browsers and local HTML fixtures; no live browser launches are part of unittest discovery. Cases cover opt-in/eligibility, unsafe fields, searchboxes, login ambiguity, foreign transitions, navigation/service filtering, JSON-LD/microdata identity, variant conflict, visible text insufficiency, protection closure/no retry, deadline/DOM/navigation budgets, cookie blocking, version mismatch, hash tampering, zero-browser replay, registry immutability and production_ready=false.

Protected hashes unchanged: **True**. Full before/after manifests cover Stage 2–5.1 reports and snapshot DB, production/normalization/research registries, LG/Sulpak/source policy files, pre-existing SQLite files and the user's uncommitted jobs.py/storage.py/worker.py contents. The 186 unresolved labels, Accesstyle negative result, next census batch, Sulpak allowlist and Mechta exclusion remain unchanged.

No production readiness was enabled. No Samsung/AEM/Shopify adapter, embedded-state extractor, general product attribute/media/manual extraction, dealer fallback or production orchestrator was added.

## Exactly one next stage

Recommend **Stage 6.1: bounded search-UI/DOM projection hardening**. Focus on preserving explicit JS-search-UI eligibility evidence and extracting the narrow rendered search region within the DOM cap, so cases like LG and Dreame can be evaluated without broadening interaction privileges. This next stage was not implemented.
