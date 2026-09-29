"""Replay only Stage 52 affected LG rows from Stage 51.1 saved responses."""
from __future__ import annotations

import gzip
import io
import json
import shutil
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from product_tool import jobs, readiness, worker
from product_tool.adapters.common import SourceDocument
from product_tool.adapters.lg_browser_search import BrowserCandidate, BrowserSearchResult
from product_tool.adapters.lg_policy import default_lg_adapters
from product_tool.adapters.lg_support import LGSupportAdapter
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession

SOURCE = ROOT / "data" / "stage51_1_pilot"
TARGET = ROOT / "data" / "stage52_pilot"
ARTICLES = ("VC5316NNTS.APSQCIS", "32LQ63006LA.ARUG", "GXDCISLLK")


class SavedTransport:
    def __init__(self):
        self.headers = {}
        self.entries = {}
        self.unrecorded_requests = []
        for line in (SOURCE / "responses" / "index.jsonl").read_text(encoding="utf8").splitlines():
            entry = json.loads(line)
            if entry["saved_as"]:
                self.entries.setdefault(entry["url"], entry)

    def get(self, url, **kwargs):
        if url not in self.entries:
            self.unrecorded_requests.append(url)
            raise requests.ConnectionError(f"No saved response for {url}")
        entry = self.entries[url]
        body = gzip.open(SOURCE / "responses" / entry["saved_as"], "rb").read()
        is_pdf = body.startswith(b"%PDF-")
        response = requests.Response()
        response.status_code = entry["status"]
        response.url = entry["final_url"]
        response._content = body.decode("utf8").encode("latin1") if is_pdf else body
        response.headers["Content-Type"] = "application/pdf" if is_pdf else "text/html; charset=utf-8"
        response.encoding = "latin-1" if is_pdf else "utf-8"
        response.raw = io.BytesIO(response._content)
        return response


class SavedSearch:
    def close(self):
        pass

    def search(self, region, queries):
        if region != "ru":
            return BrowserSearchResult(region, queries[0], "route_not_available")
        query = queries[0]
        observed = {
            "GXDCISLLK": ("https://www.lg.com/ru/support/product/lg-GX.DCISLLK",),
            "32LQ63006LA.ARUG": ("https://www.lg.com/ru/support/product/lg-32LQ63006LA.ARUG",),
        }.get(query, ())
        return BrowserSearchResult(region, query,
            "candidates_found" if observed else "no_candidates",
            tuple(BrowserCandidate(url, "support") for url in observed))


class NoDealerNetwork:
    source_key = "dns"
    site_name = "DNS"
    document_urls = {}

    def find_source(self, article, **kwargs):
        return SourceDocument("dns", "DNS", "", match_level="dealer_url_needed",
                              evidence="Stage 52 offline replay: no new dealer request")

    def find_documents(self, *args, **kwargs):
        return [], "Stage 52 offline replay: no new dealer request"


def snapshot(db, article):
    import sqlite3
    with sqlite3.connect(db) as connection:
        product_id = connection.execute("SELECT id FROM products WHERE search_code=?", (article,)).fetchone()[0]
    job = jobs.list_jobs(db, product_id)[0]
    sources = jobs.get_source_pages(db, product_id)
    state = readiness.card_readiness(db, product_id)
    return {"article": article, "job_status": job["status"], "readiness": state["verdict"],
            "exact_product": [s["source_key"] for s in sources if s["source_key"] in ("lg_kz", "lg_ru") and s["match_level"] == "full_sku"],
            "support": [{"key": s["source_key"], "match": s["match_level"], "url": s["url"]}
                        for s in sources if s["source_key"].endswith("_support")],
            "specs": sum(x["status"] in {"full_sku_lg", "supplier_confirmed"}
                         for x in jobs.get_resolved(db, product_id)),
            "photos": state["official_gallery_from_exact_pages"],
            "manual": state["instruction"], "gaps": state["gaps"],
            "documents": len(jobs.get_documents(db, product_id))}


def main():
    TARGET.mkdir(exist_ok=True)
    db = TARGET / "stage52.sqlite3"
    if db.exists():
        raise SystemExit("Stage 52 replay database already exists; refusing to overwrite it")
    shutil.copy2(SOURCE / "stage51_1.sqlite3", db)
    shutil.copy2(SOURCE / "lg_fetch_log.json", TARGET / "lg_fetch_log.json")
    before = [snapshot(db, article) for article in ARTICLES]
    transport = SavedTransport()
    search = SavedSearch()
    for article in ARTICLES:
        import sqlite3
        with sqlite3.connect(db) as connection:
            product_id = connection.execute("SELECT id FROM products WHERE search_code=?", (article,)).fetchone()[0]
        jobs.enqueue(db, product_id, [1, 2, 3, 4, 6])
    adapter_factory = lambda: default_lg_adapters(
        TARGET, underlying_lg=transport, underlying_sulpak=transport,
        min_interval_seconds=0, browser_search=search)
    def support_factory():
        page_http = PolicyAwareSession(TARGET / "lg_fetch_log.json",
                                       allowed_hosts=("www.lg.com",), underlying=transport,
                                       min_interval_seconds=0)
        pdf_http = PolicyAwareSession(TARGET / "lg_fetch_log.json",
                                      allowed_hosts=("www.lg.com", "gscs-b2c.lge.com"),
                                      underlying=BinarySafeSession(transport),
                                      min_interval_seconds=0, max_bytes=25_000_000)
        return LGSupportAdapter(http=page_http, documents_http=pdf_http)
    for article in ARTICLES:
        if not worker.run_once(db, adapter_factory=adapter_factory,
                               dns_adapter_factory=NoDealerNetwork,
                               lg_support_adapter_factory=support_factory):
            raise RuntimeError(f"No queued job for {article}")
    after = [snapshot(db, article) for article in ARTICLES]
    import sqlite3
    with sqlite3.connect(db) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    result = {"mode": "offline saved-response replay", "articles": list(ARTICLES),
              "before": before, "after": after, "integrity": integrity,
              "foreign_key_violations": foreign_keys,
              "unrecorded_requests": sorted(set(transport.unrecorded_requests))}
    (Path(__file__).parent / "affected_replay.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    for row in after:
        print(row["article"], row["job_status"], row["readiness"],
              row["specs"], row["photos"], row["documents"], flush=True)
    print("integrity", integrity, "foreign_keys", foreign_keys)


if __name__ == "__main__":
    main()
