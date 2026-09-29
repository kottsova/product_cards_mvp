"""Stage 25 step 1 -- OFFLINE. Batch 2 of the Samsung check, declared BEFORE any request.

Owner rules (2026-09-25, second message):
  * home appliances: old models are looked for too (most of the catalog is old); no novelty is required; the "novelty only" rule stays for smartphones, tablets and wearables;
  * computers, TVs and other technology: no automatic ban on old models; the concrete product and the exactness of its match to the catalog decide;
  * official site first; a dealer fallback (DNS first) only for fields the official page lacks, only for an EXACT model AND variant match, with a separate source per added field;
    never a guessed dealer URL (DNS only knows pre-verified URLs), never a dealer value in place of an official one;
  * a document is judged by its content: declarations and certificates do not count; one product per category; no mass run.

Selection (fixed here): for each of the six categories, among the catalog rows with a clean article that have an EXACT page in the saved full Samsung sitemaps (vd-sitemap.xml, da-sitemap.xml
fetched in Stage 24), the smallest SHA-256 of the upper-cased article. The provisional Stage 24 proposals for these categories (made from a 300-link partial index) are replaced by this rule.

Extra requests, all for products already chosen: the microwave MS23K3614AK/BW product page (its Stage 8.4 body was never saved, so the adapter cannot be tested on it), the A37 "buy" page
(its own JSON-LD BuyAction target: the phone gallery is not in the static product page), and the washer's only manual (28 MB, over the earlier 25 MB cap).

Output: raw/batch2_declaration.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S24 = ROOT / "reports/source_census_2026-09-25_stage24"
sys.path.insert(0, str(ROOT))

from product_tool.adapters import samsung  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

CATEGORIES = ["Холодильники", "Духовые шкафы", "Сплит-системы", "Варочные панели", "Мониторы", "Саундбары"]


def saved(name: str) -> str:
    base = S24 / "batch1/responses"
    for line in (base / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["url"].endswith(name) and entry["saved_as"]:
            with gzip.open(base / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                return handle.read()
    raise SystemExit(name)


def digest(article: str) -> str:
    return hashlib.sha256(article.upper().encode("utf-8")).hexdigest()


def main() -> None:
    urls = sitemap_locs(saved("vd-sitemap.xml")) + sitemap_locs(saved("da-sitemap.xml"))
    units = [json.loads(line) for line in (ROOT / "reports/source_census_2026-09-24_stage19/queue/coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    samsung_units = [u for u in units if u["brand"] == "Samsung"]
    chosen, pool_sizes = {}, {}
    for category in CATEGORIES:
        rows = []
        for unit in (u for u in samsung_units if u["category"] == category):
            article = unit["seller_sku"]
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-]*(?:/[A-Z0-9]+)?", article.upper()) or "_" in article:
                continue
            page = samsung.find_in_sitemap(urls, article)
            if page:
                rows.append((digest(article), article, page, unit))
        rows.sort()
        pool_sizes[category] = len(rows)
        _, article, page, unit = rows[0]
        chosen[category] = {"article": article, "title": unit["title"], "catalog_row": unit["catalog_row"], "page_url": page, "class": "appliance" if category not in ("Мониторы", "Саундбары") else "other technology",
                            "pool": len(rows), "reason": "чистый артикул, точная страница есть в полной карте сайта; наименьший SHA-256 среди таких строк категории (старые модели допустимы)"}
    microwave_url = json.loads((ROOT / "reports/source_census_2026-09-22_stage8_4/raw/microwave_fetch.json").read_text(encoding="utf-8"))["url"]
    a37 = json.loads((S24 / "raw/batch1b_result.json").read_text(encoding="utf-8"))["result"]["a37"]["url"]
    buy_url = a37.rstrip("/") + "/buy/"
    declaration = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": "25 / batch 2", "brand": "Samsung", "market": "kz_ru",
        "products": chosen,
        "extra_requests": {"microwave_product_page": microwave_url, "a37_buy_page": buy_url, "a37_buy_page_origin": "the BuyAction target printed in the A37 page's own JSON-LD",
                           "washer_manual": "the only manual link of WD10T754CBX/LD (Stage 24 batch 1, truncated at 25 MB); re-fetched under the new cap"},
        "budget": {"max_real_requests_total": 26, "max_real_requests_per_product": 3, "pacing_seconds": 1.5, "document_cap_mb": 40, "hosts": ["www.samsung.com", "*.samsung.com (document links printed by the pages)"],
                   "note": "product pages of the six chosen products: 6; their manuals: at most 2 files each (the first whose file name says RU, then, only if that file is not a Russian instruction by its text, the next RU-named file or the first other one); microwave page 1; A37 buy page 1; washer manual 1"},
        "document_rule": "the file name orders the requests only; language, instruction-ness and the model named inside are read from the text (adapters/samsung.py assess_samsung_document); declarations/certificates are excluded by content",
        "dealer_fallback": {"source": "DNS", "requests": 0, "rule": "DnsAdapter knows only pre-verified URLs (KNOWN_URLS); none exists for these Samsung products, so nothing is requested and the ready-to-ask dealer request is produced offline for cards with missing fields; a dealer value would be added only for a missing field, only on an exact model AND variant match, each with its own source, never replacing an official value (merge_dealer_fields)"},
        "stop_rule": "401/403/429 or a confirmed challenge on a Samsung host stops it in batch2/workdir/samsung_fetch_log.json and ends the batch", "url_construction": "none",
        "not_done": "the other 19 queued categories; any bulk processing of catalog rows; a new LG pilot",
    }
    (STAGE / "raw").mkdir(parents=True, exist_ok=True)
    (STAGE / "raw/batch2_declaration.json").write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for category, item in chosen.items():
        print(f"{category:<16} {item['article']:<18} pool={item['pool']:<3} {item['page_url'].split('/kz_ru/')[1][:70]}")


if __name__ == "__main__":
    with offline_only():
        main()
