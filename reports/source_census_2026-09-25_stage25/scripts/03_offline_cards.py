"""Stage 25 step 3 -- OFFLINE, zero requests. Runs adapters/samsung.py on the SAVED responses of the Stage 24 batches 1/1b and the Stage 25 batch 2: one product per category,
their documents re-assessed from the saved files (or their extracted text), dealer-fallback requests produced without any network, all facts written to raw/cards.json.

The Stage 24 report said the specification table was client-rendered and a TV had one photo. Both statements were wrong; the numbers here replace them.
"""
from __future__ import annotations

import gzip
import io
import json
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
S24 = ROOT / "reports/source_census_2026-09-25_stage24"
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from product_tool.adapters import samsung  # noqa: E402
from product_tool.adapters.dns import DnsAdapter  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402

logging.disable(logging.CRITICAL)


def responses(directory: Path) -> dict[str, dict]:
    result = {}
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        entry["dir"] = directory
        result[entry["url"]] = entry
    return result


ALL = {}
for folder in (S24 / "batch1/responses", S24 / "batch1b/responses", STAGE / "batch2/responses"):
    ALL.update(responses(folder))
EXTRACT = {}
for _base in (S24, STAGE):
    if (_base / "docs_extract/index.json").exists():
        for _r in json.loads((_base / "docs_extract/index.json").read_text(encoding="utf-8")):
            if _r.get("text_file"):
                EXTRACT[_r["url"]] = dict(_r, base=str(_base))


def html_of(url: str) -> str:
    entry = ALL[url]
    with gzip.open(entry["dir"] / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


def pages_of(url: str) -> list[str] | None:
    """Text pages of a saved document: the saved body if it is still there, else the extracted text kept by the Stage 24 pruning."""
    entry = ALL.get(url)
    if entry and entry.get("saved_as"):
        import pypdf
        with gzip.open(entry["dir"] / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
            data = handle.read().encode("latin-1", errors="replace")
        if data[:5] != b"%PDF-" or entry["truncated"]:
            return None
        return [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
    record = EXTRACT.get(url)
    if record:
        with gzip.open(Path(record["base"]) / "docs_extract" / record["text_file"], "rt", encoding="utf-8") as handle:
            return handle.read().split("\n\f\n")
    return None


def final_url(url: str) -> str:
    return url


PRODUCTS = [
    ("Телевизоры", "QE48S85HAEXCE", "https://www.samsung.com/kz_ru/tvs/oled-tv/48s85h-48-inch-4k-smart-tv-qe48s85haexce/", None),
    ("Смартфоны", "SM-A376EZAGINS", "https://www.samsung.com/kz_ru/smartphones/galaxy-a/galaxy-a37-5g-awesome-graygreen-256gb-sm-a376edggskz/", "https://www.samsung.com/kz_ru/smartphones/galaxy-a/galaxy-a37-5g-awesome-graygreen-256gb-sm-a376edggskz/buy/"),
    ("Пылесосы", "VC18M21D0VG/EV", "https://www.samsung.com/kz_ru/vacuum-cleaners/canister/canister-2100v-vc18m21d0vg-ev/", None),
    ("Стиральные машины", "WD10T754CBX/LD", None, None),
    ("Микроволновые печи", "MS23K3614AK/BW", "https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/", None),
]


def find(sub: str) -> str:
    return next(u for u in ALL if sub in u and u.startswith("https://www.samsung.com/kz_ru"))


def dealer_requests(article: str, name: str, missing: list[str]) -> dict:
    """The DNS adapter without a network: it knows only pre-verified URLs, so an unknown Samsung code yields the ready-to-ask request (or 'not needed')."""

    class Refusing:
        headers: dict = {}
        calls = 0

        def get(self, url, **kw):
            Refusing.calls += 1
            raise requests.ConnectionError("no request: offline")

    session = Refusing()
    document = DnsAdapter(session, clock=lambda: 0.0).find_source(article, deadline=1e9, model_tokens=[article.split("/")[0]], brand="Samsung", name=name, missing_fields=missing)
    return {"match_level": document.match_level, "message": document.evidence[:400], "requests_made": Refusing.calls}


def card_for(category: str, article: str, page_url: str, extra_url: str | None) -> dict:
    html = html_of(page_url)
    card = samsung.parse_product_page(html, page_url, article)
    out = {"category": category, "article": article, "url": page_url, "identity": {"level": card.identity.level, "strength": card.identity.evidence_strength, "evidence": card.identity.evidence, "jsonld_sku": card.identity.jsonld_sku,
                                                                                    "open_differences": card.identity.open_differences, "title": card.identity.title[:120]},
           "specs": {"items": len(card.specs), "groups": sorted({i.group for i in card.specs})}, "photos": {"full_size": len(card.photos.photos), "thumbnails": len(card.photos.thumbnails), "three_d_excluded": len(card.photos.three_d),
                                                                                                        "photo_urls": [p.url for p in card.photos.photos], "gap": card.photos.gap},
           "document_links": [{"file": d.file_name, "model_name": d.model_name, "language_hint": d.language_hint, "href": d.href} for d in card.documents], "missing_fields": list(card.missing_fields), "gaps": list(card.gaps)}
    if extra_url:
        extra = samsung.parse_product_page(html_of(extra_url), extra_url, article)
        out["extra_page"] = {"url": extra_url, "photos_full_size": len(extra.photos.photos), "thumbnails": len(extra.photos.thumbnails), "specs": len(extra.specs), "photo_urls": [p.url for p in extra.photos.photos]}
        if extra.photos.photos and not card.photos.photos:
            out["photos"]["full_size"] = len(extra.photos.photos)
            out["photos"]["source"] = "the product's own buy page (its JSON-LD BuyAction target)"
            out["missing_fields"] = [m for m in out["missing_fields"] if m != "фото"]
    documents = []
    for link in card.documents:
        pages = pages_of(link.href) if link.href in ALL else None
        # a document fetched by its final address is stored under the requested URL; the saved index is keyed by the requested one
        entry = {"file": link.file_name, "language_hint": link.language_hint, "link_model_name": link.model_name, "state": "candidate_link_not_fetched"}
        if link.href in ALL:
            entry["state"] = "reachable_file" if pages is not None else "reachable_but_not_a_complete_pdf"
        if pages is not None:
            facts = samsung.assess_samsung_document(pages, article, link.model_name, card.identity.level)
            entry.update({"facts": facts, "rule4_analog": samsung.rule4_analog(facts)})
        documents.append(entry)
    out["documents"] = documents
    return out


def main() -> None:
    cards = []
    for category, article, page_url, extra_url in PRODUCTS:
        if category == "Стиральные машины":
            page_url = find("wd10t754cbx-ld/")
        cards.append(card_for(category, article, page_url, extra_url))
    b2 = json.loads((STAGE / "raw/batch2_result.json").read_text(encoding="utf-8"))["products"]
    declaration = json.loads((STAGE / "raw/batch2_declaration.json").read_text(encoding="utf-8"))["products"]
    for category, item in declaration.items():
        cards.append(card_for(category, item["article"], b2[category]["url"], None))
    # the six-category hub check for tablets, on the saved hub
    hub_url = "https://www.samsung.com/kz_ru/tablets/all-tablets/"
    hub_links = samsung.hub_product_links(html_of(hub_url), hub_url)
    tablets = {"hub_product_links": len(hub_links), "catalog_row_SM-X826BZARSKZ_on_hub": samsung.find_on_hub(hub_links, "SM-X826BZARSKZ"), "catalog_row_SM-X926BZARSKZ_on_hub": samsung.find_on_hub(hub_links, "SM-X926BZARSKZ"),
               "neighbouring_model_on_hub_not_a_match": [u for u in hub_links if "sm-x406" in u.lower()][:1]}
    phone_hubs = []
    for url in ("https://www.samsung.com/kz_ru/smartphones/all-smartphones/", "https://www.samsung.com/kz_ru/smartphones/galaxy-a/"):
        phone_hubs += samsung.hub_product_links(html_of(url), url)
    tablets["a37_row_on_the_phone_hubs"] = samsung.find_on_hub(sorted(set(phone_hubs)), "SM-A376EZAGINS")
    s25 = samsung.parse_product_page(html_of("https://www.samsung.com/kz_ru/smartphones/galaxy-s25-ultra/"), "https://www.samsung.com/kz_ru/smartphones/galaxy-s25-ultra/", "SM-S938BZKBSKZ")
    tablets["s25_ultra_family_page"] = {"is_product_page": s25.identity.is_product_page, "level": s25.identity.level, "specs": len(s25.specs)}
    for card in cards:
        card["dealer_fallback"] = dealer_requests(card["article"], card["identity"]["title"], card["missing_fields"]) if card["missing_fields"] else {"match_level": "not_needed", "requests_made": 0}
    (STAGE / "raw/cards.json").write_text(json.dumps({"cards": cards, "tablets_and_phone_hubs": tablets}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spec_dump = {c["category"]: [{"group": i.group, "name": i.name, "value": i.value} for i in samsung.extract_spec_table(html_of(c["url"]))] for c in cards}
    (STAGE / "raw/spec_tables.json").write_text(json.dumps(spec_dump, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c in cards:
        docs = [(d["language_hint"], d.get("rule4_analog", d["state"])) for d in c["documents"]]
        print(f"{c['category']:<20} {c['article']:<16} {c['identity']['level']}/{c['identity']['strength']} specs={c['specs']['items']:<3} photos={c['photos']['full_size']:<3} missing={c['missing_fields']} docs={docs}")
    print(json.dumps(tablets, ensure_ascii=False))


if __name__ == "__main__":
    with offline_only():
        main()
