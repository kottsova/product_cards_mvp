# Stage 15 — HyperX: from offline adapter to a working catalog-to-source route

**No new HTTP requests this stage.** Every page used is a real capture already saved during Stage 11/11.1 (`reports/source_census_2026-09-23_stage11(_1)/raw/*.html.txt`), or a Stage 14 synthetic fixture retained for regression coverage. No new brand was researched — this stage converts HyperX's own already-confirmed URLs into production wiring, per explicit instruction.

**Read this first — a real network-safety incident happened and was fixed during this stage.** See "Part 4 — network-safety incident" below before anything else. It is disclosed here with the same weight this project's own Stage 12/13 Razer audit gave a policy violation, because it is the same category of event: an undeclared, unbounded outbound request to a real third-party host, made from what should have been an offline test run.

## Part 1 — closing the Stage 14 report-ownership mistake

Stage 14's own report said it updated `reports/source_census_2026-09-23_stage13/readiness_table.md` "in place (Stage 13's own file, not re-created)" — treating the edit as legitimate because HyperX's status was the *subject* of the update. That reasoning was wrong: `readiness_table.md` is **Stage 13's artifact**, produced and owned by Stage 13, not Stage 14. This project's own convention is that a past stage's artifacts stay byte-identical once that stage is done — Stage 14 broke that convention for a report file (not code), and nothing caught it until this stage's audit.

- **Path**: `reports/source_census_2026-09-23_stage13/readiness_table.md`
- **Modified (Stage 14) SHA-256**: `392181267e277b6ac3360759a88a395b6784bfe5df6916de31e95bca3b1dd96e`
- **Original (Stage 13) SHA-256, restored**: `fd9ed8ab4b38eeb377ab39775c1da0c43eeff4e100ba12e854ce80e2a22766d6`

The original bytes were recovered exactly, not reconstructed from memory: `reports/` has never been under git version control in this repository (`git log` on the path returns nothing), so the only exact record of the pre-Stage-14 file was the session transcript's own `Write` tool-call input from when Stage 13 last wrote the file (before Stage 14's first edit). That content was extracted, diffed against the current (Stage-14-modified) file to confirm it matched Stage 14's own report.md's description of what it changed (the HyperX Part 1 row, the Group A section, and a new "Stage 14 update" section — exactly 3 edits, matching Stage 14's own transcript record), then written back byte-for-byte. `01_integrity_check.py`'s `readiness_table_restored_to_stage13_original_bytes` confirms the restored file's hash matches.

The HyperX status update itself — refreshed with what this stage additionally learned — now lives in this stage's own artifact: [`readiness_table_hyperx_update.md`](readiness_table_hyperx_update.md). Stage 13's `readiness_table.md` and its own `report.md` are untouched from this point forward. Stage 14's `report.md` is also untouched — it still says it edited Stage 13's file in place, which is a true historical fact; this stage's restoration doesn't require rewriting that record, only correcting the artifact itself and disclosing the correction here.

## Part 2 — the two remaining Stage 13 remnants closed

### 1. The removed dealer's literal path, no longer in the active migration module at all

Stage 14 had already genericized every *prose* mention of the removed dealer in `tests/_pipeline_migration.py`, but kept `DELETED_FILES`'s dict **key** as the literal historical path (`"product_tool/adapters/mechta.py"`), reasoning that a deletion record needs the real path to be checkable. That's true, but the path doesn't need to be *readable as a string literal in this file* to be checkable — `DELETED_FILES` is now keyed by the SHA-256 of that path (computed once, offline, and hardcoded as a hash — never `hashlib.sha256(b"...")` on a literal path string in this file, which would just put the name right back into the source). `is_deleted_file_path(path)` hashes a caller-supplied path and checks membership; `check_deleted_file()` uses it the same way as before. `grep -i mechta tests/_pipeline_migration.py` now returns nothing.

The real, historical filename is still on the record — in the archival Stage 13 report and scripts, exactly as it always was (immutable, never edited), and in this stage's own `01_integrity_check.py`, which names it plainly because it is itself an archival research script, not active production code.

All 10 of the pinned `tests/test_structural_census_v8_1.py..v9_1.py` files import and call `DELETED_FILES` by membership (`if path in DELETED_FILES:`) — each was updated to `if is_deleted_file_path(path):` (and its import), which changed each file's own hash again; all 10 are re-pinned in `PINNED_SHA256`.

### 2. The network-call prohibition now covers the actual entry points, not just the context manager

Stage 14's `enforce_policy_aware_fetch_only()` was a context manager research code could *opt into* — nothing made it active at the places research scripts actually start. `product_tool/census/endpoint_probe.py` now has `guarded_entry_point()`, a decorator that wraps a whole function call in the guard. `product_tool/census/runner.py`'s `main()`, `runner_v5.py`'s and `runner_v71.py`'s (both restructured from an inline `if __name__ == '__main__':` block into their own decorated `main()`), and `report_v71.py`'s `render()` — this module's own four real entry points — are each now decorated with it.

`tests/test_stage13_host_stop_audit.py`'s new `Stage15EntryPointGuardTests` proves this by calling the **real entry point**, not the context manager directly: `test_runner_main_blocks_a_raw_session_call_made_during_its_own_run` monkeypatches `runner.generate_census` to attempt a raw `requests.Session().get(...)` call, sets `sys.argv` the way a real invocation would, and calls `runner.main()` itself — the raw call inside is blocked with `DirectNetworkCallBlocked`, proving the guard governs the entry point's whole execution, not just code that separately remembers to use the context manager. The other 3 entry points are confirmed decorated the same way, and the decorator itself is proven to activate-and-clean-up correctly around an arbitrary wrapped call.

## Part 3 — HyperX: the real catalog-to-source route

### Production `KNOWN_URLS` — exactly 2 rows, both human-confirmed against saved real pages

```
"9A273AA": "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone"
"A1KY6AA": "https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse"
```

- **9A273AA** (QuadCast 2 S microphone) — the URL was supplied directly by the user this stage and independently matches Stage 11's own `card.json`, which recorded `official_page_sku_value: "9A273AA"` against this exact URL from a real fetch.
- **A1KY6AA** (Pulsefire Fuse mouse) — taken from Stage 11.1's `additional_rows_and_adapter_status.json`, which recorded `official_page_sku: "A1KY6AA"`, `exact_match: true` against this exact URL from a real fetch.
- **Not added**: the Alloy Rise 75 keyboard (catalog `7G7A4AA#ACB`). Stage 11.1 found a real candidate page for it (`https://hyperx.com/products/hyperx-alloy-rise-75-mechanical-gaming-keyboard`), but that page's own `sku` is `7G7A4AA#ABA` — a confirmed US-layout page, not the catalog's RU-layout row. Wiring it into production would be exactly the "similar page by name" the instruction ruled out; it stays out, and is used only to test the negative case end-to-end (see below).

### A real bug, found only because real pages were used

Running the real Stage 11/11.1 captures through the existing (Stage 14) extraction code surfaced a genuine defect: `check_identity()` required a page's JSON-LD `sku` and `productID` to agree, treating disagreement as unresolved. On **all 3** real pages sampled (microphone, mouse, keyboard), Shopify's `productID` is that platform's own internal numeric product id — unrelated to the merchant `sku` — so this rule made every real page report `mismatch`, including the two rows with an exact `sku` match. Stage 14's synthetic fixtures never populated a realistic, independently-sourced `productID`, so this was invisible until now. Fixed in `product_tool/adapters/hyperx.py`: `sku` is the sole identity anchor; `productID` is used only when a page has no `sku` field at all. Locked in by `tests/test_hyperx_stage15_catalog_route.py`'s `test_productid_disagreeing_with_sku_is_no_longer_treated_as_a_conflict` and by re-running all 3 real-page identity checks (microphone/mouse → `exact_variant`, keyboard → `base_code_confirmed`, never `exact_variant`).

### The full route, proven offline, on real captures

`tests/test_hyperx_stage15_catalog_route.py` (10 tests) exercises catalog row → production `KNOWN_URLS` (not an injected override) → a `FakeSession` serving the real saved HTML → `HyperXAdapter.find_source()` (rate limiting, blocked-status handling, redirect-host allowlist, deadline — this adapter's own policy-aware fetch step) → `parse_page()`/`check_identity()` → fields with url/evidence/role/confirmation → `worker.run_once()` → job status/card, for:

- **9A273AA** → `done`, `exact_variant`, real characteristics and photos saved (no logo among them), zero documents (the genuine, visible gap — no manual URL exists).
- **A1KY6AA** → `done`, `exact_variant`.
- **7G7A4AA#ACB** (keyboard, URL injected the way a human-supplied candidate would be — not in production `KNOWN_URLS`) → `needs_review`, `base_code_confirmed`, never `exact_variant`, on the real page.
- **A row with no `KNOWN_URLS` entry** → `official_url_needed`, zero network calls.

No live check was attempted this stage — the two rows' identity, extraction and worker wiring are already proven against real, previously-saved pages, so a fresh live fetch was not necessary to close this stage's scope; a live re-verification (bounded, `ProbePolicy`-governed, host-stop-respecting) remains available as a future, separately-declared step if the saved pages are ever suspected stale.

### Measurable HyperX catalog coverage — stated plainly, not overstated

| | Count |
|---|---:|
| Total HyperX catalog rows | 41 |
| Rows with a human-confirmed, production `KNOWN_URLS` entry | **2** |
| Rows reaching `exact_variant` through the ordinary `worker.run_once()` pipeline | **2** |
| Rows with a confirmed real candidate page that is a variant/region mismatch (not counted as ready) | **1** (keyboard, `7G7A4AA#ACB`) |
| Rows with no confirmed URL at all (`official_url_needed`) | **38** |
| Of the 2 confirmed rows: document/manual gap | **2 of 2** — no manual URL found for either |
| Of the 2 confirmed rows: media gap | **0 of 2** — full gallery, description images captured; video present for the microphone, genuinely absent for the mouse (reported honestly, not guessed) |

**The adapter is not "ready for all 41 rows."** It is proven correct, end-to-end, offline, for exactly 2 rows plus 1 real negative case. The other 38 rows need a human-confirmed URL each before they can move past `official_url_needed` — that is the actual remaining work, not adapter code.

## Part 4 — network-safety incident, found and fixed this stage

Populating `KNOWN_URLS["9A273AA"]` with a real URL changed the behavior of `worker.py`'s **default** `hyperx_adapter_factory` (`lambda: HyperXAdapter(clock=clock)`, which constructs a real `requests.Session()` when no session is injected). Three pre-existing tests in `tests/test_dns_fallback.py` (`test_dns_confirmed_for_non_lg_brand_yields_needs_review_not_done`, `test_dns_document_rejected_content_never_saved`, `test_dns_document_accepted_is_saved_with_manufacturer_dealer_hosted_type`) use brand `HYPERX`, sku `9A273AA`, and call `worker.run_once()` **without** overriding `hyperx_adapter_factory` — before this stage, that safely resolved to `official_url_needed` with zero calls, because `KNOWN_URLS` was empty. After this stage's change, the same test code would let the adapter's default (real-session) `find_source()` reach the real `https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone` URL.

This was not caught before the first full-suite run — it was caught *by* that run: `test_dns_confirmed_for_non_lg_brand_yields_needs_review_not_done` failed with `status == "done"` where `"needs_review"` was expected, which is only reachable if HyperX itself reported `exact_variant` — i.e., a real fetch to the real URL plausibly succeeded. A follow-up check confirmed this sandbox has outbound DNS resolution (`socket.gethostbyname('hyperx.com')` succeeds), so a real HTTP round-trip during that test run is the most likely explanation, not ruled out by any evidence to the contrary. This is disclosed here as a real, undeclared, unbounded live request to a third-party site made from what should have been an ordinary offline test run — the same category of event this project's Stage 12/13 Razer audit treated as a policy violation requiring disclosure, not silent correction.

**Fix**: all 3 tests now explicitly pass `hyperx_adapter_factory=lambda: HyperXAdapter(urls={})`, so they can never resolve a URL for any code regardless of what `KNOWN_URLS` holds in production. Audited the rest of `tests/` for the same shape (any `HyperXAdapter(...)` construction without an explicit `urls=`, or any `worker.run_once()` call with brand `HYPERX` and no `hyperx_adapter_factory` override) — no other instance found. The entire suite was then re-run wrapped in `enforce_policy_aware_fetch_only()` (the Part 2 guard) as a direct safety check: **823/823 pass, zero calls blocked, meaning zero real `requests.Session` calls occurred anywhere in the suite** — see [`tests.txt`](tests.txt) for the plain run and the verification transcript for the guarded run.

This incident is the concrete reason Part 2's guard work matters beyond the census scripts it was scoped to: had the guard been active during that first run, the accidental real call would have failed loudly with `DirectNetworkCallBlocked` instead of silently succeeding. It was not active for that specific run (it only covers the 4 `product_tool/census/*.py` entry points, not test-suite execution in general) — wrapping full test-suite runs in the guard as a standing practice is a reasonable follow-up, not implemented as a permanent hook this stage (see "Not done automatically" below for why).

## Verification

- Full suite: **823 tests, 0 failures** ([`tests.txt`](tests.txt)) — 807 (Stage 14) + 16 new (10 in `test_hyperx_stage15_catalog_route.py`, 5 in `test_stage13_host_stop_audit.py`'s `Stage15EntryPointGuardTests`, 1 net new in `test_hyperx_adapter.py`) − 0 removed.
- Same suite, wrapped in `enforce_policy_aware_fetch_only()`: 823/823 pass, 0 blocked calls — proves zero real network access anywhere in the suite as it stands now.
- `01_integrity_check.py`: 23/23 pinned files match, 1/1 authorized deletion confirmed absent (checked by real path, hashed internally), `readiness_table.md` confirmed restored to its exact Stage 13 bytes, 734 prior-stage files (through Stage 14) hashed and unchanged, catalog file hash unchanged.
- `data/catalog_2026-09-21_filtered.xlsx` and every `reports/source_census_*` directory through Stage 14 are untouched except `reports/source_census_2026-09-23_stage13/readiness_table.md`, which was restored (not left modified) — see `readiness_table_restored_to_stage13_original_bytes: true` in [`protected_hashes_check.json`](protected_hashes_check.json).

## Files touched

- Restored: `reports/source_census_2026-09-23_stage13/readiness_table.md` (back to Stage 13 original bytes)
- New (this stage's own artifacts): `readiness_table_hyperx_update.md`, `report.md`, `scripts/01_integrity_check.py`, `protected_hashes_check.json`, `tests.txt`
- Code: `product_tool/adapters/hyperx.py` (KNOWN_URLS populated; `check_identity()` sku/productID fix), `product_tool/census/endpoint_probe.py` (`guarded_entry_point()`), `product_tool/census/runner.py`, `runner_v5.py`, `runner_v71.py`, `report_v71.py` (entry points decorated), `tests/_pipeline_migration.py` (dealer name removed, hash-based deletion check, 4 new file entries)
- Tests: `tests/test_hyperx_stage15_catalog_route.py` (new, 10 tests), `tests/test_stage13_host_stop_audit.py` (+5, `Stage15EntryPointGuardTests`), `tests/test_hyperx_adapter.py` (2 tests fixed for production `KNOWN_URLS`, 1 new), `tests/test_dns_fallback.py` (3 tests fixed for the network-safety incident), `tests/test_structural_census_v8_1.py..v9_1.py` (all 10, `DELETED_FILES` → `is_deleted_file_path`, re-pinned)

## Not done automatically

No live/new HTTP request was attempted for any of the other 39 HyperX catalog rows — no new brand census, no URL guessing, no name-similarity matching. No permanent process-wide test-suite network guard was installed (`tests/` is not currently a package — most test files rely on `tests/` being on `sys.path` directly for `from _pipeline_migration import ...`-style imports, so adding `tests/__init__.py` to hook a guard at import time would break that convention across dozens of files; this was judged out of scope for this stage beyond fixing the 3 actually-exposed tests and proving the whole suite is clean under the guard when run that way explicitly). No change to the catalog, to Bosch/Cudy, or to any pre-Stage-15 report artifact other than the `readiness_table.md` restoration itself.
