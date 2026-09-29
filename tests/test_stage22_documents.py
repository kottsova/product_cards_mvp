"""Stage 22: the LG Russia documents route. A candidate link, a reachable file and an instruction confirmed by content are three separate
states; the language is read from the file's own text, never from the label the page prints next to the link.

Offline. Fixtures are the responses the Stage 22 probe saved (support pages, PDFs) and the Stage 21 saved LG Russia product pages.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

from product_tool import jobs, readiness, worker
from product_tool.adapters.common import SourceDocument
from product_tool.adapters.lg_documents import BinarySafeSession, assess_document, document_bytes, document_languages, looks_like_pdf
from product_tool.adapters.lg_documents_adapter import LGRUDocumentAdapter, MAX_FILES_PER_PRODUCT, fetch_order, support_candidates
from product_tool.adapters.lg_policy import DOCUMENT_HOSTS, default_lg_adapters
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, request_budget

from test_lg_workflow import StaticAdapter, seed_product, source
from test_stage21_lg_fixes import _NoDealer, official_doc

ROOT = Path(__file__).resolve().parents[1]
S21 = ROOT / "reports/source_census_2026-09-24_stage21"
S22 = ROOT / "reports/source_census_2026-09-24_stage22"


def saved(directory: Path) -> dict[str, tuple[int, str]]:
    pages = {}
    for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["saved_as"]:
            with gzip.open(directory / entry["saved_as"], "rt", encoding="utf-8", newline="") as handle:
                pages[entry["url"]] = (entry["status"], handle.read())
    return pages


DOCS = saved(S22 / "docs_probe/responses")
RU_PAGES = {**saved(S21 / "probe/responses"), **saved(S21 / "verify/responses")}
XL7S_SUPPORT = "https://www.lg.com/ru/support/product/lg-XL7S.DRUSLLK"
MS_SUPPORT = "https://www.lg.com/ru/support/product/lg-MS2032GAS.BBKQCIS"
XL7S_MANUAL = "https://gscs-b2c.lge.com/open/downloadFile?fileId=3EAQjr62q61X0tBLZXc2pg"
XL7S_QUICK = "https://gscs-b2c.lge.com/open/downloadFile?fileId=GCG3kvyydm3cBKtc25zD1w"
MS_KAZAKH_PDF = "https://gscs-b2c.lge.com/open/downloadFile?fileId=MTEhHDZ1oogP22Kj48lw"
MS_ZIP = "https://gscs-b2c.lge.com/downloadFile?fileId=DgkBn9WDxL5ki4F60G4N9w"


class _Response:
    """A real requests response shape over raw bytes, as the policy-aware client reads it (stream + iter_content + encoding)."""

    def __init__(self, url, data: bytes, content_type: str, status=200):
        self.url, self.status_code, self._data = url, status, data
        self.headers = {"Content-Type": content_type}
        self.history, self.encoding = (), "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self._data,))

    def close(self):
        pass


class Transport:
    """Serves saved pages (utf-8) and saved files (their exact bytes); anything else is refused, and every call is counted."""

    def __init__(self, blocked_hosts=()):
        self.headers, self.calls = {"User-Agent": "test"}, []
        self.blocked = set(blocked_hosts)

    def get(self, url, **kwargs):
        self.calls.append(url)
        if any(host in url for host in self.blocked):
            return _Response(url, b"", "text/html", 403)
        for table in (DOCS, RU_PAGES):
            if url in table:
                status, text = table[url]
                if url in (XL7S_MANUAL, XL7S_QUICK, MS_KAZAKH_PDF, MS_ZIP):
                    return _Response(url, text.encode("latin-1"), "application/pdf" if url != MS_ZIP else "application/octet-stream;charset=UTF-8", status)
                return _Response(url, text.encode("utf-8"), "text/html;charset=UTF-8", status)
        raise requests.ConnectionError(f"not recorded: {url}")


def client(transport, log):
    return PolicyAwareSession(log, allowed_hosts=DOCUMENT_HOSTS, underlying=BinarySafeSession(transport), min_interval_seconds=0.0, sleep=lambda _s: None, max_bytes=25_000_000)


def ru_page(sku_path: str) -> SourceDocument:
    url = f"https://www.lg.com/ru/{sku_path}"
    return SourceDocument("lg_ru", "LG Россия", url, match_level="full_sku", html=RU_PAGES[url][1])


def pdf_pages(url):
    import pypdf
    import io
    import logging
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    return [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(DOCS[url][1].encode("latin-1"))).pages]


class BytesSurviveThePolicyPath(unittest.TestCase):
    def test_a_pdf_comes_back_byte_for_byte_through_the_policy_session(self):
        recorded = json.loads((S22 / "raw/docs_c_result.json").read_text(encoding="utf-8"))["results"]
        expected = {r["href"]: r["file"]["sha256"] for r in recorded}
        with TemporaryDirectory() as tmp:
            session = client(Transport(), Path(tmp) / "log.json")
            for url in (XL7S_MANUAL, MS_KAZAKH_PDF):
                data = document_bytes(session.get(url))
                self.assertTrue(looks_like_pdf(data))
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected[url])

    def test_a_zip_package_is_reachable_but_not_a_pdf(self):
        with TemporaryDirectory() as tmp:
            data = document_bytes(client(Transport(), Path(tmp) / "log.json").get(MS_ZIP))
        self.assertFalse(looks_like_pdf(data))
        self.assertEqual(data[:2], b"PK")


class ContentDecidesNotTheLabel(unittest.TestCase):
    def test_the_xl7s_user_manual_is_a_russian_instruction_by_its_text(self):
        result = assess_document(pdf_pages(XL7S_MANUAL), ["XL7S"])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["kind"], "instruction_confirmed")
        self.assertTrue(result["languages"]["russian_instruction"])

    def test_a_file_labelled_russian_whose_text_is_kazakh_is_not_a_russian_instruction(self):
        result = assess_document(pdf_pages(MS_KAZAKH_PDF), ["MS2032GAS", "MS2032GAS"])
        self.assertEqual(result["languages"]["present"], ["kk"])
        self.assertFalse(result["languages"]["russian_instruction"])
        self.assertEqual(result["names_model"], [])  # the exact model is not printed ...
        self.assertEqual((result["model_evidence"], result["model_masks"]), ("family_mask", ["MS203****"]))  # ... only the family mask, which is weaker and is reported as such
        self.assertTrue(result["accepted"])  # an instruction of that family -- in Kazakh

    def test_a_multi_language_quick_guide_counts_russian_only_for_its_russian_sections(self):
        result = assess_document(pdf_pages(XL7S_QUICK), ["XL7S"])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["languages"]["present"], ["en", "kk", "ru", "uk"])
        self.assertTrue(result["languages"]["russian_instruction"])  # its Russian sections carry real usage steps

    def test_a_legal_notice_in_russian_is_not_a_russian_instruction(self):
        notice = ("Заявление о соответствии. Настоящим LG Electronics заявляет, что радиооборудование соответствует требованиям Директивы. Полный текст заявления о соответствии "
                  "доступен по следующему интернет-адресу в сети. ") * 3
        english = ("Please read this manual carefully before operating your set and retain it for future reference. Some of the content in this manual may differ from your product. ") * 12
        languages = document_languages([notice, english])
        self.assertTrue(languages["russian_present"])
        self.assertFalse(languages["russian_instruction"])

    def test_a_conformity_declaration_is_regulatory_even_when_it_names_the_model(self):
        text = "ДЕКЛАРАЦИЯ О СООТВЕТСТВИИ\n" + "Изделие XL7S соответствует техническому регламенту. " * 30
        result = assess_document([text], ["XL7S"])
        self.assertEqual((result["accepted"], result["kind"]), (False, "regulatory_excluded"))

    def test_an_instruction_that_only_contains_a_compliance_notice_is_not_regulatory(self):
        text = "Руководство пользователя\nМеры предосторожности и безопасность. Перед использованием внимательно прочитайте инструкцию.\nXL7S\n" + "Заявление о соответствии. " * 5
        self.assertTrue(assess_document([text], ["XL7S"])["accepted"])

    def test_a_document_that_never_names_the_model_is_not_confirmed(self):
        text = "Руководство пользователя. Меры предосторожности. Перед использованием внимательно прочитайте инструкцию. " * 10
        self.assertFalse(assess_document([text], ["XL7S"])["accepted"])

    def test_nothing_is_read_from_a_name_or_url(self):
        self.assertEqual(document_languages([""])["present"], [])
        self.assertFalse(document_languages(["ru_manual_RUSSIAN.pdf " * 3])["russian_instruction"])


class ModelEvidenceTiers(unittest.TestCase):
    BODY = "Руководство пользователя. Меры предосторожности и безопасность. Перед использованием внимательно прочитайте инструкцию. Нажмите кнопку и подключите устройство. " * 4

    def test_the_exact_model_beats_a_family_mask(self):
        result = assess_document([self.BODY + " F2J3WS1W F2J3WS**"], ["F2J3WS1W"])
        self.assertEqual((result["model_evidence"], result["model_masks"]), ("exact", []))

    def test_a_family_mask_names_the_family_of_the_model(self):
        for text, model in (("F2J3WS**", "F2J3WS1W"), ("MW23R3****", "MW23R35GIB"), ("VC53*******", "VC5316NNTS"), ("65UT80*", "65UT80006LA"), ("F2T3H***", "F2T3HS6W")):
            result = assess_document([self.BODY + " " + text], [model])
            self.assertEqual(result["model_evidence"], "family_mask", (text, model))
            self.assertTrue(result["accepted"])

    def test_a_mask_of_another_family_or_a_too_short_prefix_is_not_evidence(self):
        for text, model in (("F2J3HS**", "F2J3WS1W"), ("F2J*", "F2J3WS1W"), ("MW23D3****", "MW23R35GIB"), ("65UT81*", "65UT80006LA")):
            result = assess_document([self.BODY + " " + text], [model])
            self.assertEqual(result["model_evidence"], "none", (text, model))
            self.assertFalse(result["accepted"])

    def test_an_instruction_that_never_names_the_model_is_reported_not_accepted(self):
        result = assess_document([self.BODY], ["A9N-MASTERX"])
        self.assertEqual((result["kind"], result["accepted"]), ("instruction_model_not_named", False))

    def test_a_declaration_never_becomes_an_instruction_through_a_mask(self):
        text = "ДЕКЛАРАЦИЯ О СООТВЕТСТВИИ\n" + "Изделие F2J3WS** соответствует регламенту. " * 30
        self.assertEqual(assess_document([text], ["F2J3WS1W"])["kind"], "regulatory_excluded")


class NotNamedRussianInstructionIsReportedNotSaved(unittest.TestCase):
    def test_the_second_file_is_not_fetched_when_a_russian_instruction_was_found_but_not_tied_to_the_model(self):
        import product_tool.adapters.lg_documents_adapter as module

        original = module.assess_document
        module.assess_document = lambda pages, tokens: {"accepted": False, "kind": "instruction_model_not_named", "regulatory": False, "names_model": [], "model_masks": [], "model_evidence": "none",
                                                        "instruction_markers": [], "text_chars": 10, "languages": {"russian_instruction": True, "present": ["ru"], "letters_by_language": {"ru": 9000}}}
        try:
            transport = Transport()
            with TemporaryDirectory() as tmp:
                session = client(transport, Path(tmp) / "log.json")
                adapter = LGRUDocumentAdapter(session, documents_http=session, clock=lambda: 0.0)
                documents, reason = adapter.find_documents(ru_page("microwaves/lg-ms2032gas"), "MS2032GAS", deadline=1e9)
        finally:
            module.assess_document = original
        self.assertEqual(documents, [])
        self.assertEqual(adapter.reports[0]["outcome"], "russian_instruction_model_not_named")
        self.assertEqual(len([c for c in transport.calls if "gscs-b2c" in c]), 1)
        self.assertIn("не сохранена", reason)


class TheSupportListIsOnlyCandidates(unittest.TestCase):
    def test_the_printed_list_of_both_products_is_read_as_candidate_links(self):
        xl7s = support_candidates(DOCS[XL7S_SUPPORT][1], XL7S_SUPPORT)
        self.assertEqual([(c["type"], c["label"], c["fetchable"]) for c in xl7s],
                         [("Краткое руководство", "English,Русский", True), ("Руководства пользователя", "Русский", True), ("Руководства пользователя", "Lithuanian", True)])
        ms = support_candidates(DOCS[MS_SUPPORT][1], MS_SUPPORT)
        self.assertEqual([(c["type"], c["fetchable"]) for c in ms], [("Краткое руководство", True), ("Online Manual", False), ("Руководства пользователя", True)])  # "_blank" is not an address

    def test_only_russian_labelled_guides_get_a_request_and_the_fuller_manual_goes_first(self):
        order = fetch_order(support_candidates(DOCS[XL7S_SUPPORT][1], XL7S_SUPPORT))
        self.assertEqual([c["href"] for c in order], [XL7S_MANUAL, XL7S_QUICK])

    def test_a_link_outside_lg_hosts_is_not_fetchable(self):
        html = '<div class="support-downloads"><ul class="list"><li class="manuals"><div class="type">Руководства пользователя</div><div class="name"><a href="https://evil.example/x.pdf">Русский</a></div></li></ul></div>'
        self.assertFalse(support_candidates(html, XL7S_SUPPORT)[0]["fetchable"])


class TheAdapterOnTheSavedRoute(unittest.TestCase):
    def adapter(self, transport, tmp):
        session = client(transport, Path(tmp) / "log.json")
        return LGRUDocumentAdapter(session, documents_http=session, clock=lambda: 0.0)

    def test_xl7s_gets_one_confirmed_russian_instruction_from_two_requests(self):
        transport = Transport()
        with TemporaryDirectory() as tmp:
            documents, reason = self.adapter(transport, tmp).find_documents(ru_page("audio/lg-xl7s"), "XL7S", deadline=1e9)
        self.assertEqual(reason, "")
        self.assertEqual([(d.language, d.direct_url, d.support_model, d.primary) for d in documents], [("Русский", XL7S_MANUAL, "XL7S.DRUSLLK", True)])
        self.assertEqual(transport.calls, [XL7S_SUPPORT, XL7S_MANUAL])  # the support page printed on the product page, then one file; the quick guide is not needed

    def test_ms2032gas_russian_label_but_kazakh_text_is_saved_as_kazakh(self):
        transport = Transport()
        with TemporaryDirectory() as tmp:
            adapter = self.adapter(transport, tmp)
            documents, reason = adapter.find_documents(ru_page("microwaves/lg-ms2032gas"), "MS2032GAS", deadline=1e9)
        self.assertEqual([(d.language, d.direct_url) for d in documents], [("Казахский", MS_KAZAKH_PDF)])  # saved, and its language is what the TEXT says, not the label
        self.assertIn("не на русском", reason)
        report = adapter.reports[0]
        self.assertEqual(report["outcome"], "instruction_confirmed_not_russian")
        self.assertEqual([f["state"] for f in report["files"]], ["instruction_confirmed_by_content", "reachable_but_not_a_complete_pdf"])
        self.assertEqual(report["files"][0]["assessment"]["languages"], ["kk"])
        self.assertLessEqual(len(transport.calls), 1 + MAX_FILES_PER_PRODUCT)

    def test_the_request_count_never_exceeds_one_support_page_plus_the_file_cap(self):
        for path, sku in (("audio/lg-xl7s", "XL7S"), ("microwaves/lg-ms2032gas", "MS2032GAS")):
            transport = Transport()
            with TemporaryDirectory() as tmp:
                self.adapter(transport, tmp).find_documents(ru_page(path), sku, deadline=1e9)
            self.assertLessEqual(len(transport.calls), 1 + MAX_FILES_PER_PRODUCT)

    def test_a_page_without_a_printed_support_link_makes_no_request(self):
        transport = Transport()
        page = SourceDocument("lg_ru", "LG Россия", "https://www.lg.com/ru/x/lg-y", match_level="full_sku", html="<html><a href='/ru/about'>x</a></html>")
        with TemporaryDirectory() as tmp:
            documents, reason = self.adapter(transport, tmp).find_documents(page, "Y", deadline=1e9)
        self.assertEqual((documents, transport.calls), ([], []))
        self.assertIn("не указана", reason)

    def test_a_block_on_the_document_host_stops_it_and_is_remembered(self):
        transport = Transport(blocked_hosts=("gscs-b2c.lge.com",))
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.json"
            session = client(transport, log)
            adapter = LGRUDocumentAdapter(session, documents_http=session, clock=lambda: 0.0)
            documents, _ = adapter.find_documents(ru_page("audio/lg-xl7s"), "XL7S", deadline=1e9)
            self.assertEqual(documents, [])
            self.assertEqual(len([c for c in transport.calls if "gscs-b2c" in c]), 1)  # the second candidate is never asked
            again = client(transport, log)  # a fresh process: the stop comes from the log
            self.assertEqual(again.get(XL7S_QUICK).status_code, 403)
            self.assertEqual(len([c for c in transport.calls if "gscs-b2c" in c]), 1)

    def test_the_budget_of_the_run_bounds_document_requests_too(self):
        transport = Transport()
        with TemporaryDirectory() as tmp:
            adapter = self.adapter(transport, tmp)
            budget = RequestBudget(max_per_row=1, max_total=1)
            with request_budget(budget):
                budget.begin_row("r")
                documents, _ = adapter.find_documents(ru_page("audio/lg-xl7s"), "XL7S", deadline=1e9)
        self.assertEqual((documents, len(transport.calls)), ([], 1))  # the support page used the only request; the file was refused


class TheWorkerReportsWhatWasConfirmed(unittest.TestCase):
    def test_default_adapters_use_the_document_adapter_with_a_byte_safe_document_host(self):
        with TemporaryDirectory() as tmp:
            _, ru, _, _ = default_lg_adapters(Path(tmp), clock=lambda: 0.0, browser_search=False)
            self.assertIsInstance(ru, LGRUDocumentAdapter)
            self.assertIsInstance(ru.documents_http, PolicyAwareSession)
            self.assertIsNot(ru.documents_http, ru.http)
            self.assertIn("lge.com", ru.documents_http.allowed_hosts)

    def test_a_non_russian_confirmed_instruction_is_saved_but_not_reported_as_russian(self):
        from product_tool.adapters.common import ProductDocument

        class Ru(StaticAdapter):
            def find_documents(self, document, base, *, deadline):
                return [ProductDocument("Руководства пользователя", "Казахский", "", "", "https://x/d.pdf", "https://x", base, "S3WER.X", document.url, True)], "Кандидатов: 3."

        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "b.sqlite3"
            product = seed_product(database)
            jobs.enqueue(database, product, [1, 3, 4, 6])
            ru_doc = source("lg_ru", "full_sku", [("Цвет", "Белый")], site_name="LG Россия")
            ru_doc.url = "https://www.lg.com/ru/x/lg-s3wer"
            worker.run_once(database, lambda: (StaticAdapter(official_doc()), Ru(ru_doc), StaticAdapter(source("sulpak", "full_sku", [("Цвет", "Белый")]))), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
            job = jobs.list_jobs(database, product)[0]
            events = [e["message"] for e in jobs.list_events(database, job["id"])]
            card = readiness.card_readiness(database, product)
        self.assertIn("instruction_language_not_russian", card["blocking_gaps"])
        self.assertFalse(card["instruction"]["russian"])
        self.assertTrue(any("подтверждено по содержимому: 1; русских: 0" in m for m in events), events)


if __name__ == "__main__":
    unittest.main()
