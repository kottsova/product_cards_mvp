"""Stage 20 step 1 -- OFFLINE, zero requests. Fix, BEFORE any request, the selection rule, the sample, the budget, the stop rules,
what will be measured per row, the readiness rule and the failure taxonomy of the LG pilot.

Selection rule (deterministic; nothing about a row's expected result is used):
  1. candidates = every unit of the Stage 19 queue with family "lg" and status "ready_to_run" (578);
  2. group by catalog category (12 categories: they stand for different product-page types);
  3. from each category take the unit with the smallest SHA-256 of its upper-cased seller article;
  4. run them in alphabetical order of category.

Output: raw/pilot_selection.json, raw/predeclaration.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
QUEUE = ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl"
sys.path.insert(0, str(ROOT))

from product_tool.adapters.dns import KNOWN_URLS as DNS_KNOWN  # noqa: E402
from product_tool.adapters.sulpak import KNOWN_LG_URLS  # noqa: E402

SELECTION_RULE = ("Per catalog category among the Stage 19 ready_to_run LG units: the unit with the smallest SHA-256(upper-cased seller article); "
                  "categories in alphabetical order.")

READINESS_RULE = {
    "export_ready": "job status done AND an official page whose article matches the full row article (match_level full_sku, no error) AND >=1 official specification fact AND >=1 official gallery photo (kind product_gallery, not excluded, selected for export) AND >=1 instruction whose language is stated as Russian by the source AND no unresolved conflict",
    "export_ready_with_gaps": "official full_sku page AND >=1 official specification fact AND >=1 official gallery photo, but at least one of: instruction missing, supplier confirmation missing, job not done, unresolved conflict -- the gaps are listed",
    "not_ready": "anything else (no official full_sku page, or no official specifications, or no official gallery photo)",
    "note": "`done` is never read as readiness by itself; the job status is reported next to the rule's verdict.",
}

FAILURE_TAXONOMY = {
    "kz_sitemap_error": "LG Kazakhstan: the sitemap could not be fetched or parsed (error on the sitemap request)",
    "kz_no_slug_in_sitemap": "LG Kazakhstan: mismatch, 'page not found in the LG sitemap' -- no product URL whose slug equals the article or its base model",
    "kz_page_unrecognised": "LG Kazakhstan: a page was fetched but lacks the expected product-card markup",
    "kz_base_model_only": "LG Kazakhstan: page found for the base model, full article not on the page",
    "kz_page_error": "LG Kazakhstan: HTTP error on a product page",
    "ru_no_page": "LG Russia: HTTP error on the single URL the adapter builds (https://www.lg.com/ru/laundry/lg-{model})",
    "ru_page_unrecognised": "LG Russia: a page came back without the expected markup",
    "ru_base_model_only": "LG Russia: page found, only the base model on it",
    "documents_no_support_link": "instructions: the RU page was read but no support-model link was extracted (the extraction only recognises one support model name)",
    "documents_not_checked": "instructions: not attempted because there was no usable LG Russia page",
    "documents_none_ru": "instructions: support page read, no document labelled Russian",
    "supplier_no_candidate": "Sulpak: no bounded candidate URL for the article (it only fetches URLs listed in adapters/sulpak.KNOWN_LG_URLS)",
    "no_supplier_confirmation_so_not_done": "worker rule: without a trusted-supplier full_sku confirmation an LG job finishes needs_review, never done",
    "budget_exhausted": "the pilot's request budget refused a request",
    "host_stopped": "a host was stopped by the policy (block) -- the pilot halts",
}


def main() -> None:
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    units = [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line]
    ready = [u for u in units if u["family"] == "lg" and u["status"] == "ready_to_run"]
    by_category = defaultdict(list)
    for unit in ready:
        by_category[unit["category"]].append(unit)
    chosen = []
    for category in sorted(by_category):
        best = min(by_category[category], key=lambda u: hashlib.sha256(u["seller_sku"].upper().encode("utf-8")).hexdigest())
        chosen.append({"category": category, "candidates_in_category": len(by_category[category]), "seller_sku": best["seller_sku"], "catalog_row": best["catalog_row"], "brand": best["brand"],
                       "title": best["title"], "unit_id": best["unit_id"], "sha256_of_article": hashlib.sha256(best["seller_sku"].upper().encode("utf-8")).hexdigest(),
                       "article_has_suffix": "." in best["seller_sku"], "flags": best["flags"]})
    assert len(ready) == 578 and len(chosen) == 12
    selection = {"rule": SELECTION_RULE, "input": "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl", "input_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
                 "candidates": len(ready), "categories": {c: len(v) for c, v in sorted(by_category.items())}, "rows": chosen,
                 "rows_with_article_suffix": sum(1 for c in chosen if c["article_has_suffix"])}
    (STAGE / "raw/pilot_selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    skus = {c["seller_sku"].upper() for c in chosen}
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "budget": {"max_requests_per_row": 5, "max_requests_total": 60, "rows": 12,
                   "counted": "every real HTTP request of the LG official adapters and Sulpak (retries included); a sitemap answered from the in-process cache is not a request",
                   "refusal": "a request over budget is refused before it is made (marker [policy_budget_exhausted]) and the row records it"},
        "hosts_allowed": ["www.lg.com", "lg.com", "www.sulpak.kz", "sulpak.kz"],
        "stop_rule": "any 401/403/429 or confirmed challenge (any HTTP status) stops that host in the persisted log (workdir/lg_fetch_log.json); the pilot halts before the next row and lists rows not run",
        "pacing_seconds_between_requests": 1.0,
        "workflow": "the ordinary worker.run_once(database) with the default adapter factories (LGAdapter, LGRUAdapter, SulpakAdapter through PolicyAwareSession; DNS default), stages 1,2,3,4,6, one job per row",
        "dealer_check": {"dns_known_urls_for_pilot_rows": sorted(s for s in skus if s in {k.upper() for k in DNS_KNOWN}), "sulpak_known_urls_for_pilot_rows": sorted(s for s in skus if s in KNOWN_LG_URLS),
                         "reading": "DNS and Sulpak fetch only URLs listed in their KNOWN_URLS maps; a row not listed there makes no dealer request"},
        "measured_per_row": ["official exact page found (lg_kz, lg_ru: match level and url)", "variant confirmed (full_sku on the page)", "specification facts per source and resolved statuses",
                             "photos per source and kind (gallery / feature / excluded)", "instructions found and their stated language",
                             "what Sulpak and DNS added (facts, photos, match level)", "final job status and message", "card readiness by the rule below", "failure codes from the taxonomy below",
                             "the requests made (url, status) and the responses saved for offline diagnosis"],
        "readiness_rule": READINESS_RULE, "failure_taxonomy": FAILURE_TAXONOMY,
        "export_check": "after the pilot the ordinary Excel export (exporter.export_batch) is produced for the pilot batch and counted per row",
        "not_done_here": "the full run of the 578 rows",
    }
    (STAGE / "raw/predeclaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("chosen:")
    for c in chosen:
        print(f"  {c['category']:<28} {c['seller_sku']:<20} (of {c['candidates_in_category']:>3}) suffix={c['article_has_suffix']}")
    print("dealer_check:", declaration["dealer_check"])


if __name__ == "__main__":
    main()
