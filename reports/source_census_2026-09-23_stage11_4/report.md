# Stage 11.4 — DNS dealer fallback, wired into the real pipeline

Unlike every prior stage, this one's explicit mandate was to modify the application itself, not just research and report. All 703 prior stage report files remain byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No network requests were made this stage** — no Technopark URL was supplied, so the manual for `9A273AA` stays open, per instructions, rather than pursued further. Catalog data and the production registry (`source_catalog.v2.json` etc.) were not touched; Sulpak's LG-only allowlist and Mechta's exclusion are unchanged and re-verified by test.

## What "wired into the real pipeline" means concretely

Stage 11.3 left the DNS-fallback rule as a JSON policy document only. This stage makes it real, callable code inside `product_tool/worker.py::run_once` — the same function that actually processes queued jobs against the sqlite job database, the one `product_tool/web.py`'s UI enqueues into. Five new/changed files:

| File | What it does |
|---|---|
| `product_tool/adapters/dns.py` (new) | `DnsAdapter` — a product-page fetcher and a bounded, Range-aware PDF fetcher, both host-role-locked |
| `product_tool/adapters/document_verification.py` (new) | Content-based accept/reject logic: regulatory-document exclusion, model/code matching, language detection |
| `product_tool/source_types.py` (new) | Classifies any `source_key` as `official` / `dealer` / `unknown`, for provenance labeling |
| `product_tool/dealer_fallback.py` (new) | Builds explicit per-field provenance records (`source_type='dealer'`, URL, evidence, identity level) |
| `product_tool/worker.py` (modified) | Runs the DNS stage after LG/Sulpak/Mechta (for LG) or in place of them (for any other brand); `product_tool/jobs.py`/`display.py` (modified) — generic schema support and a `"DNS"` display label |

## Why no schema migration or resolution-logic rewrite was needed

`resolve_attributes()` (`resolution.py`) already resolves each attribute name independently: a `SUPPLIERS`-tier (`sulpak`/`mechta`) full-SKU match wins outright; else an `OFFICIAL`-tier value for that exact attribute name wins and a same-name dealer fact is never even considered; only when **neither** has anything for that name does a lone unconfirmed source (any `source_key` outside those two sets, including `"dns"`) get picked up — and it lands in `needs_review`, never silently confirmed. Since `"dns"` was deliberately **not** added to `SUPPLIERS` or `OFFICIAL`, this is exactly "official first, dealer fills only genuinely missing fields, never silently overwrites, single-dealer conflicts go to review" — with **zero changes to `resolution.py`**, confirmed by `SourcePriorityTests`/`ConflictTests` in the new test file. The existing `source_pages`/`extracted_attribute_facts`/`product_documents`/`photo_candidates` tables are already keyed generically by `source_key`, so `"dns"` slots in without any migration.

## Host roles and limits, enforced in code

- `PAGE_HOST = "www.dns-shop.ru"`, `DOCUMENT_HOST = "drv.dns-shop.ru"` — a page URL on the document host (or vice versa) is rejected *before any request*, proven by `HostRoleTests`.
- Reuses the project's existing `product_tool.census.endpoint_probe.ProbePolicy` dataclass as this adapter's own request policy (10s timeout, 900KB page cap, 2s min interval) rather than inventing a second policy type.
- Every response's redirect chain (`response.history` + final URL) is checked host-by-host; a hop off the allowed host aborts the request rather than following it (`test_redirect_off_allowed_host_is_not_followed`).
- **`KNOWN_URLS`/`KNOWN_DOCUMENT_URLS` are explicit, pre-verified maps only** — `{"9A273AA": "<the Stage 11.3 URL>"}` and the matching PDF URL. There is no crawl/search/discover method on `DnsAdapter` at all (`test_no_crawl_or_search_method_exists_on_the_adapter`), and an unconfigured search code makes **zero** network calls (`test_unconfigured_search_code_makes_no_network_call`) — this is what "no mass collection" means in code, mirroring the exact existing pattern already used by `SulpakAdapter`/`MechtaAdapter` (a single hardcoded LG demo URL).
- HTTP 401 (Stage 11.3's own finding on the DNS product page) is recorded as `match_level="blocked"` with **exactly one** request attempt logged — never retried with different headers (`test_401_is_recorded_as_blocked_and_not_retried`).

## Document verification — full content, not filename, before acceptance

`document_verification.verify_document()` runs in this fixed order: (1) if the text identifies itself as a declaration of conformity / certificate, reject outright as `regulatory_excluded` — **even if the model and code both match** (`test_regulatory_document_rejected_even_when_model_and_code_match`, using a synthetic fixture that deliberately contains the correct model *and* code, to prove exclusion wins regardless); (2) otherwise require the expected model name *or* the exact manufacturer/seller code to appear in the document's own extracted text.

**The Stage 11.3 PDF is now a permanent negative fixture** (`tests/fixtures/stage11_4/hyperx_quadcast_original_manual_excerpt.txt`, a short factual excerpt — document number, part number, spec values — quoted from what was actually fetched and verified that stage): `Document No. 480HX-MICQC.A01`, part number `HX-MICQC-BK` — the **original** HyperX QuadCast, not "2 S". `test_old_quadcast_manual_is_rejected_for_quadcast_2s` asserts `verify_document()` rejects it as `model_mismatch` for `9A273AA` — regardless of DNS's own filename/label claiming otherwise. A synthetic positive fixture (clearly marked as fabricated, since no real confirmed QuadCast 2S manual text exists in this project yet) exercises the accepted path for comparison.

## Offline test coverage

`tests/test_dns_fallback.py` — **31 tests, all offline, no network**:

- **Source priority**: official wins outright; DNS fills only a field official never touched; a `needs_review` status, never a silent overwrite.
- **Conflict**: two differing dealer-tier values → `needs_review`, empty selected value.
- **Identity verification**: model+code together confirm; a similar-but-wrong model name without the exact code stays `unconfirmed`.
- **Provenance**: `source_type='dealer'`, URL, evidence, and identity level are all present and correctly derived; official sources classify as `'official'`.
- **Host-role enforcement + no mass crawl**: wrong-host URLs rejected pre-request; unconfigured codes make zero calls; no crawl/search method exists.
- **401 handling**: recorded as blocked, exactly one attempt.
- **Document verification**: the old-QuadCast negative fixture rejected; the synthetic positive fixture accepted with both `en`/`ru` detected; the regulatory-document fixture rejected even on an exact model/code match.
- **Worker integration**: a confirmed DNS-only result for a non-LG brand yields `needs_review` (never `done`); an unconfirmed one yields `error` (same outcome as before this stage, since virtually every catalog row still has no configured DNS URL); the LG/Sulpak/Mechta `adapter_factory` is proven **never called** for non-LG brands (Sulpak/Mechta stay LG-only); a rejected DNS document is never saved; an accepted one is saved carrying the `manufacturer_manual_dealer_hosted` type in its title.
- **Sulpak/Mechta unchanged**: allowlist and exclusion re-verified against the live `source_catalog.v2.json`; DNS confirmed absent from the production registry.

Full existing suite: **742 tests total, 10 failures** — all 10 are the *same* pre-existing "Stage 2–8 files byte-identical" check in `test_structural_census_v8_1.py` through `v9_1.py`, now correctly reporting that `product_tool/display.py`/`jobs.py`/`worker.py` differ from the Stage 8 baseline. This is the honest, expected, and only consequence of this stage's explicit mandate — those 10 old test files were **not** edited to hide it (an earlier attempt to add an exemption there was reverted, once it became clear those test files are themselves treated as protected artifacts by later stages' own checks). All 37 pre-existing LG/web/importer tests, and all 31 new DNS tests, pass. Full output: [`tests.txt`](tests.txt).

## Manual for 9A273AA — still open

No Technopark URL was supplied this message. Per instructions, the manual stays exactly as Stage 11.3 left it: a Quick Start Guide is physically confirmed included in the box; no online document or language is confirmed; the one DNS-linked PDF actually checked is the wrong model's manual and is now a permanent rejection fixture. If a Technopark link is supplied later, it will be checked as a separate document source under the same `verify_document()` rules — full content, exact model/code, never a filename/label alone.

## Artifacts

- [`report.md`](report.md) — this file
- [`protected_hashes_check.json`](protected_hashes_check.json) — confirms all 703 prior report files untouched, and names exactly the 3 intentionally-changed production files
- [`scripts/protected_hashes.py`](scripts/protected_hashes.py) — the integrity-check script
- [`tests.txt`](tests.txt) — full test suite output (742 tests, 10 explained failures)
- Code: `product_tool/adapters/dns.py`, `product_tool/adapters/document_verification.py`, `product_tool/source_types.py`, `product_tool/dealer_fallback.py`, and the diffs to `product_tool/{display,jobs,worker}.py`
- Tests: `tests/test_dns_fallback.py`, `tests/fixtures/stage11_4/*.txt`

## Not started automatically

No mass DNS collection — `DnsAdapter.KNOWN_URLS`/`KNOWN_DOCUMENT_URLS` still contain exactly the one `9A273AA` entry each. No network requests this stage. No promotion of dns-shop.ru into the production registry. No change to Sulpak's allowlist or Mechta's exclusion.
