# Stage 10.1 — bounded verification of www.xbox.com / support.xbox.com and targeted confirmation of XXU-00015

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 10](../source_census_2026-09-23_stage10/report.md). All 535 prior files (Stage 2–10 + catalog + 7 registry files) were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No general Xbox census was run; only the two hosts named by the user and the single catalog row `XXU-00015` were touched.**

## 1. Offline provenance, fixed before any request

[`offline_provenance.json`](offline_provenance.json): the exact source links, and the redirect chain of the page they came from, are read straight from Stage 10's own `bounded_probe_result.json` (request #3: `support.microsoft.com/en-us/all-products` → 200 → `support.microsoft.com/en-us/all-products-list`). Of the 7 off-host links Stage 10 recorded, 5 belong to the two hosts named this stage (`www.xbox.com`, `support.xbox.com`); the 2 `www.microsoft.com/...` links are explicitly out of scope and untouched. Per-host reasoning for *why each host is plausibly official* (before any content check) is recorded separately for each host in the same file — link-provenance only, not yet content-verified.

## 2. Research-only source profile

[`research_source_profile.json`](research_source_profile.json): a two-domain profile modeled on `official_domains.v1.json`'s own schema, `enabled=false` / `research_enabled=false` for both entries until this stage's own probe could verify a real connection to official content. **This file is not merged into `product_tool/config/official_domains.v1.json`** — confirmed unchanged in the integrity check.

## 3. Budget, declared before the first HTTP request

[`budget_predeclaration.json`](budget_predeclaration.json): `allowed_hosts=("www.xbox.com","support.xbox.com")`, 16 requests total / 10 per host, robots.txt fetched first on each host and its `Disallow` rules honored for every later request, 403/429/challenge stops that host only, off-host links/redirects recorded but never followed. A second, explicit **budget revision** ([`budget_revision_1_document_fetch.json`](budget_revision_1_document_fetch.json)) was declared, again before any request under the new values, once the official sitemap turned out to be gzip-compressed binary content that the original HTML-sized cap (750,000 bytes) could not safely hold or decode — this reused the same Range-based, byte-exact assembly mechanism proven in Stage 8.6, adapted to this stage's own hosts/budget.

## 4. Host and role confirmation

Full detail: [`card.json`](card.json) → `host_confirmations`.

| Host | robots.txt | Role confirmed this stage | Evidence |
|---|---|---|---|
| `www.xbox.com` | 200, 9 `Disallow` rules (none blocking browsing/console paths) | **Product page (commercial storefront) — confirmed** | Content includes Microsoft's shared "UHF" corporate footer component (`Microsoft corporate links` nav → `microsoft.com/trademarks`), and a sitemap-listed URL is a real PDP-style console page with purchase options, pricing CTAs and full tech specs |
| `support.xbox.com` | 200, 0 `Disallow` rules | **Support — structure confirmed, content not verified** | robots.txt + a 2,973-URL en-US sitemap describe a help-article structure consistent with an official support portal; individual article pages could not be read (see below) |

Neither host was promoted into `official_domains.v1.json` or `source_catalog.v2.json` — that stays a separate, explicit, out-of-band decision.

## 5. Official evidence for the exact model and variant

Full detail: [`card.json`](card.json) → `variant_evidence`. The console landing page was found via `www.xbox.com`'s own declared `robots.txt` → `sitemap.xml` (a 930-entry sitemap index) → `cms-sitemap-0.xml.gz` (a CMS content-page chunk, fetched complete and byte-verified via Range requests) → `https://www.xbox.com/en-US/consoles/xbox-series-s` — **every hop from an already-declared, official location, nothing guessed.**

That page (HTTP 200, 633KB, not truncated) offers **exactly three** named purchase options:

- `512GB All-Digital Robot White`
- **`1TB All-Digital Carbon Black`** ← matches the catalog row
- `1TB All-Digital Robot White`

and an explicit spec line pairing color and capacity together: *"XBOX Series S Robot White: 512GB Custom NVME SSD / **XBOX Series S Carbon Black: 1TB Custom NVME SSD** / XBOX Series S Robot White: 1TB Custom NVME SSD"*. Model, capacity, and color are confirmed **together, in one named option** — not inferred by combining separate mentions — and the page's own text distinguishes this option from both the 512GB white and the 1TB white variants explicitly, so nothing is merged. The page never exposes a manufacturer/region SKU code; per instructions, the catalog's seller article (`XXU-00015`) is not expected to appear there and its absence is not itself evidence of anything. Catalog↔official linkage is therefore **by model + capacity + color descriptive consistency** (no conflicting field), stated as the strongest available evidence, not a code-level proof — the same standard Stage 9.1 established for the PlayStation controller.

## 6. What can be exported with evidence

Full list with per-field evidence: [`card.json`](card.json) → `exportable_fields_with_evidence`. In addition to brand/model/variant: full **technical specifications** (CPU, GPU, memory, storage — the 1TB figure explicitly tied to Carbon Black —, expandable-storage support, video output up to 1440p/120FPS with HDMI 2.1 ALLM/VRR/FreeSync, audio formats, ports, Wi-Fi, dimensions, weight), and **3 product images** whose filenames explicitly say `Carbon-Aware` (of 75 total image/video assets on the page; the other 72 depict the console generically and are not claimed as color-specific evidence).

## 7. What blocks full readiness

The instruction manual could not be confirmed present **or** absent. `support.xbox.com`'s own sitemap named two real, live, on-topic articles — `help/hardware-network/console/unbox-xbox-series-xs-console` and `help/hardware-network/getting-started-set-up/set-up-new-series-x-s` (both HTTP 200) — but every page fetched from this host, including these two, is a bare client-rendered SPA shell (`<noscript>You need to enable JavaScript to run this app.</noscript>`, ~2.9KB). Rendering it would require Chromium, which is explicitly out of scope for this stage. This is recorded as a **structural access blocker**, not a confirmed absence and not an unsearched gap — the candidate URLs are known for a future, differently-authorized attempt.

**Export readiness: still `not_ready`, but narrowly** — criteria 1–4 of the 5-point criterion now pass (a substantial change from Stage 10, which failed at criterion 1); only criterion 5 (manual) remains open, and for a stated structural reason.

## Request log and budget verification

[`checkpoint.json`](checkpoint.json): **15 requests total**, 8 to `www.xbox.com`, 7 to `support.xbox.com`, 0 rejections, 0 protection stops, well inside both declared budgets. One redundant, honestly-disclosed ad hoc re-fetch of an already-permitted `robots.txt` URL (made once during interactive investigation before the logging script existed) is included in the log rather than hidden. `cms-assets.xboxservices.com` (the image CDN referenced by URL on the confirmed page) and `www.microsoft.com/store` were never contacted — recorded as out-of-scope, not fetched.

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_provenance.json`](offline_provenance.json) — exact source links, redirect chain, per-host reasoning
- [`research_source_profile.json`](research_source_profile.json) — research-only, non-production source profile
- [`budget_predeclaration.json`](budget_predeclaration.json), [`budget_revision_1_document_fetch.json`](budget_revision_1_document_fetch.json) — budgets, declared before use
- `phase1`–`phase7` `*.json` — every discovery/fetch step, in order, with its own request log
- [`card.json`](card.json) — host/role confirmation, variant evidence, exportable fields, blockers
- [`checkpoint.json`](checkpoint.json) — aggregate request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–10 + catalog + registry integrity check
- [`raw/`](raw) — every fetched page/sitemap saved offline (root pages, both sitemaps, the CMS chunk, the console landing page, the two support-article shells)
- [`scripts/`](scripts) — all 13 scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v10_1.py` — checks that only the two named hosts are in scope and Microsoft-store links are excluded, that the research source profile is unpromoted (`enabled=false`, not present in `official_domains.v1.json`), that both budgets were declared before use and every request stayed on an allowed host with no protection stops, that `www.xbox.com` is confirmed as a product-role host while `support.xbox.com`'s content-access blocker is recorded, that the Carbon 1TB variant is found without being confused with the other two SKUs, that the manual gap is phrased as a JS-access blocker rather than a false "confirmed absent," that 4 of 5 readiness criteria pass, and that every prior stage's files plus the catalog and registry remain byte-identical.

## Not started automatically

No general Xbox census. No other catalog row. No promotion of either host into `official_domains.v1.json` or `source_catalog.v2.json`. No Chromium session was started to read `support.xbox.com`'s article content — that remains a separate, explicit decision for the user to authorize if wanted.
