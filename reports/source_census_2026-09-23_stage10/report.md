# Stage 10 — Xbox/Microsoft: one catalog-first full cycle

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 9.1](../source_census_2026-09-22_stage9_1/report.md). All 518 prior stage-directory files, the catalog, and 7 registry/config files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No Samsung or PlayStation work was opened this stage.**

## 1. Offline catalog check: which brand labels carry "Xbox"

Full detail: [`offline_row_analysis.json`](offline_row_analysis.json). The catalog's `Товары` sheet has exactly 8 columns, no dedicated manufacturer/region-code field — same schema already established in Stage 9.1.

Scanning all rows offline for `xbox`/`microsoft` (case-insensitive, in any column) found **48 rows under two different brand labels**:

| Brand label (catalog `Бренд` column) | Rows | What they are |
|---|---:|---|
| **Microsoft** | 45 | First-party Xbox consoles, gamepads, headsets, accessories, plus one unrelated Microsoft mouse |
| **Asus** | 3 | "ROG Xbox Ally" / "ROG Xbox Ally X" — Asus-branded Windows handhelds that carry "Xbox" in the *name* only |

Per instruction, brand is taken from the catalog's own `Бренд` column, never inferred from the word "Xbox" inside `Наименование`. **The 3 Asus rows are not merged into Microsoft and are out of scope this stage** — Asus was not investigated further, exactly as instructed.

## 2. Selected row

Row 9661, seller article **`XXU-00015`**, brand `Microsoft`, category `Игровые консоли`:

| Field | Value |
|---|---|
| Бренд | Microsoft |
| Категория | Игровые консоли |
| Артикул продавца | XXU-00015 |
| Артикулы WB | 366726945 |
| Наименование | Игровая консоль Xbox Series S Carbon 1TB |
| Альтернативные наименования | — |
| ТНВЭД | — |
| Повторов в выгрузках | 1 |

**Why this row:** its `Наименование` carries three independent, checkable model/variant descriptors in one string — product line (Xbox Series S, current generation, as opposed to the older Xbox One family also present under this brand), storage capacity (1TB, itself a variant marker since row 9658/`RRS-00011` is the same line at the base 512GB capacity), and color/finish (Carbon). A current, still-supported line was preferred over the discontinued Xbox One family to maximize the chance of a live official page. Full reasoning and every one of the 45 candidate rows: [`offline_row_analysis.json`](offline_row_analysis.json).

## 3. Known official sources and routes, checked before any request

Full detail: [`known_routes_review.json`](known_routes_review.json). Checked registries: `official_domains.v1.json` (17 domains, production-adjacent research registry with page/support/document host roles), `source_catalog.v2.json` (executable production registry), `source_candidates.v1.json`, `source_research.v1.json`.

**Finding:** neither `official_domains.v1.json` nor the production `source_catalog.v2.json` has any Microsoft/Xbox entry. The only confirmed official route on file anywhere is `support.microsoft.com`, recorded in `source_research.v1.json` with `official_status="official_verified"` but **`source_role="support"`** (it is the sole host under both `page_hosts` and `support_hosts`; `asset_document_hosts` is empty), and `checkpoint.status="pending"` — it had never actually been probed. There is no host on file anywhere with a manufacturer/retailer role for this brand family — nothing confirmed to carry commercial product-page content. Its three already-declared `probe_targets` (none invented this stage): the all-products support page, `robots.txt`, `sitemap.xml`.

This means: unlike PlayStation (Stage 8/9, `direct.playstation.com`) or Samsung (Stage 8.1–8.6, `downloadcenter.samsung.com`), **this project has no verified commercial product-page domain for Microsoft/Xbox yet** — only a support portal.

## 4. Budget, declared before any request

[`budget_predeclaration.json`](budget_predeclaration.json): `allowed_hosts=("support.microsoft.com",)` only, max 6 requests total / 6 per host / 1 host, the 3 already-known URLs above plus up to 3 same-host candidate links discovered on the support page, 512 KB/request cap, 2s interval, 10s timeout. Stop conditions: budget exhausted, any 403/429/challenge, an off-host redirect or link (recorded, not followed), or no same-host candidates left.

## 5. What the bounded probe found

Full log: [`bounded_probe_result.json`](bounded_probe_result.json), [`checkpoint.json`](checkpoint.json). **3 requests made, all to `support.microsoft.com`, 0 rejections:**

| # | URL | Status | Result |
|---|---|---:|---|
| 1 | `/robots.txt` | 200 | ordinary page, 1,080 bytes |
| 2 | `/sitemap.xml` | 404 | does not exist at this path |
| 3 | `/en-us/all-products` | 200 (redirected same-host to `/en-us/all-products-list`) | 108,197 bytes read, **not truncated** — the full page |

The all-products page is Microsoft's own official global-navigation hub. It labels "Xbox" as its own product line and links to it — but every one of those links (`support.xbox.com`, `www.xbox.com`, `www.microsoft.com/en-us/store/b/xbox`) is **off the pre-declared allowlist**. They were recorded as discovered leads and **not followed** — this is the AccessProbe host-allowlist behavior working as designed, not a missed opportunity. The fetched page text contains **zero** occurrences of "Series S" or "Carbon" — no product/variant content at all, only navigation.

## 6. Identity statuses (separated)

Full detail: [`card.json`](card.json).

| Question | Status |
|---|---|
| Is Microsoft a real corporate entity with Xbox as a self-declared first-party line? | **Confirmed officially** — `support.microsoft.com` itself links to Xbox as its own product family |
| Is the specific model "Xbox Series S" confirmed by any fetched official content? | **Not confirmed** — zero mentions in the one page reached |
| Is the variant (1TB, Carbon) confirmed? | **Not confirmed** |
| Can the catalog row be linked to a confirmed variant? | **Not applicable yet** — no confirmed variant exists to link it to (this question is downstream of variant confirmation, per the Stage 9.1 methodology) |
| Specifications | **Not found** — no product page reached |
| Images | **Not found** — no product page reached, no image step attempted |
| Instruction manual | **Not searched** — the Stage 8.6 bounded-document mechanism (`fetch_document_bounded`) was never invoked because no candidate PDF URL was discovered within the allowed host/budget |

## 7. What is already exportable with evidence

Only the brand-level fact, and only with an explicit caveat: **`Бренд = Microsoft`** is cross-checked against the officially-confirmed corporate entity at `support.microsoft.com` (HTTP 200, fetched this stage) — this confirms Microsoft exists and operates Xbox as a product line, but **does not by itself confirm this specific catalog row is a genuine Microsoft product** (that link is catalog-only). `Категория`, `Наименование`, and `Артикул продавца` remain catalog-only, unverified text — per project rule, absence of conflict is never treated as proof of a match. No numeric or descriptive field, image, or manual reached official-evidence status this stage. Absence of confirmed specs does not hide the one field that is genuinely confirmable (the brand) — both are stated separately in [`card.json`](card.json), not merged.

## 8. Is the card ready? Explicit 5-point criterion

All 5 fail, and — unlike prior products — the failure starts at criterion 1, earlier than any product processed so far (Samsung's microwave reached `ready_with_minor_gaps`; PlayStation's DualSense reached `not_ready` only on the specs criterion):

1. Brand/model confirmed by an official source — ❌ (brand only, not model)
2. Catalog row linked to a confirmed variant — ❌ (no confirmed variant to link to)
3. Official matched image — ❌
4. Sufficient specifications — ❌
5. Manual confirmed present or absence explicitly noted — ❌ (neither could be checked)

**Export readiness: `not_ready`.** The blocker is structural, not this-product-specific: `official_domains.v1.json` has no verified product-page host for Microsoft/Xbox, only a support-role host that carries no product-specific content.

## 9. Gaps and a path forward (not acted on this stage)

`support.xbox.com`, `www.xbox.com`, and `www.microsoft.com/en-us/store/b/xbox` were discovered as literal, non-guessed hrefs on an official Microsoft page, but have no `ownership_evidence` recorded in `official_domains.v1.json` and are off this stage's allowlist — so they were recorded, not requested. A future stage could add them to `official_domains.v1.json` through the same evidence-gathering process already used for the 17 existing entries (e.g. LG), then re-run a bounded discovery from there. This stage stops here and does not do that itself.

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_row_analysis.json`](offline_row_analysis.json) — full catalog scan, brand separation, row selection and reasoning
- [`known_routes_review.json`](known_routes_review.json) — registry check for existing official Microsoft/Xbox sources
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget/hosts/stop-conditions, declared before any request
- [`bounded_probe_result.json`](bounded_probe_result.json) — the 3 executed requests and their evidence
- [`checkpoint.json`](checkpoint.json) — budget + full request log in one place
- [`card.json`](card.json) — identity statuses, exportable fields, 5-point criterion, gaps
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–9.1 + catalog + registry integrity check
- [`raw/support_all_products.html.txt`](raw/support_all_products.html.txt) — the one bounded page fetched, saved offline
- [`scripts/`](scripts) — all 7 scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v10.py` — checks the catalog schema, that the 3 Asus ROG Xbox Ally rows are counted separately from the 45 Microsoft rows and never merged, that the selected row and its capacity/color reasoning are recorded, that no product-page domain is registered for Microsoft/Xbox, that all 3 executed requests stayed on the single allowlisted host and within budget, that discovered off-host Xbox links were recorded but not fetched, that the card's five criteria all fail with reasons, that the manual gap is stated as "not searched" rather than a false "confirmed absent", and that every prior stage directory plus the catalog and registry files remain byte-identical.

## Not started automatically

No Samsung or PlayStation work was opened. No new domain was added to `official_domains.v1.json`. No further Microsoft/Xbox row beyond the one selected was pursued this stage.
