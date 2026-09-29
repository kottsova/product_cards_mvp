"""Stage 15: the real catalog-row -> official-URL -> fetch -> HyperXAdapter
-> identity/variant -> fields-with-evidence -> gaps -> card route, proven
against REAL saved Stage 11/11.1 captures (not Stage 14's synthetic
fixtures) and against production KNOWN_URLS itself, not an injected
override.

No new HTTP requests are made anywhere in this file: every page comes from
reports/source_census_2026-09-23_stage11(_1)/raw/*.html.txt, saved during
Stage 11's and Stage 11.1's own live research (see those stages' card.json
/ additional_rows_and_adapter_status.json for the human identity check this
file's assertions cross-validate against).

This file also locks in the Stage 15 correction to check_identity(): a
real Shopify page's JSON-LD `productID` is that platform's own internal
numeric id, not comparable to the catalog's seller article, and must never
be treated as a second identity anchor that has to agree with `sku`.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from product_tool import jobs, worker
from product_tool.adapters.hyperx import HyperXAdapter, KNOWN_URLS, check_identity
from product_tool.adapters.structured_page import extract_json_ld_product

ROOT = Path(__file__).resolve().parents[1]
STAGE11_RAW = ROOT / "reports/source_census_2026-09-23_stage11/raw"
STAGE11_1_RAW = ROOT / "reports/source_census_2026-09-23_stage11_1/raw"

MICROPHONE_URL = "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone"
MOUSE_URL = "https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse"
KEYBOARD_URL = "https://hyperx.com/products/hyperx-alloy-rise-75-mechanical-gaming-keyboard"


def real_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FakeResponse:
    """Stage 16: shaped for AccessProbe.probe() -- see test_hyperx_adapter.py's
    own FakeResponse docstring for why."""
    def __init__(self, url: str, text: str, status: int = 200, headers=None):
        self.url, self.text, self.status_code = url, text, status
        self.history = ()
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self.text.encode("utf-8"),))

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, pages: dict[str, FakeResponse]):
        self.pages = pages
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected network call to {url!r}")
        return self.pages[url]


def _tmp_log_path(case: unittest.TestCase) -> Path:
    tmp = TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    return Path(tmp.name) / "hyperx_fetch_log.json"


class NoOpDnsAdapter:
    source_key = "dns"
    site_name = "DNS"
    document_urls: dict[str, str] = {}

    def find_source(self, search_code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
        from product_tool.adapters.common import SourceDocument
        if missing_fields is not None and not missing_fields:
            return SourceDocument("dns", "DNS", "", match_level="not_needed", evidence="Всё уже найдено официальным источником.")
        return SourceDocument("dns", "DNS", "", match_level="unknown", evidence="Нет проверенного дилерского кандидата.")

    def find_documents(self, search_code, *, deadline, **kwargs):
        return [], "Дилерский документ не проверялся в этом тесте."


def seed_product(database: Path, *, sku: str, name: str, category: str) -> int:
    jobs.initialize(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO batches (id, filename, sheet_name, mapping_json, confirmed_at) VALUES ('b1','fixture.xlsx','Товары','{}','2026-01-01')"
        )
        cursor = connection.execute(
            "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
            "VALUES ('b1',2,?,?,?, '', ?,0,'[]','{}')",
            (name, "HYPERX", sku, category),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


# --------------------------------------------------------------------------
# 1. Identity, on real captures -- locks in the sku-vs-productID fix
# --------------------------------------------------------------------------

class RealCaptureIdentityTests(unittest.TestCase):
    def test_microphone_real_page_sku_matches_catalog_exactly(self):
        html = real_html(STAGE11_RAW / "hyperx_quadcast_2s_product_page.html.txt")
        fields = extract_json_ld_product(html, MICROPHONE_URL)
        result = check_identity(fields, catalog_code="9A273AA")
        self.assertEqual(result.level, "exact_variant")
        self.assertEqual(result.page_base, "9A273AA")

    def test_mouse_real_page_sku_matches_catalog_exactly(self):
        html = real_html(STAGE11_1_RAW / "hyperx_mouse_product_page.html.txt")
        fields = extract_json_ld_product(html, MOUSE_URL)
        result = check_identity(fields, catalog_code="A1KY6AA")
        self.assertEqual(result.level, "exact_variant")
        self.assertEqual(result.page_base, "A1KY6AA")

    def test_keyboard_real_page_is_a_confirmed_region_mismatch_not_exact(self):
        html = real_html(STAGE11_1_RAW / "hyperx_keyboard_product_page.html.txt")
        fields = extract_json_ld_product(html, KEYBOARD_URL)
        result = check_identity(fields, catalog_code="7G7A4AA#ACB")
        self.assertEqual(result.level, "base_code_confirmed")
        self.assertNotEqual(result.level, "exact_variant")
        self.assertEqual(result.page_base, "7G7A4AA")
        self.assertEqual(result.page_suffix, "ABA")  # catalog wants #ACB

    def test_productid_disagreeing_with_sku_is_no_longer_treated_as_a_conflict(self):
        # Real Shopify pages populate productID with their own internal
        # numeric id (unrelated to the merchant sku) -- this must not make
        # an otherwise-exact sku match report as unresolved/mismatch.
        html = real_html(STAGE11_RAW / "hyperx_quadcast_2s_product_page.html.txt")
        fields = extract_json_ld_product(html, MICROPHONE_URL)
        sku_field = next(f for f in fields if f.name == "sku")
        product_id_field = next(f for f in fields if f.name == "productID")
        self.assertEqual(sku_field.value, "9A273AA")
        self.assertNotEqual(product_id_field.value.upper(), sku_field.value.upper())


# --------------------------------------------------------------------------
# 2. Production KNOWN_URLS itself -- not an injected override
# --------------------------------------------------------------------------

class ProductionKnownUrlsTests(unittest.TestCase):
    def test_the_two_stage15_rows_are_still_known_in_production(self):
        # Stage 18 added 11 more and Stage 19 seven variant rows (each backed by reports/source_census_2026-09-24_stage18/
        # raw/accepted_urls.json); a coverage test pins the whole map to that file.
        self.assertEqual(len(KNOWN_URLS), 20)
        self.assertEqual(KNOWN_URLS["9A273AA"], MICROPHONE_URL)
        self.assertEqual(KNOWN_URLS["A1KY6AA"], MOUSE_URL)

    def test_the_mismatched_keyboard_row_is_not_in_production_known_urls(self):
        # 7G7A4AA#ACB's only found candidate page is a confirmed #ABA
        # (US-layout) mismatch -- never wired into production as if it
        # were a confirmed match for this row.
        self.assertNotIn("7G7A4AA#ACB", KNOWN_URLS)
        self.assertNotIn("7G7A4AA", KNOWN_URLS)


# --------------------------------------------------------------------------
# 3. Full offline replay through worker.run_once(), real captures, real URLs
# --------------------------------------------------------------------------

class FullCatalogRouteOfflineReplayTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "batches.sqlite3"

    def test_quadcast_2s_reaches_done_via_production_known_urls_and_a_real_page(self):
        product = seed_product(self.database, sku="9A273AA", name="Микрофон для пк игровой QuadCast 2S Black", category="Микрофоны")
        jobs.enqueue(self.database, product, [1, 3, 4, 6])
        html = real_html(STAGE11_RAW / "hyperx_quadcast_2s_product_page.html.txt")
        session = FakeSession({MICROPHONE_URL: FakeResponse(MICROPHONE_URL, html)})
        # No urls= override: this resolves the fetch URL from production
        # KNOWN_URLS itself, exactly as worker.py's real hyperx_adapter_factory
        # would construct it with no test double for the URL mapping.
        self.assertTrue(worker.run_once(
            self.database, clock=lambda: 0,
            dns_adapter_factory=lambda: NoOpDnsAdapter(),
            hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=lambda: 0, fetch_log_path=_tmp_log_path(self)),
        ))
        self.assertEqual(session.calls, [MICROPHONE_URL])
        job = jobs.list_jobs(self.database, product)[0]
        self.assertEqual(job["status"], "done")
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertEqual(pages["hyperx"]["match_level"], "exact_variant")
        self.assertTrue(jobs.get_facts(self.database, product))
        photos = jobs.get_photo_candidates(self.database, product, include_excluded=False)
        self.assertTrue(photos)
        for photo in photos:
            self.assertNotIn("logo", photo["url"].lower())
        # The genuine, still-open gap: no manual URL was ever found.
        self.assertEqual(jobs.get_documents(self.database, product), [])

    def test_pulsefire_fuse_reaches_done_via_production_known_urls_and_a_real_page(self):
        product = seed_product(self.database, sku="A1KY6AA", name="Беспроводная мышь Pulsefire Fuse", category="Мыши")
        jobs.enqueue(self.database, product, [1, 3, 4, 6])
        html = real_html(STAGE11_1_RAW / "hyperx_mouse_product_page.html.txt")
        session = FakeSession({MOUSE_URL: FakeResponse(MOUSE_URL, html)})
        self.assertTrue(worker.run_once(
            self.database, clock=lambda: 0,
            dns_adapter_factory=lambda: NoOpDnsAdapter(),
            hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=lambda: 0, fetch_log_path=_tmp_log_path(self)),
        ))
        self.assertEqual(session.calls, [MOUSE_URL])
        job = jobs.list_jobs(self.database, product)[0]
        self.assertEqual(job["status"], "done")
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertEqual(pages["hyperx"]["match_level"], "exact_variant")

    def test_keyboard_row_with_a_real_confirmed_mismatch_page_never_reaches_exact_variant(self):
        # 7G7A4AA#ACB has no production KNOWN_URLS entry (see
        # ProductionKnownUrlsTests) -- this proves the negative case
        # end-to-end with the real page content anyway, injecting the URL
        # the way a human-supplied candidate would be, exactly as Stage 14
        # did with a synthetic page.
        product = seed_product(self.database, sku="7G7A4AA#ACB", name="Проводная клавиатура для ПК Alloy Rise 75 (Red switch) (RU)", category="Клавиатуры")
        jobs.enqueue(self.database, product, [1, 3, 4, 6])
        html = real_html(STAGE11_1_RAW / "hyperx_keyboard_product_page.html.txt")
        session = FakeSession({KEYBOARD_URL: FakeResponse(KEYBOARD_URL, html)})
        worker.run_once(
            self.database, clock=lambda: 0,
            dns_adapter_factory=lambda: NoOpDnsAdapter(),
            hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=lambda: 0, urls={"7G7A4AA#ACB": KEYBOARD_URL}, fetch_log_path=_tmp_log_path(self)),
        )
        job = jobs.list_jobs(self.database, product)[0]
        self.assertNotEqual(job["status"], "done")
        self.assertEqual(job["status"], "needs_review")
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertNotEqual(pages["hyperx"]["match_level"], "exact_variant")
        self.assertEqual(pages["hyperx"]["match_level"], "base_code_confirmed")

    def test_a_row_with_no_known_url_gets_official_url_needed_and_zero_requests(self):
        # 20 of the 21 HyperX rows without a URL of record (the 21st is the region-mismatched keyboard) have no production KNOWN_URLS entry
        # at all -- this must never silently guess one.
        product = seed_product(self.database, sku="B9ZZZ00", name="Некий другой товар HyperX", category="Прочее")
        jobs.enqueue(self.database, product, [1, 3, 4, 6])
        session = FakeSession({})
        worker.run_once(
            self.database, clock=lambda: 0,
            dns_adapter_factory=lambda: NoOpDnsAdapter(),
            hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=lambda: 0, fetch_log_path=_tmp_log_path(self)),
        )
        self.assertEqual(session.calls, [])
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertEqual(pages["hyperx"]["match_level"], "official_url_needed")


if __name__ == "__main__":
    unittest.main()
