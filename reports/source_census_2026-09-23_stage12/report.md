# Stage 12 — pinned-hash migration protection, a real `dealer_url_needed` fix, and one bounded Razer official-discovery cycle

**No QuadCast 2S work this stage. No broad brand census.** Catalog, production registry, and every prior stage's report artifacts (through Stage 11.5, 712 files hashed) remain byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json).

## Part A — hardening Stage 11.5's migration protection

### 1. Membership alone was not protection — now it's a pinned hash

Stage 11.5 introduced `is_authorized_change(path)`: any of the 13 migration files skipped the byte-identical check entirely, with no further verification. That closed the *original* gap (Stage 11.4's real edits correctly failing 10 historical tests) but opened a smaller one: nothing stopped a *later*, unrelated, undocumented edit to one of those same 13 files from being silently waved through by the same membership check.

**The fix:** [`tests/_pipeline_migration.py`](../../tests/_pipeline_migration.py) now carries `PINNED_SHA256`, the exact SHA-256 of each of the 13 files as of this migration, and `check_migrated_file(path, actual_sha256)` — the real check every affected test now calls: not just "is this path authorized" but "does its *current* content match the hash pinned when it was authorized." A file that's authorized-but-no-longer-matches-its-pin fails the test again, with an explicit message naming both hashes and stating plainly that being on the list once doesn't excuse new, unpinned content.

All 10 `tests/test_structural_census_v8_1.py`..`v9_1.py` files were updated (byte-level scripted patch, idempotent, verified against the actual on-disk content of each file rather than assumed) to call `check_migrated_file()` in place of the old bare `continue`. `v8_2.py`'s `test_stage8_1_untouched` (a dict-equality check, structurally different from the others) was rewritten individually to apply the same pinned check per key.

**Self-test of the mechanism:** while implementing Part A's second fix (below), the hash-pinning caught its own trigger — editing `worker.py` immediately failed 10 tests with `'product_tool/worker.py' no longer matches its pinned post-migration hash`, exactly as designed. The fix was to update `PINNED_SHA256["product_tool/worker.py"]` to the new hash and extend that file's documented reason in `_pipeline_migration.py`, not to weaken the check — this is the real proof the mechanism catches what membership alone could not.

### 2. `dealer_url_needed`: concrete missing fields, not a static default

**What was actually wrong:** `worker.py` never passed `missing_fields` to `DnsAdapter.find_source()` at all. `dns.py`'s fallback (`missing_fields or [...]`) therefore fired its full hardcoded `["характеристики", "фото", "инструкция"]` list on *every* `dealer_url_needed`, regardless of what a job actually requested or what other sources had already found for that row.

**The fix (two files):**
- `worker.py`: new `_compute_missing_fields(database, product_id, stages)` checks `jobs.get_facts()` / `get_photo_candidates(include_excluded=False)` / `get_documents()` for the product, restricted to the stages the job actually requested (3/4/6), and passes the real — possibly empty — list into `find_source()`.
- `dns.py`: `find_source()` now distinguishes `missing_fields=None` (caller did not check — kept the old default for backward compatibility with direct callers) from an explicit `[]` (caller checked, nothing is missing). An explicit empty list now returns `match_level="not_needed"` and raises no ask at all.

**Effect on duplicate requests:** because missing fields are recomputed from live DB state on every run rather than a fixed default, a field that gets filled by any source between two job runs drops out of the ask on the very next run. `ComputeMissingFieldsTests.test_worker_stops_asking_once_the_gap_is_filled_elsewhere` (`tests/test_dns_fallback.py`) proves this directly: run 1 (nothing known) asks about "характеристики"; the gap is then closed exactly the way a real source would close it; run 2 for the *same catalog row* returns `match_level="not_needed"` and the finish message no longer contains the ask.

5 new tests, all passing: `DealerUrlNeededTests.test_explicit_empty_missing_fields_means_not_needed_not_dealer_url_needed`, and the `ComputeMissingFieldsTests` class (4 tests). See [`protected_hashes_check.json`](protected_hashes_check.json)'s `dealer_url_needed_fix_summary` for the same account in machine-readable form.

### 3. Clean result

Full suite: **756 tests, 0 failures** ([`tests.txt`](tests.txt)) — 751 prior + 5 new. All 13 pinned files independently reverified against `check_migrated_file()` (`pinned_hash_check_all_ok: true`). 712 files across every prior `reports/source_census_*` directory (2026-09-21 through Stage 11.5) hashed as an untouched-artifact snapshot; catalog and 7 registry config files hashed too. No network requests in Part A.

## Part B — one Razer catalog row, official-only, bounded

### Selection (offline)

`data/catalog_2026-09-21_filtered.xlsx` has 89 Razer rows. Selected: **`RZ01-04640100-R3M1`, "Проводная мышка DeathAdder V3 Black"** (Мыши) — a single, unambiguous variant (one color, wired, non-Pro) of a current flagship product, with Razer's own structured part-number scheme as an exact-match anchor.

### Known route, then bounded discovery — not a guess, not a user question

`product_tool/config/adapter_profiles.v1.json` (`razer_global_candidate`) already recorded `razer.com` as a real, previously-observed manufacturer domain (Stage 8: homepage + one category page, direct access, no protection detected) — but `completeness_status: "product_page_not_found"` for *any* Razer SKU. A route existed, so per instructions this called for bounded official discovery, not a question to the user.

**Budget, declared before any further request** ([`budget_predeclaration_partb.json`](budget_predeclaration_partb.json)): host `www.razer.com` only, 7 additional requests, 2s min interval, first-party-navigation-only, stop on any 401/403/429 with no retry/bypass. Full request log: [`raw/partb_fetch_log.json`](raw/partb_fetch_log.json).

- `robots.txt` → **403**, a large bot-challenge page, not real `robots.txt`. Recorded as blocked, not retried, not bypassed. No sitemap-based discovery was possible as a result.
- Homepage and the one previously-known category page → 200, matching Stage 8.
- Homepage refetched to parse its own links → found `<a href="/gaming-mice/razer-deathadder-v3">Razer DeathAdder V3</a>` among 625 real links on the page — first-party navigation, not a guess, not a search engine.
- That URL → **200**, host stayed on `www.razer.com` throughout, no off-allowlist redirect. **5 requests total this stage; 5 of the declared 7 left unused.**

### What was extracted, with evidence and URL per field

Full detail: [`raw/partb_razer_deathadder_v3_evidence.json`](raw/partb_razer_deathadder_v3_evidence.json).

- **Identity — `base_model_confirmed`, not full SKU.** Title/H1/JSON-LD all read "Razer DeathAdder V3"; the page's own embedded state has `"Color / Design": "Black"` (matches the catalog variant exactly) and the base code `RZ01-04640100` appears verbatim in the page's canonical URL. But this US-store listing's own full code is `RZ01-04640100-R3U1` — region suffix **U1**, not the catalog's **M1**. Same base model, different regional listing. This mirrors the project's existing LG base-model-vs-full-SKU distinction and is reported the same honest way: a real, named gap, not papered over.
- **Characteristics — 20 fields, all sourced from one place.** The page embeds a JSON state object in its own initial HTML (SSR hydration) — no JavaScript execution, no Chromium — containing a full spec table: sensor (Focus Pro 30K Optical), DPI (30000), IPS (750), buttons (6), switch type/lifecycle, cable, dimensions (128.0×68.0×44.0mm), weight (59g), box contents, and more.
- **Official images** — one catalog-style primary product photo plus three marketing/detail images, all on Razer's own CDN (`assets3.razerzone.com` / `assets2.razerzone.com`).
- **Description** — meta description and marketing intro copy, both from the same page.
- **Instruction/manual — gap, honestly reported, not guessed.** Box Contents names an "Important Product Information Guide," confirming one exists, but no document link appears anywhere in this page's own HTML. Every support/manual link on the page points to `mysupport.razer.com` — a different host, never predeclared in this stage's allowlist — so it was not fetched. Not a silent omission; recorded as a named gap.
- **Dealer fallback — genuinely not needed, not guessed.** `adapters/dns.py`'s `KNOWN_URLS` has no entry for this code or its base; no DNS URL was searched for or invented. Technopark still has no adapter (Stage 11.5, unchanged). Official data recorded here takes priority over any future dealer value for the same field; a conflicting dealer value would go to review, never silently overwrite it.

### Not done, deliberately

No Chromium. No search engine. No dealer mass search. No model brute-forcing. No invented endpoint (`mysupport.razer.com` was seen linked, not guessed, and not fetched without a declared allowlist entry). No region-specific (`R3M1`) Razer URL was guessed to "complete" the SKU match. Catalog, production registry, and every pre-Stage-12 report directory untouched — reconfirmed in the same `protected_hashes_check.json` as Part A.

## Artifacts

- [`report.md`](report.md) — this file
- [`protected_hashes_check.json`](protected_hashes_check.json) — Part A: pinned-hash reverification (13/13 ok) + prior-stage/catalog/registry integrity (712 files) + machine-readable fix summary
- [`budget_predeclaration_partb.json`](budget_predeclaration_partb.json) — Part B budget, declared before discovery requests
- [`raw/partb_fetch_log.json`](raw/partb_fetch_log.json) — every HTTP request made this stage, in order, with outcome
- [`raw/partb_razer_deathadder_v3_evidence.json`](raw/partb_razer_deathadder_v3_evidence.json) — identity, characteristics, images, description, manual gap, dealer-fallback status, each with its source
- [`scripts/01_pin_migration_hashes.py`](scripts/01_pin_migration_hashes.py), [`scripts/02_fill_pinned_hashes.py`](scripts/02_fill_pinned_hashes.py), [`scripts/03_integrity_and_dealer_fix_check.py`](scripts/03_integrity_and_dealer_fix_check.py) — the scripts behind the artifacts above
- [`tests.txt`](tests.txt) — full suite, 756 tests, 0 failures
- Code: `tests/_pipeline_migration.py`, `product_tool/adapters/dns.py`, `product_tool/worker.py`
- Tests: `tests/test_dns_fallback.py` (+5 tests: `DealerUrlNeededTests` x1, `ComputeMissingFieldsTests` x4)
