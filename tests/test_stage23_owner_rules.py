"""Stage 23: the owner's four answers after the second LG pilot, as rules with tests (offline).

1. A market tag "_KZ" / "_SU" is dropped only to FIND the candidate page; the match stays base_model until the official content shows the full article.
2. A support URL that contains the full article proves nothing; the support page must itself name that article as its product.
3. When LG Kazakhstan and LG Russia differ, no value is chosen: both sources stay and the field goes to review.
4. A Russian instruction whose text names no model is accepted only with content proof of a Russian instruction, an official support page that names the exact article
   on a product page that shows it, and no conflicting model in the text -- and it is marked as tied by the support page, not by the PDF.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from product_tool import jobs, readiness, worker
from product_tool.adapters import lg_documents_adapter as module
from product_tool.adapters.common import SourceDocument
from product_tool.adapters.lg import LG_KZ_SITEMAP, LGAdapter, lg_base_model
from product_tool.adapters.lg_documents import assess_document, conflicting_models
from product_tool.adapters.lg_documents_adapter import SUPPORT_TIE_NOTE, LGRUDocumentAdapter, support_page_ties_article

from coverage_controls import FixtureSession
from test_lg_workflow import StaticAdapter, seed_product, source
from test_stage21_lg_fixes import D3DifferentQuantitiesKeepDifferentNames, _NoDealer, official_doc
from test_stage22_documents import DOCS, MS_SUPPORT, XL7S_SUPPORT, Transport, client, ru_page


class MarketTagIsOnlyForFindingThePage(unittest.TestCase):
    def test_the_tag_is_dropped_for_the_base_model_and_only_kz_and_su(self):
        table = {"43LM5772PLA_KZ": "43LM5772PLA", "50QNED816QA_SU": "50QNED816QA", "DC90V9V9W.ABWPCOM_KZ": "DC90V9V9W", "43LM5772PLA": "43LM5772PLA", "A9K_MAX1": "A9K_MAX1",
                 "XX100_RU": "XX100_RU", "24MR400-B.ARUQ": "24MR400-B", "abc.xy_KZ": "ABC.XY"}
        for full, base in table.items():
            self.assertEqual(lg_base_model(full), base, full)

    def kz(self, page_text, slug="43lm5772pla"):
        url = f"https://www.lg.com/kz/tv/{slug}/"
        html = f"<html><body><h1>LG {page_text}</h1><section id='pdp-overview-section'><p>{page_text}</p></section><section id='pdp-specs-section'></section></body></html>"
        return FixtureSession({LG_KZ_SITEMAP: (200, f"<urlset><url><loc>{url}</loc></url></urlset>"), url: (200, html)})

    def test_the_page_is_found_through_the_base_model_and_stays_base_model(self):
        doc = LGAdapter(self.kz("Телевизор 43LM5772PLA"), clock=lambda: 0.0).find_source("43LM5772PLA_KZ", deadline=1e9)
        self.assertEqual((doc.match_level, doc.found_model), ("base_model", "43LM5772PLA"))
        self.assertNotEqual(doc.match_level, "full_sku")

    def test_only_the_full_article_on_the_official_page_makes_it_exact(self):
        doc = LGAdapter(self.kz("Телевизор 43LM5772PLA_KZ"), clock=lambda: 0.0).find_source("43LM5772PLA_KZ", deadline=1e9)
        self.assertEqual(doc.match_level, "full_sku")

    def test_a_tagged_article_with_a_base_page_ends_in_review_not_done(self):
        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "b.sqlite3"
            product = seed_product(database, sku="43LM5772PLA_KZ")
            jobs.enqueue(database, product, [1, 3])
            doc = LGAdapter(self.kz("Телевизор 43LM5772PLA"), clock=lambda: 0.0).find_source("43LM5772PLA_KZ", deadline=1e9)
            doc.source_key, doc.site_name = "lg_kz", "LG Казахстан"
            worker.run_once(database, lambda: (StaticAdapter(doc), StaticAdapter(SourceDocument("sulpak", "Sulpak", "", match_level="unknown"))), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
            self.assertEqual(jobs.list_jobs(database, product)[0]["status"], "needs_review")
            self.assertIn("no_official_full_sku_page", readiness.card_readiness(database, product)["blocking_gaps"])


class SupportPageMustNameTheArticle(unittest.TestCase):
    def html(self, model):
        return f'<div class="support-product-area"><div class="text-block"><div class="model">{model}</div></div></div>'

    def test_the_printed_product_is_the_article_or_the_article_with_a_regional_suffix(self):
        self.assertEqual(support_page_ties_article(self.html("A9N-MASTERX"), "A9N-MASTERX")[0], True)
        self.assertEqual(support_page_ties_article(self.html("50UT91006LA.ARUG"), "50UT91006LA")[0], True)
        self.assertEqual(support_page_ties_article(self.html("24MR400-B.ARUQ"), "24MR400-B.ARUQ")[0], True)

    def test_a_different_or_shorter_product_does_not_tie(self):
        self.assertFalse(support_page_ties_article(self.html("24MR400-B"), "24MR400-B.ARUQ")[0])  # the page names only the base model
        self.assertFalse(support_page_ties_article(self.html("A9N-MASTERY"), "A9N-MASTERX")[0])
        self.assertFalse(support_page_ties_article(self.html("A9N-MASTERX2"), "A9N-MASTERX")[0])
        self.assertFalse(support_page_ties_article("<html><body>A9N-MASTERX</body></html>", "A9N-MASTERX")[0])  # the text elsewhere on the page is not the product heading
        self.assertFalse(support_page_ties_article(self.html("A9N-MASTERX"), "")[0])

    def test_a_url_containing_the_article_is_not_evidence(self):
        with TemporaryDirectory() as tmp:
            transport = Transport()
            session = client(transport, Path(tmp) / "log.json")
            adapter = LGRUDocumentAdapter(session, documents_http=session, clock=lambda: 0.0)
            page = ru_page("audio/lg-xl7s")
            page.found_model = "XL7S.NOSUCH"  # an article the support heading ("XL7S") does not name
            self.patch_text(lambda pages, tokens: {"accepted": False, "kind": "instruction_model_not_named", "regulatory": False, "names_model": [], "model_masks": [], "model_evidence": "none",
                                                   "conflicting_models": [], "instruction_markers": [], "text_chars": 9, "languages": {"russian_instruction": True, "present": ["ru"], "letters_by_language": {"ru": 9000}}})
            try:
                documents, _ = adapter.find_documents(page, "XL7S", deadline=1e9)
            finally:
                self.restore()
        self.assertEqual(documents, [])
        self.assertFalse(adapter.reports[0]["support_page_ties_full_article"])

    def patch_text(self, fake):
        self._original = module.assess_document
        module.assess_document = fake

    def restore(self):
        module.assess_document = self._original


RUSSIAN_NO_MODEL = ("Руководство пользователя. Меры предосторожности и безопасность. Перед использованием внимательно прочитайте инструкцию. Нажмите кнопку питания и подключите "
                    "устройство. Не допускайте попадания воды. Эксплуатация изделия. ") * 60


class RussianInstructionTiedBySupportPage(unittest.TestCase):
    def run_adapter(self, support_url_page, sku_path, model, found_model, pages, match_level="full_sku"):
        original_pdf, transport = module._pdf_pages, Transport()
        module._pdf_pages = lambda data: pages
        try:
            with TemporaryDirectory() as tmp:
                session = client(transport, Path(tmp) / "log.json")
                adapter = LGRUDocumentAdapter(session, documents_http=session, clock=lambda: 0.0)
                page = ru_page(sku_path)
                page.found_model, page.match_level = found_model, match_level
                documents, reason = adapter.find_documents(page, model, deadline=1e9)
                return documents, reason, adapter.reports[0]
        finally:
            module._pdf_pages = original_pdf

    def test_the_content_proves_a_russian_instruction_and_the_support_page_names_the_article_so_it_is_accepted_and_marked(self):
        documents, reason, report = self.run_adapter(XL7S_SUPPORT, "audio/lg-xl7s", "XL7S", "XL7S", [RUSSIAN_NO_MODEL])
        self.assertEqual(reason, "")
        self.assertEqual([(d.language, d.title.endswith(SUPPORT_TIE_NOTE)) for d in documents], [("Русский", True)])
        self.assertEqual(report["files"][0]["state"], "instruction_confirmed_by_support_page")
        self.assertTrue(report["support_page_ties_full_article"])

    def test_a_product_page_that_does_not_show_the_full_article_is_not_enough(self):
        documents, reason, report = self.run_adapter(XL7S_SUPPORT, "audio/lg-xl7s", "XL7S", "XL7S", [RUSSIAN_NO_MODEL], match_level="base_model")
        self.assertEqual(documents, [])
        self.assertFalse(report["support_page_ties_full_article"])

    def test_a_text_that_is_not_a_russian_instruction_is_not_accepted_through_the_support_page(self):
        english = ("Please read this manual carefully before operating your set and retain it for future reference. Safety instructions and installing the product. ") * 40
        documents, _, _ = self.run_adapter(XL7S_SUPPORT, "audio/lg-xl7s", "XL7S", "XL7S", [english])
        self.assertEqual(documents, [])

    def test_a_conflicting_model_in_the_text_blocks_acceptance(self):
        text = RUSSIAN_NO_MODEL + " Модель MS2033GAS и MS2033G*."
        documents, _, report = self.run_adapter(MS_SUPPORT, "microwaves/lg-ms2032gas", "MS2032GAS", "MS2032GAS", [text])
        self.assertEqual(documents, [])
        self.assertEqual(report["files"][0]["assessment"]["kind"], "instruction_conflicting_model")
        self.assertIn("MS2033GAS", report["files"][0]["assessment"]["conflicting_models"])

    def test_conflicting_models_are_siblings_only_not_the_model_itself_or_its_family(self):
        self.assertEqual(conflicting_models("MS2033GAS", ["MS2032GAS"]), ["MS2033GAS"])
        self.assertEqual(conflicting_models("MS2032GAS MS203**** MS2032", ["MS2032GAS"]), [])
        self.assertEqual(conflicting_models("Русский текст с кодом 65UT81*", ["55UT81006LA"]), [])  # another screen size is another first characters
        self.assertEqual(assess_document([RUSSIAN_NO_MODEL + " F2J3HS1W"], ["F2J3WS1W"])["kind"], "instruction_conflicting_model")

    def test_a_named_model_still_needs_no_support_page_tie(self):
        text = RUSSIAN_NO_MODEL + " XL7S"
        documents, _, report = self.run_adapter(XL7S_SUPPORT, "audio/lg-xl7s", "XL7S", "", [text], match_level="base_model")
        self.assertEqual([d.language for d in documents], ["Русский"])
        self.assertFalse(documents[0].title.endswith(SUPPORT_TIE_NOTE))  # tied by the text itself, so no marker
        self.assertEqual(report["files"][0]["state"], "instruction_confirmed_by_content")


class RegionalDisagreementKeepsBothSources(unittest.TestCase):
    def test_no_value_is_chosen_both_sources_stay_and_the_field_goes_to_review(self):
        with TemporaryDirectory() as tmp:
            database = Path(tmp) / "b.sqlite3"
            product = seed_product(database)
            jobs.enqueue(database, product, [1, 3, 4])
            kz = source("lg_kz", "full_sku", [("Цвет корпуса", "платиновое серебро")], site_name="LG Казахстан")
            ru = source("lg_ru", "full_sku", [("Цвет корпуса", "темно-серебристый")], site_name="LG Россия")
            worker.run_once(database, lambda: (StaticAdapter(kz), StaticAdapter(ru), StaticAdapter(SourceDocument("sulpak", "Sulpak", "", match_level="unknown"))), clock=lambda: 0, dns_adapter_factory=lambda: _NoDealer())
            resolved = {r["normalized_name"]: r for r in jobs.get_resolved(database, product)}
            row = resolved["color__body"]
            self.assertEqual((row["selected_value"], row["status"], bool(row["conflict"])), ("", "official_regions_conflict", True))
            facts = {(f["source_key"], f["normalized_value"]) for f in jobs.get_facts(database, product) if f["normalized_name"] == "color__body"}
            self.assertEqual(facts, {("lg_kz", "платиновое серебро"), ("lg_ru", "темно-серебристый")})
            self.assertEqual(jobs.list_jobs(database, product)[0]["status"], "needs_review")
            self.assertIn("unresolved_conflicts", readiness.card_readiness(database, product)["blocking_gaps"])


if __name__ == "__main__":
    unittest.main()
