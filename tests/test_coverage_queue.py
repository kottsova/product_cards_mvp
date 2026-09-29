"""Stage 17/18: the offline coverage queue (Stage 18: fixtures are scoped, identity risks are not conflicts,
the HyperX URL map is pinned to its evidence).

Everything here is offline: the catalog is read only, transports are
in-memory, and the process-wide network guard (tests/_bootstrap.py) is on.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from product_tool import jobs, worker
from product_tool.adapters import dns as dns_module
from product_tool.adapters import hyperx as hyperx_module
from product_tool.census.brands import load_brand_normalization
from product_tool.coverage import classify as C
from product_tool.coverage import executor, planner
from product_tool.coverage.catalog_units import CatalogUnit, load_catalog, reconcile, unit_id_for
from product_tool.coverage.facts import FamilyFacts, ScopeFacts, load_config, recorded_blocked_hosts, route_for_brand, working_routes
from product_tool.offline_guard import guard_state, offline_only

import coverage_controls as controls

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog_2026-09-21_filtered.xlsx"
CATALOG_SHA256 = "99789238cde44dd2a5ec776f504944d9d91ab5698770cff8126f353212e107ba"

_PLAN = None


def plan():
    global _PLAN
    if _PLAN is None:
        _PLAN = planner.build_plan()
    return _PLAN


def make_unit(brand, category, sku, *, row=2, title="", alt="") -> CatalogUnit:
    return CatalogUnit(unit_id_for(brand, category, sku), row, brand, category, sku, "", title, alt, 1, brand, "column", False, ())


def make_facts(family, **kw) -> FamilyFacts:
    values = dict(family=family, official_route_known=True, hosts=(f"www.{family}.example",), fixture_level="none",
                  fixture_missing_layers=(), discovery_status="none", discovery_route="", profile_status="product_page_not_found",
                  host_blocked=False, blocked_reason="", template_group="", evidence=(), note="")
    values.update(kw)
    return FamilyFacts(**values)


def make_scope(family, categories, *, market_matches=True, layers=None, level="", scope_id="", discovery="none") -> ScopeFacts:
    layers = layers or {"identity": "observed", "specifications": "observed", "media": "observed"}
    return ScopeFacts(
        scope_id=scope_id or f"{family}_scope", family=family, label=f"{family} scope", categories=tuple(categories), hosts=(f"www.{family}.example",),
        market="kz_ru" if market_matches else "en-us", market_matches_catalog=market_matches, market_reason="test", page_template="t",
        layers=tuple(sorted(layers.items())), declared_level=level, discovery_status=discovery, discovery_route="", evidence=(), observed_urls=(), note="", caveat="",
    )


def make_context(units, facts, *, blocked=None, product_facts=(), product_flags=()):
    return C.ClassifierContext.build(
        units, brands=load_brand_normalization(), facts=facts, routes=working_routes(), supplementary=(),
        blocked_hosts=blocked or {}, product_facts=list(product_facts), product_flags=list(product_flags),
    )


class CatalogIsReadOnlyAndReconciles(unittest.TestCase):
    def test_totals_match_the_workbook_and_the_file_is_untouched(self):
        before = (CATALOG.stat().st_mtime_ns, CATALOG.stat().st_size)
        snapshot = load_catalog(CATALOG)
        result = reconcile(snapshot)
        self.assertEqual(result["observed"], {"unique_products": 16888, "source_rows": 19917, "brands": 289, "categories": 228, "brand_category_pairs": 1058})
        self.assertEqual(snapshot.sha256, CATALOG_SHA256)
        self.assertEqual((CATALOG.stat().st_mtime_ns, CATALOG.stat().st_size), before)

    def test_unit_key_is_brand_category_article_and_empty_brands_stay_separate(self):
        snapshot = load_catalog(CATALOG)
        self.assertEqual(len({u.unit_id for u in snapshot.units}), 16888)
        self.assertEqual(sum(1 for u in snapshot.units if not u.brand), 32)  # kept as their own units

    def test_a_row_that_does_not_reconcile_is_refused(self):
        snapshot = load_catalog(CATALOG)
        broken = type(snapshot)(snapshot.path, snapshot.sha256, snapshot.units[:-1], snapshot.pair_rows, snapshot.context)
        with self.assertRaises(ValueError):
            reconcile(broken)


class EveryUnitHasOneStatus(unittest.TestCase):
    def test_partition_of_units_pairs_and_rows(self):
        data = plan()
        statuses = {s["id"] for s in load_config()["statuses"]}
        self.assertEqual(len(data["units"]), 16888)
        self.assertTrue(all(u["status"] in statuses for u in data["units"]))
        self.assertEqual(sum(data["summary"]["units_by_status"].values()), 16888)
        self.assertEqual(sum(data["summary"]["pairs_by_status"].values()), 1058)
        self.assertEqual(sum(p["unique_products"] for p in data["pairs"]), 16888)
        self.assertEqual(sum(p["source_rows"] for p in data["pairs"]), 19917)
        self.assertEqual(data["summary"]["source_rows"], 19917)

    def test_ready_units_are_only_lg_discovery_and_hyperx_exact_urls(self):
        ready = [u for u in plan()["units"] if u["status"] == C.READY]
        routes = {u["route_id"] for u in ready}
        expected = {"hyperx_official", "samsung_official", "bosch_home_official"}
        if not recorded_blocked_hosts(load_config()).get("www.lg.com"):
            expected.add("lg_official")
        self.assertEqual(routes, expected)
        # Stage 27: Samsung offers exactly the products the one-per-category rule selected, never the brand's 1182 rows
        samsung = [u for u in ready if u["route_id"] == "samsung_official"]
        self.assertEqual(len(samsung), 20)
        self.assertEqual(len({u["category"] for u in samsung}), 20)
        self.assertTrue(all(u["url_basis"] == "selected_one_per_category" and u["reason"] == "selected_one_per_category" for u in samsung))
        hyperx = [u for u in ready if u["route_id"] == "hyperx_official"]
        self.assertEqual(sorted(u["seller_sku"] for u in hyperx), sorted(hyperx_module.KNOWN_URLS))
        self.assertTrue(all(u["exact_url"].startswith("https://hyperx.com/products/") for u in hyperx))
        self.assertTrue(all(u["url_basis"] == "adapter_discovery" for u in ready if u["route_id"] == "lg_official"))

    def test_hyperx_twenty_of_forty_one_have_exact_urls(self):
        rows = [u for u in plan()["units"] if u["family"] == "hyperx"]
        self.assertEqual(len(rows), 41)
        self.assertEqual(Counter(u["status"] for u in rows), {C.READY: 20, C.URL_MISSING: 20, C.IDENTITY_CONFLICT: 1})
        conflict = next(u for u in rows if u["status"] == C.IDENTITY_CONFLICT)
        self.assertEqual(conflict["seller_sku"], "7G7A4AA#ACB")

    def test_units_keep_the_variant_they_were_catalogued_as(self):
        codes = {u["seller_sku"] for u in plan()["units"] if u["family"] == "playstation"}
        self.assertIn("CFI-ZCT1W_cosmic_red", codes)
        self.assertGreater(len([c for c in codes if c.startswith("CFI-ZCT1")]), 20)  # no merging of colour/revision variants

    def test_plan_is_reproducible_byte_for_byte(self):
        self.assertEqual(planner.plan_bytes(plan()), planner.plan_bytes(planner.build_plan()))


class ClassificationRules(unittest.TestCase):
    def setUp(self):
        self.units = []
        self.facts = {}

    def classify(self, unit, facts=None, **kw):
        context = make_context([unit], facts if facts is not None else self.facts, **kw)
        return C.classify(unit, context)

    def test_each_status_is_reachable_with_its_own_reason(self):
        facts = {
            "cudy": make_facts("cudy", fixture_level="category_scoped", scopes=(make_scope("cudy", ["Микроволновые печи"], level="full_value"),)),
            "apple": make_facts("apple"),
            "jbl": make_facts("jbl", host_blocked=True, blocked_reason="every_profile_http_blocked"),
            "xiaomi_global": make_facts("xiaomi_global", fixture_level="structural_partial", fixture_missing_layers=("specifications",)),
        }
        cases = [
            (make_unit("Cudy", "Микроволновые печи", "MS1"), C.ROUTE_NO_ADAPTER),
            (make_unit("Apple", "Смартфоны", "A1"), C.NEEDS_FIXTURE),
            (make_unit("JBL", "Колонки", "J1"), C.HOST_BLOCKED),
            (make_unit("Accesstyle", "Кабели", "K1"), C.MANUAL),
            (make_unit("", "Кабели", "K2"), C.MANUAL),
            (make_unit("HYPERX", "Мыши", "NOURL1"), C.URL_MISSING),
            (make_unit("LG", "Микроволновые печи", "MS2032GAS"), C.READY),
        ]
        for unit, expected in cases:
            self.assertEqual(self.classify(unit, facts).status, expected, unit.brand)
        conflict = [make_unit("Apple", "Смартфоны", "DUP", title="Смартфон iPhone 15 A2846"), make_unit("Apple", "Планшеты", "DUP", title="Планшет iPad Pro M4 A2836")]
        context = make_context(conflict, facts)
        self.assertEqual(C.classify(conflict[0], context).status, C.IDENTITY_CONFLICT)

    def test_xiaomi_structural_page_without_specifications_needs_a_fixture(self):
        facts = {"xiaomi_global": make_facts("xiaomi_global", fixture_level="structural_partial", fixture_missing_layers=("specifications",))}
        result = self.classify(make_unit("Xiaomi", "Смартфоны", "X1"), facts)
        self.assertEqual((result.status, result.reason), (C.NEEDS_FIXTURE, "structural_missing_specifications"))

    def test_a_recorded_host_stop_beats_ready_and_survives_as_data(self):
        blocked = {"hyperx.com": ["some_fetch_log.json"]}
        with patch.dict(hyperx_module.KNOWN_URLS, {"NEWSKU1": "https://hyperx.com/products/x"}):
            result = self.classify(make_unit("HYPERX", "Мыши", "NEWSKU1"), {}, blocked=blocked)
        self.assertEqual((result.status, result.reason), (C.HOST_BLOCKED, "host_stop_recorded"))

    def test_url_on_record_is_ready_without_a_guess(self):
        with patch.dict(hyperx_module.KNOWN_URLS, {"NEWSKU2": "https://hyperx.com/products/new"}):
            result = self.classify(make_unit("HYPERX", "Мыши", "NEWSKU2"), {})
        self.assertEqual((result.status, result.url_basis, result.exact_url), (C.READY, "known_url_map", "https://hyperx.com/products/new"))

    def test_confirmed_product_fact_wins_over_a_ready_route(self):
        fact = {"brand_family": "hyperx", "seller_sku": "9A273AA", "status": C.IDENTITY_CONFLICT, "reason": "test", "detail": "x"}
        result = self.classify(make_unit("HYPERX", "Микрофоны", "9A273AA"), {}, product_facts=[fact])
        self.assertEqual(result.status, C.IDENTITY_CONFLICT)

    def test_dealer_url_never_makes_a_unit_ready_or_official(self):
        unit = make_unit("Kingston", "Флеш-накопители", "DEALERONLY")
        facts = {"kingston": make_facts("kingston")}
        from product_tool.coverage.facts import SupplementaryRoute
        dealer = SupplementaryRoute("dns_dealer", "dns", dns_module.PAGE_HOST, lambda: {"DEALERONLY": "https://www.dns-shop.ru/product/x/"}, "any")
        context = C.ClassifierContext.build([unit], brands=load_brand_normalization(), facts=facts, routes=working_routes(), supplementary=(dealer,), blocked_hosts={}, product_facts=[])
        result = C.classify(unit, context)
        self.assertEqual(result.status, C.NEEDS_FIXTURE)          # not ready: the official route still has no adapter
        self.assertEqual(result.exact_url, "")                    # the dealer URL is not recorded as the product URL
        self.assertEqual(result.dealer_exact_urls, (("dns", "https://www.dns-shop.ru/product/x/"),))

    def test_repeated_article_is_flagged_and_stopped_for_the_manufacturer_code_route(self):
        unit = make_unit("LG", "Мониторы", "24BK550Y-B24BK550Y-B")
        result = self.classify(unit, {})
        self.assertEqual((result.status, result.reason), (C.MANUAL, "seller_sku_not_a_manufacturer_code"))
        self.assertIn("sku_repeated_halves", result.flags)

    def test_bosch_is_routed_by_category_and_ambiguous_categories_go_to_a_person(self):
        units = [make_unit("BOSCH", "Стиральные машины", "B1"), make_unit("BOSCH", "Шуруповерты", "B2"), make_unit("BOSCH", "Кабели", "B3")]
        facts = {"bosch_home": make_facts("bosch_home", fixture_level="category_scoped", scopes=(make_scope("bosch_home", ["Стиральные машины"]),)), "bosch_tools": make_facts("bosch_tools")}
        context = make_context(units, facts)
        results = [C.classify(u, context) for u in units]
        self.assertEqual([r.family for r in results], ["bosch_home", "bosch_tools", "bosch_category_routed"])
        self.assertEqual([r.status for r in results], [C.MANUAL, C.MANUAL, C.MANUAL])
        self.assertEqual(results[0].reason, "not_selected_one_card_per_category")
        self.assertEqual(results[1].reason, "worker_dispatch_and_brand_family_disagree")

    def test_host_stop_from_a_saved_log_reaches_the_plan(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "hyperx_fetch_log.json"
            log.write_text(json.dumps([{"url": "https://hyperx.com/products/a", "status_code": 403}]), encoding="utf-8")
            data = planner.build_plan(extra_fetch_logs=(log,))
        rows = [u for u in data["units"] if u["family"] == "hyperx"]
        self.assertEqual(Counter(u["status"] for u in rows), {C.HOST_BLOCKED: 40, C.IDENTITY_CONFLICT: 1})
        known = len(hyperx_module.KNOWN_URLS)
        self.assertEqual(data["summary"]["units_by_status"]["ready_to_run"], plan()["summary"]["units_by_status"]["ready_to_run"] - known)


class RegistryMatchesWorkerDispatch(unittest.TestCase):
    """A route only counts if run_once() really dispatches to it."""

    def _dispatch(self, brand: str) -> set[str]:
        called: set[str] = set()
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            jobs.initialize(workdir / "batches.sqlite3")
            unit = {"catalog_row": 2, "brand": brand, "category": "Мыши", "title": "t", "seller_sku": "DISPATCH1"}
            if brand.casefold() == "bosch":
                from product_tool.adapters.bosch_home import verified_pages
                unit["category"] = verified_pages()["TWK7203"]["category"]
                unit["seller_sku"] = "TWK7203"
            product_id = executor._ensure_product(workdir / "batches.sqlite3", unit, "dispatch")
            jobs.enqueue(workdir / "batches.sqlite3", product_id, [1])

            class Stub:
                source_key, site_name = "hyperx", "stub"
                def find_source(self, code, *, deadline):
                    from product_tool.adapters.common import SourceDocument
                    return SourceDocument(self.source_key, self.site_name, "", match_level="official_url_needed")

            def hyperx_factory():
                called.add("hyperx")
                return Stub()

            def lg_factory():
                called.add("lg")
                from product_tool.adapters.common import SourceDocument

                class LgStub(Stub):
                    def __init__(self, key): self.source_key, self.site_name = key, key
                    def find_source(self, code, *, deadline):
                        return SourceDocument(self.source_key, self.site_name, "", match_level="mismatch")
                return (LgStub("lg_kz"), LgStub("lg_ru"), LgStub("sulpak"))

            def samsung_factory():
                called.add("samsung")
                from product_tool.adapters.common import SourceDocument

                class SamsungStub(Stub):
                    source_key, site_name, reports = "samsung", "stub", {}
                    def find_source(self, code, *, deadline, category="", name=""):
                        return SourceDocument("samsung", "stub", "", match_level="unknown")
                return SamsungStub()

            def bosch_factory():
                from product_tool.adapters.common import SourceDocument
                called.add("bosch_home")
                class BoschStub(Stub):
                    source_key, site_name, reports = "bosch_home", "stub", {}
                    def find_source(self, code, *, category, deadline):
                        return SourceDocument("bosch_home", "stub", "", error="offline dispatch stub")
                return BoschStub()

            worker.run_once(workdir / "batches.sqlite3", clock=lambda: 0.0, adapter_factory=lg_factory, hyperx_adapter_factory=hyperx_factory, samsung_adapter_factory=samsung_factory, bosch_adapter_factory=bosch_factory, dns_adapter_factory=lambda: controls.NoDealer())
        return called

    def test_registry_routes_equal_the_workers_dispatch_table(self):
        for route in working_routes():
            for alias in sorted(route.brand_aliases):
                expected = {route.family}
                self.assertEqual(self._dispatch(alias.upper()), expected, alias)
        # Both selected-product routes are dispatched by run_once; this test uses one selected Bosch row.
        self.assertEqual(self._dispatch("Samsung"), {"samsung"})
        self.assertEqual(self._dispatch("Bosch"), {"bosch_home"})

    def test_brand_registry_family_agrees_with_every_route_alias(self):
        registry = load_brand_normalization()
        from product_tool.census.catalog import category_group
        for route in working_routes():
            for unit in (u for u in load_catalog(CATALOG).units if u.brand.casefold() in route.brand_aliases):
                actual = registry.get(unit.brand).family_for(category_group(unit.category))
                if route.family == "bosch_home" and actual != "bosch_home":
                    continue  # Bosch Tools and ambiguous categories are not this route.
                self.assertEqual(actual, route.family)

    def test_research_scripts_are_not_adapters(self):
        source = (ROOT / "product_tool/worker.py").read_text(encoding="utf-8")
        self.assertNotIn("census", source)
        self.assertEqual({r.family for r in working_routes()}, {"lg", "hyperx", "samsung", "bosch_home"})
        for route in working_routes():
            self.assertIsNotNone(route_for_brand(working_routes(), sorted(route.brand_aliases)[0]))

    def test_planner_config_evidence_and_priority_list_are_real(self):
        config = load_config()
        paths = set()
        for facts in config["family_facts"].values():
            paths.update(facts.get("evidence", ()))
        for facts in config["family_facts"].values():
            for scope in facts.get("scopes", ()):
                paths.update(scope["evidence"])
        paths.update(config["url_findings"]["hyperx"]["evidence"])
        for fact in config["product_facts"]:
            paths.update(fact["evidence"])
        for item in config["product_flags"]:
            paths.update(rel.split(" ", 1)[0] for rel in item["evidence"])
        for item in (*config["confirmed_exact_urls"]["counted"], *config["confirmed_exact_urls"]["not_counted"]):
            paths.update(item["evidence"])
        paths.update(config["host_stop_logs"]["static"])
        for rel in sorted(paths):
            self.assertTrue((ROOT / rel).is_file(), rel)
        stage8 = (ROOT / "product_tool/census/structural_report_v8.py").read_text(encoding="utf-8")
        listed = re.search(r"PRIORITY=\[([^\]]+)\]", stage8).group(1)
        self.assertEqual([x.strip(" '") for x in listed.split(",")], config["priority_brands"]["families"])


class RequestsAreGroupedNotRepeated(unittest.TestCase):
    def test_groups_cover_every_non_ready_unit_once_with_one_message_each(self):
        data = plan()
        groups = data["request_groups"]
        not_ready = sum(1 for u in data["units"] if u["status"] != C.READY)
        self.assertEqual(sum(g["units"] for g in groups), not_ready)
        self.assertEqual(len({g["group_id"] for g in groups}), len(groups))
        self.assertLess(len(groups), not_ready / 20)  # hundreds of groups, not thousands of messages
        self.assertTrue(all(g["message_ru"] for g in groups))
        assigned = Counter(u["request_group_id"] for u in data["units"] if u["request_group_id"])
        self.assertEqual({g["group_id"]: g["units"] for g in groups}, dict(assigned))

    def test_url_requests_are_keyed_by_brand_category_group_host_and_reason(self):
        asks = [g for g in plan()["request_groups"] if g["status"] == C.URL_MISSING]
        self.assertEqual(sum(g["units"] for g in asks), 20)
        self.assertEqual(len(asks), 1)  # one question for the brand and host, not one per category or per row
        for group in asks:
            self.assertEqual(group["host"], "hyperx.com")
            self.assertEqual(group["reason"], "no_confirmed_exact_url")
            self.assertEqual(group["brand_labels"], ["HYPERX"])
            self.assertEqual(len(group["items"]), 20)
            self.assertEqual(sum(group["findings_by_outcome"].values()), 20)
            self.assertNotIn("not_examined", group["findings_by_outcome"])

    def test_blocked_hosts_are_grouped_by_host_and_reason(self):
        blocked = [g for g in plan()["request_groups"] if g["status"] == C.HOST_BLOCKED]
        self.assertTrue(blocked)
        self.assertTrue(all(g["kind"] == "human_decision" for g in blocked))
        self.assertIn("recorded_block_in_evidence", {g["reason"] for g in blocked})


class PriorityQueueAndWaves(unittest.TestCase):
    def test_priority_queue_follows_the_users_list(self):
        queue = plan()["priority_queue"]
        self.assertEqual([row["family"] for row in queue], load_config()["priority_brands"]["families"])
        self.assertEqual(sorted(row["recommended_rank"] for row in queue), list(range(1, 15)))
        xbox = next(row for row in queue if row["family"] == "xbox")
        self.assertEqual(xbox["unique_products"], 0)
        razer = next(row for row in queue if row["family"] == "razer")
        self.assertTrue(razer["host_blocked"])
        self.assertEqual(max(queue, key=lambda r: r["recommended_rank"])["family"], "razer")  # blocked brands go last

    def test_every_first_wave_has_a_measured_gain_and_the_full_criteria(self):
        waves = plan()["waves"]
        self.assertEqual([w["wave_id"] for w in waves], ["W1-A", "W1-B", "W1-C", "W1-D"])
        wanted = {c["id"] for c in load_config()["wave_readiness_criteria"]}
        self.assertEqual(wanted, {"identity_exact", "variants_positive_negative", "specifications", "gallery_complete",
                                  "documents_evidence", "run_once_offline", "checkpoint_resume", "policy_fetch", "coverage_delta"})
        for wave in waves:
            self.assertEqual({c["id"] for c in wave["readiness_criteria"]}, wanted)
            gain = wave["expected_gain"]
            self.assertEqual(gain["adapter_ready_units"], sum(f["adapter_ready_units"] for f in wave["per_family"]))
            self.assertEqual(gain["waiting_on_fixture_units"], sum(f["waiting_on_fixture_units"] for f in wave["per_family"]))
            self.assertLessEqual(gain["ready_guaranteed_by_urls_on_record_units"], gain["ready_via_confirmed_discovery_route_units"] or gain["adapter_ready_units"])
            self.assertLessEqual(gain["ready_via_confirmed_discovery_route_units"], gain["adapter_ready_units"])
            for family in wave["per_family"]:
                self.assertTrue(family["prerequisites"])

    def test_wave_gain_counts_only_units_whose_own_category_is_proven(self):
        data = plan()
        by_family = Counter(u["family"] for u in data["units"] if u["status"] == C.ROUTE_NO_ADAPTER)
        for wave in data["waves"]:
            for family in wave["per_family"]:
                self.assertEqual(family["adapter_ready_units"], by_family[family["family"]])
                ready_scopes = [s for s in family["scopes"] if s["next_step"] == "build_adapter"]
                self.assertEqual(sum(s["units"] for s in ready_scopes), family["adapter_ready_units"])
        wave_d = next(w for w in data["waves"] if w["wave_id"] == "W1-D")
        self.assertEqual(wave_d["expected_gain"]["adapter_ready_units"], 0)  # Stage 27: Samsung has its adapter (it left this wave); PlayStation and Microsoft have no proven category
        self.assertEqual(wave_d["expected_gain"]["ready_guaranteed_by_urls_on_record_units"], 0)
        self.assertNotIn("samsung", [f["family"] for f in wave_d["per_family"]])
        playstation = next(f for f in wave_d["per_family"] if f["family"] == "playstation")
        microsoft = next(f for f in wave_d["per_family"] if f["family"] == "microsoft")
        self.assertEqual((playstation["adapter_ready_units"], microsoft["adapter_ready_units"]), (0, 0))

    def test_no_wave_promises_readiness_through_a_discovery_route_that_is_not_proven_for_the_category(self):
        proven = []
        for wave in plan()["waves"]:
            for family in wave["per_family"]:
                for scope in family["scopes"]:
                    if scope["discovery_status"] != "confirmed":
                        self.assertNotEqual(scope["after_adapter"], C.READY, scope["scope_id"])
                    elif scope["next_step"] == "build_adapter":
                        proven.append(scope["scope_id"])
        self.assertEqual(proven, [])  # Stage 27: the only proven scope (Samsung microwaves) is served by the wired Samsung adapter now

    def test_razer_stays_out_of_wave_scope_while_its_host_is_stopped(self):
        for wave in plan()["waves"]:
            self.assertNotIn("razer", wave["families"])


class ExecutorPassesRowsToRunOnce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.result = controls.run_controls(Path(cls.tmp.name), plan()["units"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def entry(self, name, key):
        return self.result[name]["units"][self.result["units"][key]]

    def test_confirmed_hyperx_rows_become_cards_with_evidence_and_gaps(self):
        for key, sku in (("mic", "9A273AA"), ("mouse", "A1KY6AA")):
            entry = self.entry("main", key)
            self.assertEqual((entry["seller_sku"], entry["outcome"], entry["job_status"]), (sku, "card", "done"))
            card = entry["card"]
            hyperx = next(s for s in card["sources"] if s["source_key"] == "hyperx")
            self.assertEqual(hyperx["match_level"], "exact_variant")
            self.assertTrue(hyperx["url"].startswith("https://hyperx.com/products/"))
            self.assertGreater(card["facts"], 0)
            self.assertGreater(card["photos"], 0)
            self.assertIn("documents", card["gaps"])  # the gap is stated, never filled
            self.assertEqual(entry["network_calls_refused"], [])

    def test_row_without_a_url_stops_with_the_exact_reason_and_no_request(self):
        entry = self.entry("main", "duo")
        self.assertEqual((entry["outcome"], entry["stop_code"]), ("stopped", "official_url_needed"))
        self.assertEqual(entry["plan_status"], C.URL_MISSING)
        self.assertNotIn("https://hyperx.com/products/", "".join(self.result["sessions"]["hyperx_calls"]).replace(hyperx_module.KNOWN_URLS["9A273AA"], "").replace(hyperx_module.KNOWN_URLS["A1KY6AA"], ""))
        self.assertNotIn("4P5E2AA", hyperx_module.KNOWN_URLS)

    def test_identity_conflict_is_not_handed_to_run_once_but_the_negative_variant_never_becomes_exact(self):
        entry = self.entry("main", "keyboard")
        self.assertEqual((entry["outcome"], entry["stop_code"], entry["stopped_before_run_once"]), ("stopped", "region_suffix_mismatch_confirmed", True))
        forced = self.result["main"]["units"]["control-negative-keyboard"]
        self.assertEqual((forced["outcome"], forced["stop_code"]), ("review", "identity_base_code_only"))
        hyperx = next(s for s in forced["card"]["sources"] if s["source_key"] == "hyperx")
        self.assertEqual(hyperx["match_level"], "base_code_confirmed")

    def test_finished_checkpoint_is_not_rerun_and_makes_no_call(self):
        calls = self.result["sessions"]["hyperx_calls"]
        self.assertEqual(calls, [hyperx_module.KNOWN_URLS["9A273AA"], hyperx_module.KNOWN_URLS["A1KY6AA"]])  # once each; the resume pass added none
        self.assertEqual(self.result["sessions"]["negative_calls"], [controls.KEYBOARD_URL])
        self.assertTrue(all(e.get("resume_skips", 0) >= 1 for e in self.result["main"]["units"].values() if e["outcome"] in {"card", "review", "stopped"} and e["catalog_row"] < 100000))

    def test_host_stop_survives_a_restart_and_no_request_is_made(self):
        stopped = self.result["host_stop"]["units"]
        first = stopped[self.result["units"]["mic"]]
        second = stopped[self.result["units"]["mouse"]]
        self.assertEqual(first["stop_code"], "host_blocked")
        self.assertEqual((second["outcome"], second["stop_code"], second["stopped_before_run_once"]), ("stopped", "host_blocked", True))
        self.assertEqual(self.result["sessions"]["restarted_session_calls"], [])

    def test_lg_row_runs_through_the_ordinary_adapters_to_a_card(self):
        entry = self.entry("lg", "lg")
        self.assertEqual((entry["outcome"], entry["job_status"]), ("card", "done"))
        keys = {s["source_key"]: s["match_level"] for s in entry["card"]["sources"]}
        self.assertEqual(keys["lg_kz"], "full_sku")
        self.assertEqual(keys["sulpak"], "full_sku")
        self.assertGreater(entry["card"]["facts"], 0)
        self.assertEqual(self.result["sessions"]["lg_refused"], [])

    def test_default_transport_refuses_and_names_the_missing_fixture(self):
        unit = next(u for u in plan()["units"] if u["seller_sku"] == self.entry("lg", "lg")["seller_sku"] and u["family"] == "lg")
        unit = dict(unit, status=C.READY, reason="forced_offline_fixture_control", next_action="run_once")
        with TemporaryDirectory() as tmp:
            checkpoint = executor.run_units([unit], workdir=Path(tmp), checkpoint_path=Path(tmp) / "cp.json")
        entry = checkpoint["units"][unit["unit_id"]]
        self.assertEqual((entry["outcome"], entry["stop_code"]), ("stopped", "offline_no_fixture_transport"))
        self.assertTrue(entry["network_calls_refused"])

    def test_non_runnable_unit_creates_no_job(self):
        unit = next(u for u in plan()["units"] if u["status"] == C.HOST_BLOCKED)
        with TemporaryDirectory() as tmp:
            executor.run_units([unit], workdir=Path(tmp), checkpoint_path=Path(tmp) / "cp.json")
            connection = sqlite3.connect(Path(tmp) / "batches.sqlite3")
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM search_jobs").fetchone()[0], 0)
            finally:
                connection.close()

    def test_checkpoint_is_written_atomically_and_reloadable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cp.json"
            executor.save_checkpoint(path, {"version": 1, "units": {"a": {"outcome": "card"}}})
            self.assertEqual(executor.load_checkpoint(path)["units"]["a"]["outcome"], "card")
            self.assertFalse(path.with_name("cp.json.tmp").exists())


class OfflineGuardAndDelta(unittest.TestCase):
    def test_offline_only_blocks_http_and_dns_and_restores(self):
        import socket
        import requests
        from product_tool.census.endpoint_probe import RealNetworkIOBlocked

        ambient = guard_state()
        with offline_only():
            with self.assertRaises(RealNetworkIOBlocked):
                socket.getaddrinfo("example.invalid", 443)
            with self.assertRaises(RealNetworkIOBlocked):
                requests.Session().get("https://example.invalid/")
        self.assertEqual(guard_state(), ambient)

    def test_delta_reports_movement_between_two_plans(self):
        with TemporaryDirectory() as tmp:
            before, after = Path(tmp) / "b.jsonl", Path(tmp) / "a.jsonl"
            rows = [{"unit_id": "1", "status": C.URL_MISSING, "reason": "no_confirmed_exact_url"}, {"unit_id": "2", "status": C.URL_MISSING, "reason": "no_confirmed_exact_url"},
                    {"unit_id": "3", "status": C.NEEDS_FIXTURE, "reason": "x"}]
            before.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            after.write_text("".join(json.dumps(r) + "\n" for r in [dict(rows[0], status=C.READY, reason="exact_url_on_record"), rows[1], dict(rows[2], status=C.URL_MISSING)]), encoding="utf-8")
            result = planner.delta(before, after)
        self.assertEqual(result["ready_to_run_gain"], 1)
        self.assertEqual(result["moves"], [{"from": C.URL_MISSING, "to": C.READY, "units": 1}, {"from": C.NEEDS_FIXTURE, "to": C.URL_MISSING, "units": 1}])
        self.assertEqual(result["moves_by_cause"]["exact_url_confirmed"]["units"], 1)

    def test_delta_keeps_the_kinds_of_movement_apart(self):
        rows = {
            "scope": ({"status": C.ROUTE_NO_ADAPTER, "reason": "fixture_full_value"}, {"status": C.NEEDS_FIXTURE, "reason": "no_product_page_evidence_for_category"}),
            "identity": ({"status": C.IDENTITY_CONFLICT, "reason": "seller_sku_shared_across_category"}, {"status": C.MANUAL, "reason": "brand_missing"}),
            "url": ({"status": C.URL_MISSING, "reason": "no_confirmed_exact_url"}, {"status": C.READY, "reason": "exact_url_on_record"}),
        }
        with TemporaryDirectory() as tmp:
            before, after = Path(tmp) / "b.jsonl", Path(tmp) / "a.jsonl"
            before.write_text("".join(json.dumps(dict(v[0], unit_id=k)) + "\n" for k, v in rows.items()), encoding="utf-8")
            after.write_text("".join(json.dumps(dict(v[1], unit_id=k)) + "\n" for k, v in rows.items()), encoding="utf-8")
            result = planner.delta(before, after)
        self.assertEqual({cause: item["units"] for cause, item in result["moves_by_cause"].items()},
                         {"evidence_scope_corrected": 1, "identity_rule_corrected": 1, "exact_url_confirmed": 1})


class FixturesAreScopedNotBrandWide(unittest.TestCase):
    def test_a_fixture_covers_only_its_own_category_and_market(self):
        scope = make_scope("cudy", ["Микроволновые печи"], level="full_value")
        facts = {"cudy": make_facts("cudy", fixture_level="category_scoped", scopes=(scope,))}
        units = [make_unit("Cudy", "Микроволновые печи", "M1"), make_unit("Cudy", "Телевизоры", "T1")]
        context = make_context(units, facts)
        results = [C.classify(u, context) for u in units]
        self.assertEqual([r.status for r in results], [C.ROUTE_NO_ADAPTER, C.NEEDS_FIXTURE])
        self.assertEqual(results[1].reason, "no_product_page_evidence_for_category")
        self.assertIn("Микроволновые печи", results[1].detail)

    def test_a_page_from_a_foreign_market_or_with_missing_layers_is_not_coverage(self):
        foreign = make_scope("playstation", ["Геймпады"], market_matches=False)
        thin = make_scope("cudy", ["Телевизоры"], layers={"identity": "observed", "specifications": "absent", "media": "observed"})
        facts = {"playstation": make_facts("playstation", fixture_level="category_scoped", scopes=(foreign,)),
                 "cudy": make_facts("cudy", fixture_level="category_scoped", scopes=(thin,))}
        units = [make_unit("Playstation", "Геймпады", "P1"), make_unit("Cudy", "Телевизоры", "T2")]
        context = make_context(units, facts)
        self.assertEqual([(r.status, r.reason) for r in (C.classify(u, context) for u in units)],
                         [(C.NEEDS_FIXTURE, "fixture_market_differs_from_catalog"), (C.NEEDS_FIXTURE, "structural_missing_specifications")])

    def test_a_family_wide_fixture_without_a_declared_scope_is_never_applied(self):
        facts = {"cudy": make_facts("cudy", fixture_level="full_value")}
        unit = make_unit("Cudy", "Микроволновые печи", "M2")
        result = C.classify(unit, make_context([unit], facts))
        self.assertEqual((result.status, result.reason), (C.NEEDS_FIXTURE, "fixture_scope_not_declared"))

    def test_in_the_real_queue_every_official_route_unit_names_its_scope(self):
        data = plan()
        ready = [u for u in data["units"] if u["status"] == C.ROUTE_NO_ADAPTER]
        self.assertEqual(Counter(u["scope_id"] for u in ready), {"cudy_com_routers": 28})
        # Stage 27: Samsung has a working adapter; its rows are ready only when selected (one per category), the rest wait for the owner
        by_reason = Counter(u["reason"] for u in data["units"] if u["family"] == "samsung")
        self.assertEqual(by_reason, {"selected_one_per_category": 20, "not_selected_one_card_per_category": 1136, "seller_sku_not_a_manufacturer_code": 26})

    def test_playstation_and_microsoft_are_not_covered_by_one_page(self):
        data = plan()
        for family in ("playstation", "microsoft"):
            rows = [u for u in data["units"] if u["family"] == family]
            self.assertTrue(rows)
            self.assertNotIn(C.ROUTE_NO_ADAPTER, {u["status"] for u in rows}, family)
        reasons = Counter(u["reason"] for u in data["units"] if u["family"] in {"playstation", "microsoft"})
        self.assertEqual(set(reasons), {"fixture_market_differs_from_catalog", "no_product_page_evidence_for_category"})

    def test_scoped_families_make_no_family_wide_claim(self):
        facts = plan()["family_facts"]
        for family in ("samsung", "playstation", "microsoft", "bosch_home", "cudy", "hyperx"):
            self.assertEqual(facts[family]["fixture_level"], "category_scoped", family)
            self.assertTrue(facts[family]["scopes"], family)
        for family, entry in facts.items():
            if not entry["scopes"]:
                self.assertNotIn(entry["fixture_level"], {"full_value", "structural_sufficient"}, family)


class SharedSellerSkuIsARiskNotAConflict(unittest.TestCase):
    def classify(self, first_title, second_title):
        units = [make_unit("Xiaomi", "Весы", "SKU-X1", title=first_title, row=2), make_unit("Xiaomi", "Умные весы", "SKU-X1", title=second_title, row=3)]
        facts = {"xiaomi_global": make_facts("xiaomi_global", fixture_level="structural_partial", fixture_missing_layers=("specifications",))}
        context = make_context(units, facts)
        return [C.classify(u, context) for u in units]

    def test_titles_that_agree_keep_their_own_route_and_carry_the_risk(self):
        for result in self.classify("Умные весы Mi Smart Scale S400", "Весы Body Composition Scale S400"):
            self.assertEqual(result.status, C.NEEDS_FIXTURE)
            self.assertIn("seller_sku_shared_across_category", result.flags)
            self.assertEqual(result.sku_risk, "shared_across_category;titles_agrees")

    def test_titles_without_a_model_are_uninformative_not_a_conflict(self):
        for result in self.classify("Рюкзак Mi Casual Daypack", "Чехол для ноутбука"):
            self.assertNotEqual(result.status, C.IDENTITY_CONFLICT)
            self.assertTrue(result.sku_risk.endswith("titles_uninformative"))

    def test_only_titles_that_name_different_models_are_a_conflict(self):
        for result in self.classify("Весы Smart Scale S400", "Весы Smart Scale S800"):
            self.assertEqual((result.status, result.reason), (C.IDENTITY_CONFLICT, "seller_sku_shared_titles_contradict"))

    def test_in_the_real_queue_only_the_confirmed_region_mismatch_is_a_conflict(self):
        data = plan()
        conflicts = [u for u in data["units"] if u["status"] == C.IDENTITY_CONFLICT]
        self.assertEqual([(u["family"], u["seller_sku"]) for u in conflicts], [("hyperx", "7G7A4AA#ACB")])
        shared = [u for u in data["units"] if u["sku_risk"]]
        self.assertEqual(len(shared), 68)
        self.assertTrue(all(u["sku_risk"].endswith(("titles_agrees", "titles_uninformative")) for u in shared))
        self.assertTrue(all({"seller_sku_shared_across_brand", "seller_sku_shared_across_category"} & set(u["flags"]) for u in shared))

    def test_the_risk_travels_into_the_checkpoint(self):
        unit = next(u for u in plan()["units"] if u["sku_risk"])
        with TemporaryDirectory() as tmp:
            checkpoint = executor.run_units([unit], workdir=Path(tmp), checkpoint_path=Path(tmp) / "cp.json")
        entry = checkpoint["units"][unit["unit_id"]]
        self.assertEqual(entry["sku_risk"], unit["sku_risk"])
        self.assertTrue(entry["flags"])
        self.assertTrue(entry["title"])


class ExactVariantCriterionIsSourceSpecific(unittest.TestCase):
    def criterion(self):
        return next(c for c in load_config()["wave_readiness_criteria"] if c["id"] == "identity_exact")["text"]

    def test_the_criterion_does_not_require_the_seller_sku_on_the_official_site(self):
        text = self.criterion()
        self.assertIn("not by finding the seller SKU on the official site", text)
        self.assertIn("model and variant", text)
        self.assertNotIn("page's own code equals the catalog code", text)

    def test_a_confirmed_regional_code_mismatch_still_blocks_exact_variant(self):
        self.assertIn("confirmed mismatch", self.criterion())
        check = hyperx_module.IdentityCheck("7G7A4AA", "ACB", "7G7A4AA", "ABA", (object(),))
        self.assertEqual(check.level, "base_code_confirmed")


STAGE18 = ROOT / "reports/source_census_2026-09-24_stage18"


def _load_report_script(name: str):
    path = STAGE18 / "scripts" / name
    spec = importlib.util.spec_from_file_location("stage18_" + re.sub(r"\W", "_", name), path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


class KnownUrlsMatchTheirEvidence(unittest.TestCase):
    """hyperx.KNOWN_URLS is the working map. Every entry beyond the two Stage 15 rows must be backed by a saved
    official page whose own sku equals the catalog code; nothing is in the map without such a page."""

    @classmethod
    def setUpClass(cls):
        cls.accepted = json.loads((STAGE18 / "raw/accepted_urls.json").read_text(encoding="utf-8"))["accepted"]

    def test_the_map_is_the_two_stage15_rows_plus_the_stage18_and_stage19_accepted_rows(self):
        expected = {"9A273AA": "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone",
                    "A1KY6AA": "https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse"}
        expected.update({item["seller_sku"]: item["url"] for item in self.accepted})
        stage19 = json.loads((STAGE18.parent / "source_census_2026-09-24_stage19/raw/accepted_variant_urls.json").read_text(encoding="utf-8"))["accepted"]
        expected.update({item["seller_sku"]: item["url"] for item in stage19})
        self.assertEqual(hyperx_module.KNOWN_URLS, expected)
        self.assertEqual((len(self.accepted), len(stage19)), (11, 7))

    def test_every_accepted_page_replays_offline_as_exact_variant_with_the_title_on_the_page(self):
        assemble = _load_report_script("05_assemble_findings.py")
        hx = _load_report_script("hx_matching.py")
        pages = _load_report_script("07_replay_new_ready_rows.py").saved_pages()
        units = {u["seller_sku"].upper(): u for u in plan()["units"] if u["family"] == "hyperx"}
        adapter = hyperx_module.HyperXAdapter(session=object(), fetch_log_path=Path("unused_fetch_log.json"))
        for item in self.accepted:
            html = pages[item["url"]]
            document = adapter.parse_page(html, item["url"], catalog_code=item["seller_sku"]).document
            self.assertEqual(document.match_level, "exact_variant", item["seller_sku"])
            self.assertEqual(document.found_model.upper(), item["seller_sku"].upper())
            name_tokens = set(hx._words(assemble.product_name(html)))
            self.assertTrue(all(token in name_tokens for token in hx.model_tokens(units[item["seller_sku"].upper()]["title"])[0]), item["seller_sku"])
            if item["basis"] != "saved_official_snapshot":
                self.assertEqual(hashlib.sha256(html.encode("utf-8")).hexdigest(), item["content_sha256"], item["seller_sku"])

    def test_every_accepted_url_is_an_observed_official_url_not_a_pattern(self):
        offline = json.loads((STAGE18 / "raw/offline_candidates.json").read_text(encoding="utf-8"))
        saved_links = {"https://hyperx.com" + c["path"] for i in offline["items"] for c in i["candidates"]}
        live = json.loads((STAGE18 / "raw/live_discovery_result.json").read_text(encoding="utf-8"))
        products_sitemap = next(e for e in live["fetch_log"] if e["kind"] == "sitemap" and "sitemap_products" in e["url"])
        with gzip.open(STAGE18 / products_sitemap["saved_as"], "rt", encoding="utf-8", newline="") as handle:
            sitemap_text = handle.read()
        for item in self.accepted:
            if item["basis"] == "saved_official_snapshot":
                self.assertIn("search-result page", item["how_the_url_was_observed"])
                continue
            self.assertTrue(item["url"] in saved_links or item["url"] in sitemap_text, item["url"])

    def test_a_rejected_or_unmatched_row_is_not_in_the_map(self):
        stage18_findings = json.loads((STAGE18 / "raw/url_findings.json").read_text(encoding="utf-8"))["findings"]
        findings = json.loads((STAGE18.parent / "source_census_2026-09-24_stage19/raw/url_findings.json").read_text(encoding="utf-8"))["findings"]
        self.assertEqual(len(stage18_findings), 27)  # Stage 18's own record stays as it was
        self.assertEqual(set(stage18_findings) & set(hyperx_module.KNOWN_URLS), {"727A8AA", "727A9AA", "A59YZAA", "A59Z0AA", "AJ0T1AA", "B5VC5AA", "BS7C1AA"})
        self.assertEqual(set(findings) & set(hyperx_module.KNOWN_URLS), set())  # Stage 19: what is still without a URL is not in the map
        self.assertEqual(len(findings), 20)
        self.assertNotIn("7G7A4AA#ACB", hyperx_module.KNOWN_URLS)
        self.assertEqual(set(load_config()["url_findings"]["hyperx"]["rows"]), set(findings))


class UrlDiscoveryWaveStayedInsideItsBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = json.loads((STAGE18 / "raw/live_discovery_result.json").read_text(encoding="utf-8"))
        cls.budget = json.loads((STAGE18 / "raw/budget_predeclaration.json").read_text(encoding="utf-8"))

    def test_budget_was_declared_before_the_first_request_and_respected(self):
        self.assertLess(self.budget["declared_at"], self.live["fetch_log"][0]["checked_at"])
        self.assertLessEqual(self.live["requests_made"], self.budget["max_requests_total"])
        self.assertLessEqual(self.live["sitemap_requests"], self.budget["max_sitemap_requests"])
        self.assertLessEqual(self.live["page_requests"], self.budget["max_product_page_requests"])
        self.assertEqual(self.live["requests_made"], len(self.live["fetch_log"]))

    def test_every_request_went_to_hyperx_and_none_was_a_block(self):
        from urllib.parse import urlsplit
        for entry in self.live["fetch_log"]:
            self.assertIn(urlsplit(entry["url"]).hostname, {"hyperx.com", "www.hyperx.com"})
            self.assertNotIn(entry["http_status"], {401, 403, 429})
        self.assertEqual(self.live["halted"], "")

    def test_every_page_request_was_an_observed_url_without_query_or_pattern(self):
        offline = json.loads((STAGE18 / "raw/offline_candidates.json").read_text(encoding="utf-8"))
        saved_links = {"https://hyperx.com" + c["path"] for i in offline["items"] for c in i["candidates"]}
        index = next(e for e in self.live["fetch_log"] if e["kind"] == "sitemap" and e["url"] == "https://hyperx.com/sitemap.xml")
        with gzip.open(STAGE18 / index["saved_as"], "rt", encoding="utf-8", newline="") as handle:
            index_text = handle.read()
        products = next(e for e in self.live["fetch_log"] if e["kind"] == "sitemap" and e is not index)
        self.assertIn(products["url"], index_text)  # the child sitemap is a <loc> of the declared index
        with gzip.open(STAGE18 / products["saved_as"], "rt", encoding="utf-8", newline="") as handle:
            product_sitemap = handle.read()
        for entry in self.live["fetch_log"]:
            if entry["kind"] == "page":
                self.assertTrue(entry["url"] in saved_links or entry["url"] in product_sitemap, entry["url"])
                self.assertNotIn("?", entry["url"])  # no variant ids, no search queries


class NewlyReadyRowsThroughRunOnce(unittest.TestCase):
    """The rows that got a URL are replayed through the ordinary worker.run_once() on the saved official pages."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        module = _load_report_script("07_replay_new_ready_rows.py")
        cls.summary, cls.checkpoint_path = module.replay(Path(cls.tmp.name) / "replay", plan()["units"])
        cls.recorded = json.loads((STAGE18 / "controls/new_ready_summary.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_eleven_rows_are_replayed_once_and_resume_makes_no_call(self):
        self.assertEqual(self.summary["units"], 11)
        self.assertEqual(self.summary["requests_to_fixture_transport"], 11)
        self.assertEqual(self.summary["resume_pass_new_calls"], 0)
        self.assertEqual(self.summary["refused_requests"], [])

    def test_stage18_recorded_six_cards_and_five_reviews_and_stage19_code_now_gives_eleven_cards(self):
        # The recorded Stage 18 result is history (extraction rule before Stage 19): 6 cards, 5 reviews on attribute conflicts.
        self.assertEqual(self.recorded["outcomes"], {"card": 6, "review": 5})
        self.assertEqual(self.recorded["stop_codes"], {"attribute_conflict": 5})
        # The same 11 pages through the current adapter: every conflict was two different parts of one device (or a price
        # widget), see tests/test_stage19_variants.py; nothing is left for review.
        self.assertEqual(self.summary["outcomes"], {"card": 11})
        self.assertTrue(all(row["hyperx_match_level"] == "exact_variant" and row["conflicts"] == 0 for row in self.summary["per_unit"]))
        for row in self.summary["per_unit"]:
            self.assertEqual(row["job_status"], "done")
            self.assertIn("documents", row["gaps"])  # the gap is stated, never filled

    def test_a_review_row_is_never_counted_as_a_card(self):
        reviews = [row for row in self.recorded["per_unit"] if row["outcome"] == "review"]
        self.assertEqual(len(reviews), 5)
        self.assertTrue(all(row["conflicts"] for row in reviews))


class ExcludedDealerIsAbsentFromActiveFiles(unittest.TestCase):
    """The rule is tested without writing the name: every word window of the
    name's length in every active file is hashed and compared with the
    excluded dealer's SHA-256 digests. reports/ (immutable history) and data/
    (local run databases) are outside the scan."""

    def test_no_active_file_names_the_excluded_dealer(self):
        suffixes = {".py", ".json", ".md", ".html", ".js", ".txt", ".toml", ".cfg"}
        lengths = set(_NAME_HASHES.values())
        files = [ROOT / "README.md"] + [
            p for top in ("product_tool", "tests", "docs") for p in (ROOT / top).rglob("*")
            if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts
        ]
        offenders = set()
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in set(re.findall(r"[A-Za-zА-Яа-яЁё]{5,}", text)):
                lowered = token.casefold()
                for length in lengths:
                    for i in range(len(lowered) - length + 1):
                        if hashlib.sha256(lowered[i:i + length].encode("utf-8")).hexdigest() in _NAME_HASHES:
                            offenders.add(str(path.relative_to(ROOT)))
        self.assertEqual(sorted(offenders), [])


# SHA-256 of the excluded dealer's name (Latin and Cyrillic spellings), casefolded -> length.
_NAME_HASHES: dict[str, int] = {'5214d6d0806772c829030cb6b707188fe7b6ff9b3455978bb87b1ca1dc34af5d': 6, 'd34e6c59394b6eb5a1c6565b72d68a2cb5fd4d9db96f4b275aa5f6c4fd56efb8': 5}


if __name__ == "__main__":
    unittest.main()
