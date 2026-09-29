# Stage 16 — closing the Stage 15 network vulnerability at the root

**No new HTTP requests this stage.** Everything below is offline code/test work. Catalog and every prior stage's report artifacts (through Stage 15) remain byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json).

## Part 1 — what is known and what is not known about Stage 15's possible network call

**Known:**
- Stage 15 populated `HyperXAdapter.KNOWN_URLS["9A273AA"]` with a real hyperx.com URL.
- `worker.py`'s default `hyperx_adapter_factory` (used whenever a test doesn't override it) built `HyperXAdapter(clock=clock)`, which built a bare `requests.Session()`.
- Three pre-existing tests in `tests/test_dns_fallback.py` used brand `HYPERX`, sku `9A273AA`, and called `worker.run_once()` without overriding `hyperx_adapter_factory` — a combination that was safe before Stage 15 (empty `KNOWN_URLS` → `official_url_needed`, zero calls) and was not safe after.
- The first full-suite run after that change showed one of those tests getting `status == "done"` where `"needs_review"` was expected — a result only reachable if HyperX's adapter reported `exact_variant`, which requires a real, successful page fetch.
- `socket.gethostbyname('hyperx.com')` succeeds in this sandbox — outbound DNS resolution is available.

**Not known, and not knowable after the fact:**
- Whether a TCP connection actually completed, whether hyperx.com actually responded, what (if anything) it returned, or how many bytes crossed the network. Nothing in this project logs raw socket activity, and the request (if it happened) was not captured anywhere.
- Whether this was a single request or (given `worker.run_once()` only processes one job per call, and the test in question seeds exactly one job) more than one.

**What this stage does about the gap between those two states:** rather than trying to establish after the fact whether a real call happened, Stage 16 makes it structurally impossible for this specific scenario — and the general class of scenario — to go undetected or succeed silently again. See Parts 2–3.

## Part 2 — the ordinary adapter fetch path is now policy-aware, at the root

### Why "urls={} in a test" was never enough

The test substitution stopped ONE specific scenario (a code path that happens to look up an empty dict). It did nothing for the actual root cause: `HyperXAdapter`'s ordinary fetch path was a bare `requests.Session().get(url, timeout=...)` — no `ProbePolicy`, no allowlist beyond one manual host string comparison, no redirect-chain check beyond one manual pass, no persisted memory of a prior block, and critically, nothing stopping a REAL call if a real URL was configured and no test double was supplied. Any future test (or a genuine future production row) that reached this path with a real `KNOWN_URLS` entry and no override would hit the same exposure Stage 15 did.

### The fix

**`product_tool/adapters/policy_fetch.py`** (new) — `PolicyAwareFetcher`, wrapping `product_tool.census.endpoint_probe.AccessProbe` (the project's own policy-aware client: `ProbePolicy`, host allowlist, redirect-chain host checks, 401/403/429/challenge detection, in-process host-stop) with a JSON-file-backed fetch log. Every real fetch outcome (`status_code`, `final_url`, timestamp) is appended to this file; on construction, `blocked_hosts_from_fetch_log()` (already used by the project's own research scripts since Stage 13) seeds a fresh `AccessProbe` with every host the log has ever recorded a block for — so a host-stop survives a fresh `HyperXAdapter` instance or process, not just one instance's lifetime.

**`product_tool/adapters/hyperx.py`** — `find_source()` no longer talks to `requests` directly at all. It calls `self._fetcher.get(url, allowed_hosts=..., deadline=...)`, maps the returned `ProbeResult`'s `access_status` to the same `SourceDocument` outcomes as before (`blocked`, `unknown`/redirect-rejected, `unknown`/error, or a real parse). One honest behavior change, documented in code: `AccessProbe` treats a bare 401 as a generic error (`AccessStatus.UNAVAILABLE`), not a host-stop signal the way 403/429 are — the pre-Stage-16 code lumped 401 in with 403/429 as "blocked"; this is now `"unknown"` instead. HyperX has never actually returned 401 in any real or saved capture this project has seen, so this is a documented, low-risk gap, not a silent one.

**`product_tool/worker.py`** — the default `hyperx_adapter_factory` now passes `fetch_log_path=database.parent / "hyperx_fetch_log.json"`, colocating the persisted log with whatever jobs database a given run uses. In production this sits next to `data/batches.sqlite3`; in every test using a temp-dir database, it is automatically isolated too.

### The 3 originally-exposed tests, fixed properly this time

Stage 15's fix (`urls={}` on those 3 tests) still stands — but is now one of two independent layers, not the only one. See Part 3.

## Part 3 — the ordinary test run is now safe by default, without a special wrapper command

### `tests/__init__.py` doesn't work — and why

The first attempt was a `tests/__init__.py` that activates a network guard at import time. Empirically, this is dead code: `unittest discover -s tests` (this project's own documented command, `README.md`) never imports `tests/__init__.py` as a package init. `top_level_dir` defaults to `start_dir`, so `tests` itself is treated as the top, discovered modules get bare names (`test_x`, not `tests.test_x`), and `tests/` is only ever added to `sys.path` — the package `__init__.py` is simply never touched. Verified directly: `'tests' in sys.modules` is `False` after a real `TestLoader().discover('tests', ...)` call.

### What actually works

**`tests/test_000_network_safety.py`** (new) — every `test_*.py` file's own module-level code runs at import time, during discovery, before any test in any file executes. Naming this file so it sorts first alphabetically among `test_*.py` files (`'0'` sorts before every other file's first post-`"test_"` character, all letters) means its activation runs before anything else does, for the rest of the process. It calls `product_tool.census.endpoint_probe.block_all_real_network_io()` and enters it without a matching exit — deliberate, since a test process is short-lived and this is a test run, not a library import someone else depends on staying unblocked.

**`product_tool/census/endpoint_probe.py`** — new `block_all_real_network_io()` / `RealNetworkIOBlocked`: patches `requests.adapters.HTTPAdapter.send` (below `Session.get()`, below `AccessProbe`'s own immunity to the *other* guard) so a real HTTP call of any kind — including through `AccessProbe`'s otherwise-legitimate real-session path — fails before any socket I/O. This is a deliberately different, stricter guarantee than `enforce_policy_aware_fetch_only()` (Stage 14), which exempts `AccessProbe` on purpose, because that guard is about "did research code bypass `AccessProbe`", not "is this a test process." No `FakeSession`/`FakeResponse` test double anywhere in this project is a real `requests.Session`, so none of them are affected.

**Also fixed:** `enforce_policy_aware_fetch_only()` itself was not reentrant — it unconditionally restored `requests.Session.get` to `_REAL_SESSION_GET` on exit, so a test that itself calls this context manager (several already do, to test the guard's own behavior) would silently clear an outer, process-wide activation on exit. Now it saves and restores whatever the value *was*, not a hardcoded original — verified against all existing guard tests, none of which broke.

### Proof, not assertion

- `test_the_guard_is_active_for_this_process` (`test_000_network_safety.py`) and `test_the_ordinary_test_run_itself_is_already_guarded_no_wrapper_needed` (`test_hyperx_stage16_policy_fetch.py`, a *different* file, checking the activation survived across file boundaries) both check by introspection, without attempting any real `.get()` call themselves (so they carry zero network risk even if run outside `-s tests` discovery).
- `test_run_once_with_real_known_url_and_no_factory_override_does_not_make_an_unaccounted_request` reproduces Stage 15's exact scenario — `worker.run_once()`, real `KNOWN_URLS["9A273AA"]`, no factory override — self-contained (activates the guard itself, not relying on the ambient one, so it is correct regardless of invocation). `worker.run_once()` has a pre-existing, unrelated broad `except Exception` (a general safety net so one bad adapter/job never crashes the whole worker loop), so `RealNetworkIOBlocked` does not propagate out of it; the test instead asserts the job ends in `"error"` (never `"done"`, which only a real successful response could produce) and, via `assertLogs`, that the swallowed exception really was `RealNetworkIOBlocked`.

## Part 4 — persisted host-stop, proven across a fresh instance

`tests/test_hyperx_stage16_policy_fetch.py`'s `PersistedHostStopTests`: a `FakeSession` returns 403 once; the fetch log records it; a **second, separate** `PolicyAwareFetcher`/`HyperXAdapter` instance, constructed with a session that raises on any `.get()` call at all (`RefusingSession`), is pointed at the same log path and correctly refuses the host — `access_status == CAPTCHA_OR_BLOCKED`, `http_status is None` (short-circuited, zero real calls) — proving the stop survives "a new run," not just one instance's lifetime. A separate test confirms a genuine 200 is logged too, but does not itself stop the host (only 401/403/429 do, matching `blocked_hosts_from_fetch_log()`'s existing rule).

## Part 5 — the productID/sku fix does not hide a real conflict

Stage 15's correction (JSON-LD `sku` is the sole identity anchor; `productID`, a Shopify-internal id, is a fallback only when `sku` is absent) is unchanged. Three new tests in `IdentityFixDoesNotHideRealConflictsTests` verify it was never a blanket loosening:
- A genuinely different `sku` (a different product entirely) plus an unrelated `productID` still reports `mismatch`.
- A genuine region-suffix conflict (`sku` base matches, suffix doesn't) still reports `base_code_confirmed`, never `exact_variant`.
- Two JSON-LD blocks disagreeing on `sku` itself (not `sku` vs `productID`) are still treated as unresolved (`mismatch`, empty `page_base`) — the fix only changed which *field* is the anchor, not this safety property.

## Part 6 — the removed dealer's literal exclusion, gone from the census registry scripts

`product_tool/census/runner.py`'s `probe_sources()` and `runner_v2.py`'s own eligibility loop each carried `and record.source_id != "mechta"` in their eligibility filter — a literal named exclusion, exactly the kind of dedicated branch Stage 13's mandate said should never exist. Neither script's underlying registry (`load_source_catalog()`) has ever had a record for that `source_id` at all (confirmed: no match anywhere in `product_tool/census/registry.py` or `models.py`'s data), so the check was dead weight, redundant with the generic `official_status == OFFICIAL_VERIFIED` filter already present in both. **Removed, not replaced with another branch**, per instruction.

**Verified absent** (`grep -rn -i mechta`) in: `product_tool/census/runner.py`, `runner_v2.py`, `product_tool/templates/*.html`, `docs/*.md`, `product_tool/config/*.json`, and `tests/_pipeline_migration.py`.

**Deliberately left alone**, with reasoning: a further, broader grep across all of `tests/` finds the literal name in ~10 places, split into two categories —
1. **Archival-content tests** (`test_structural_census_v11_2.py`, `v11_3.py`) — assert that a saved, immutable Stage 11.2/11.3 JSON artifact (`checkpoint.json`, `card.json`) still says what it always said (e.g. `"Mechta remains excluded"`). These test that history wasn't rewritten; the name there is the archive's own content, not an active rule.
2. **Negative-existence-proof tests** (`test_dns_fallback.py`, `test_source_census.py`, `test_source_census_v2.py`, and 6 pinned `test_structural_census_v8*.py` files) — `assertNotIn("mechta", ...)` against the *active* `source_catalog.v2.json`/registry, proving the removal happened. This is the same shape of check Stage 13/14 already reviewed and kept in place across those same 6 pinned files without objection; rewriting all of them (6 more pin-hash churns) for a negative-existence check was judged out of this stage's explicit scope (`runner.py`/`runner_v2.py` were the named removal targets) and lower value than the actual fixes above. Flagged here for the user to weigh in on if this reasoning is wrong.

No occurrence was found in any `.html` template or `docs/*.md` file (already clean since Stage 13/14).

**Also found, also deliberately left alone**: `product_tool/census/report_v5_1.py`, `report_v6.py`, `report_v7.py`, `report_v71.py`, `runner_v5.py`, `structural_report_v8.py` each embed the name inside a literal prose string that is part of that script's own report-generation output (e.g. `"...the Mechta exclusion remains unchanged..."`) — frozen historical report text these Stage 5–8 one-off scripts would regenerate verbatim if ever re-run, not an active filtering condition the way `runner.py`/`runner_v2.py`'s `!= "mechta"` was. All 6 are part of the Stage 8 pinned baseline; editing prose-only text in them for no behavior change would mean re-pinning 6 more files for what is, unlike `runner.py`/`runner_v2.py`, not a named branch at all. Left alone, flagged here for the same reason as the test files above.

## Verification

- **Ordinary test run, the exact documented command, no wrapper**: `python -m unittest discover -s tests -v` → **833 tests, 0 failures** ([`tests.txt`](tests.txt)) — 823 (Stage 15) + 10 new (`test_000_network_safety.py`: 1; `test_hyperx_stage16_policy_fetch.py`: 9) + 0 removed.
- `01_integrity_check.py`: 24/24 pinned files match (4 changed this stage: `worker.py`, `endpoint_probe.py`, `runner.py`, plus `runner_v2.py` newly added to the pinned set), 1/1 authorized deletion confirmed absent, `readiness_table.md` still matches its Stage 13 original bytes, 740 prior-stage files (through Stage 15) hashed and unchanged, catalog file hash unchanged.

## Files touched

- New: `product_tool/adapters/policy_fetch.py`, `tests/test_000_network_safety.py`, `tests/test_hyperx_stage16_policy_fetch.py`
- Code: `product_tool/adapters/hyperx.py` (ordinary fetch path rewired), `product_tool/census/endpoint_probe.py` (`block_all_real_network_io()`/`RealNetworkIOBlocked`, reentrant `enforce_policy_aware_fetch_only()`), `product_tool/worker.py` (default factory colocates the fetch log), `product_tool/census/runner.py` + `runner_v2.py` (literal exclusion removed), `tests/_pipeline_migration.py` (4 hash updates, `runner_v2.py` newly pinned, all reasons dated and explicit)
- Deleted: `tests/__init__.py` (built, found not to activate under the documented invocation, removed rather than left as a false sense of protection)
- Tests fixed for the new AccessProbe-shaped fetch path: `test_hyperx_adapter.py`, `test_hyperx_worker_integration.py`, `test_hyperx_stage15_catalog_route.py` (FakeResponse/FakeSession rebuilt to match `AccessProbe.probe()`'s expectations; every `HyperXAdapter(...)` construction now gets an isolated tmpdir `fetch_log_path`)

## Not done automatically — unchanged, stated again

**HyperX catalog coverage is still 2 confirmed URLs of 41 rows.** This stage touched zero rows' worth of new coverage — it hardened the fetch path and the test-safety net around the 2 rows Stage 15 already wired in, nothing more. No new brand census, no new URL search, no change to Bosch/Cudy, no change to the catalog or any pre-Stage-16 report artifact.
