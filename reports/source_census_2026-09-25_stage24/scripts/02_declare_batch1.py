"""Stage 24 step 2 -- OFFLINE. Declares batch 1 of the Samsung check BEFORE any request: candidates, routes, budget, decision rules, stop rule, what is measured.

Batch 1 = at most one catalog product per selected category; five categories are fetched, the sixth (microwave ovens, MS23K3614AK/BW) reuses its Stage 8.4-8.6 evidence
and makes no request. No catalog rows are processed in bulk. The remaining 25 categories stay queued.

Output: raw/batch1_declaration.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402

BASE = "https://www.samsung.com/kz_ru/"


def main() -> None:
    proposals = {p["category"]: p for p in json.loads((STAGE / "raw/selection_proposal.json").read_text(encoding="utf-8"))["proposals"]}
    candidates = {
        "Телевизоры": [proposals["Телевизоры"]["article"], *proposals["Телевизоры"]["fallbacks"]],
        "Смартфоны": [proposals["Смартфоны"]["article"], *proposals["Смартфоны"]["fallbacks"]],
        "Планшеты": [proposals["Планшеты"]["article"], *proposals["Планшеты"]["fallbacks"]],
        "Пылесосы": [proposals["Пылесосы"]["article"], *proposals["Пылесосы"]["fallbacks"]],
        "Стиральные машины": [proposals["Стиральные машины"]["article"], *proposals["Стиральные машины"]["fallbacks"]],
        "Микроволновые печи": [proposals["Микроволновые печи"]["article"]],
    }
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": "24 / batch 1", "brand": "Samsung", "market": "kz_ru",
        "candidates_in_order": candidates,
        "no_request_for": {"Микроволновые печи": "MS23K3614AK/BW: the saved evidence of Stages 8.4-8.6 is used unchanged"},
        "budget": {"max_real_requests_total": 30, "max_real_requests_per_category": 10, "pacing_seconds": 1.5, "hosts": ["www.samsung.com and *.samsung.com subdomains (a document link printed on an official page)"],
                   "not_fetched": "images (their URLs are recorded, no image is downloaded); support.samsung.com search (client-rendered, Stage 8.2.2); any URL not printed by an official page or listed in an official sitemap",
                   "shared_requests": "the two sitemaps and the hub pages are charged to the total and to the first category that needs them"},
        "routes_observed_before": {
            "vd_sitemap": BASE + "vd-sitemap.xml", "da_sitemap": BASE + "da-sitemap.xml",
            "tv_hub_2026": BASE + "tvs/best-2026/", "phone_hubs": [BASE + "smartphones/all-smartphones/", BASE + "smartphones/galaxy-a/"], "tablet_hub": BASE + "tablets/all-tablets/",
            "origin": "links in the Samsung link indexes of Stages 8.2 / 8.2.1 and the b2c-sitemap branches of Stage 8.2.1"},
        "steps": {
            "shared": "GET vd-sitemap.xml and da-sitemap.xml (2). A candidate's page = the sitemap URL whose alphanumeric slug contains the alphanumeric article (the part before '/' is the fallback key); nothing is built.",
            "Телевизоры": "GET the 2026 hub (1). Currency = the hub links to the candidate's page or names its series (e.g. s85h). The first candidate (in order) that has a sitemap page is fetched (1). Currency is reported separately; a card without confirmed currency does not count as a NEW electronics card.",
            "Смартфоны": "GET all-smartphones and galaxy-a hubs (2). Model tokens in order: a36, a56, a26, s25. The first model with a link on a hub is the page fetched (1). Currency = that link. No such link -> no eligible current model, category stays queued.",
            "Планшеты": "GET the all-tablets hub (1). The candidate's model code (sm-x826) or series (tab s10) must be linked; then that page is fetched (1). Otherwise: the current lineup does not contain the catalog tablet -> no eligible novelty, category stays queued.",
            "Пылесосы / Стиральные машины": "The first candidate (in order) with a page in da-sitemap.xml is fetched (1 each); old models are allowed. No candidate in the sitemap -> outcome recorded, nothing else requested.",
            "documents": "On each fetched product page: the first anchor that looks like a manual (href has .pdf or CDCttType=UM, not a delivery/terms/energy-label file) on a *.samsung.com host is fetched once as a complete PDF (cap 25 MB). Nothing else is fetched. State per file: candidate link -> reachable file -> instruction confirmed by content (text, language by chunk, model named), as in Stage 22.",
        },
        "measured_per_product": ["exact official page found (sitemap/hub url; sku on the page equals the catalog article: exact_article / base_code / none)", "identity fields the GENERIC extractor (structured_page.py) returns",
                                 "specification rows: generic dom table rows vs spec text only Samsung-specific logic can read", "photo URLs: generic gallery extractor vs Samsung-specific image rule",
                                 "document: link / file / content-confirmed, language, model", "currency evidence for electronics"],
        "stop_rule": "401/403/429 or a confirmed challenge on any Samsung host stops that host in batch1/workdir/samsung_fetch_log.json and ends the batch; the remaining categories are recorded as not run",
        "url_construction": "none", "not_done": "any bulk processing of catalog rows; queued categories; new pilots of other brands",
    }
    (STAGE / "raw/batch1_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(candidates, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    with offline_only():
        main()
