# Stage 43 — real LG site search wired into the production pipeline

Batch `ae3d2cb381744ba8a811e54231233254` from `тест.xlsx` (12 rows); the file was not re-loaded. Pre-run SQLite backup: `batches_before_stage43.sqlite3`, SHA-256 `48c5033627e8bcafa165224b60cdee889b085006c4c0da3ca0aed4bf9170cb68`.

## Goal

Before this stage, the LG adapters found a product's official page only by matching its article against the KZ/RU sitemap. A row not in the sitemap under a recognizable slug stayed `mismatch`/`unknown` even when LG's own site search could, in principle, find it — exactly the gap the owner's old scripts (`A:\work\dev\lg\lgworkingwithonemodel.py`, `lg1.py`, read-only reference) filled by driving a real browser against LG's search. This stage wires a bounded version of that into the production path.

## What was actually found on the live site (facts, not assumption)

A feasibility check was run before any production code was written (`feasibility_check*.py`, not committed):

1. **KZ (`www.lg.com/kz/...`)** — ANY navigation, even the plain homepage, is met with a confirmed browser-verification challenge under a plain, non-stealth headless Chromium session (the project's existing `census/browser_runtime.py`/`census/browser_worker.py`, unmodified). Checked twice (homepage alone; the guessed search URL). No stealth driver, no CAPTCHA bypass, no silent reset was used or considered — the finding is recorded into the same persisted `lg_fetch_log.json` the plain-HTTP path already uses, so it stops both paths, this run and every future one.
2. **RU (`www.lg.com/ru/...`)** — the obvious guess, a plain `?search=<query>` GET, renders an empty "no results" page shell for *every* query, including a code known to exist (confirmed by three separate DOM re-reads with waits in between — not a rendering-timing issue). The real route was found by actually clicking the header search field and submitting a query like a real user, in a plain headless session, and reading back the URL the site's own client JS navigated to: `.../ru/search/search-support?search=<query>&...`. It returns `/ru/support/product/lg-<code>` links — LG's *support* catalog, not commerce product pages.
3. A candidate support page commonly **redirects from a full-article URL to the shared base model**, and then prints only ONE — not necessarily the target — variant's own sales code (`data-product-id`). This matches Stage 42's independent finding for the same behavior on a different row.

These facts shaped the design (`docs/LG_STAGE43_BROWSER_SEARCH.md`): browser search is discovery-only, RU-only (KZ is a confirmed, honestly-reported dead end), and a hit is never enough by itself — only the **candidate page's own printed code** is evidence, appended as a sentence, never a silent upgrade of `match_level`.

## Code (Stage 43 migration, `tests/_pipeline_migration.py`)

- New: `product_tool/adapters/lg_browser_search.py` (`LGBrowserSearch`, `BrowserSearchResult`) — a thin, bounded wrapper around the existing `census.browser_runtime` subprocess; no new browser driver code.
- `product_tool/adapters/lg.py` (protected, migration + repin): `LGAdapter`/`LGRUAdapter` gain an optional `browser_search=None` parameter; `find_source` tries it only after the sitemap misses `full_sku`; a new `_augment_with_browser_search()` fetches any support-page candidate through the *existing* plain-HTTP path and appends an evidence sentence (confirmed / different code found / search's own stop reason) — never changes `match_level` by itself. A multi-unit kit article is searched **per component**.
- `product_tool/adapters/policy_fetch.py`: two small public wrappers (`read_log`/`append_log_entry`) so the browser path and the plain-HTTP path share one persisted challenge-stop log.
- `product_tool/adapters/lg_policy.py`: `default_lg_adapters()` now returns a 4-tuple `(lg_kz, lg_ru, sulpak, browser_search)`, wiring a real `LGBrowserSearch` in by default (`browser_search=True`); every offline test that calls it now explicitly passes `browser_search=False` so no offline test can launch a real browser.
- `product_tool/worker.py` (protected, migration + repin): unpacks 2/3/4-tuples; closes `browser_search` in a `finally` after the job (bounded one-product lifetime); `OFFICIAL_BUDGET_SECONDS` raised 20→45 so a row that needs the fallback has room for it. **A real bug was found and fixed during this stage**: the new `finally` block referenced `lg_browser_search` even on the Bosch/other-brand early-return paths, which never assign it — `UnboundLocalError` on every non-LG job. Fixed by initializing it before the `try` block; caught by the offline suite (`tests.test_coverage_queue`, `tests.test_stage36_bosch_home`), not by hand.

## Tests

New `tests/test_lg_browser_search.py` (9 tests, fake driver, no real subprocess): candidates found and filtered to support URLs; no candidates across both queries; a confirmed challenge persisted and a later instance launches nothing; runtime unavailable; an already-stopped host short-circuits mid-instance too; driver closed after use. Extended `tests/test_lg_workflow.py` (`LGBrowserSearchFallbackTests`, 6 tests): default `None` is byte-for-byte the old behavior; a support page confirming the exact article adds a note without upgrading `match_level`; a different code found is reported, not hidden; a stop reason is surfaced when the sitemap found nothing; a sitemap `full_sku` never triggers browser search; a kit's components are searched individually. Four existing tests (`test_stage20_lg_policy.py` ×2, `test_stage22_documents.py`, `test_stage37_lg_batch.py`) updated for the new 4-tuple and to explicitly disable the real browser for offline runs.

Full offline suite: `python -m tests -q`, 1281 tests, `OK` (`full_tests_final.log`; a first final run caught one forgotten re-pin — the evidence-dedupe fix to `lg.py` made after the first hash computation — fixed and re-run clean).

## Live validation (staged, budgets declared before each step)

1. Feasibility check on one query (~6 real navigations across the two routes above) — see facts section.
2. Code built and tested offline.
3. Live check on 5 of the batch's own codes through the real `find_source` (`MS2082F`, both `P12ED` kit components, `RNC9.DRUSLLK`, `W4W8LVPKZHM.APBPCOM`, `ON77DKDRUSLLK`) — confirmed the mechanism end to end, including one genuine new confirmation (`W4W8LVPKZHM.APBPCOM` on RU) and several honest "found a different code" results.
4. One live run of the full 12-row batch: DB backed up, the project's own embedded web app restarted (`uvicorn product_tool.web:create_app`, port 8765) so it runs the new code, the 12 rows re-enqueued through the real `/batches/{id}/lg-search` route (not a script bypassing the app), processed by the app's own background worker thread, then the real Excel export downloaded and product pages spot-checked (all HTTP 200).

## Per-row result (12 of 12)

| # | Article | Category | KZ | RU | Job | Card readiness |
|---|---|---|---|---|---|---|
| 4 | `P12ED.NSAR + P12ED.USAR` | сплит-система | mismatch — no KZ search route | mismatch — search found the code, but every landed support page names a *different* article (`P12EP`/`P12EP1` family, both components) | needs_review | not_ready |
| 5 | `S3WER.ALWPCOM` | Паровой шкаф | **full_sku** (own page field) | base_model (search hit a transient browser error this run — reported, not hidden) | **done** | export_ready_with_gaps |
| 6 | `MS2082F` | Микроволновая печь | mismatch — no KZ search route | mismatch — search found a different real model (`MS2044V...`), confirming the code itself is likely not LG's actual designation | needs_review | not_ready |
| 7 | `TW4V7EB1W` | Стиральная машина | full_sku (sitemap) | mismatch — search found three different, unrelated RU models; this article does not appear to be sold in Russia under this code | needs_review | export_ready_with_gaps |
| 8 | `GC-B459MLWM.ADSQCIS` | Холодильник | full_sku (sitemap) | full_sku (sitemap) | needs_review (real conflicts, unrelated to identity) | export_ready_with_gaps |
| 9 | `VK89309H` | Пылесос | full_sku (sitemap) | full_sku (sitemap) | needs_review (1 real conflict) | export_ready_with_gaps |
| 10 | `W4W8LVPKZHM.APBPCOM` | Стирально-сушильная машина | full_sku (sitemap) | base_model, but **search confirmed the exact article on the official support page** (new evidence) | needs_review (real conflicts) | export_ready_with_gaps |
| 11 | `86NANO81A6A` | Телевизор | full_sku (sitemap) | full_sku (sitemap) | needs_review (1 real conflict) | export_ready_with_gaps |
| 12 | `RNC9.DRUSLLK` | Аудиосистема | full_sku (own page field) | full_sku (own page field) | needs_review (1 real conflict) | export_ready_with_gaps |
| 13 | `S40T` | Саундбар | full_sku (sitemap) | full_sku (sitemap) | done | export_ready |
| 14 | `ON66` | Музыкальный центр | full_sku (sitemap) | full_sku (sitemap) | needs_review (1 real conflict) | export_ready_with_gaps |
| 15 | `ON77DKDRUSLLK` | Микросистема | base_model — no KZ search route | base_model — search found two different codes (`ON77DK.DLVALLK`, `ON66.DCISLLK`), neither matches | needs_review | not_ready |

Full per-row evidence text: `batch_summary.json`.

## Database integrity

`PRAGMA integrity_check = ok`, `foreign_key_check = []`. Row-count comparison against the pre-run backup: `search_jobs` 22→34 (+12, exactly the new jobs), `job_events` 255→399, `fetch_attempts` 81→129, `source_snapshots` 78→124 — all additive and all inside this batch's 12 products. `source_pages`, `extracted_attribute_facts`, `resolved_attributes`, `photo_candidates`, `product_documents` are unchanged in *count* (each is upserted per product/source, not accumulated) and every row belonging to a product outside this batch is byte-identical in every table checked. SHA-256 of the database after the run: `45e67636c5be4df6ff9341b71f96c179f906c51233f32da6c5f2053e2fe4392d`.

Excel export downloaded live (`batch_after_stage43.xlsx`) and spot-checked: row 2 (`S3WER.ALWPCOM`) now reads "Завершено (done)" / "Есть пробелы (export_ready_with_gaps)". `/products/4,5,6,10,12,15` all returned HTTP 200 on the restarted live app.

## Plain-language summary

**Before this stage**, of the 12 rows, 6 already resolved their full official article through the sitemap alone (`TW4V7EB1W` on KZ, `GC-B459MLWM.ADSQCIS`, `VK89309H`, `86NANO81A6A`, `S40T`, `ON66`), and only **1 card (`S40T`) was fully finished (`done`)**.

**After wiring in the real search**, the app itself found a genuinely new confirmation for one more product (`W4W8LVPKZHM.APBPCOM`, on the Russia site, via the support catalog) and one more card moved to a finished state (`S3WER.ALWPCOM` — steam cabinet, **now `done`**), for **2 finished cards** and **8 of 12 usable** (`export_ready` or `export_ready_with_gaps`, i.e. enough for a person to review and confirm — the remaining gaps on those 8 are real conflicts between KZ and RU values or a still-missing Russian instruction, not identity). **3 rows genuinely cannot be found**, even by search, and the app now says exactly why for each: the two-unit air-conditioner kit (`P12ED`) and the microwave (`MS2082F`) are not recognized under those codes anywhere on LG's site (search actively found *other*, different LG models instead — this points at the catalog's own codes being off, not at a missing feature); the microsystem (`ON77DKDRUSLLK`) is close but not exact (search found two related-but-different codes). For Kazakhstan specifically: the site itself shows a browser-verification page on any automated visit, so KZ-side search could not be used at all — this is recorded honestly, never bypassed, and it only affects KZ; the Kazakhstan sitemap path (which already covers 9 of 12 rows) is completely unaffected.
