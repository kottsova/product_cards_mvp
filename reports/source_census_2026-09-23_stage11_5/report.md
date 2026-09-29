# Stage 11.5 — closing the historical-test gap, scoping DNS precisely, hardening document checks

**No new HTTP requests this stage. No QuadCast 2S manual search.** All 707 prior stage report files (through Stage 11.4) remain byte-identical: [`migration_record_and_integrity.json`](migration_record_and_integrity.json). Catalog and production registry untouched.

## 1. The 10 historical protection tests — explained, then fixed, not hidden

Stage 11.4 authorized real pipeline changes to `product_tool/{display,jobs,worker}.py`. Every one of `tests/test_structural_census_v8_1.py` through `v9_1.py` independently re-checks those exact files against a frozen Stage 8 snapshot (`reports/source_census_2026-09-22_stage8/protected_hashes_after.json`) — so all ten started failing the moment Stage 11.4 touched them, correctly and honestly.

**The fix, in order:**

1. [`tests/_pipeline_migration.py`](../../tests/_pipeline_migration.py) (new) — the single, explicit, documented record: which files changed, in two categories (`PRODUCTION_CODE_MIGRATION`: the 3 files Stage 11.4 was authorized to change; `TEST_FILE_MIGRATION`: the 10 test files, changed only because fixing #1 required editing them too), each with a plain-English reason. `is_authorized_change(path)` is the one function every affected test now calls.
2. Each of the 10 test files' Stage-8-baseline check now skips paths where `is_authorized_change()` is true — every *other* file is still verified byte-for-byte with zero exceptions.
3. Editing those 10 files necessarily changed their own hashes too — which broke the *cross-stage* checks (`test_stage8_1_untouched` in `v8_2.py`, `test_stage8_1_and_stage8_2_untouched` in `v8_2_1.py`, and so on through `v9_1.py`, each comparing an earlier test file's current hash against a value frozen in that later stage's own `reports/.../protected_hashes_check.json`). The same `is_authorized_change()` exemption was applied there too — including fixing one file (`v8_2.py`) whose check used a full-dict equality rather than a per-key loop, which needed the *expected* side filtered the same way as the *current* side, not just a `continue`.

**Result:** [`migration_record_and_integrity.json`](migration_record_and_integrity.json) records exactly 13 authorized changes (3 production files + 10 test files), all independently reverified as actually different from the Stage 8 baseline (`all_changed_as_expected: true`) — nothing was papered over by asserting a false "unchanged." Full suite: **751 tests, 0 failures** ([`tests.txt`](tests.txt)). No test was skipped, deleted, or commented out — every one of the ten still runs its full original check, just with one documented, narrow exemption apiece.

## 2. DNS scope, made precise in code and here

**The rule**: DNS may be used for any brand/category. **What that means in code**: a network request only happens when `adapters/dns.py`'s `KNOWN_URLS`/`KNOWN_DOCUMENT_URLS` already has a pre-verified exact URL for that product's search code — still exactly one entry each (`9A273AA`), unchanged this stage. For every other row, `find_source()` now returns an explicit `match_level="dealer_url_needed"` instead of a bare "unknown," carrying a structured request (`product_tool/dealer_fallback.py::dealer_url_needed_request`):

```
DealerUrlNeeded(
    status="dealer_url_needed",
    brand="HYPERX", model_variant_hint="Микрофон QuadCast 2S Black", seller_code="9A273AA",
    missing_fields=("характеристики", "фото", "инструкция"),
    message="Нет проверенного дилерского URL для «HYPERX Микрофон QuadCast 2S Black» "
            "(артикул 9A273AA). Не хватает: характеристики, фото, инструкция. Нужна точная "
            "ссылка на карточку товара у дилера (DNS и/или Технопарк) -- не будет угадана и "
            "не будет запущен общий поиск."
)
```

`worker.py` now surfaces this message verbatim as the job's finish message for a non-LG product with no known DNS URL, instead of a generic "not found." Tested by `DealerUrlNeededTests` (3 tests) and `HostRoleTests.test_unconfigured_search_code_makes_no_network_call` (reconfirms zero network calls either way).

## 3. Two dealer roles, not one — the user's stated preference, recorded

`product_tool/dealer_fallback.py`'s module docstring now states it directly: **Technopark**, once an exact page exists, is for **cross-checking disputed/conflicting characteristics and variant identity against the official source**; **DNS** is for **filling in characteristics/photos/instructions the official source never supplied**. Official sources always have priority over either. `source_types.py` now classifies `"technopark"` as a dealer-type source key (for future display/provenance use) — but **no adapter module exists** (`TechnoparkPolicyTests.test_no_technopark_adapter_module_exists_yet` asserts `ModuleNotFoundError`), and nothing claims a QuadCast 2S manual exists there. No request was made to technopark.kz or any other host this stage.

## 4. Document verification, hardened: a match alone is not enough if it contradicts itself

`document_verification.verify_document()` gained `conflicting_model_tokens`/`conflicting_codes` parameters (optional, empty by default — fully backward compatible, confirmed by `test_no_conflicting_list_supplied_does_not_reject`). **A model or code match is now accepted only when no known conflicting model/code reference is also present** in the same text — a document can legitimately mention the right code in a passing compatibility note while actually covering a different, named sibling model, and that must still be rejected. New `document_type="conflicting_model_reference"` value, with the specific conflicting token recorded on the result (`conflicting_reference_found`).

**The exact case asked for** — "code matched, but the document is for a different model" — is now a named, tested scenario: `test_code_matches_but_conflicting_sibling_model_is_rejected`, using a new synthetic fixture (`hyperx_quadcast_s_manual_with_2s_compatibility_note_synthetic.txt`) where `9A273AA` genuinely appears in the text (a compatibility note) but the document's own subject is the sibling `QuadCast S`. Result: `matched_code=True`, `accepted=False`, `document_type="conflicting_model_reference"`. A second test (`test_conflicting_code_also_triggers_rejection`) proves the symmetric case (model matches, conflicting code present).

**The Stage 11.3 PDF stays the permanent negative fixture**, unchanged: `hyperx_quadcast_original_manual_excerpt.txt` (`Document No. 480HX-MICQC.A01`, part number `HX-MICQC-BK` — the original QuadCast, not "2 S") — still rejected for `9A273AA` as `model_mismatch` (`test_old_quadcast_manual_is_rejected_for_quadcast_2s`), independent of and prior to this stage's new conflicting-reference logic.

## 5. Clean test result

`tests/test_dns_fallback.py`: **40 tests** (31 from Stage 11.4 + 9 new this stage), all passing. Full suite: **751 tests, 0 failures.**

## Artifacts

- [`report.md`](report.md) — this file
- [`migration_record_and_integrity.json`](migration_record_and_integrity.json) — the 13-entry authorized-change record (old hash / new hash / reason, per file) plus full prior-stage/catalog/registry integrity confirmation
- [`scripts/01_apply_test_migration.py`](scripts/01_apply_test_migration.py) — the byte-safe patch script used on the 10 test files
- [`scripts/02_migration_record_and_integrity.py`](scripts/02_migration_record_and_integrity.py) — builds the record above
- [`tests.txt`](tests.txt) — full test suite output (751 tests, 0 failures)
- Code: `tests/_pipeline_migration.py` (new), `product_tool/dealer_fallback.py`, `product_tool/adapters/dns.py`, `product_tool/adapters/document_verification.py`, `product_tool/source_types.py`, `product_tool/worker.py` (all extended, not rewritten)
- Tests/fixtures: `tests/test_dns_fallback.py` (+9 tests), `tests/fixtures/stage11_4/hyperx_quadcast_s_manual_with_2s_compatibility_note_synthetic.txt` (new)

## Not started automatically

No new HTTP requests. No QuadCast 2S manual search (DNS, Technopark, or otherwise). No Technopark adapter built. No promotion of any dealer source into the production registry. No other catalog row touched.
