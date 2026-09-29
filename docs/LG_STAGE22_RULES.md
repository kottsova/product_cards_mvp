# Stage 22: LG Russia documents, LG Russia photos, second pilot

Evidence and numbers: `reports/source_census_2026-09-24_stage22/report.md`.

## Documents route (LG Russia)
Product page (`/ru/<category>/lg-<model>`, found through the observed RU sitemap) -> the support page printed on it (`/ru/support/product/lg-<full code>`) -> its static list `.support-downloads li.manuals` -> a file on `gscs-b2c.lge.com`. The ajax widget of `/ru/support/manuals` is not used: its endpoint is read by script from a category picker that a product page does not print.

`adapters/lg_documents_adapter.py::LGRUDocumentAdapter.find_documents` -- at most 1 support page and 2 files per product; only printed hrefs on `lg.com` / `*.lge.com`; only guides whose printed type says "руководство" and whose printed label says Russian are requested (the label orders and limits requests, it never counts as evidence). The old label-based `LGRUAdapter.find_documents` is kept only for injected test adapters; the default adapters (`lg_policy.default_lg_adapters`) use the new class.

Three states, never merged: **candidate link** (printed href) -> **reachable file** (status 200, complete, starts with `%PDF-`; a ZIP package or a file over the 25 MB cap is reachable but not a PDF) -> **instruction confirmed by content** (`adapters/lg_documents.py::assess_document`): not a conformity declaration (a heading at the head plus hardly any instruction wording), at least two instruction words, and the text names the model (`exact`) or its family by a mask such as `F2J3WS**` (`family_mask`, at least 4 fixed characters that start the model). An instruction that names neither is reported (`instruction_model_not_named`) and not saved. The language is read from the extracted text only, chunk by chunk (~600 characters): a Russian *instruction* needs >= 2500 Russian letters and >= 2 instruction words, so a legal notice printed in ten languages is not one. A confirmed non-Russian instruction is saved with its real language (`Казахский`, ...) and readiness then shows `instruction_language_not_russian`.

The bytes of a PDF travel through the policy-aware session: `BinarySafeSession` marks document responses as latin-1, which is lossless, and `document_bytes()` restores the bytes (allowlist, redirect check, host stop, budget and log are unchanged).

## LG Russia photos
Gallery nodes `#desktop_summary_gallery` / `#mobile_summary_gallery`; a thumbnail is taken at the largest size its own node names (`data-large` > `data-zoom-image` > `data-medium` > `data-src` > `src`); accepted paths: `/ru/images/<category>/<md...>/[gallery/]<file>` (or the older `/stylers/`); the objet placeholder and everything else are dropped; duplicates (thumbnail and large, desktop and mobile) merge. A photo never raises a page's match level; `readiness` also reports `official_gallery_from_exact_pages`.

## Naming and comparison
`normalization.py`: one edge (width / height / depth alone) and "depth with the door" have their own names. `resolution.py`: the comparison key also reads `~` as `-` and MHz/kHz/GHz/Hz as their Cyrillic forms.

## Open decisions for the owner (not implemented)
1. The market tag `_KZ` / `_SU` at the end of an article (36 of 578 rows) is not part of the LG model; without a rule those rows are not found.
2. A base-model RU page whose own support link prints the row's full article (4 of 4 in the pilot): is that an exact-variant confirmation?
3. When both regions have an exact page and differ (5 of 11 such rows in the pilot): which region wins?
4. An instruction whose text names neither the model nor its family, tied to the product only by the official support page: sufficient or not?
