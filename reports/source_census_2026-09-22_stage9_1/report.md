# Stage 9.1 — DualSense Cosmic Red: separating product identity, variant identity, and catalog-row mapping

Baseline (immutable, read-only): [Stage 8](../source_census_2026-09-22_stage8/report.md) through [Stage 9](../source_census_2026-09-22_stage9/report.md). All Stage 2–8 files, every Stage 8.1–8.6 file, and every Stage 9 file were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json), which also confirms the catalog and production registry are unchanged. **No other products were searched this stage; Samsung was not investigated.**

**0 new network requests were made this stage** — see "Why no network check" below.

## Offline row analysis

Both catalog rows for `CFI-ZCT1J 02` and `CFI-ZCT1W_cosmic_red` were re-read field-by-field, together with the catalog's full schema: [`offline_row_analysis.json`](offline_row_analysis.json).

The catalog has exactly **8 columns** (Бренд, Категория, Артикул продавца, Артикулы WB, Наименование, Альтернативные наименования, ТНВЭД, Повторов в выгрузках) — **there is no dedicated manufacturer/region-code field**. "Артикул продавца" is seller-entered free text, not verified against any manufacturer registry by the catalog itself.

| Field | Row `CFI-ZCT1J 02` | Row `CFI-ZCT1W_cosmic_red` | Is this variant evidence? |
|---|---|---|---|
| Бренд / Категория | identical | identical | no |
| Наименование | "Геймпад DualSense для PS5 Cosmic Red" | "Беспроводной геймпад DualSense Cosmic Red" | no — same product+color, differs only in phrasing |
| Артикул продавца | `CFI-ZCT1J 02` | `CFI-ZCT1W_cosmic_red` | **unverified** — the only field that could plausibly indicate a real distinction, but per instruction this string difference alone cannot prove one |
| Артикулы WB | `366727052` | `1055973578; 1137034269` | no — expected for any two independent marketplace listings regardless of underlying product identity |
| ТНВЭД | null | `9504500009` | no — presence vs. absence, most simply explained as incomplete seller data entry, not a genuine classification conflict |
| Повторов в выгрузках | `1` | `2` | no — scrape/export bookkeeping |

**No rows were merged or deleted.**

## Why no network check was performed

Per instructions, a bounded network check is only warranted if offline data shows a substantial difference. It does not — every differing field except the seller article itself is marketplace-listing metadata, and the seller article alone is explicitly disallowed as standalone proof.

As a second check, every **already-known** official PlayStation route (from Stage 8.2/Stage 9, not invented) was reviewed offline: [`known_routes_review.json`](known_routes_review.json).

1. **Controllers category link index** (Stage 8.2, 90 links from `direct.playstation.com/en-us/accessories/controllers-and-remotes`): exactly **one** link matches both "DualSense" and "Cosmic Red" — there is no second, differently-coded official listing to compare against.
2. **The product page's own support links** (Stage 9): already checked — all generic e-commerce policy pages, none SKU-specific.
3. **The product page's own body/microdata** (Stage 9): already searched for any `CFI-` pattern — zero matches.

All three known routes are exhausted; none is capable of confirming or refuting a difference. [`budget_predeclaration.json`](budget_predeclaration.json) states the limits that would have applied had a check been triggered (max 3 requests, 1 host, `direct.playstation.com` only) — they were never invoked.

## Two separated questions

Full detail: [`identity_variant_vs_catalog_mapping.json`](identity_variant_vs_catalog_mapping.json).

### (1) Is the product variant confirmed by official features?

**Yes.** Brand (Sony/PlayStation), model name (DualSense® Wireless Controller), and color (Cosmic Red, via a structured `Color:` label) are all confirmed from the official page. This confirms that a real, first-party product with exactly this name and color exists — it does **not** confirm which manufacturer/regional code applies, since the page only exposes its own internal webstore `sku` (`1000050734`), never a `CFI-ZCT1x`-style code.

### (2) Can this confirmed variant be linked to the catalog rows?

**Linked to both, by descriptive consistency — not by code confirmation.** Both rows' own names describe the identical product+color as the confirmed variant, with no conflicting descriptor in either (no different color, edition, or bundle). Neither row's manufacturer code is confirmed present on the official page.

**Explicit caveat, stated directly in the artifact:** absence of evidence that the two seller articles denote different products is **not proof** that they denote the same one — it is the strongest conclusion the available evidence supports, stated as such. This is a correction to Stage 9's framing, which treated the code's absence on the page as disproof of linkage — that was not warranted; the absence only means the page doesn't *display* the code. **Stage 9's own artifacts are left byte-identical**; this is new reporting only.

| Seller article | Catalog name | Mapped official page | Manufacturer code confirmed? |
|---|---|---|---|
| `CFI-ZCT1J 02` | Геймпад DualSense для PS5 Cosmic Red | direct.playstation.com/.../dualsense-wireless-controller-cosmic-red... | No |
| `CFI-ZCT1W_cosmic_red` | Беспроводной геймпад DualSense Cosmic Red | direct.playstation.com/.../dualsense-wireless-controller-cosmic-red... | No |

## Export readiness (recomputed)

Explicit 5-point criterion, stated before judging: [`card.json`](card.json).

1. Brand/model confirmed by an official source. ✅
2. Every catalog row linked to the confirmed variant by stated evidence (descriptive consistency counts when no comparable official code exists). ✅ — **this criterion now passes**, reversing Stage 9's blocking finding, for the reasons above.
3. At least one official, matched image confirmed. ✅
4. Specifications sufficient for a customer-facing listing. ❌ — only qualitative marketing text (haptic feedback, adaptive triggers, USB-C/battery, Bluetooth); no numeric specs found. **Stated as its own, separate gap.**
5. Manual confirmed present (with language) or its absence explicitly noted. ✅ (explicitly noted as not found in checked sources — **stated as its own, separate gap**, not merged with the specs gap).

**Export readiness: still `not_ready`** — but now for a narrower, different reason than Stage 9: it fails criterion 4 (specifications) alone. The manufacturer/regional-code question remains an open, explicitly-stated residual item (not a blocking ambiguity, not a resolved certainty) — if a future official source contradicts the current linkage, this card should be revisited.

## Artifacts

- [`report.md`](report.md) — this file
- [`offline_row_analysis.json`](offline_row_analysis.json) — full catalog schema + field-by-field row comparison
- [`known_routes_review.json`](known_routes_review.json) — review of already-known official routes, why no network check was triggered
- [`identity_variant_vs_catalog_mapping.json`](identity_variant_vs_catalog_mapping.json) — the two separated questions
- [`card.json`](card.json) — recomputed card, explicit criterion, separated gaps
- [`checkpoint.json`](checkpoint.json) — budget declaration and 0-request log
- [`budget_predeclaration.json`](budget_predeclaration.json) — limits that would have applied if a check had been triggered
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–9 + catalog + registry integrity check
- [`raw/`](raw) — re-read catalog rows and header, saved offline
- [`scripts/`](scripts) — the 5 offline analysis scripts used, for reproducibility
- [`tests.txt`](tests.txt) — full test suite output

## Tests

New regression tests: `tests/test_structural_census_v9_1.py` — checks the Stage 2–9 protection guarantee, that both catalog rows are preserved with full fields, that the seller-article difference is marked `unverified` (never treated as proof), that marketplace-metadata fields (WB numbers, TNVED, repeat count) are never treated as variant evidence, that both questions (variant confirmation vs. row mapping) are answered separately, that criterion 2 now passes while criterion 4 still fails, and that the specs gap and manual gap remain two distinct entries rather than one merged item.

## Not started automatically

No further PlayStation items, Samsung work, or broader search was opened beyond this disambiguation.
