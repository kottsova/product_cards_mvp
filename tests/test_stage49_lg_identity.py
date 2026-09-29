from __future__ import annotations

from pathlib import Path
from contextlib import closing
from sqlite3 import connect
from tempfile import TemporaryDirectory
import hashlib
import unittest

from bs4 import BeautifulSoup

from product_tool import jobs, worker
from product_tool.adapters.lg import _product_designation, _support_page_sales_code
from product_tool.adapters.common import SourceDocument
from product_tool.fetch_history import latest_source_snapshot
from product_tool.lg_identity import (allows_evidence, article_has_variant, product_edges,
                                      structured_sales_relation, support_edges)
from product_tool.readiness import card_readiness

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "reports" / "lg_live_batch_2026-09-29_stage49" / "batches_before_stage49.sqlite3"
ARTICLE = "ON77DKDRUSLLK"


class LGIdentityGraphTests(unittest.TestCase):
    def test_main_sales_code_accepts_only_whole_model_and_suffix(self):
        self.assertEqual(structured_sales_relation(ARTICLE, "ON77DK.DRUSLLK.EEAK.KZ.C"), "exact")
        self.assertEqual(structured_sales_relation(ARTICLE, "ON77DK.DRUSLLK"), "exact")
        self.assertEqual(structured_sales_relation(ARTICLE, "ON77DK.DLVALLK"), "regional_variant_of")
        self.assertEqual(structured_sales_relation(ARTICLE, "ON77DK.DRUSLLKX"), "regional_variant_of")
        self.assertEqual(structured_sales_relation(ARTICLE, "ON77DK"), "family_of")
        self.assertEqual(structured_sales_relation("P12ED.NSAR + P12ED.USAR", "P12ED.USAR"), "component_of")
        self.assertTrue(article_has_variant(ARTICLE, ("ON77DK.DRUSLLK",)))
        self.assertFalse(article_has_variant("ON66", ("ON66.DRUSLLK",)))

    def test_identity_depends_on_main_pdp_field_not_url_or_related_tile(self):
        html = '''<link rel="canonical" href="/ru/audio/lg-on77dkdrusllk">
                  <div class="related">ON77DKDRUSLLK</div>
                  <div class="GPC0009" data-adobe-salesmodelcode="ON77DK"
                       data-adobe-salessuffixcode="DLVALLK"></div>'''
        found, level, _ = _product_designation(BeautifulSoup(html, "html.parser"), ARTICLE, "ON77DK", region="ru")
        self.assertNotEqual(level, "full_sku")
        self.assertNotEqual(found, ARTICLE)

    def test_support_kit_relation_cannot_approve_specs_or_photo(self):
        edges = support_edges("lg_kz_support", "https://www.lg.com/kz/support/product-support/",
                              "P12ED.NSAR + P12ED.USAR", ("P12ED.USAR", "P12ED.NSAR"))
        self.assertEqual(sum(e.relation == "component_of" for e in edges), 2)
        self.assertTrue(any(e.relation == "support_for" for e in edges))
        self.assertTrue(allows_evidence("support_for", "manual"))
        self.assertFalse(allows_evidence("support_for", "specs"))
        self.assertFalse(allows_evidence("support_for", "photo"))
        self.assertFalse(allows_evidence("family_of", "photo"))
        self.assertTrue(allows_evidence("family_of", "photo", official_family_shared=True))

    def test_worker_persists_support_identity_from_same_fetched_response(self):
        support_url = "https://www.lg.com/ru/support/product/lg-MODEL"
        support_html = '<div data-product-id="MODEL.OTHER"></div>'

        class StaticOfficial:
            def __init__(self, key, document):
                self.source_key = self.site_name = key
                self.document = document
                self.reports = []
                self.document_calls = 0

            def find_source(self, *args, **kwargs):
                return self.document

            def find_documents(self, *args, **kwargs):
                self.document_calls += 1
                self.reports.append({"support_page_url": support_url,
                                     "support_page_sales_code": "MODEL.OTHER",
                                     "_support_html": support_html,
                                     "outcome": "no_verified_russian_instruction", "files": []})
                return [], "No verified PDF"

        class NoDealer:
            source_key = site_name = "dns"
            document_urls = {}
            def find_source(self, *args, **kwargs):
                return SourceDocument(self.source_key, self.site_name, "", match_level="unknown")
            def find_documents(self, *args, **kwargs):
                return [], "No observed URL"

        with TemporaryDirectory() as temporary:
            db = Path(temporary) / "batch.sqlite3"
            jobs.initialize(db)
            with closing(connect(db)) as connection:
                connection.execute("INSERT INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('b','x.xlsx','Sheet1','{}','now')")
                connection.execute("INSERT INTO products(id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'b',2,'test','LG','MODEL.SUFFIX','','audio',0,'[]','{}')")
                connection.commit()
            kz = StaticOfficial("lg_kz", SourceDocument("lg_kz", "LG KZ", "", match_level="unknown"))
            ru = StaticOfficial("lg_ru", SourceDocument("lg_ru", "LG RU", "https://www.lg.com/ru/audio/lg-model",
                found_model="MODEL.SUFFIX", match_level="full_sku", html='<div class="GPC0009" data-adobe-salesmodelcode="MODEL" data-adobe-salessuffixcode="SUFFIX"></div>'))
            dealer = StaticOfficial("sulpak", SourceDocument("sulpak", "Sulpak", "", match_level="unknown"))
            jobs.enqueue(db, 1, [1, 6])
            self.assertTrue(worker.run_once(db, adapter_factory=lambda: (kz, ru, dealer), dns_adapter_factory=NoDealer))
            support = next(x for x in jobs.get_source_pages(db, 1) if x["source_key"] == "lg_ru_support")
            self.assertEqual((support["url"], support["found_model"], support["match_level"]),
                             (support_url, "MODEL.OTHER", "base_model"))
            self.assertEqual(ru.document_calls, 1)
            snapshot = latest_source_snapshot(db, 1, "lg_ru_support")
            self.assertEqual(snapshot["content"], support_html)

    @unittest.skipUnless(DATABASE.exists(), "Saved LG batch unavailable")
    def test_saved_main_product_pages_and_offline_readiness(self):
        expected = {"lg_kz": "2ac75cd1b9d267a83378d4c6499a1e13793b3bf21edfee2aa75750dc1f89ed57",
                    "lg_ru": "40fe379b2aa72f675b3002816a947a7f9bf72e43d7c2b2f078342f45ee2730a9"}
        with TemporaryDirectory() as temporary:
            db = Path(temporary) / "batch.sqlite3"
            with closing(connect(DATABASE)) as source, closing(connect(db)) as target:
                source.backup(target)
            before = card_readiness(db, 15)
            self.assertEqual(before["verdict"], "not_ready")
            for key, region in (("lg_kz", "kz"), ("lg_ru", "ru")):
                snapshot = latest_source_snapshot(db, 15, key)
                self.assertEqual(hashlib.sha256(snapshot["content"].encode()).hexdigest(), expected[key])
                found, level, evidence = _product_designation(
                    BeautifulSoup(snapshot["content"], "html.parser"), ARTICLE, "ON77DK", region=region)
                self.assertEqual((found, level), (ARTICLE, "full_sku"))
                self.assertIn("ON77DK.DRUSLLK", evidence)
                with closing(connect(db)) as connection:
                    connection.execute("UPDATE source_pages SET found_model=?, match_level=?, evidence=? WHERE product_id=15 AND source_key=?",
                                       (found, level, evidence, key))
                    connection.commit()
            jobs.resolve_product(db, 15)
            after = card_readiness(db, 15)
            self.assertEqual(after["verdict"], "export_ready_with_gaps")
            self.assertEqual(after["official_facts_from_exact_pages"], after["official_facts"])
            self.assertEqual(after["official_gallery_from_exact_pages"], after["official_gallery_selected"])
            self.assertIn("instruction_variant_link_unconfirmed", after["blocking_gaps"])
            self.assertEqual(card_readiness(db, 4)["verdict"], "not_ready")
            self.assertTrue(card_readiness(db, 4)["instruction"]["russian"])
            with closing(connect(db)) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM products WHERE id=15").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
