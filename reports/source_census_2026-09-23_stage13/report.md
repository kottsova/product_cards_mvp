# Stage 13 — offline audit: Stage 12's Razer policy violation, full Mechta removal, and an honest coverage map

**No new HTTP requests this stage.** Catalog and every prior stage's report artifacts (Stage 12 and earlier, 721 files hashed) remain byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). Stage 12's own `report.md` and `raw/` files are **not edited** — this report corrects and supersedes its Part B findings without rewriting history.

## 1. Stage 12's razer.com request chronology — a real policy violation, found and fixed

Full reconstruction: [`raw/stage12_razer_request_chronology_audit.json`](raw/stage12_razer_request_chronology_audit.json); the fetch log used by the new regression test: [`raw/stage12_razer_fetch_log_for_host_stop.json`](raw/stage12_razer_fetch_log_for_host_stop.json).

**Execution order, exact and authoritative** (from the session transcript itself — the actual order tool calls ran in):

| # | URL | Result | Classification |
|---|---|---|---|
| 1 | `https://www.razer.com/robots.txt` | HTTP **403**, a 669,719-byte bot-challenge page, not real `robots.txt` | **BLOCK EVENT** |
| 2 | `https://www.razer.com/` | 200 | **POLICY VIOLATION** — after #1 |
| 3 | `https://www.razer.com/shop/gear-and-apparel/apparel-shirts` | 200 | **POLICY VIOLATION** |
| 4 | `https://www.razer.com/` (refetched to parse links) | 200, saved 16:37:14+04:00 | **POLICY VIOLATION** |
| 5 | `https://www.razer.com/gaming-mice/razer-deathadder-v3` | 200, saved 16:37:39+04:00 | **POLICY VIOLATION** |

**Timestamps**: precise wall-clock times exist only for requests #4 and #5 (OS file mtimes of the two scratch-directory copies saved that session — 16:37:14 and 16:37:39, both 2026-09-23). Requests #1–3 have no recorded timestamp, only their certain relative order; this gap is itself a symptom of the same root cause below.

**Root cause**: this project already has the exact mechanism required — `product_tool/census/endpoint_probe.py::AccessProbe`. On any 403/429 response, it adds the host to an internal stopped-hosts set; every later `.probe()` call to that host short-circuits with zero network calls (proven by the pre-existing `tests/test_source_census.py::SafeProbeTests::test_403_stops_repeated_request_to_endpoint`). Stage 12 Part B did not use it. It used four ad-hoc `requests.Session().get()` calls run directly via the Bash tool, which has no memory of anything and enforces nothing. Requests #2–5 would have been physically impossible through `AccessProbe` once #1 returned 403.

**Consequence for Stage 12's findings**: everything in `reports/source_census_2026-09-23_stage12/raw/partb_razer_deathadder_v3_evidence.json` — identity, characteristics, images, description — was obtained from requests #4 and #5, both post-block. **This is downgraded, not deleted.** It is not confirmed evidence of a compliant pipeline result, it does not certify a Razer adapter as ready, and it is not cited that way in the readiness table below (see Razer's row in [`readiness_table.md`](readiness_table.md)). The M1-catalog-vs-U1-page suffix difference Stage 12 already found stays exactly as unresolved as Stage 12 left it — not investigated further this stage, per instruction.

## 2. The fix: the stop now survives a fresh run, not just one instance

Membership in a stopped-hosts set that lives only inside one `AccessProbe` object would not have prevented Stage 12's mistake anyway — the actual bug was *not using AccessProbe at all*. The real gap: even a compliant future script, run as a fresh process, starts with an empty stopped-hosts set and would have to hit `robots.txt` and get blocked *again* before stopping — it has no memory of Stage 12's own finding.

**Fix**, in `product_tool/census/endpoint_probe.py`:
- `blocked_hosts_from_fetch_log(entries)` — derives the blocked-host set from any past run's fetch log (`{"url":..., "status_code":...}` records).
- `AccessProbe.__init__(..., initial_stopped_hosts=())` — seeds a brand-new instance with that persisted set.

A future Razer script that loads Stage 12's own fetch log through `blocked_hosts_from_fetch_log()` and passes it as `initial_stopped_hosts` will refuse **every** further request to `www.razer.com` — proven, not asserted, by `tests/test_stage13_host_stop_audit.py::Stage12RazerHostStopAuditTests::test_seeding_a_fresh_accessprobe_with_this_log_blocks_every_further_request`, which seeds a brand-new `AccessProbe` (a stand-in for a fresh process) with Stage 12's actual recorded log and confirms zero network calls for four different URLs, including one never previously tried. A second, generic version of the same guarantee (unrelated to Razer specifically) lives in `tests/test_source_census.py::SafeProbeTests`. 5 new tests total, all passing.

## 3. Mechta removed completely — not disabled, not renamed, not kept as a special case

Per instruction: no `not_allowed` rule naming Mechta, no dedicated processing branch, no user-facing message with that name anywhere active. The general "an unlisted/`not_allowed` dealer is excluded" rule stays — and stays unnamed, exactly as it already was (`product_tool/sources.py::default_source_registry()` and `product_tool/census/registry.py::SourceCatalog.for_brand()` both already filtered by `official_status == "not_allowed"` generically; removing Mechta's record didn't touch that mechanism, it just removed the one example that used to trip it).

**Deleted**: `product_tool/adapters/mechta.py` (the module itself).
**Edited** (config/registry, production code, UI, docs — 8 files): `product_tool/config/source_catalog.v2.json` (record removed entirely), `product_tool/resolution.py` (`SUPPLIERS` now `{"sulpak"}`; the N-suppliers-agree/conflict logic itself was *kept* — it's generic multi-supplier resolution, not Mechta-specific — but de-hardcoded: no literal "Mechta"/"Sulpak" in messages, `source` string is now `"+".join(sorted(keys))`), `product_tool/jobs.py` (`identification_status()` now derives from `resolution.SUPPLIERS` and each page's own `site_name`, not a hardcoded 2-branch `sulpak`/`mechta` check), `product_tool/worker.py` (adapter_factory tuple contract shrank from 3/4-tuple to 2/3-tuple; the fallback loop became a direct Sulpak call), `product_tool/display.py`, `product_tool/exporter.py` (dropped the `Mechta` column from the "Проверка источников" export sheet), `product_tool/templates/product.html` (dropped the Mechta comparison column and photo-selection button), `product_tool/source_types.py`, `product_tool/dealer_fallback.py`.
**Docs**: `README.md` (not protected, edited directly), `docs/SOURCE_CENSUS.md`, `docs/MULTI_DOMAIN_OFFICIAL_FALLBACK_V7.md` (both protected — see migration below).
**Tests**: `tests/test_dns_fallback.py`, `test_lg_workflow.py`, `test_lg_extended.py`, `test_source_census.py`, `test_structural_census_v11_3.py` rewritten to test the *generic* exclusion mechanism with a synthetic example instead of Mechta by name; the genuine two-or-more-suppliers-agree logic in `resolution.py` is now tested with a monkeypatched synthetic second supplier key (`supplier_b`), proving the mechanism without reintroducing a dealer name.

**Migration bookkeeping**: 9 of the above files were already `product_tool`-tree files protected by the Stage 8 baseline (`display.py`, `jobs.py`, `worker.py` already authorized from Stage 11.4; `product_tool/census/endpoint_probe.py`, `source_catalog.v2.json`, `resolution.py`, `exporter.py`, both docs pages newly authorized this stage) plus the 10 `test_structural_census_v8_1..v9_1.py` files (already authorized, re-pinned again — this is their third round of legitimate, documented edits). `product_tool/adapters/mechta.py`'s deletion required extending the migration system itself: `tests/_pipeline_migration.py` now has `DELETED_FILES` + `check_deleted_file()`, a third protection category alongside "authorized edit" — a path in `DELETED_FILES` must be independently confirmed **absent**, never merely assumed. All 10 baseline-check test files updated to use it. Two older per-stage registry checks (`tests/test_internal_search_v5_1.py`, Stage 5.1; `tests/test_identity_reconciliation_v71.py`, Stage 7.1) needed the same exemption, plus a path-separator normalization their older manifests store with backslashes. **19 files pinned, 1 deletion confirmed, all verified**: [`protected_hashes_check.json`](protected_hashes_check.json).

**Deliberately left alone**: `product_tool/census/{report_v5_1,report_v6,report_v7,report_v71,runner,runner_v2,runner_v5,structural_report_v8}.py` still mention Mechta (2 — `runner.py`, `runner_v2.py` — have a live `!= "mechta"` filter). These are one-off, per-stage research scripts from Stages 2–8, never imported by `worker.py`/`jobs.py`/`display.py`/`exporter.py`/`web.py` (confirmed by grep), and are themselves part of the Stage 8 protected baseline the same way `reports/` JSON is. Treated as historical research archive, not active product code — consistent with the instruction's own carve-out for immutable research history.

**Final grep across every active file** (excludes `reports/`), after all edits:
```
README.md                                    -- clean (0 matches)
product_tool/census/report_v5_1.py           -- historical script, left as-is (documented above)
product_tool/census/report_v6.py             -- historical script, left as-is
product_tool/census/report_v7.py             -- historical script, left as-is
product_tool/census/report_v71.py            -- historical script, left as-is
product_tool/census/runner.py                -- historical script, left as-is
product_tool/census/runner_v2.py             -- historical script, left as-is
product_tool/census/runner_v5.py             -- historical script, left as-is
product_tool/census/structural_report_v8.py  -- historical script, left as-is
tests/_pipeline_migration.py                 -- the migration record itself, documents the removal
tests/test_dns_fallback.py                   -- generic-rule test + comments about the removal
tests/test_source_census.py                  -- generic-rule test (full removal, not "disabled")
tests/test_source_census_v2.py               -- pre-existing assertNotIn, still valid
tests/test_structural_census_v11_2.py        -- frozen Stage 11.2 fetch-log check (historical fact)
tests/test_structural_census_v11_3.py        -- frozen Stage 11.3 fetch-log check + live-catalog fix
tests/test_structural_census_v8.py           -- pre-existing assertNotIn, still valid
tests/test_structural_census_v8_1.py         -- assertNotIn fix + DELETED_FILES handling
tests/test_structural_census_v8_2.py         -- assertNotIn fix + DELETED_FILES handling
tests/test_structural_census_v8_2_1.py       -- assertNotIn fix + DELETED_FILES handling
tests/test_structural_census_v8_2_2.py       -- assertNotIn fix + DELETED_FILES handling
tests/test_structural_census_v8_5.py         -- frozen Stage 8.5 fetch-log check (historical fact)
```
No production code, config, UI template, or live documentation path remains in that list. `product_tool/config/source_catalog.v2.json` no longer contains the string `mechta` in any form (`test_schema_loads_and_mechta_is_fully_removed`, `test_mechta_still_disabled` [renamed content, same test name kept]).

## 4. Full suite: 762 tests, 0 failures

[`tests.txt`](tests.txt). Started this stage at 756 (Stage 12's count); net +6 after adding the host-stop regression tests, rewriting the Mechta-specific tests into generic-mechanism tests, and consolidating a couple that no longer made sense as separate cases.

## 5. Readiness map and priority queue

Full detail, all 127 structural-census profiles accounted for: [`readiness_table.md`](readiness_table.md). Summary:

- **Production-ready**: LG (`lg_kz`,`lg_ru`) + Sulpak, both real adapters in the live pipeline. Nothing else.
- **Real full-value cards exist but no adapter was ever built from them**: Samsung (2 cards), PlayStation (1), Xbox/Microsoft (1), HyperX (1) — four brands where the *research* is done and the *code* isn't.
- **Razer's one card is invalid this stage** (§1 above) — excluded from "ready" status until its host is deliberately un-blocked under policy and re-verified through `AccessProbe`.
- **Structural-only evidence (field names, not values)**: Bosch (Home strongest — explicit gtin+mpn), Xiaomi/POCO, Asus, DeLonghi, Nintendo, Cudy, Dreame — grouped in the priority queue by which of the 5 structural layers (discovery/identity/specs/media/documents) each one actually has confirmed, not by brand name or a guessed storefront engine:
  - **Group A** (specs+media both confirmed, only documents missing): Bosch, HyperX, Cudy — shortest path to a second production adapter, Bosch especially given its identity strength.
  - **Group B** (media confirmed, specs+documents both missing): Xiaomi/POCO, Asus, DeLonghi, Nintendo — largest by product count, least structurally solved.
  - **Group C** (documents confirmed, specs+media missing): Dreame — the only profile with a working documents layer; n=1, nothing to generalize from yet.
- **113 of 127 profiles**: no real Product page at all yet, `production_ready: false` across the board. One catalog brand (Accesstyle, 26 products) has no research profile whatsoever.
- **Samsung's own structural profile entries are stale** — they still say `product_page_not_found` despite two real full-value cards existing from later stage work. A bookkeeping gap worth fixing before trusting `adapter_profiles.v1.json` at face value for Samsung.

No new brand census was run this stage — every fact above comes from re-reading what Stages 2–12 already produced.

## Artifacts

- [`report.md`](report.md) — this file
- [`readiness_table.md`](readiness_table.md) — the full 127-profile map and template-shape priority queue
- [`raw/stage12_razer_request_chronology_audit.json`](raw/stage12_razer_request_chronology_audit.json) — the reconstructed request-by-request audit
- [`raw/stage12_razer_fetch_log_for_host_stop.json`](raw/stage12_razer_fetch_log_for_host_stop.json) — the fetch log the new regression test reads
- [`protected_hashes_check.json`](protected_hashes_check.json) — 19/19 pinned files verified, 1/1 authorized deletion confirmed absent, 721 prior-stage files hashed
- [`scripts/01_patch_registry_hash_checks.py`](scripts/01_patch_registry_hash_checks.py), [`02_add_deleted_files_handling.py`](scripts/02_add_deleted_files_handling.py), [`03_fill_pinned_hashes.py`](scripts/03_fill_pinned_hashes.py), [`04_integrity_check.py`](scripts/04_integrity_check.py)
- [`tests.txt`](tests.txt) — full suite, 762 tests, 0 failures
- Code: `product_tool/census/endpoint_probe.py`, `product_tool/adapters/mechta.py` (deleted), `product_tool/config/source_catalog.v2.json`, `product_tool/resolution.py`, `product_tool/jobs.py`, `product_tool/worker.py`, `product_tool/display.py`, `product_tool/exporter.py`, `product_tool/templates/product.html`, `product_tool/source_types.py`, `product_tool/dealer_fallback.py`, `README.md`, `docs/SOURCE_CENSUS.md`, `docs/MULTI_DOMAIN_OFFICIAL_FALLBACK_V7.md`
- Tests: `tests/test_stage13_host_stop_audit.py` (new), `tests/test_source_census.py` (+2), `tests/_pipeline_migration.py` (extended), plus every file listed in §3's grep output
