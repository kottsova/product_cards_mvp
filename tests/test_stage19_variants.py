"""Stage 19: variant extraction in the working HyperX adapter, the five Stage 18 review rows, the persisted
confirmed-challenge stop, sitemap URL decoding, and the evidence behind the seven variant URLs.

Everything is offline: pages are the copies saved by Stage 18/19 (real hyperx.com HTML), transports are in-memory.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from product_tool.adapters import hyperx as hyperx_module
from product_tool.adapters.common import RawAttribute
from product_tool.adapters.hyperx import HyperXAdapter, KNOWN_URLS, format_attribute_scope, parse_attribute_scope, _spec_attributes
from product_tool.adapters.policy_fetch import PolicyAwareFetcher, stopped_hosts_from_fetch_log
from product_tool.adapters.sitemap_urls import sitemap_locs
from product_tool.adapters.structured_page import ExtractedField, ROLE_DOM_TABLE, extract_dom_spec_table, extract_shopify_product
from product_tool.census.endpoint_probe import AccessStatus, ProbePolicy
from product_tool.census.models import ProtectionStatus
from product_tool.coverage import planner
from product_tool.coverage.facts import load_config, recorded_blocked_hosts

from coverage_controls import FixtureSession

ROOT = Path(__file__).resolve().parents[1]
S18 = ROOT / "reports/source_census_2026-09-24_stage18"
S19 = ROOT / "reports/source_census_2026-09-24_stage19"
GROUP_A = ["727A8AA", "727A9AA", "A59YZAA", "A59Z0AA", "AJ0T1AA", "B5VC5AA", "BS7C1AA"]
CLOUD_III = "https://hyperx.com/products/hyperx-cloud-iii-wired-gaming-headset"


def gz(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


def page(handle: str) -> str:
    return gz(S18 / "raw/pages" / f"products_hyperx-{handle}.gz")


def adapter() -> HyperXAdapter:
    return HyperXAdapter(session=object(), fetch_log_path=Path("unused_fetch_log.json"))


class VariantLinkageFromThePagesOwnData(unittest.TestCase):
    """Each of the seven group-A codes is tied to a variant id and a URL by two in-page sources, none constructed."""

    @classmethod
    def setUpClass(cls):
        cls.linkage = {r["seller_sku"]: r for r in json.loads((S19 / "raw/variant_linkage.json").read_text(encoding="utf-8"))["rows"]}

    def test_all_seven_are_linked_and_the_url_is_printed_in_the_page(self):
        self.assertEqual(sorted(self.linkage), sorted(GROUP_A))
        for sku, row in self.linkage.items():
            html = gz(S18 / "raw/pages" / f"products_{urlsplit(row['page_url']).path.rsplit('/', 1)[-1]}.gz")
            product = extract_shopify_product(html, row["page_url"])
            variant = product.variant_by_sku(sku)
            self.assertIsNotNone(variant, sku)
            self.assertTrue(variant.confirmed, sku)
            self.assertEqual(set(variant.sources), {"product_json", "json_ld_offer"})
            self.assertIn(variant.url, html, sku)  # the address exists verbatim in the source, it was not assembled
            parts = urlsplit(variant.url)
            self.assertEqual((parts.hostname, parts.query), ("hyperx.com", f"variant={variant.variant_id}"))
            self.assertEqual(variant.url, row["variant"]["url"])
            self.assertTrue(row["url_observed_in_page_data"])

    def test_the_example_from_the_task_is_727A8AA_id_and_url(self):
        variant = extract_shopify_product(page("cloud-iii-wired-gaming-headset"), CLOUD_III).variant_by_sku("727A8AA")
        self.assertEqual(variant.variant_id, "43656365375645")
        self.assertEqual(variant.url, f"{CLOUD_III}?variant=43656365375645")

    def test_a_url_whose_id_disagrees_with_the_embedded_json_is_not_confirmed(self):
        html = page("cloud-iii-wired-gaming-headset").replace("?variant=43656365375645", "?variant=1")
        variant = extract_shopify_product(html, CLOUD_III).variant_by_sku("727A8AA")
        self.assertFalse(variant.confirmed)
        document = adapter().parse_page(html, CLOUD_III, catalog_code="727A8AA").document
        self.assertEqual(document.match_level, "mismatch")  # never promoted on an unconfirmed record
        self.assertEqual(document.photos, [])

    def test_all_seven_pass_the_recorded_offline_checks(self):
        result = json.loads((S19 / "raw/variant_linkage.json").read_text(encoding="utf-8"))
        self.assertEqual((result["rows_examined"], result["variants_linked_and_url_observed"], result["variants_passing_every_offline_check"]), (7, 7, 7))


class VariantExtractionInTheAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = page("cloud-iii-wired-gaming-headset")
        cls.product = extract_shopify_product(cls.html, CLOUD_III)
        cls.default = cls.product.variant_by_sku(cls.product.selected_sku)
        cls.black = adapter().parse_page(cls.html, CLOUD_III, catalog_code="727A8AA").document
        cls.blackred = adapter().parse_page(cls.html, CLOUD_III, catalog_code="727A9AA").document

    def variant_attrs(self, document):
        return {a.name: a.value for a in document.attributes if a.scope == "variant"}

    def test_exact_variant_comes_from_the_in_page_record_and_says_so(self):
        self.assertEqual((self.black.match_level, self.black.found_model), ("exact_variant", "727A8AA"))
        self.assertIn("variant_source=in_page_variant_record", self.black.evidence)
        self.assertIn(f"page selected '{self.default.sku}'", self.black.evidence)

    def test_sku_name_colour_and_gtin_are_the_selected_variants_not_the_defaults(self):
        attrs = self.variant_attrs(self.blackred)
        self.assertEqual(attrs["SKU"], "727A9AA")
        self.assertEqual(attrs["Color"], "Black-Red")
        self.assertTrue(attrs["Variant name"].endswith("Black-Red"))
        self.assertEqual(attrs["GTIN-12"], "197029008237")
        for value in attrs.values():
            self.assertNotIn(self.default.sku, value)
            self.assertNotEqual(value, self.default.barcode)
            self.assertNotIn("White-Pink", value)

    def test_photos_belong_to_the_variant_and_other_variants_are_excluded_with_a_reason(self):
        media_by_url = {m.src.split("?")[0].rsplit("/", 1)[-1]: m for m in self.product.media}
        chosen = [c for c in self.blackred.photo_candidates if not c.excluded_reason and c.kind == "product_gallery"]
        self.assertEqual(len(chosen), 7)
        self.assertEqual(self.blackred.photos, [c.url for c in chosen])
        excluded = [c for c in self.blackred.photo_candidates if c.excluded_reason]
        self.assertGreater(len(excluded), 40)
        self.assertTrue(all(c.kind == "excluded" and "other variant" in c.excluded_reason for c in excluded))
        wanted = {m.media_id for m in self.product.media if m.tag == "Black/Red"}
        self.assertEqual(len(wanted), 7)
        chosen_urls = {u.split("?")[0].rsplit("/", 1)[-1] for u in self.blackred.photos}
        self.assertEqual(chosen_urls, {m.src.split("?")[0].rsplit("/", 1)[-1] for m in self.product.media if m.tag == "Black/Red"})
        self.assertFalse(set(self.blackred.photos) & set(self.black.photos))  # two variants never share a photo

    def test_model_wide_infographics_go_to_the_feature_group_not_the_variant_gallery(self):
        # The site tags six annotated infographics "(Black) - 02..07"; they are shared by the model.
        from collections import Counter
        kinds = Counter(c.kind for c in self.black.photo_candidates if not c.excluded_reason)
        self.assertEqual(kinds, {"product_gallery": 7, "feature": 6})
        features = [c for c in self.black.photo_candidates if c.kind == "feature"]
        self.assertTrue(all("annotated" in c.url for c in features))
        self.assertEqual(len(self.black.photos), 13)
        self.assertIn("6 model-wide infographics", self.black.evidence)

    def test_specifications_and_description_are_marked_as_shared_by_the_model(self):
        model = [a for a in self.blackred.attributes if a.scope == "model"]
        self.assertGreater(len(model), 10)
        scope = parse_attribute_scope(self.blackred.evidence)
        self.assertEqual(set(scope["model"]), {a.name for a in model})
        self.assertEqual(set(scope["variant"]), set(self.variant_attrs(self.blackred)))
        self.assertFalse(set(scope["variant"]) & set(scope["model"]))
        self.assertIn("description=shared_model", self.blackred.evidence)

    def test_the_default_variant_is_its_own_variant_and_nothing_else_changes_hands(self):
        document = adapter().parse_page(self.html, CLOUD_III, catalog_code=self.default.sku).document
        self.assertEqual(document.match_level, "exact_variant")
        self.assertIn("variant_source=page_selected_variant", document.evidence)
        self.assertEqual(self.variant_attrs(document)["SKU"], self.default.sku)

    def test_a_code_the_page_does_not_list_gets_no_variant_data_and_no_photos(self):
        document = adapter().parse_page(self.html, CLOUD_III, catalog_code="727A8ZZ").document
        self.assertNotEqual(document.match_level, "exact_variant")
        self.assertEqual(document.photos, [])
        self.assertEqual([a for a in document.attributes if a.scope == "variant"], [])
        self.assertTrue(all(c.excluded_reason for c in document.photo_candidates if c.kind == "excluded"))

    def test_a_region_suffix_mismatch_is_still_never_exact(self):
        html = page("alloy-origins-mechanical-gaming-keyboard")
        document = adapter().parse_page(html, "https://hyperx.com/products/hyperx-alloy-origins-mechanical-gaming-keyboard", catalog_code="4P5N9AA#ACB").document
        self.assertEqual(document.match_level, "base_code_confirmed")
        self.assertEqual(document.photos, [])

    def test_when_media_cannot_be_attributed_only_the_featured_media_is_claimed(self):
        url = "https://hyperx.com/products/hyperx-alloy-origins-60-mechanical-gaming-keyboard"
        html = page("alloy-origins-60-mechanical-gaming-keyboard")
        product = extract_shopify_product(html, url)
        self.assertEqual(len(product.variants), 2)
        variant = product.variant_by_sku("4P5N4AA#ABA")
        media, basis = product.variant_media(variant)
        self.assertIn(basis, {"featured_media_only", "unattributable"})
        self.assertLessEqual(len(media), 1)


class FiveStage18ReviewRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = json.loads((S19 / "raw/conflict_analysis.json").read_text(encoding="utf-8"))
        cls.accepted = {a["seller_sku"]: a for a in json.loads((S18 / "raw/accepted_urls.json").read_text(encoding="utf-8"))["accepted"]}

    def html_of(self, sku):
        item = self.accepted[sku]
        if item["basis"] == "saved_official_snapshot":
            connection = sqlite3.connect(f"file:{ROOT / item['database']}?mode=ro", uri=True)
            try:
                return connection.execute("SELECT content FROM source_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()[0]
            finally:
                connection.close()
        return gz(S18 / item["saved_as"])

    def test_every_conflict_is_traced_to_the_fragments_and_resolved_with_a_proven_cause(self):
        self.assertEqual((self.analysis["stage18_conflicts_total"], self.analysis["resolved"], self.analysis["still_disputed"]), (7, 7, 0))
        self.assertEqual((self.analysis["rows"], self.analysis["rows_with_every_conflict_resolved"]), (5, 5))
        causes = {(c["seller_sku"], c["name"]): c["cause"] for c in self.analysis["conflicts"]}
        self.assertEqual(causes[("B5VC4AA", "unit_price")], "not_a_specification")
        self.assertEqual(sum(1 for v in causes.values() if v == "different_device_node"), 6)

    def test_the_headset_and_microphone_values_now_carry_their_own_names(self):
        for sku in ("4P5J1AA", "4P5L3AA", "683L9AA", "B5VC4AA"):
            document = adapter().parse_page(self.html_of(sku), self.accepted[sku]["url"], catalog_code=sku).document
            names = {a.name: a.value for a in document.attributes}
            self.assertIn("Sensitivity", names)
            self.assertIn("Sensitivity (microphone)", names)
            self.assertNotEqual(names["Sensitivity"], names["Sensitivity (microphone)"])
            self.assertRegex(names["Sensitivity"], r"(?i)dB\s*SPL")
            self.assertRegex(names["Sensitivity (microphone)"], r"(?i)dBV|dBFS")

    def test_a_price_widget_is_not_a_specification(self):
        html = self.html_of("B5VC4AA")
        self.assertIn("Unit price", html)
        names = {f.name for f in extract_dom_spec_table(html, "https://hyperx.com/x")}
        self.assertNotIn("Unit price", names)

    def test_a_disputed_repeat_inside_one_block_is_left_as_a_conflict(self):
        def row(name, value, block):
            return ExtractedField(name, value, "u", "e", ROLE_DOM_TABLE, "confirmed", "Headphone Specifications", block)
        attributes = _spec_attributes([row("Weight", "300 g", 1), row("Weight", "310 g", 1), row("Sensitivity", "103 dBSPL/mW", 1), row("Sensitivity", "-15 dBV", 2)])
        self.assertEqual([a.name for a in attributes if a.name.startswith("Weight")], ["Weight", "Weight"])  # same block: nothing proves they differ
        self.assertEqual(sorted(a.name for a in attributes if a.name.startswith("Sensitivity")), ["Sensitivity", "Sensitivity (Headphone Specifications #2)"])
        self.assertTrue(all(a.scope == "model" for a in attributes))

    def test_heading_plus_list_specifications_are_now_read(self):
        for handle, sku in (("cloud-ii-core-wireless-gaming-headset", "6Y2G8AA"), ("cloud-iii-wireless-gaming-headset", "77Z46AA")):
            html = page(handle)
            self.assertEqual([f for f in extract_dom_spec_table(html, "https://hyperx.com/x") if f.role == ROLE_DOM_TABLE and f.section == ""], [])
            fields = extract_dom_spec_table(html, "https://hyperx.com/x")
            self.assertGreater(len(fields), 15, handle)
            names = {f.name for f in fields}
            self.assertTrue({"Frequency Response", "Sensitivity", "Battery Life"} <= names, handle)
            document = adapter().parse_page(html, KNOWN_URLS[sku], catalog_code=sku).document
            self.assertIn("Sensitivity (microphone)", {a.name for a in document.attributes})


class ConfirmedChallengeStopsTheHostAcrossInstances(unittest.TestCase):
    URL = "https://hyperx.com/products/x"
    CONFIRMED = '<html><body>Attention Required<div class="g-recaptcha" data-x="1"></div></body></html>'
    SUSPECTED = "<html><body>" + "An ordinary product page with plenty of visible text. " * 12 + "Security check</body></html>"
    ORDINARY = "<html><body>" + "An ordinary product page with plenty of visible text. " * 12 + "</body></html>"

    def fetch_twice(self, first_body, second_body):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "fetch_log.json"
            first_session, second_session = FixtureSession({self.URL: (200, first_body)}), FixtureSession({self.URL: (200, second_body)})
            policy = ProbePolicy(min_interval_seconds=0.0)
            first = PolicyAwareFetcher(log, session=first_session, policy=policy).get(self.URL, allowed_hosts=("hyperx.com",))
            entries = json.loads(log.read_text(encoding="utf-8"))
            second = PolicyAwareFetcher(log, session=second_session, policy=policy).get(self.URL, allowed_hosts=("hyperx.com",))
            planner_view = recorded_blocked_hosts(load_config(), Path(tmp), extra_logs=(log,))
            return first, entries, second, second_session, planner_view

    def test_a_confirmed_challenge_with_http_200_is_logged_and_stops_a_new_fetcher(self):
        first, entries, second, second_session, planner_view = self.fetch_twice(self.CONFIRMED, self.ORDINARY)
        self.assertEqual((first.http_status, first.access_status, first.protection_status), (200, AccessStatus.CAPTCHA_OR_BLOCKED, ProtectionStatus.CHALLENGE_CONFIRMED))
        self.assertEqual((entries[0]["status_code"], entries[0]["protection_status"]), (200, "challenge_confirmed"))
        self.assertEqual(second_session.calls, [])  # the new instance made no request
        self.assertEqual(second.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertIsNone(second.http_status)
        self.assertIn("hyperx.com", planner_view)  # the planner and the executor read the same rule

    def test_challenge_suspected_alone_is_logged_but_does_not_stop_anything(self):
        first, entries, second, second_session, planner_view = self.fetch_twice(self.SUSPECTED, self.ORDINARY)
        self.assertEqual((first.http_status, first.protection_status), (200, ProtectionStatus.CHALLENGE_SUSPECTED))
        self.assertEqual(entries[0]["protection_status"], "challenge_suspected")
        self.assertEqual(second_session.calls, [self.URL])  # the second fetcher really fetched
        self.assertEqual(second.http_status, 200)
        self.assertNotIn("hyperx.com", planner_view)

    def test_the_rule_reads_old_logs_and_ignores_the_suspected_status(self):
        old = [{"url": "https://a.example/x", "status_code": 403}, {"url": "https://b.example/x", "status_code": 200}]
        new = [{"url": "https://c.example/x", "status_code": 200, "protection_status": "challenge_suspected"},
               {"url": "https://d.example/x", "status_code": 200, "final_url": "https://e.example/y", "protection_status": "browser_verification_required"},
               {"url": "https://f.example/x", "status_code": 200, "protection_status": "ordinary_page"}]
        self.assertEqual(stopped_hosts_from_fetch_log(old + new), frozenset({"a.example", "d.example", "e.example"}))

    def test_every_fetch_now_records_the_protection_status(self):
        first, entries, *_ = self.fetch_twice(self.ORDINARY, self.ORDINARY)
        self.assertEqual(entries[0]["protection_status"], "ordinary_page")
        self.assertEqual(entries[0]["access_status"], "direct_access")


class SitemapUrlsAreDecoded(unittest.TestCase):
    def test_amp_entities_in_loc_become_ampersands(self):
        xml = ('<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap>'
               '<loc>https://hyperx.com/sitemap_products_1.xml?from=1&amp;to=2</loc></sitemap></sitemapindex>')
        self.assertEqual(sitemap_locs(xml), ["https://hyperx.com/sitemap_products_1.xml?from=1&to=2"])

    def test_the_saved_stage18_sitemap_index_decodes_and_the_old_regex_did_not(self):
        text = gz(S18 / "raw/pages/sitemap.xml.gz")
        locs = sitemap_locs(text)
        products = [u for u in locs if "sitemap_products" in u][0]
        self.assertEqual(products, "https://hyperx.com/sitemap_products_1.xml?from=7006261084317&to=9027383132317")
        self.assertNotIn("&amp;", "".join(locs))
        self.assertIn("&amp;", "".join(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)))  # what Stage 18's script requested

    def test_truncated_or_hostile_locs_are_handled(self):
        truncated = "<urlset><url><loc>https://hyperx.com/products/a?x=1&amp;y=2</loc></url><url><loc>https://hyperx.com/pro"
        self.assertEqual(sitemap_locs(truncated), ["https://hyperx.com/products/a?x=1&y=2"])
        self.assertEqual(sitemap_locs("<urlset><url><loc>javascript:alert(1)</loc></url><url><loc>ftp://x/y</loc></url></urlset>"), [])

    def test_the_real_products_sitemap_is_read_completely(self):
        locs = sitemap_locs(gz(S18 / "raw/pages/sitemap_products_1.xml.gz"))
        self.assertGreater(len([u for u in locs if "/products/" in u]), 200)
        self.assertTrue(all("&amp;" not in u for u in locs))


class EvidenceBehindTheSevenVariantUrls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.accepted = json.loads((S19 / "raw/accepted_variant_urls.json").read_text(encoding="utf-8"))
        cls.live = json.loads((S19 / "raw/live_variant_result.json").read_text(encoding="utf-8"))
        cls.budget = json.loads((S19 / "raw/budget_predeclaration.json").read_text(encoding="utf-8"))
        cls.gap = json.loads((S19 / "raw/live_snapshot_gap_result.json").read_text(encoding="utf-8"))
        cls.budget2 = json.loads((S19 / "raw/budget_predeclaration_2.json").read_text(encoding="utf-8"))

    def test_the_map_gained_exactly_the_seven_accepted_urls(self):
        self.assertEqual({a["seller_sku"] for a in self.accepted["accepted"]}, set(GROUP_A))
        self.assertEqual(self.accepted["rejected"], [])
        for a in self.accepted["accepted"]:
            self.assertEqual(KNOWN_URLS[a["seller_sku"]], a["url"])
            self.assertTrue(all(a["checks"].values()), a["seller_sku"])
        stage18 = {a["seller_sku"]: a["url"] for a in json.loads((S18 / "raw/accepted_urls.json").read_text(encoding="utf-8"))["accepted"]}
        expected = {"9A273AA": "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone", "A1KY6AA": "https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse", **stage18,
                    **{a["seller_sku"]: a["url"] for a in self.accepted["accepted"]}}
        self.assertEqual(KNOWN_URLS, expected)
        self.assertEqual(len(KNOWN_URLS), 20)

    def test_budgets_were_declared_first_and_respected(self):
        self.assertLess(self.budget["declared_at"], self.live["fetch_log"][0]["checked_at"])
        self.assertLessEqual(self.live["requests_made"], self.budget["max_requests_total"])
        self.assertEqual({u["url"] for u in self.budget["urls"]}, {e["url"] for e in self.live["fetch_log"]})
        self.assertLess(self.budget2["declared_at"], self.gap["request"]["checked_at"])
        self.assertEqual(self.budget2["max_requests_total"], 1)
        self.assertEqual(self.gap["request"]["url"], self.budget2["url"])

    def test_every_request_was_to_hyperx_without_a_block_and_no_confirmed_challenge(self):
        entries = self.live["fetch_log"] + [self.gap["request"]]
        for entry in entries:
            self.assertEqual(urlsplit(entry["url"]).hostname, "hyperx.com")
            self.assertEqual(entry["http_status"], 200)
            self.assertNotIn(entry["protection_status"], {"challenge_confirmed", "browser_verification_required"})
        self.assertEqual((self.live["halted"], self.gap["halted"]), ("", False))
        self.assertEqual(len(entries), 8)  # 7 variant pages + 1 page for the sanitised-snapshot gap

    def test_the_variant_page_still_selects_the_default_variant_in_its_json_ld(self):
        # This is why identity for these rows cannot come from "the page selected it".
        for a in self.accepted["accepted"]:
            html = gz(S19 / a["saved_as"])
            product = extract_shopify_product(html, a["url"])
            self.assertNotEqual(product.selected_sku, a["seller_sku"])
            document = adapter().parse_page(html, a["url"], catalog_code=a["seller_sku"]).document
            self.assertEqual(document.match_level, "exact_variant")
            self.assertIn("variant_source=in_page_variant_record", document.evidence)
            self.assertEqual(hashlib.sha256(html.encode("utf-8")).hexdigest(), a["content_sha256"])

    def test_the_live_page_for_the_sanitised_snapshot_row_has_variant_data_and_photos(self):
        parse = self.gap["parse"]
        self.assertEqual((parse["match_level"], parse["photos"], parse["excluded_photos"]), ("exact_variant", 11, 0))
        self.assertIn("single_variant_product", parse["evidence"])


class AllTwentyReadyRowsThroughRunOnce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        import sys
        path = S19 / "scripts/04_replay_all_ready_rows.py"
        spec = importlib.util.spec_from_file_location("stage19_replay", path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT))
        spec.loader.exec_module(module)
        cls.tmp = TemporaryDirectory()
        cls.summary, _ = module.replay(Path(cls.tmp.name) / "replay", planner.build_plan()["units"])
        cls.recorded = json.loads((S19 / "controls/all_ready_summary.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_twenty_rows_twenty_cards_no_conflict_no_new_call_on_resume(self):
        self.assertEqual((self.summary["units"], self.summary["outcomes"], self.summary["stop_codes"]), (20, {"card": 20}, {}))
        self.assertEqual((self.summary["requests_to_fixture_transport"], self.summary["resume_pass_new_calls"], self.summary["refused_requests"]), (20, 0, []))
        self.assertTrue(all(r["conflicts"] == 0 and r["hyperx_match_level"] == "exact_variant" for r in self.summary["per_unit"]))
        self.assertEqual(self.summary["per_unit"], self.recorded["per_unit"])

    def test_the_five_review_rows_are_resolved(self):
        rows = self.summary["stage18_review_rows"]
        self.assertEqual([r["seller_sku"] for r in rows], ["4P5D4AA", "4P5J1AA", "4P5L3AA", "683L9AA", "B5VC4AA"])
        self.assertTrue(all(r["stage18_outcome"] == "review" and r["now_outcome"] == "card" and r["now_conflict_names"] == [] for r in rows))

    def test_the_seven_variant_rows_use_the_variant_record_and_only_their_own_photos(self):
        by_sku = {r["seller_sku"]: r for r in self.summary["per_unit"]}
        for sku in GROUP_A:
            self.assertEqual(by_sku[sku]["variant_source"], "in_page_variant_record", sku)
            self.assertGreater(by_sku[sku]["photos"], 0)
            self.assertGreater(by_sku[sku]["photos_excluded"], 0)

    def test_cards_state_which_attributes_are_shared_and_which_gaps_remain(self):
        for row in self.summary["per_unit"]:
            self.assertGreater(row["shared_model_attributes"] + row["variant_attributes"], 0)
            self.assertEqual(row["documents"], 0)
            self.assertIn("documents", row["gaps"])  # never filled from a neighbour or a guess
        self.assertEqual({r["seller_sku"] for r in self.summary["per_unit"] if r["shared_model_attributes"] == 0}, set())


if __name__ == "__main__":
    unittest.main()
