# Stage 43: real LG site search wired into the production pipeline

Evidence: `reports/lg_live_batch_2026-09-28_stage43/report.md`. Code: `product_tool/adapters/lg_browser_search.py`, `product_tool/adapters/lg.py` (`_augment_with_browser_search`), `product_tool/adapters/lg_policy.py`, `product_tool/worker.py`.

## What changed

`LGAdapter.find_source` / `LGRUAdapter.find_source` now try LG's own site search (a real, bounded, non-stealth headless-Chromium render — `adapters/lg_browser_search.LGBrowserSearch`, reusing the project's existing `census/browser_runtime.py`/`census/browser_worker.py`) whenever the sitemap lookup does not reach `full_sku`. It is opt-in (`browser_search=None` by default, unchanged behavior); `lg_policy.default_lg_adapters()` — the worker's real default — wires in a real one.

## Two real routes, two real outcomes

- **KZ (`www.lg.com/kz/...`).** ANY navigation, even the plain homepage, is met with a confirmed browser-verification challenge under a plain, non-stealth headless session — checked directly, twice, before any code was written. This is recorded into the same persisted `lg_fetch_log.json` the plain-HTTP path already uses (`protection_status: challenge_confirmed`), so it stops both paths, this run and every future one. No stealth driver, no CAPTCHA bypass, no silent reset was used or considered.
- **RU (`www.lg.com/ru/...`).** The obvious guess — a plain `?search=<query>` GET — renders an empty "no results" page shell for every query (confirmed with a known-good code); it is **not** used. The real route, captured from an actual client-driven search submission (the header search box, typed and submitted, in a plain headless session), is `.../ru/search/search-support?search=<query>&...`. It returns `/ru/support/product/lg-<code>` links — LG's *support* catalog, not commerce product pages.

## The evidence rule (support-page hit ≠ automatic upgrade)

A support-page candidate is fetched through the same plain-HTTP path used for a sitemap-found page, and its **own printed sales code** (`data-product-id`) is read — not its URL, not its search-result label. Following such a link often redirects straight to the shared base model's support page, which prints only ONE (not necessarily the target) variant's code. So:

- the printed code equals the target exactly → an evidence sentence confirming the article, quoting the support page URL;
- the printed code differs → an evidence sentence naming the different code found, so a human sees the discrepancy instead of silence;
- no candidate at all, or the search itself was stopped (challenge / runtime unavailable / host already stopped) → that reason is appended verbatim.

`match_level` is **never** upgraded by a search hit alone — exactly the project's existing rule that a URL/label proves nothing on its own (Stage 23, `support_page_ties_article`). This keeps the same discipline Stage 41 already applied to colour/variant fields: a fact is shown as confirmed only when the authoritative page's own field says so.

## Kit articles

A multi-unit article (e.g. `P12ED.NSAR + P12ED.USAR`) is searched **per component**, not as one opaque string — each half gets its own sitemap attempt and its own browser-search attempt, and its own evidence sentence.
