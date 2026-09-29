"""Offline replay of the SAVED Samsung responses (Stages 24-25) for the ordinary worker path (Stage 26).

`Replay` is a requests-session double for PolicyAwareSession: it serves the saved page bodies and sitemaps under the addresses they were fetched from, serves a saved document as a stub PDF
(`%PDF-` plus the requested address), and REFUSES everything else with a ConnectionError, recording it. The PDFs themselves were pruned after Stages 24-25 (only their extracted text was kept), so
the text reader given to the adapter maps the stub back to that saved text; everything else (allowlist, redirect check, size cap, budget, stop log, byte handling) runs as in production.

No socket is opened anywhere here.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
S24 = ROOT / "reports/source_census_2026-09-25_stage24"
S25 = ROOT / "reports/source_census_2026-09-25_stage25"
S27 = ROOT / "reports/source_census_2026-09-25_stage27"
S28 = ROOT / "reports/source_census_2026-09-26_stage28"
S29 = ROOT / "reports/source_census_2026-09-26_stage29"
RESPONSE_DIRS = (S24 / "batch1/responses", S24 / "batch1b/responses", S25 / "batch2/responses", S27 / "batch4/responses", S28 / "dishwasher/responses", S28 / "route_study/responses", S29 / "batch5a/responses")
EXTRACT_DIRS = (S24, S25, S27, S28, S29)
DOCUMENT_HOST = "org.downloadcenter.samsung.com"
STUB = b"%PDF-1.7\n%replay:"


def _load():
    pages, documents, truncated = {}, {}, set()
    for directory in RESPONSE_DIRS:
        for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["saved_as"]:
                with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                    pages[entry["url"]] = (entry["status"], handle.read())
            elif DOCUMENT_HOST in entry["url"] and entry["status"] == 200:
                documents[entry["url"]] = entry["final_url"]
                if entry.get("truncated"):
                    truncated.add(entry["url"])          # the file was cut at the size cap: the replay serves a body that is not a complete PDF
                else:
                    truncated.discard(entry["url"])      # a later, complete fetch of the same file (the washer manual, Stage 25) replaces the cut one
    text, raw_bytes = {}, {}
    for base in EXTRACT_DIRS:
        index = base / "docs_extract/index.json"
        if index.exists():
            for record in json.loads(index.read_text(encoding="utf-8")):
                if record.get("text_file"):
                    with gzip.open(base / "docs_extract" / record["text_file"], "rt", encoding="utf-8") as handle:
                        text[record["url"]] = handle.read().split("\n\f\n")
                    raw_bytes[record["url"]] = record["bytes"]
    return pages, documents, text, truncated, raw_bytes


PAGES, DOCUMENTS, DOCUMENT_TEXT, TRUNCATED_DOCUMENTS, DOCUMENT_RAW_BYTES = _load()


class _Response:
    def __init__(self, url: str, data: bytes, content_type: str, status: int = 200):
        self.url, self.status_code, self._data = url, status, data
        self.headers = {"Content-Type": content_type}
        self.history, self.encoding = (), "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self._data,))

    def close(self):
        pass


class Replay:
    """Serves saved responses; every call is counted; an unsaved address is refused (never fetched)."""

    def __init__(self, blocked_hosts: tuple[str, ...] = (), extra_pages: dict[str, tuple[int, str]] | None = None, document_cap: int = 40_000_000):
        self.headers = {"User-Agent": "replay"}
        self.document_cap = document_cap          # a file bigger than the cap is served cut, as the policy session cuts it (the adapter's default cap is 40 MB)
        self.calls: list[str] = []
        self.refused: list[str] = []
        self.blocked = tuple(blocked_hosts)
        self.pages = {**PAGES, **(extra_pages or {})}

    def get(self, url, **kwargs):
        self.calls.append(url)
        if any(host in url for host in self.blocked):
            return _Response(url, b"", "text/html", 403)
        if url in self.pages:
            status, text = self.pages[url]
            return _Response(url, text.encode("utf-8"), "text/html;charset=UTF-8", status)
        if url in TRUNCATED_DOCUMENTS:
            return _Response(DOCUMENTS[url], b"<cut at the size cap>", "application/pdf")
        if url in DOCUMENTS and url in DOCUMENT_TEXT:
            if DOCUMENT_RAW_BYTES.get(url, 0) > self.document_cap:
                return _Response(DOCUMENTS[url], b"<cut at the size cap>", "application/pdf")
            return _Response(DOCUMENTS[url], STUB + url.encode("ascii", "replace"), "application/pdf")
        self.refused.append(url)
        raise requests.ConnectionError(f"not recorded: {url}")

    def pages_reader(self, data: bytes) -> list[str]:
        """The text of the saved document a stub stands for (the PDFs were pruned; their extracted text was kept)."""
        requested = data[len(STUB):].decode("ascii", "replace")
        return DOCUMENT_TEXT[requested]


def page_url(fragment: str) -> str:
    return next(u for u in PAGES if fragment in u and u.startswith("https://www.samsung.com/kz_ru"))


# ---------------------------------------------------------------- the ordinary worker path over the replay ---------------------------------

CATALOG = ROOT / "data/catalog_2026-09-21_filtered.xlsx"
# The eleven cards of Stages 24-25 (one per category; tablets have no suitable novelty): category, catalog article.
CARDS = (("Телевизоры", "QE48S85HAEXCE"), ("Смартфоны", "SM-A376EZAGINS"), ("Пылесосы", "VC18M21D0VG/EV"), ("Стиральные машины", "WD10T754CBX/LD"), ("Микроволновые печи", "MS23K3614AK/BW"),
         ("Холодильники", "RB31FERNDSA"), ("Духовые шкафы", "NV7B4120ZAS/WT"), ("Сплит-системы", "AR80F09CABWNER"), ("Варочные панели", "NZ64T3506AK/WT"), ("Мониторы", "LS24D300GAIXCI"), ("Саундбары", "HW-Q800D"))


_CATALOG_INDEX: dict[str, dict] = {}


CARDS4 = (("Машины посудомоечные", "DW60M5050BB/WT"), ("Сушильные машины", "DV16DG8600BVLD"), ("Колонки", "MX-ST50B"), ("Роботы-пылесосы", "VR50T95735W/EV"))


def catalog_units(articles: set[str]) -> dict[str, dict]:
    """The catalog rows of the given articles, read-only (the first row of each article). The catalog is read once per process."""
    if not _CATALOG_INDEX:
        from product_tool.coverage.catalog_units import load_catalog
        for unit in load_catalog(CATALOG).units:
            _CATALOG_INDEX.setdefault(unit.seller_sku, {"catalog_row": unit.row_number, "brand": unit.brand, "category": unit.category, "title": unit.title, "seller_sku": unit.seller_sku})
    return {article: _CATALOG_INDEX[article] for article in articles}


class NoNetworkSession:
    """The session the dealer adapter gets: any request is a failure, and it is counted (a dealer without a verified exact URL must make none)."""

    def __init__(self):
        self.headers: dict = {}
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        raise requests.ConnectionError("no dealer request is allowed without a verified exact URL")


def workbook_of(rows: list[list[str]]) -> bytes:
    from io import BytesIO
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet.title = "Товары"
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def run_products(workdir: Path, cards=CARDS, *, stages=(1, 2, 3, 4, 6), dealer_factory=None, replay: Replay | None = None, blocked_hosts: tuple[str, ...] = (), document_cap: int = 40_000_000, recorded_documents: dict | None = None) -> dict:
    """The ORDINARY path over the replay: an Excel book of catalog rows is uploaded to the web app, the draft is confirmed into a batch, a search job is created for every product (the product
    page's own POST), worker.run_once() processes the queue, and the batch is exported through the web route. Returns the per-card outcome, the export bytes and the transports' counters."""
    from fastapi.testclient import TestClient

    from product_tool import jobs, storage, worker
    from product_tool.adapters.dns import DnsAdapter
    from product_tool.adapters.samsung_source import default_samsung_adapter
    from product_tool.web import create_app

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    database = workdir / "batches.sqlite3"
    replay = replay or Replay(blocked_hosts=blocked_hosts, document_cap=document_cap)
    dealer_session = NoNetworkSession()
    units = catalog_units({article for _, article in cards})
    rows = [["Предмет", "Бренд", "Наименование", "Артикул продавца", "Модель"]] + [[units[a]["category"], units[a]["brand"], units[a]["title"], a, ""] for _, a in cards]
    with TestClient(create_app(workdir)) as client:
        uploaded = client.post("/upload", files={"file": ("samsung.xlsx", workbook_of(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, follow_redirects=False)
        assert uploaded.status_code == 303, uploaded.text
        draft_path = uploaded.headers["location"]
        form = {}
        for number, (_, article) in enumerate(cards, start=2):
            form.update({f"brand_{number}": units[article]["brand"], f"search_code_{number}": article, f"alternate_code_{number}": "", f"category_{number}": units[article]["category"]})
        confirmed = client.post(f"{draft_path}/confirm", data=form, follow_redirects=False)
        assert confirmed.status_code == 303, confirmed.text
        batch_id = confirmed.headers["location"].rsplit("/", 1)[-1]
        products = {p["search_code"]: p for p in storage.get_batch(database, batch_id)["products"]}
        for _, article in cards:
            started = client.post(f"/products/{products[article]['id']}/search", data={"stages": [str(n) for n in stages]}, follow_redirects=False)
            assert started.status_code == 303, started.text
        while worker.run_once(database, clock=lambda: 0.0,
                              samsung_adapter_factory=lambda: default_samsung_adapter(workdir, clock=lambda: 0.0, underlying=replay, min_interval_seconds=0.0, pages_reader=replay.pages_reader, document_max_bytes=document_cap, recorded_documents=recorded_documents),
                              dns_adapter_factory=dealer_factory or (lambda: DnsAdapter(dealer_session, clock=lambda: 0.0))):
            pass
        exported = client.get(f"/batches/{batch_id}/export.xlsx")
        assert exported.status_code == 200, exported.text[:200]
    outcomes = []
    for category, article in cards:
        product_id = products[article]["id"]
        job = jobs.list_jobs(database, product_id)[0]
        outcomes.append({"category": category, "article": article, "product_id": product_id, "job_id": job["id"], "status": job["status"], "message": job["message"]})
    return {"database": database, "outcomes": outcomes, "replay": replay, "dealer_session": dealer_session, "batch_id": batch_id, "export": exported.content}
