"""Stage 18 step 3 -- ONE bounded live wave against hyperx.com (research script, not an adapter).

Budget (declared in raw/budget_predeclaration.json BEFORE the first request):
  host hyperx.com only; at most 30 requests in total
    <= 3  sitemap requests: the sitemap index robots.txt declares, then at most two product sitemaps that index itself lists
    <= 27 product-page requests, each one a page whose URL was OBSERVED (saved official links, or a <loc> of the sitemap)
  no URL is built from a pattern; no search, no collection paging, no variant guessing
  every request goes through PolicyAwareFetcher (allowlist, redirect checks, min interval, persisted fetch log);
  the first 401/403/429/challenge halts the run and the host stays stopped for later runs (data/hyperx_fetch_log.json).

A page is accepted for a catalog row only when HyperXAdapter.parse_page() -- the working adapter's own identity rule --
returns exact_variant AND the page name carries every distinctive model token of the catalog title.
Nothing is added to hyperx.KNOWN_URLS by this script.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
RAW = STAGE / "raw"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import hx_matching  # noqa: E402
from product_tool.adapters.hyperx import ALLOWED_HOSTS, DEFAULT_FETCH_LOG_PATH, HyperXAdapter  # noqa: E402
from product_tool.adapters.policy_fetch import PolicyAwareFetcher  # noqa: E402
from product_tool.census.endpoint_probe import AccessStatus, ProbePolicy  # noqa: E402
from product_tool.census.models import EndpointCapability, ProtectionStatus  # noqa: E402

MAX_REQUESTS, MAX_SITEMAP, MAX_PAGES = 30, 3, 27
SITEMAP_INDEX = "https://hyperx.com/sitemap.xml"  # declared by robots.txt, saved in Stage 11.1
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
STOP_PROTECTION = {ProtectionStatus.CHALLENGE_CONFIRMED, ProtectionStatus.BROWSER_VERIFICATION_REQUIRED}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_rows() -> dict[str, dict]:
    rows = [json.loads(line) for line in (STAGE / "queue_a_evidence_scope" / "coverage_units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    return {r["seller_sku"].upper(): r for r in rows if r["status"] == "adapter_url_missing" and r["family"] == "hyperx"}


class Run:
    def __init__(self) -> None:
        self.requests = self.sitemap_requests = self.page_requests = 0
        self.log: list[dict] = []
        self.halted = ""
        self.fetcher = PolicyAwareFetcher(DEFAULT_FETCH_LOG_PATH, policy=ProbePolicy(max_bytes=3_000_000, min_interval_seconds=2.0))
        (RAW / "pages").mkdir(parents=True, exist_ok=True)

    def get(self, url: str, kind: str):
        if self.halted or self.requests >= MAX_REQUESTS:
            return None
        if kind == "sitemap" and self.sitemap_requests >= MAX_SITEMAP:
            return None
        if kind == "page" and self.page_requests >= MAX_PAGES:
            return None
        if urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise ValueError(f"not an allowed HyperX host: {url}")
        capability = EndpointCapability.SITEMAP if kind == "sitemap" else EndpointCapability.PRODUCT_PAGE
        result = self.fetcher.get(url, allowed_hosts=tuple(ALLOWED_HOSTS), capability=capability)
        if result.http_status is not None:
            self.requests += 1
            if kind == "sitemap":
                self.sitemap_requests += 1
            else:
                self.page_requests += 1
        body = result.diagnostic_text or ""
        entry = {
            "n": self.requests, "kind": kind, "url": url, "http_status": result.http_status, "final_url": result.final_url,
            "access_status": result.access_status.value, "protection_status": result.protection_status.value,
            "bytes": len(body.encode("utf-8")), "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest() if body else "",
            "checked_at": result.checked_at, "error": result.error,
        }
        self.log.append(entry)
        if result.access_status in (AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED) or result.protection_status in STOP_PROTECTION:
            self.halted = f"{result.http_status or 'prior block'} / {result.access_status.value} / {result.protection_status.value} on {url}"
        if body and result.http_status == 200:
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(url).path.strip("/") or "root")
            with gzip.open(RAW / "pages" / f"{name}.gz", "wt", encoding="utf-8", newline="") as handle:
                handle.write(body)
            entry["saved_as"] = f"raw/pages/{name}.gz"
        return result


def verify(adapter: HyperXAdapter, rows: dict[str, dict], run: Run, url: str, skus: list[str]) -> list[dict]:
    result = run.get(url, "page")
    if result is None or result.http_status != 200:
        return [{"seller_sku": s, "url": url, "outcome": "not_fetched", "detail": (result.error if result else run.halted or "budget")} for s in skus]
    out = []
    page_url = (result.final_url or url).split("?", 1)[0]
    for sku in skus:
        document = adapter.parse_page(result.diagnostic_text, page_url, catalog_code=sku).document
        page_tokens = set(hx_matching._words(_page_name(result.diagnostic_text)))
        title_tokens = hx_matching.model_tokens(rows[sku]["title"])[0]
        title_ok = all(token in page_tokens for token in title_tokens)
        out.append({
            "seller_sku": sku, "url": page_url, "match_level": document.match_level, "page_sku": document.found_model,
            "page_name": _page_name(result.diagnostic_text), "title_tokens_all_on_page_name": title_ok, "evidence": document.evidence,
            "outcome": "accepted" if document.match_level == "exact_variant" and title_ok else "rejected",
        })
    return out


def _page_name(html: str) -> str:
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            kind = item.get("@type")
            if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                return str(item.get("name", ""))
    return ""


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    done = {item["seller_sku"] for item in json.loads((RAW / "offline_snapshot_check.json").read_text(encoding="utf-8"))["exact_variant_matches"]}
    offline = json.loads((RAW / "offline_candidates.json").read_text(encoding="utf-8"))
    todo = {sku: rows[sku] for sku in rows if sku not in done and "title_names_other_manufacturer" not in rows[sku]["flags"]}
    budget = {
        "declared_at": now(), "host": "hyperx.com", "max_requests_total": MAX_REQUESTS, "max_sitemap_requests": MAX_SITEMAP,
        "max_product_page_requests": MAX_PAGES, "sitemap_index": SITEMAP_INDEX, "order": ["saved-link candidate pages", "sitemap index", "product sitemaps", "sitemap-candidate pages"],
        "url_sources_allowed": ["links saved on official pages (Stage 11 / 11.1)", "<loc> entries of the sitemap index declared in robots.txt"],
        "forbidden": ["URL built from a pattern", "site search", "collection paging", "variant id guessing", "any other host"],
        "stop_rule": "first 401/403/429/challenge halts the run; hyperx.com stays stopped via data/hyperx_fetch_log.json",
        "rows_in_scope": len(rows), "rows_already_confirmed_offline": sorted(done), "rows_skipped_before_any_request": sorted(set(rows) - set(todo) - done),
        "script": "reports/source_census_2026-09-24_stage18/scripts/03_live_discovery.py",
    }
    (RAW / "budget_predeclaration.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run = Run()
    adapter = HyperXAdapter(session=object(), fetch_log_path=RAW / "unused_fetch_log.json")
    if run.fetcher._probe._stopped_hosts & {"hyperx.com", "www.hyperx.com"}:
        (RAW / "live_discovery_result.json").write_text(json.dumps({"halted": "hyperx.com already stopped in data/hyperx_fetch_log.json", "requests": 0}, indent=2) + "\n", encoding="utf-8")
        print("host already stopped: 0 requests")
        return

    results: list[dict] = []
    tried_urls: dict[str, list[str]] = {}

    # Phase A: candidate pages whose links are already saved from official pages.
    by_url: dict[str, list[str]] = {}
    for item in offline["items"]:
        sku = item["seller_sku"].upper()
        if sku in todo and item["candidates"]:
            url = "https://hyperx.com" + item["candidates"][0]["path"]
            by_url.setdefault(url, []).append(sku)
    for url, skus in by_url.items():
        results += verify(adapter, rows, run, url, skus)
        tried_urls[url] = skus
        if run.halted:
            break
    resolved = {r["seller_sku"] for r in results if r["outcome"] == "accepted"}

    # Phase B: the sitemap the robots.txt declares -> product sitemaps -> slugs -> candidates for the rest.
    sitemap_slugs: list[str] = []
    if not run.halted:
        index = run.get(SITEMAP_INDEX, "sitemap")
        if index is not None and index.http_status == 200:
            children = [u for u in LOC.findall(index.diagnostic_text) if "product" in urlsplit(u).path.lower() and urlsplit(u).hostname in ALLOWED_HOSTS]
            for child in children[: MAX_SITEMAP - 1]:
                sitemap = run.get(child, "sitemap")
                if sitemap is None or sitemap.http_status != 200:
                    break
                sitemap_slugs += [hx_matching.slug_of(u) for u in LOC.findall(sitemap.diagnostic_text) if "/products/" in u]
    if sitemap_slugs and not run.halted:
        by_slug = {slug: slug for slug in sitemap_slugs}
        rest = [sku for sku in todo if sku not in resolved and sku not in {s for skus in tried_urls.values() for s in skus}]
        for sku in rest:
            found = hx_matching.candidates(todo[sku]["title"], sorted(by_slug), limit=1)
            if not found:
                results.append({"seller_sku": sku, "outcome": "no_candidate_in_sitemap", "detail": "no observed product slug carries every model token of the title"})
                continue
            url = "https://hyperx.com/products/" + found[0]
            if url in tried_urls:
                tried_urls[url].append(sku)
                continue
            tried_urls[url] = [sku]
        # verify each distinct sitemap candidate once, for every row that maps to it
        for url, skus in list(tried_urls.items()):
            if url in by_url:
                continue
            results += verify(adapter, rows, run, url, skus)
            if run.halted:
                break

    accepted = [r for r in results if r["outcome"] == "accepted"]
    output = {
        "finished_at": now(), "requests_made": run.requests, "sitemap_requests": run.sitemap_requests, "page_requests": run.page_requests,
        "halted": run.halted, "sitemap_product_slugs_seen": len(sitemap_slugs), "accepted_rows": len(accepted),
        "results": results, "fetch_log": run.log,
    }
    (RAW / "live_discovery_result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"requests={run.requests} (sitemap {run.sitemap_requests}, pages {run.page_requests}) halted={run.halted!r} accepted={len(accepted)} slugs={len(sitemap_slugs)}")
    for item in results:
        print(" ", item["seller_sku"], item["outcome"], item.get("match_level", ""), item.get("page_sku", ""), item.get("url", ""))


if __name__ == "__main__":
    main()
