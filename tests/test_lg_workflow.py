"""Offline acceptance checks for exact LG matching and the queued web workflow."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.sax.saxutils import escape

from fastapi.testclient import TestClient
from openpyxl import Workbook
import requests

from product_tool import jobs, storage, worker
from product_tool.adapters.lg import (
    LGAdapter, LGSourceError, LookupResult, extract_lg_attributes,
    extract_lg_description, extract_lg_photos, lg_url_matches_article,
    match_kind,
)
from product_tool.web import create_app


TW_URL = "https://www.lg.com/kz/laundry/washing-machines/tw4v7eb1w/"
F2_URL = "https://www.lg.com/kz/laundry/washing-dryer-washing-machines/f2v5hg1w/"
S3_URL = "https://www.lg.com/kz/laundry/styler/s3wer/"
OTHER_URL = "https://www.lg.com/kz/laundry/styler/s3wer-blwpcom/"


def page_html(sku: str) -> str:
    return (
        '<html><head><meta property="og:description" content="LG overview"></head><body>'
        '<h1>Товар LG</h1>'
        '<section id="pdp-overview-section"><h2>Описание</h2><p>Точная модель.</p></section>'
        '<section id="pdp-specs-section"><div class="c-compare-selling--all">'
        '<div class="c-compare-selling__item">'
        '<span class="c-compare-selling__spec-name">Загрузка</span>'
        '<span class="c-compare-selling__spec-desc">11 кг</span></div>'
        '<div class="c-compare-selling__item">'
        '<span class="c-compare-selling__spec-name">Опция</span>'
        '<span class="c-compare-selling__spec-desc">Нет</span></div>'
        '</div></section>'
        '<div id="popSummaryGallery"><div id="tabpanel-image">'
        '<div class="c-gallery__display"><img src="/content/dam/lg/photo.jpg?size=300">'
        '</div></div></div>'
        '<script>var product = {"sku": "' + sku + '"};</script>'
        '</body></html>'
    )


class FakeResponse:
    def __init__(self, url: str, body: str, status_code: int = 200):
        self.url = url
        self.text = body
        self.content = body.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, pages: dict[str, str], *, fail_sitemap: bool = False):
        self.pages = pages
        self.fail_sitemap = fail_sitemap
        self.calls: list[str] = []

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.calls.append(url)
        if url.endswith("/sitemap.xml"):
            if self.fail_sitemap:
                raise requests.Timeout("timeout")
            locations = "".join(f"<url><loc>{escape(link)}</loc></url>" for link in self.pages)
            return FakeResponse(url, f"<urlset>{locations}</urlset>")
        return FakeResponse(url, self.pages.get(url, ""), 200 if url in self.pages else 404)


def workbook_bytes(brand: str, code: str) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Товары"
    sheet.append(["Бренд", "Артикул", "Название", "Категория"])
    sheet.append([brand, code, f"Модель {code}", "Стиральная машина"])
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


class LGAdapterTests(unittest.TestCase):
    def test_exact_url_and_sku_reject_related_bundle(self) -> None:
        bundle = "https://www.lg.com/kz/laundry/washer-and-dryer-set/tw4v7eb1w-dc90v5/"
        self.assertTrue(lg_url_matches_article(TW_URL, "TW4V7EB1W"))
        self.assertFalse(lg_url_matches_article(bundle, "TW4V7EB1W"))
        adapter = LGAdapter(FakeSession({
            bundle: page_html("TW4V7EB1W.DC90V5"),
            TW_URL: page_html("TW4V7EB1W.ABWPCOM.EEAK.KZ.C"),
        }))
        found = adapter.find_page("TW4V7EB1W")
        self.assertEqual(found.status, "exact")
        self.assertEqual(found.page_url, TW_URL)

    def test_region_suffix_requires_full_page_sku(self) -> None:
        exact = LGAdapter(FakeSession({S3_URL: page_html("S3WER.ALWPCOM.EEAK.KZ.C")}))
        found = exact.find_page("S3WER.ALWPCOM")
        self.assertEqual(found.status, "exact")
        self.assertEqual(found.page_url, S3_URL)

        other = LGAdapter(FakeSession({S3_URL: page_html("S3WER.BLWPCOM.EEAK.KZ.C")}))
        found = other.find_page("S3WER.ALWPCOM")
        self.assertEqual(found.status, "needs_review")
        self.assertEqual(found.page_url, "")
        self.assertEqual(found.candidate_urls, (S3_URL,))

    def test_extraction_keeps_sources_and_skips_no_values(self) -> None:
        adapter = LGAdapter(FakeSession({F2_URL: page_html("F2V5HG1W.ABWPCOM")}))
        page = adapter.fetch_page(F2_URL)
        self.assertEqual(match_kind(page, "F2V5HG1W"), "exact")
        self.assertIn("Точная модель.", extract_lg_description(page.soup))
        self.assertEqual(extract_lg_attributes(page.soup), {"Загрузка": "11 кг"})
        self.assertEqual(
            extract_lg_photos(page.soup, page.url),
            ["https://www.lg.com/content/dam/lg/photo.jpg"],
        )

    def test_site_failure_is_not_reported_as_not_found(self) -> None:
        adapter = LGAdapter(FakeSession({}, fail_sitemap=True))
        with self.assertRaises(LGSourceError):
            adapter.find_page("TW4V7EB1W")


class LGWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "batches.sqlite3"
        self.client = TestClient(create_app(self.root))
        self.addCleanup(self.client.close)

    def confirmed_product(self, brand: str = "LG", code: str = "TW4V7EB1W") -> int:
        uploaded = self.client.post(
            "/upload", files={"file": ("example.xlsx", workbook_bytes(brand, code), "application/octet-stream")},
            follow_redirects=False,
        )
        self.assertEqual(uploaded.status_code, 303)
        draft_path = uploaded.headers["location"]
        confirmed = self.client.post(
            f"{draft_path}/confirm",
            data={
                "brand_2": brand, "search_code_2": code,
                "alternate_code_2": "", "category_2": "Стиральная машина",
            },
            follow_redirects=False,
        )
        self.assertEqual(confirmed.status_code, 303, confirmed.text)
        batch_id = confirmed.headers["location"].rsplit("/", 1)[-1]
        return storage.get_batch(self.database, batch_id)["products"][0]["id"]

    def test_site_queues_then_worker_saves_sourced_results(self) -> None:
        product_id = self.confirmed_product()
        response = self.client.post(
            f"/products/{product_id}/search", data={"stages": ["2", "3", "4"]},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)
        queued = jobs.list_jobs(self.database, product_id)[0]
        self.assertEqual(queued["status"], "queued")
        self.assertFalse(jobs.get_result(self.database, product_id)["page_url"])
        self.assertIn("В очереди", self.client.get(f"/products/{product_id}").text)

        session = FakeSession({TW_URL: page_html("TW4V7EB1W.ABWPCOM.EEAK.KZ.C")})
        self.assertTrue(worker.run_once(self.database, lambda: LGAdapter(session)))
        finished = jobs.list_jobs(self.database, product_id)[0]
        self.assertEqual(finished["status"], "done")
        self.assertEqual(finished["stages"], [2, 3, 4])
        result = jobs.get_result(self.database, product_id)
        self.assertEqual(result["page_url"], TW_URL)
        self.assertEqual(result["attributes"], {"Загрузка": "11 кг"})
        self.assertEqual(len(result["photos"]), 1)
        self.assertEqual(result["sources"], {
            "link": TW_URL, "description": TW_URL,
            "attributes": TW_URL, "photos": TW_URL,
        })
        self.assertTrue(any(event["stage"] == 1 for event in jobs.list_events(self.database, finished["id"])))
        self.assertIn("Готово", self.client.get(f"/products/{product_id}").text)
        self.assertFalse(worker.run_once(self.database, lambda: LGAdapter(session)))

        with TestClient(create_app(self.root)) as restarted:
            self.assertIn("Готово", restarted.get(f"/products/{product_id}").text)
            self.assertIn("Точная модель.", restarted.get(f"/products/{product_id}").text)

    def test_uncertain_candidate_stops_before_extraction(self) -> None:
        product_id = self.confirmed_product(code="S3WER.ALWPCOM")
        jobs.enqueue(self.database, product_id, [1, 2, 3, 4])
        session = FakeSession({S3_URL: page_html("S3WER.BLWPCOM.EEAK.KZ.C")})
        worker.run_once(self.database, lambda: LGAdapter(session))
        self.assertEqual(jobs.list_jobs(self.database, product_id)[0]["status"], "needs_review")
        result = jobs.get_result(self.database, product_id)
        self.assertEqual(result["match_status"], "needs_review")
        self.assertFalse(result["description"])
        self.assertIn("Нужна проверка", self.client.get(f"/products/{product_id}").text)

    def test_missing_model_has_not_found_status(self) -> None:
        product_id = self.confirmed_product(code="UNKNOWN123")
        jobs.enqueue(self.database, product_id, [1])
        session = FakeSession({F2_URL: page_html("F2V5HG1W.ABWPCOM")})
        worker.run_once(self.database, lambda: LGAdapter(session))
        self.assertEqual(jobs.list_jobs(self.database, product_id)[0]["status"], "not_found")
        self.assertFalse(jobs.get_result(self.database, product_id)["page_url"])
        self.assertIn("Не найдено", self.client.get(f"/products/{product_id}").text)
    def test_worker_error_and_restart_recovery(self) -> None:
        product_id = self.confirmed_product()
        jobs.enqueue(self.database, product_id, [1])
        claimed = jobs.claim_next(self.database)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(jobs.recover_interrupted(self.database), 1)
        self.assertEqual(jobs.list_jobs(self.database, product_id)[0]["status"], "queued")
        worker.run_once(
            self.database, lambda: LGAdapter(FakeSession({}, fail_sitemap=True))
        )
        self.assertEqual(jobs.list_jobs(self.database, product_id)[0]["status"], "error")
        self.assertIn("sitemap", self.client.get(f"/products/{product_id}").text)

    def test_only_lg_and_one_active_job(self) -> None:
        product_id = self.confirmed_product(brand="Samsung")
        response = self.client.post(
            f"/products/{product_id}/search", data={"stages": "1"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("только для товаров LG", response.text)
        product_id = self.confirmed_product()
        jobs.enqueue(self.database, product_id, [1])
        with self.assertRaises(ValueError):
            jobs.enqueue(self.database, product_id, [2])


if __name__ == "__main__":
    unittest.main()