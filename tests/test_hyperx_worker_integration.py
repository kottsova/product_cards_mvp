"""Stage 14: offline replay of the full worker.run_once() pipeline for
HyperX -- the completion criteria this stage was built against:

  * an ordinary offline run produces cards for the two exact HyperX rows
    (9A273AA, A1KY6AA) with evidence and explicit gaps;
  * a mismatched regional keyboard variant never gets exact_variant;
  * the dealer (DNS) fallback is only ever asked about fields HyperX itself
    did not already fill.

Every test injects a HyperXAdapter seeded with a synthetic fixture and an
explicit urls dict (dependency injection, exactly like the existing
LG/Sulpak/DNS worker tests) -- no real network, no real hyperx.com URL is
claimed anywhere. No network access is used anywhere in this file.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from product_tool import jobs, worker
from product_tool.adapters.dns import DnsAdapter
from product_tool.adapters.hyperx import HyperXAdapter

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage14_hyperx"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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
    """Stands in for DNS in these tests -- HyperX's own official coverage
    is what's under test, not the dealer fallback's own behavior (already
    covered by tests/test_dns_fallback.py)."""
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


def seed_product(database: Path, *, sku: str, name: str, category: str = "Микрофоны") -> int:
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


class OfflineReplayTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "batches.sqlite3"

    def _run(self, *, sku: str, name: str, page_url: str, fixture: str) -> int:
        product = seed_product(self.database, sku=sku, name=name)
        jobs.enqueue(self.database, product, [1, 3, 4, 6])
        session = FakeSession({page_url: FakeResponse(page_url, read(fixture))})
        hyperx_factory = lambda: HyperXAdapter(session, clock=lambda: 0, urls={sku: page_url}, fetch_log_path=_tmp_log_path(self))
        self.assertTrue(worker.run_once(
            self.database, clock=lambda: 0,
            dns_adapter_factory=lambda: NoOpDnsAdapter(),
            hyperx_adapter_factory=hyperx_factory,
        ))
        return product

    def test_quadcast_2s_card_is_done_with_evidence_and_explicit_gaps(self):
        product = self._run(
            sku="9A273AA", name="Микрофон для пк игровой QuadCast 2S Black",
            page_url="https://hyperx.com/products/hyperx-quadcast-2s-black",
            fixture="quadcast_2s_black_9a273aa_synthetic.html",
        )
        job = jobs.list_jobs(self.database, product)[0]
        self.assertEqual(job["status"], "done")

        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertEqual(pages["hyperx"]["match_level"], "exact_variant")
        self.assertIn("exact_variant", pages["hyperx"]["evidence"])

        facts = jobs.get_facts(self.database, product)
        self.assertTrue(facts)  # real characteristics were saved, not just identity

        photos = jobs.get_photo_candidates(self.database, product, include_excluded=False)
        self.assertTrue(photos)
        for photo in photos:
            self.assertNotIn("logo", photo["url"].lower())

        # The explicit gap: no manual/document was found (Quick Start Guide
        # mention in the fixture is not a link), and this must be visible,
        # not silently treated as complete.
        self.assertEqual(jobs.get_documents(self.database, product), [])

    def test_pulsefire_fuse_card_is_also_done(self):
        product = self._run(
            sku="A1KY6AA", name="Беспроводная мышь Pulsefire Fuse",
            page_url="https://hyperx.com/products/hyperx-pulsefire-fuse",
            fixture="pulsefire_fuse_a1ky6aa_synthetic.html",
        )
        job = jobs.list_jobs(self.database, product)[0]
        self.assertEqual(job["status"], "done")
        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertEqual(pages["hyperx"]["match_level"], "exact_variant")

    def test_mismatched_regional_keyboard_never_gets_exact_variant_and_goes_to_review(self):
        product = self._run(
            sku="7G7A4AA#ACB", name="Проводная клавиатура для ПК Alloy Rise 75 (Red switch) (RU)",
            page_url="https://hyperx.com/products/hyperx-alloy-rise-75-us",
            fixture="alloy_rise_75_aba_region_mismatch_synthetic.html",
        )
        job = jobs.list_jobs(self.database, product)[0]
        self.assertNotEqual(job["status"], "done")
        self.assertEqual(job["status"], "needs_review")

        pages = {p["source_key"]: p for p in jobs.get_source_pages(self.database, product)}
        self.assertNotEqual(pages["hyperx"]["match_level"], "exact_variant")
        self.assertEqual(pages["hyperx"]["match_level"], "base_code_confirmed")

    def test_dealer_fallback_is_only_asked_about_fields_hyperx_left_missing(self):
        # HyperX's own page has no video for the Pulsefire Fuse mouse and no
        # document for either product -- but it DOES have characteristics
        # and photos. The dealer fallback must only ever be asked about
        # what is genuinely still missing (documents here), matching the
        # existing _compute_missing_fields policy, unchanged by this stage.
        product = seed_product(self.database, sku="9A273AA", name="Микрофон для пк игровой QuadCast 2S Black")
        jobs.enqueue(self.database, product, [1, 3, 4, 6])
        page_url = "https://hyperx.com/products/hyperx-quadcast-2s-black"
        session = FakeSession({page_url: FakeResponse(page_url, read("quadcast_2s_black_9a273aa_synthetic.html"))})

        seen_missing_fields = {}

        class RecordingDnsAdapter(NoOpDnsAdapter):
            def find_source(self, search_code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
                seen_missing_fields["value"] = missing_fields
                return super().find_source(search_code, deadline=deadline, model_tokens=model_tokens, brand=brand, name=name, missing_fields=missing_fields)

        worker.run_once(
            self.database, clock=lambda: 0,
            dns_adapter_factory=lambda: RecordingDnsAdapter(),
            hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=lambda: 0, urls={"9A273AA": page_url}, fetch_log_path=_tmp_log_path(self)),
        )
        # Characteristics and photos were already found by HyperX -- only
        # the instruction/document category is genuinely still missing.
        self.assertEqual(seen_missing_fields["value"], ["инструкция"])


if __name__ == "__main__":
    unittest.main()
