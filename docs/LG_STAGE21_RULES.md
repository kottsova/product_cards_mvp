# Stage 21: readiness, quantity names, base-model search, LG Russia route

Evidence and numbers: `reports/source_census_2026-09-24_stage21/report.md`.

## D2 — job status and card readiness are separate
- A job is `done` when an official LG page (KZ or RU) shows the FULL article and there are no real conflicts. A dealer confirmation is not required. An official page found only by base model still needs a dealer's full article, as before.
- `product_tool/readiness.py` (`card_readiness`) is a separate verdict and is written into every job's last message: `export_ready`, `export_ready_with_gaps`, `not_ready`.
  Blocking gaps: `no_official_full_sku_page`, `no_official_specifications`, `no_official_gallery_photo`, `unresolved_conflicts`, `instruction_missing`, `instruction_language_not_russian`. Advisory: `dealer_cross_check_missing`.
- A `done` row can therefore be `not_ready` (for example an exact page with no gallery photo). Nothing is hidden behind `done`.

## D3 — different quantities keep different names
- `normalization.py`: `NAME_RULES` are anchored to the start of a name; a qualifier suffix is added for with/without stand, gross/net, indoor/outdoor unit, cavity, turntable, speaker parts, wall mount, washing/drying, and for the colour of a part (`color__door`, `color__body`, …). A row whose name is unmapped but whose value is a size or a weight gets `__dimensions` / `__weight`. Dash-only values are dropped.
- Two different values of the SAME quantity still conflict (in one source or between regions); the tests include a real conflict.
- `resolution.py` compares a canonical key (spacing, thousands separators, `шт.`, `×`/`х`, a unit mark after a number, `(r/l)`/`(п/л)`, `меньше`/`менее` are formatting). Display and storage keep the normalized value. A different colour, size, depth or wording of a fact is not forgiven.
- Left on review on purpose: a count against presence (`1` against `true`).

## D4 — base-model search
`lg_base_model` drops a regional suffix of 3+ capital letters (`24MR400-B.ARUQ` → `24MR400-B`). A base-code hit is `base_model`; it becomes `full_sku` only when the page prints the full article. A suffix that distinguishes variants is not stripped by this rule.

## LG Russia route
- Pages: `lg.com/sitemap.xml` → `ru/index.xml` → `ru/sitemap.xml` (product urlset). `LGRUAdapter` reads that sitemap through the policy session (shared per log and URL) and matches slug keys; it never builds a product URL. A miss is `mismatch` with no error.
- Documents: not established. `/ru/support/manuals` loads its list by script. Exact remainder: one request for `/lg5-common-gp/js/common-support.min.js`, then one request per product to the ajax `manual-select-category-result`. `find_documents` for LG Russia is unchanged.
- Known gap: RU gallery photos are not extracted (the filter wants `/stylers/`; the saved pages use `/ru/images/<category>/<md…>/gallery/`).
