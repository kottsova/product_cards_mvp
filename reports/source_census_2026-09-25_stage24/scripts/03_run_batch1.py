"""Stage 24 step 3 -- Samsung batch 1: fetch exactly what raw/batch1_declaration.json declared (<= 30 real requests, <= 10 per category, 1.5 s pacing), through the
policy-aware session (allowlist, redirect check, persisted host stop, budget, response recorder). No catalog row is processed in bulk.

Output: raw/batch1_result.json, batch1/responses/* (every real response, gzip), batch1/workdir/samsung_fetch_log.json
"""
from __future__ import annotations

import io
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from product_tool.adapters.common import SourceError, fetch_with_retry  # noqa: E402
from product_tool.adapters.lg_documents import BinarySafeSession, assess_document, document_bytes, looks_like_pdf  # noqa: E402
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget  # noqa: E402
from product_tool.adapters.sitemap_urls import sitemap_locs  # noqa: E402
from product_tool.adapters.structured_page import extract_dom_spec_table, extract_json_ld_product  # noqa: E402

logging.disable(logging.CRITICAL)
BASE = "https://www.samsung.com/kz_ru/"
VD, DA = BASE + "vd-sitemap.xml", BASE + "da-sitemap.xml"
HUB_TV = BASE + "tvs/best-2026/"
HUB_PHONES = [BASE + "smartphones/all-smartphones/", BASE + "smartphones/galaxy-a/"]
HUB_TABLETS = BASE + "tablets/all-tablets/"
PHONE_TOKENS = ["a36", "a56", "a26", "s25"]
WORKDIR = STAGE / "batch1/workdir"
PER_CATEGORY, TOTAL = 10, 30


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def hub_links(html: str, page_url: str) -> list[str]:
    """Every /kz_ru/ address the hub prints: anchors and addresses embedded in its scripts/JSON."""
    found = {urljoin(page_url, a["href"]) for a in BeautifulSoup(html, "html.parser").select("a[href]")}
    for raw in re.findall(r"""(?:https?://www\.samsung\.com)?/kz_ru/[^"'\s<>\\)]+""", html):
        found.add(urljoin(page_url, raw))
    return sorted(u.split("#")[0] for u in found if "/kz_ru/" in u)


def sitemap_match(urls: list[str], article: str) -> str:
    for key in (norm(article), norm(article.split("/")[0])):
        if len(key) >= 6:
            hit = next((u for u in urls if key in norm(u.rsplit("/kz_ru/", 1)[-1])), "")
            if hit:
                return hit
    return ""


def analyze_page(html: str, url: str, article: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    fields = extract_json_ld_product(html, url)
    by_name = {}
    for f in fields:
        by_name.setdefault(f.name, []).append(f.value)
    sku = (by_name.get("sku") or [""])[0]
    a, base = norm(article), norm(article.split("/")[0])
    match = "no_sku_on_page" if not sku else "exact_article" if norm(sku) == a else "base_code" if norm(sku) in (base,) or base in norm(sku) or norm(sku) in a else "different_sku"
    spec_rows = extract_dom_spec_table(html, url)
    images = sorted({m for m in re.findall(r"https://images\.samsung\.com/[^\"'\s<>\\)]+", html) if base[:6] in norm(m) or a[:8] in norm(m)})
    anchors = [(urljoin(url, x["href"]), " ".join(x.get_text(" ").split())[:80]) for x in soup.select("a[href]")]
    pdfs = [(h, t) for h, t in anchors if re.search(r"\.pdf(?:$|\?)|CDCttType=", h, re.I)]
    text = " ".join(soup.get_text(" ").split())
    return {"url": url, "html_bytes": len(html), "title": (soup.title.string or "").strip()[:140] if soup.title else "", "canonical": (soup.select_one('link[rel="canonical"]') or {}).get("href", ""),
            "json_ld_product": bool(fields), "json_ld_fields": {k: v[:2] for k, v in by_name.items() if k != "json_ld_image"}, "json_ld_images": len(by_name.get("json_ld_image", [])), "sku_vs_catalog_article": match,
            "generic_dom_spec_rows": len(spec_rows), "generic_spec_sample": [(f.name, f.value) for f in spec_rows[:5]], "product_named_images_in_html": images[:6], "product_named_images_count": len(images),
            "pdf_like_links": pdfs[:6], "visible_text_chars": len(text), "has_spec_shell": bool(soup.select("[class*=spec], [id*=spec]")),
            "article_in_visible_text": (base in norm(text)) or (a in norm(text))}


def main() -> None:
    declaration = json.loads((STAGE / "raw/batch1_declaration.json").read_text(encoding="utf-8"))
    assert declaration["budget"]["max_real_requests_total"] == TOTAL and declaration["budget"]["max_real_requests_per_category"] == PER_CATEGORY
    started = now()
    assert started > declaration["declared_at"]
    candidates = declaration["candidates_in_order"]
    WORKDIR.mkdir(parents=True, exist_ok=True)
    plain = requests.Session()
    plain.headers.update({"User-Agent": "ProductCardsSourceCensus/2.0 (bounded diagnostic probe)", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"})
    client = PolicyAwareSession(WORKDIR / "samsung_fetch_log.json", allowed_hosts=("samsung.com",), underlying=BinarySafeSession(plain), max_bytes=25_000_000, min_interval_seconds=1.5)
    budget = RequestBudget(max_per_row=PER_CATEGORY, max_total=TOTAL)
    steps, categories, halted, pages = [], {}, "", {}

    def fetch(label: str, url: str):
        nonlocal halted
        if halted:
            steps.append({"step": label, "url": url, "skipped": halted})
            return None
        try:
            response = fetch_with_retry(client, url, deadline=1e12, clock=lambda: 0.0)
            steps.append({"step": label, "url": url, "status": response.status_code, "bytes": len(response.content), "final_url": response.url, "content_type": response.headers.get("Content-Type", "")})
            return response
        except SourceError as exc:
            steps.append({"step": label, "url": url, "error": str(exc)})
            if any(m in str(exc) for m in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                halted = str(exc)
            return None

    def fetch_document(category: str, page: dict, article: str) -> dict:
        record = {"candidates": page["pdf_like_links"], "state": "no_manual_link_on_the_page"}
        usable = [(h, t) for h, t in page["pdf_like_links"] if (urlsplit(h).hostname or "").endswith("samsung.com") and not re.search(r"delivery|tnc|terms|energy|eprel|warranty", h, re.I)]
        usable.sort(key=lambda x: 0 if re.search(r"CDCttType=UM", x[0]) else 1)
        if not usable:
            return record
        href = usable[0][0]
        record.update({"state": "candidate_link", "href": href, "anchor": usable[0][1]})
        response = fetch(f"{category}: document", href)
        if response is None:
            record["state"] = "candidate_link_unreachable"
            return record
        data = document_bytes(response)
        record.update({"bytes": len(data), "final_url": response.url, "content_type": response.headers.get("Content-Type", ""), "truncated": bool(response.truncated)})
        if not looks_like_pdf(data) or response.truncated:
            record["state"] = "reachable_but_not_a_complete_pdf"
            return record
        record["state"] = "reachable_file"
        try:
            import pypdf
            texts = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
        except Exception as exc:  # noqa: BLE001
            record["parse_error"] = str(exc)[:120]
            return record
        assessment = assess_document(texts, [article.split("/")[0]])
        languages = assessment["languages"]
        record.update({"pages": len(texts), "assessment": {"kind": assessment["kind"], "accepted": assessment["accepted"], "model_evidence": assessment["model_evidence"], "names_model": assessment["names_model"],
                                                          "conflicting_models": assessment["conflicting_models"], "languages": languages["present"], "letters_by_language": languages["letters_by_language"],
                                                          "russian_instruction": languages["russian_instruction"]}})
        record["state"] = "instruction_confirmed_by_content" if assessment["accepted"] else "reachable_file_not_confirmed_as_instruction"
        return record

    def product(category: str, url: str, article: str) -> dict:
        response = fetch(f"{category}: product page", url)
        if response is None:
            return {"state": "page_unreachable", "url": url}
        info = analyze_page(response.text, response.url, article)
        info["document"] = fetch_document(category, info, article)
        return info

    with request_budget(budget), record_responses(STAGE / "batch1/responses"):
        budget.begin_row("shared: sitemaps")
        vd, da = fetch("vd-sitemap", VD), fetch("da-sitemap", DA)
        vd_urls = sitemap_locs(vd.text) if vd else []
        da_urls = sitemap_locs(da.text) if da else []
        pages["sitemaps"] = {"vd_urls": len(vd_urls), "da_urls": len(da_urls)}

        # -- TV -------------------------------------------------------------------------------------------------------
        category = "Телевизоры"
        budget.begin_row(category)
        result = {"candidates": candidates[category], "outcome": "not_run"}
        categories[category] = result
        hub = fetch("TV 2026 hub", HUB_TV)
        hub_urls = hub_links(hub.text, hub.url) if hub else []
        hub_norm = norm(" ".join(hub_urls)) + norm(hub.text if hub else "")
        result["hub"] = {"url": HUB_TV, "links": len(hub_urls)}
        for article in candidates[category]:
            page_url = sitemap_match(vd_urls, article)
            series = re.search(r"QE\d{2,3}([A-Z]+\d+[A-Z])", article)
            token = norm(series.group(1)) if series else ""
            result.setdefault("checked_candidates", []).append({"article": article, "sitemap_page": page_url, "series_token": token, "on_2026_hub": bool(token and token in hub_norm), "code_on_hub": norm(article) in hub_norm})
            if page_url:
                result.update({"chosen": article, "currency_confirmed_by_hub": bool(token and token in hub_norm) or norm(article) in hub_norm, "page": product(category, page_url, article), "outcome": "page_found"})
                break
        else:
            result["outcome"] = "no_candidate_with_a_sitemap_page"

        # -- smartphones ---------------------------------------------------------------------------------------------
        category = "Смартфоны"
        budget.begin_row(category)
        result = {"candidates": candidates[category], "outcome": "not_run", "model_tokens": PHONE_TOKENS}
        categories[category] = result
        links = []
        for hub_url in HUB_PHONES:
            hub = fetch("phones hub", hub_url)
            if hub:
                links += hub_links(hub.text, hub.url)
        links = sorted(set(links))
        result["hub_links"] = len(links)
        for token in PHONE_TOKENS:
            hits = [u for u in links if re.search(rf"/(?:galaxy-)?{token}(?![0-9a-z])", u.split("/kz_ru/")[-1]) or f"galaxy-{token}" in u]
            result.setdefault("checked_models", []).append({"token": token, "links_on_hubs": hits[:4]})
            if hits:
                base_page = next((u for u in hits if not u.rstrip("/").endswith("/buy")), hits[0].rsplit("/buy", 1)[0] + "/")
                result.update({"chosen_model_token": token, "currency_confirmed_by_hub_link": True, "page": product(category, base_page, next(c for c in candidates[category])), "outcome": "family_page_found"})
                break
        else:
            result["outcome"] = "no_catalog_model_on_the_current_official_lists"

        # -- tablets --------------------------------------------------------------------------------------------------
        category = "Планшеты"
        budget.begin_row(category)
        result = {"candidates": candidates[category], "outcome": "not_run"}
        categories[category] = result
        hub = fetch("tablets hub", HUB_TABLETS)
        links = hub_links(hub.text, hub.url) if hub else []
        result["hub_links"] = len(links)
        hits = [u for u in links if "smx826" in norm(u) or "tabs10" in norm(u)]
        result["catalog_model_links_on_hub"] = hits[:5]
        tablet_links = sorted({u for u in links if "/tablets/galaxy-tab" in u})
        result["tablet_product_links_on_hub"] = tablet_links[:12]
        if hits:
            result.update({"currency_confirmed_by_hub_link": True, "page": product(category, hits[0], candidates[category][0]), "outcome": "page_found"})
        else:
            result["outcome"] = "catalog_tablet_not_on_the_current_official_list"

        # -- appliances (old models allowed) ------------------------------------------------------------------------------------------------
        for category in ("Пылесосы", "Стиральные машины"):
            budget.begin_row(category)
            result = {"candidates": candidates[category], "outcome": "not_run"}
            categories[category] = result
            for article in candidates[category]:
                page_url = sitemap_match(da_urls, article)
                result.setdefault("checked_candidates", []).append({"article": article, "sitemap_page": page_url})
                if page_url:
                    result.update({"chosen": article, "page": product(category, page_url, article), "outcome": "page_found"})
                    break
            else:
                result["outcome"] = "no_candidate_with_a_sitemap_page"
        categories["Микроволновые печи"] = {"candidates": candidates["Микроволновые печи"], "outcome": "saved_evidence_used", "requests": 0}
    result = {"started_at": started, "finished_at": now(), "requests_made": budget.total, "budget_log": budget.log, "halted": halted, "steps": steps, "sitemaps": pages["sitemaps"], "categories": categories}
    (STAGE / "raw/batch1_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("requests", budget.total, "halted", halted)
    for c, r in categories.items():
        print(f"  {c:<22} {r['outcome']:<45} {r.get('chosen', '')}")
    for s in steps:
        print("   ", s["step"], s.get("status") or s.get("error") or s.get("skipped"), s["url"][-70:])


if __name__ == "__main__":
    main()
