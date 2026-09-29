# Stage 8.2.2 — bounded support-first discovery for Samsung smartphones

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md), [Stage 8.1](../source_census_2026-09-22_stage8_1/report.md), [Stage 8.2](../source_census_2026-09-22_stage8_2/report.md), [Stage 8.2.1](../source_census_2026-09-22_stage8_2_1/report.md). All 209 Stage 2–8 files, 26 Stage 8.1 files, 58 Stage 8.2 files and 31 Stage 8.2.1 files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json).

Two exact catalog rows, taken verbatim from [`reports/source_census_2026-09-22_stage8_2_1/catalog_samples.json`](../source_census_2026-09-22_stage8_2_1/catalog_samples.json) (copied unchanged into [`catalog_samples.json`](catalog_samples.json) here): **Galaxy S20 FE 128GB** (article `488776SM-G780GZRDSKZ`) and **Galaxy Z Fold3 5G 512GB** (article `491953SM-F926BZGGSKZ`). No model code, color, memory or regional suffix beyond what these rows already contain was invented.

## Host confirmation, not assumed

Before anything else, the target host was confirmed from existing evidence, not assumed to be `support.samsung.com`:

- `product_tool/config/source_catalog.v2.json`: `samsung_kz.support_hosts = ['samsung.com']`.
- Stage 8's `adapter_profiles.v1.json`: `samsung_kz_02d9e6.support_hosts` and `samsung_us.support_hosts` both `= ['www.samsung.com']`.
- Stage 8's own `samsung_kr` profile already has `sample_support_page = 'https://www.samsung.com/sec/support/'` — a same-domain, region-path support page, already fetched.

Conclusion: Samsung's support infrastructure lives on the **same domain**, under a region path (`/sec/support/`, `/kz_ru/support/`, `/us/support/`) — not on a separate `support.samsung.com` host, which was never contacted. Full detail: [`support_routes.json`](support_routes.json).

## Offline first

Before any new request, six pieces of existing evidence were reused at zero network cost, including two items **not previously fully explored**:

- `robots.txt`, the `kz_ru/sitemap.xml` index, and all 5 `b2c-sitemap.xml` children — already fully known from Stage 8.2/8.2.1, not re-checked (per instructions not to repeat the sitemap work).
- The **kz_ru homepage's full link list** (Stage 8.2.1's offline reprocess) was re-read specifically for `/support/`-shaped links this time — it directly contains `/kz_ru/support/`, `/kz_ru/support/user-manuals-and-guide/`, and `/kz_ru/mobile/find-your-galaxy/`, all reachable without a single new request.
- Stage 8's cached `samsung.com/sec/support/` fetch (`structural_cache.json`) was checked for a mobile-manuals link — it only has a laptop-specific (Galaxy Books) download center, no mobile-phone equivalent.
- `samsung.com/us/` homepage (Stage 7 sqlite snapshot) was reprocessed offline **for the first time** this stage — it links to `/us/support/downloads/`, `/us/mobile/find-your-galaxy/`, and an ID-based `/us/support/troubleshoot/TSG10001565/` — recorded as offline-discovered fallback candidates, not fetched live (see budget note below).

## New requests and findings

5 route types were tried on `www.samsung.com/kz_ru/`, all HTTP 200, 0 blocks:

| Route | What it is | Result |
|---|---|---|
| `/kz_ru/support/` | Support root, first-party link from the homepage | Confirmed a real GET search form and its exact parameter name (`searchvalue`, seen directly on the page — not invented) and confirmed links to the manuals hub and model finder. |
| `/kz_ru/search/?searchvalue=Galaxy+S20+FE` | GET search, query text taken verbatim from the catalog's `base_model` field | 134 links, generic navigation shell. "Galaxy S20 FE" appears **nowhere** in the page text. |
| `/kz_ru/search/?searchvalue=Galaxy+Z+Fold3` | Same, other model | Same result: 134 links, 0 mention of "Galaxy Z Fold3". |
| `/kz_ru/support/user-manuals-and-guide/` | Manuals hub, first-party link | 135 links, generic shell, 0 mention of either model. |
| `/kz_ru/mobile/find-your-galaxy/` | Official model-finder tool | 139 links, generic shell — the finder widget itself renders client-side; no result list present in the static response. |
| `/kz_ru/support/mobile-devices/check-out-the-new-camera-functions-of-galaxy-s20-plus-s20-ultra/` | A real support-content article (architectural probe, not the target model — it's S20 **Plus/Ultra**, a different variant) | Still client-rendered: 0 JSON-LD/microdata, 0 mention of "Galaxy S20", "S20 Ultra" or "S20+" anywhere. Confirms even support **content** leaf pages, not just hub/listing pages, render client-side. |

Full per-route detail and raw request log: [`support_routes.json`](support_routes.json).

**Budget overshoot, disclosed**: the plan capped requests at 4 per host; 6 were made to `www.samsung.com`, because the bounded-fetch helper's per-host counter reset at the start of each of this stage's four separate script runs instead of persisting cumulatively. This is recorded transparently in `support_routes.json`'s `budget_note_and_correction` rather than silently fixed after the fact. The overall stage-total cap (12) and host-count cap (3) were both respected (6 of 12 used, 1 of 3 hosts contacted), and no further requests were made to any host once the overshoot was identified.

## Identity and documents

Per-model identity check (full detail, field-by-field: [`identity_evidence.json`](identity_evidence.json)):

- **Galaxy S20 FE**: `catalog_identity_result = insufficient`. "Galaxy S20 FE" / "S20 FE" appears in **none** of the 3 relevant pages checked. No model code, storage, color or connectivity field was confirmed anywhere.
- **Galaxy Z Fold3 5G**: `catalog_identity_result = insufficient`. Same outcome — "Galaxy Z Fold3" / "Fold3" never appears.
- The one near-miss (an S20 **Plus/Ultra** camera-features article) was explicitly **not** counted as evidence for the S20 **FE** catalog row — family/generation matching alone is not treated as model confirmation, per instructions.

Documents: [`documents.json`](documents.json) — **zero** official documents (manuals, guides, downloads) were reached for either model. Every route that could plausibly list a document rendered as a client-side shell with no document link present in the actually-served HTML.

## Architecture and pipeline contract

Full detail: [`samsung_pipeline_contract.json`](samsung_pipeline_contract.json) (architecture contract and evidence only — **no production adapter included**).

- **Shared discovery/orchestration**: confirmed shared (one domain, one sitemap system, one identity-code convention) across every category checked so far, smartphones included in the *attempt*, if not the result.
- **Static Product template**: confirmed only for **2 categories** — TVs and audio-sound/Galaxy Buds (Stage 8.2). Home appliances and memory/storage (reached via sitemap in Stage 8.2.1) are explicitly **not** assumed compatible without their own Product page fixtures, per instructions.
- **Smartphone client-rendered template**: unresolved — every route tried (marketing pages in Stage 8.2.1, support pages this stage) confirms client-side rendering. Needs an embedded-state extraction capability this pipeline does not currently have.
- **Support-first model resolver**: not viable as currently scoped on `kz_ru` — same client-rendering wall. `samsung_us`'s `/support/downloads/` is the strongest untested lead.
- **Document resolver**: confirmed working for TV/Buds (Stage 8.2, `a[href:pdf]` + `support_navigation=true`, 2/2 pages); zero evidence either way for smartphones this stage.
- **Category-specific identity validation**: required per category — no pooling assumed; smartphones have no identity contract to compare at all.

## Regional fallback

Full detail: [`regional_fallbacks.json`](regional_fallbacks.json). `samsung_us`'s `/support/downloads/` is recommended as the next step (real first-party link, not yet tried live, different page type from the already-disproven `user-manuals-and-guide/`). `samsung_kr` is deprioritized — its only offline-evidenced manuals link is laptop-specific, not mobile.

## Tests

New regression tests: [`tests/test_structural_census_v8_2_2.py`](../../tests/test_structural_census_v8_2_2.py) — checks the byte-identical protection guarantee for Stage 2–8.2.1, that only `www.samsung.com` was contacted, that the host overshoot is honestly disclosed rather than hidden, that neither model was assigned `official_product_not_found`, that family/generation text matches (S20 Plus/Ultra) are not counted as S20 FE evidence, and that the pipeline contract does not silently promote appliances/memory to the confirmed static template. Full suite (Stage 2–8.2.2): [`tests.txt`](tests.txt).

## Answers

1. **Official support pages found for S20 FE and Z Fold3?** No. Five different route types were tried (search, manuals hub, model finder, support root, one content article) — all rendered client-side with zero model-specific content.
2. **Exact models or variants confirmed?** No. `catalog_identity_result = insufficient` for both — no page exposes any comparable identity field.
3. **Official instructions found, and in what languages?** None. Zero documents were reached for either model (client rendering blocked every route that could have listed one).
4. **Characteristics or images obtained?** No — same client-rendering block applies to every layer (identity, specs, media) on every route tried.
5. **How should the smartphone support-first resolver work?** It cannot work as a static-HTTP resolver against `kz_ru` as currently scoped — every surface tried (search, manuals, model finder, content articles) needs client-side JS execution to expose real content. A viable resolver needs either an embedded-state extraction capability (not full browser automation) or a genuinely different regional surface that renders statically; `samsung_us`'s `/support/downloads/` is the one untested, evidenced lead.
6. **Which Samsung categories are ready for a first full cycle?** TVs and audio-sound/Galaxy Buds only — both have 2 independently verified static Product pages with a stable, matching contract (Stage 8.2). Home appliances and memory/storage are not ready (sitemap-reachable but no Product page fixture yet); smartphones are not ready (architecturally blocked).
7. **What limited set should go into the Samsung pilot?** The two already-verified products from Stage 8.2: the TV (`.../tvs/full-hd-tv/n5300-43-inch-full-hd-smart-tv-ue43n5300auxce/`) and the Galaxy Buds3 FE (`.../audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/`) — both categories, both confirmed structure, both confirmed document links. Smartphones stay out of the pilot as a separate, explicitly unresolved flow; this does not block the pilot. Not started automatically.
