# Stage 14 — HyperX: from confirmed research to a real pipeline adapter

**No new HTTP requests this stage.** Catalog and every prior stage's report artifacts (through Stage 13, 731 files hashed) remain byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). This is the first implementation step of Stage 13's own priority queue, not a new brand census — no Bosch or Cudy identity/adapter was built.

## Part A — closing the two Stage 13 remnants

### 1. The removed dealer's name, genericized in the active migration record

`tests/_pipeline_migration.py`'s prose (in `PRODUCTION_CODE_MIGRATION` and `DELETED_FILES`) named "Mechta" repeatedly in its own reasoning text. Rewrote every prose mention to describe it generically ("a second, no-longer-authorized LG-only supplier adapter") while keeping the one place a real name is unavoidable: `DELETED_FILES`'s dict **key** is the literal historical path (`product_tool/adapters/mechta.py`) — renaming that would make the deletion record itself inaccurate, so it stays, with a comment explaining why. `check_deleted_file()` and the "must be genuinely absent, never merely assumed" verification are unchanged.

### 2. Research code can no longer bypass the host-stop rule with a raw `requests.Session`

Stage 13 fixed the narrower gap (seeding a *new* `AccessProbe` with a past block). The actual Stage 12 mistake — never using `AccessProbe` at all — was still possible. `product_tool/census/endpoint_probe.py` now has:
- `enforce_policy_aware_fetch_only()` — a context manager that, while active, makes **every** direct `requests.Session.get()` call not routed through `AccessProbe.probe()` raise `DirectNetworkCallBlocked` before any network I/O.
- `AccessProbe` itself is immune to its own guard: `probe()` now calls through a `_get()` helper that, for a real `requests.Session`, always uses a reference captured at import time (`_REAL_SESSION_GET`), so legitimate research through the correct path keeps working no matter when the guard is installed.

Audited `product_tool/census/*.py` for direct `requests` usage outside `endpoint_probe.py`/`probe.py`: **none found** — the library modules already only ever touch the network through `AccessProbe`. Stage 12's violation was ad-hoc code outside any checked-in script, which is exactly what this guard is for: any future research code (script or one-off) that wraps its work in `enforce_policy_aware_fetch_only()` gets the same protection Stage 12 should have had. 3 new regression tests in `tests/test_stage13_host_stop_audit.py`, including one reproducing "403 via a real AccessProbe run, then a direct-`Session` bypass attempt" end to end and confirming the bypass makes zero further requests.

## Part B — the HyperX adapter

### What's genuinely new

- **`product_tool/adapters/structured_page.py`** (new) — reusable, source-agnostic Product-page extraction, built from Stage 8.1's confirmed structural contract (JSON-LD Product + Shopify DOM): `extract_json_ld_product`, `extract_dom_spec_table` (`dl:dt+dd`, `table`, `details+summary`), `extract_main_gallery` (strictly `data-media-id`/`data-fancybox` — a logo carrying a `srcset`, even one that also happens to carry a gallery attribute, is excluded by an explicit logo-class check, not by accident), `extract_description_images`, `extract_video`. Every single field returned is an `ExtractedField(name, value, url, evidence, role, confirmation)` — never a bare value.
- **`product_tool/adapters/hyperx.py`** (new) — `HyperXAdapter`, the source-specific part: identity via `split_hyperx_code()` (base code vs `#region-suffix`, e.g. `7G7A4AA#ACB`) and `check_identity()`, classifying a match as `exact_variant` (full code matches), `base_code_confirmed` (base matches, suffix doesn't — same tier logic as LG's base/full-SKU and Stage 12's Razer M1/U1), `mismatch`, or `unknown`. `find_documents()` never turns box-contents text into a document — only a genuine link would count, and none exists yet. `KNOWN_URLS` is **intentionally empty** in production: no human has verified a real per-SKU hyperx.com URL, and none was guessed.
- **`product_tool/worker.py`** — new `is_hyperx` branch and `hyperx_adapter_factory` parameter (mirrors `dns_adapter_factory`), wired into the same `run_once()` every other source uses. Finish-status priority: `exact_variant` → `done`; else a DNS confirmation is never discarded just because HyperX itself found nothing this run → `needs_review`; else HyperX's own error/`official_url_needed` → `error`; else (`base_code_confirmed`/`mismatch`/conflict) → `needs_review`, never silently accepted.
- **`product_tool/resolution.py`** — `OFFICIAL` gained `"hyperx"`. The `official_base_only`/`official_regions_conflict` messages, previously hardcoded to say "LG", are now generic (built from each source's own `site_name`) since they're no longer LG-exclusive once a second official source exists.
- **`product_tool/source_types.py`** — `"hyperx"` added to `OFFICIAL_SOURCE_KEYS`.

### Fixtures — synthetic, offline, clearly labeled

No real hyperx.com page content is stored anywhere (consistent with this project's no-raw-content rule) and no new HTTP request was made. `tests/fixtures/stage14_hyperx/` holds 5 synthetic HTML files, each opening with an explicit "SYNTHETIC, not a real capture" comment, built to match the *already-confirmed* structural contract:
- `quadcast_2s_black_9a273aa_synthetic.html`, `pulsefire_fuse_a1ky6aa_synthetic.html` — the two positive catalog rows.
- `alloy_rise_75_aba_region_mismatch_synthetic.html` — the negative case: page code `7G7A4AA#ABA` against catalog `7G7A4AA#ACB`.
- `bosch_boundary_synthetic.html`, `cudy_boundary_synthetic.html` — **boundary tests only**, shaped after each brand's own confirmed structural contract, used solely to prove `structured_page.py` generalizes for JSON-LD/DOM-table extraction and correctly finds **zero** gallery images for their non-Shopify markup. No Bosch/Cudy identity check or adapter exists.

### Verified, offline

- `tests/test_structured_page.py` (18 tests) — every extraction primitive, plus the Bosch/Cudy boundary tests.
- `tests/test_hyperx_adapter.py` (20 tests) — identity logic, full-page parsing, host/blocked-status policy, the Quick-Start-Guide-is-not-a-document rule.
- `tests/test_hyperx_worker_integration.py` (4 tests) — **offline replay through the real `worker.run_once()`**: 9A273AA → `done`, `exact_variant`, real characteristics and photos saved, zero documents (the genuine gap, visible not hidden); A1KY6AA → `done`, `exact_variant`; the `#ABA`-vs-`#ACB` keyboard → `needs_review`, match level `base_code_confirmed`, **never** `exact_variant`; and a dedicated test proving the DNS dealer fallback is asked only about `["инструкция"]` — the one category HyperX's own page didn't fill — never characteristics or photos it already found.

Full suite: **807 tests, 0 failures** ([`tests.txt`](tests.txt)) — 762 (Stage 13) + 45 new.

### Catalog row coverage — stated plainly

**0 of HyperX's 41 catalog rows have a human-verified real URL in production.** `KNOWN_URLS` is empty by design; supplying one is the actual remaining gap, not more code. 2 rows (9A273AA, A1KY6AA) plus the negative regional-suffix case are proven correct end-to-end — identity, extraction, worker wiring, dealer-fallback interaction — through synthetic fixtures and offline `run_once()` replay, ready for the moment a real URL is supplied. This is stated the same way in [`readiness_table.md`](../source_census_2026-09-23_stage13/readiness_table.md), which this stage updates in place (Stage 13's own file, not re-created) — HyperX moved out of the "structural only" bucket; Bosch and Cudy did not move at all.

### Known, documented limitation (not fixed this stage)

`resolve_attributes()`'s per-attribute `official_base_only` status wording still reads as tentative ("не подтверждено") even for a HyperX `exact_variant` match, because the function's official-source branch doesn't currently consult each page's own `match_level` — only whether a single unconflicted official source exists. The *value* resolved is still correct either way (the official source's own fact is what gets picked); only the status label's phrasing is imprecise for HyperX's stronger identity tier. Fixing it properly means threading `match_level` into `resolve_attributes()`, a larger change than "add the HyperX adapter" — left as a named gap rather than silently patched over or silently left unmentioned.

## Artifacts

- [`report.md`](report.md) — this file
- [`protected_hashes_check.json`](protected_hashes_check.json) — 19/19 pinned files verified, 1/1 authorized deletion confirmed absent, 731 prior-stage files hashed
- [`scripts/01_integrity_check.py`](scripts/01_integrity_check.py)
- [`tests.txt`](tests.txt) — full suite, 807 tests, 0 failures
- Code: `product_tool/adapters/structured_page.py` (new), `product_tool/adapters/hyperx.py` (new), `product_tool/worker.py`, `product_tool/resolution.py`, `product_tool/source_types.py`, `tests/_pipeline_migration.py`, `product_tool/census/endpoint_probe.py`
- Tests: `tests/test_structured_page.py` (new), `tests/test_hyperx_adapter.py` (new), `tests/test_hyperx_worker_integration.py` (new), `tests/test_stage13_host_stop_audit.py` (+3), `tests/test_dns_fallback.py` (fixed for the new OFFICIAL/is_hyperx interaction)
- Fixtures: `tests/fixtures/stage14_hyperx/` (5 synthetic HTML files)
- Updated: `reports/source_census_2026-09-23_stage13/readiness_table.md` (HyperX's status; Stage 13's own report.md untouched)

## Not started automatically

No real hyperx.com URL was found, verified, or guessed. No Bosch or Cudy identity check or production adapter. No new brand census. No document/manual-fetch logic for HyperX (find_documents() is honest about finding nothing, not a stub pretending to work). No change to the catalog or any pre-Stage-14 report artifact.
