# Stage 11.3 — DNS manual check for 9A273AA, and a formalized dealer-fallback rule

Baseline (immutable, read-only): [Stage 2](../source_census_2026-09-22_stage2/report.md) through [Stage 11.2](../source_census_2026-09-23_stage11_2/report.md). All 683 prior files were rehashed after this stage and are byte-identical: [`protected_hashes_check.json`](protected_hashes_check.json). **No Sulpak, Mechta, Kingston, HIPER, or other brand/dealer host was contacted; no other catalog row was touched.**

This stage replaces Stage 11.2's "leave the manual field open" decision with the user's new instruction to check a specific DNS page and PDF.

## 1. Budget, declared before any request

[`budget_predeclaration.json`](budget_predeclaration.json): hosts `www.dns-shop.ru` and `drv.dns-shop.ru` (both exact URLs supplied by the user, neither guessed), max 8 requests / 6 per host, robots.txt first on each host, an explicit identity-verification requirement (model name **and** manufacturer code must both appear in fetched content before anything is treated as evidence — a similar title is not enough), and an explicit note that declarations of conformity / certificates are not searched for or considered.

## 2. DNS product page — blocked

`https://www.dns-shop.ru/product/driver/e949b555b392d582/mikrofonnyj-komplekt-hyperx-quadcast-2-s-cernyj/` returned **HTTP 401**. No workaround (header spoofing, browser automation) was attempted, per policy — this is recorded as an access limitation, not retried. Because the page never loaded, identity linkage could not be checked from the page itself.

## 3. The PDF — fetched completely, verified by content, and REJECTED as a mismatch

`https://drv.dns-shop.ru/drivers/Manuals/H/hyperx-quadcast-2-s_instrukcia_104913_30102025.pdf` was fetched with Stage 8.6's bounded, Range-aware mechanism: **4 requests, 4,978,169 bytes, `complete`** (assembled size matches the declared total exactly).

Content verification (`pypdf`, 241 pages) found:

- A single, consistent header throughout all 241 pages: **"Document No. 480HX-MICQC.A01"**, part number **"HX-MICQC-BK"** — this is the manufacturer's own document-numbering convention for the **original HyperX QuadCast** microphone, not "QuadCast 2 S."
- **Zero** occurrences of "QuadCast 2 S," "2S," or "9A273AA" anywhere in the document.
- The document's own specification page lists **48kHz/16-bit sampling, -36dB sensitivity, 710g total weight** — the official 9A273AA page (Stage 11) states **32-bit/192kHz, '-8 dBFS±4dB sensitivity, 1.84 lb (≈834g) total weight**. These are two different products by their own official spec sheets, not a units/rounding discrepancy.
- It is a genuine **manufacturer document** (HyperX's own numbering, ~15-language installation-guide compilation) — but for the wrong model.

**Verdict: content-verified mismatch.** DNS's filename claims this is the QuadCast 2S instruction, but the document's own content says otherwise. Per instructions, a similar-sounding filename is not accepted as identity confirmation — **this PDF is rejected as evidence for catalog row `9A273AA`.**

## 4. Manual status for 9A273AA — unchanged in substance, one more source checked and rejected

Still **not confirmed online, not declared absent**. The Quick Start Guide remains confirmed only as a physical box-content item (Stage 11). This stage's DNS lead was investigated and correctly rejected on content grounds — this demonstrates the fallback rule's discipline (reject mismatches, don't paper over them), not a failure of the process.

## 5. The DNS dealer-fallback rule — formalized, tested once

Per the user's explicit authorization, recorded in [`card.json`](card.json) → `dns_dealer_fallback_rule`:

> dns-shop.ru (`www.dns-shop.ru` product pages; `drv.dns-shop.ru` manuals/drivers) may be used as a **fallback** source for any catalog row when official characteristics, photos, or instructions are insufficient. **The official source always has priority.** Every DNS-sourced field must carry its own URL, its own provenance, and its own exact model+variant verification — a dealer card is never imported wholesale, and identity is never confirmed by a similar title alone. On conflict with an official value, the field goes to **human review**; the official value is kept, never silently overwritten.

**Tested this stage on `9A273AA` only** — no other catalog row, no DNS crawl beyond the two user-provided URLs. The test outcome demonstrates the rule working exactly as intended: the PDF was checked on its actual content, not accepted on filename similarity, and correctly rejected.

**Sulpak and Mechta are unchanged.** Sulpak stays scoped to its exact existing LG household-appliance allowlist (washers/dryers, refrigerators, vacuums, microwaves) — no network activity this stage. Mechta remains excluded (`official_status=not_allowed`, `enabled=false`).

**Production registry status:** this rule is recorded as a research/policy artifact in this stage's own report directory. `product_tool/config/source_catalog.v2.json` (the executable production registry) was **not** modified — `dns-shop.ru` is not an enabled production source. Promoting it there is a separate, explicit, out-of-band decision.

## Request log and budget verification

[`checkpoint.json`](checkpoint.json): **7 requests total** — 2 to `www.dns-shop.ru` (robots.txt, the blocked product page), 5 to `drv.dns-shop.ru` (robots.txt [404, no restrictions declared] + 4 Range requests assembling the PDF). Well within the declared budget of 8. The 401 was recorded, not retried; no protection-bypass technique was used.

## Artifacts

- [`report.md`](report.md) — this file
- [`budget_predeclaration.json`](budget_predeclaration.json) — budget, declared before any request
- `phase1_robots_and_dns_page.json`, `phase2_pdf_fetch.json` — the two live phases
- [`pdf_content_verification.json`](pdf_content_verification.json) — page count, model/SKU search, language detection, manufacturer-origin evidence
- [`card.json`](card.json) — full verdict, manual status, and the formalized DNS fallback rule
- [`checkpoint.json`](checkpoint.json) — request log and budget verification
- [`protected_hashes_check.json`](protected_hashes_check.json) — Stage 2–11.2 + catalog + registry integrity check
- [`raw/`](raw) — fetched robots.txt/HTML pages saved offline (PDF bytes hashed/verified and discarded, per the no-raw-content rule — kept only in session scratch)
- [`scripts/`](scripts) — all 6 scripts used, for reproducibility

## Tests

New regression tests: `tests/test_structural_census_v11_3.py` — checks that the DNS page's 401 is recorded honestly, that identity was not falsely confirmed from a blocked page, that the PDF was fetched byte-complete, that zero model/SKU mentions were found despite 415 HyperX mentions (confirming manufacturer origin without confirming model), that the verdict is stated as a content-verified mismatch and rejection, that declarations/certificates are explicitly excluded from consideration, that the manual status is phrased as open (never absent), that the fallback rule text includes official-priority, per-field provenance, no-wholesale-import, and review-on-conflict requirements, that the rule was tested only on `9A273AA`, that Sulpak's allowlist and Mechta's disabled status are unchanged, that `source_catalog.v2.json` has no DNS entry, and that every prior stage (through 11.2) plus the catalog and registry remain byte-identical.

## Not started automatically

No DNS crawl beyond the two user-provided URLs. No Sulpak/Mechta network activity. No other catalog row. No production-registry promotion of dns-shop.ru.
