"""Regression coverage for market, category, endpoint and clustering semantics."""

import json
from pathlib import Path
import unittest

from product_tool.census.candidates import SourceCandidate, load_source_candidates
from product_tool.census.discovery import (
    detect_embedded_state,
    detect_internal_search,
    json_ld_products,
    json_ld_field_coverage,
    parse_sitemap,
    validate_product_candidate,
)
from product_tool.census.models import (
    AccessStatus,
    EndpointCapability,
    FingerprintStatus,
    OfficialStatus,
    ProtectionStatus,
    SourceRecord,
)
from product_tool.census.probe import AccessProbe, ProbePolicy, classify_protection
from product_tool.census.registry import CANONICAL_SOURCE_CATALOG, SourceCatalog, load_source_catalog
from product_tool.census.runner_v2 import _clusters
from product_tool.sources import default_source_registry

from _source_policy import unapproved_source_ids


def source_record(source_id="test", **overrides):
    value = {
        "source_id": source_id,
        "adapter_id": "research_pending",
        "brands": ["Brand"],
        "category_groups": [],
        "category_patterns": [],
        "markets": [],
        "source_role": "manufacturer",
        "candidate_url": f"https://{source_id}.example/",
        "page_hosts": [f"{source_id}.example"],
        "support_hosts": [],
        "asset_document_hosts": [],
        "capabilities": ["identity"],
        "identity_strategy": "model",
        "priority": 10,
        "official_status": "candidate",
        "access_status": "not_checked",
        "fingerprint_status": "not_checked",
        "adapter_status": "research_pending",
        "lifecycle_status": "candidate",
        "host_verification": "not_checked",
        "enabled": False,
        "last_checked_at": "",
        "evidence": [],
        "source_country": "",
        "source_locale": "en",
        "source_languages": ["en"],
        "market_scope": "unknown",
        "identity_scope": "unknown",
    }
    value.update(overrides)
    return SourceRecord.from_dict(value)


class MarketAndCategorySelectionTests(unittest.TestCase):
    def test_unknown_and_any_catalog_market_do_not_filter_regional_sources(self):
        regional = source_record(markets=["DE"], source_country="DE", market_scope="country")
        catalog = SourceCatalog([regional])
        self.assertEqual(catalog.match("Brand", "Ноутбуки", "unknown"), (regional,))
        self.assertEqual(catalog.match("Brand", "Ноутбуки", "any"), (regional,))

    def test_exact_global_precedes_regional_at_equal_identity(self):
        global_source = source_record("global", market_scope="global", identity_scope="exact_product", priority=50)
        regional = source_record("regional", markets=["KZ"], source_country="KZ", market_scope="country", identity_scope="exact_product", priority=1)
        matched = SourceCatalog([regional, global_source]).match("Brand", "Ноутбуки", "KZ")
        self.assertEqual([item.source_id for item in matched], ["global", "regional"])

    def test_exact_regional_precedes_global_family_only(self):
        global_source = source_record("global", market_scope="global", identity_scope="family_only", priority=1)
        regional = source_record("regional", markets=["KZ"], source_country="KZ", market_scope="country", identity_scope="exact_product", priority=50)
        matched = SourceCatalog([global_source, regional]).match("Brand", "Ноутбуки", "KZ")
        self.assertEqual([item.source_id for item in matched], ["regional", "global"])

    def test_category_group_and_pattern_are_both_enforced(self):
        record = source_record(category_groups=["major_home_appliances"], category_patterns=["стираль"])
        catalog = SourceCatalog([record])
        self.assertEqual(catalog.match("Brand", "Стиральные машины", "unknown"), (record,))
        self.assertEqual(catalog.match("Brand", "Телевизоры", "unknown"), ())
        self.assertEqual(catalog.match("Brand", "Пылесосы", "unknown"), ())

    def test_sulpak_lg_scope(self):
        catalog = load_source_catalog()
        for category in ("Стиральные машины", "Сушильные машины", "Холодильники", "Пылесосы", "Микроволновые печи"):
            self.assertEqual([item.source_id for item in catalog.match("LG", category, "unknown") if item.source_id == "sulpak"], ["sulpak"], category)
        for category in ("Телевизоры", "Мониторы", "Аудиосистемы", "Ноутбуки", "Смартфоны", "Проекторы"):
            self.assertFalse(any(item.source_id == "sulpak" for item in catalog.match("LG", category, "unknown")), category)
        self.assertEqual([item.source_id for item in catalog.review_matches("LG", "Сплит-системы")], ["sulpak"])
        self.assertFalse(any(item.source_id == "sulpak" for item in catalog.match("LG", "Сплит-системы", "unknown")))
        self.assertEqual(unapproved_source_ids(default_source_registry().definitions), set())

    def test_only_canonical_v2_catalog_is_executable(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(CANONICAL_SOURCE_CATALOG.name, "source_catalog.v2.json")
        self.assertFalse((root / "product_tool/config/source_catalog.json").exists())
        legacy = root / "_legacy_source_catalog_test.json"
        legacy.write_text('{"schema_version":1,"sources":[]}', encoding="utf-8")
        try:
            with self.assertRaisesRegex(ValueError, "canonical"):
                load_source_catalog(legacy)
        finally:
            legacy.unlink()

    def test_domain_name_never_promotes_candidate_to_official(self):
        record = source_record(candidate_url="https://brand.example/", official_status="candidate")
        self.assertEqual(record.official_status, OfficialStatus.CANDIDATE)


class ProtectionClassificationTests(unittest.TestCase):
    def test_weak_captcha_term_is_only_suspected(self):
        html = "<html><body><h1>Ordinary product page</h1><p>" + ("normal content " * 20) + "</p><script>const captchaMode=false;</script></body></html>"
        result = classify_protection(html, http_status=200)
        self.assertEqual(result.status, ProtectionStatus.CHALLENGE_SUSPECTED)

    def test_confirmed_challenge_requires_converging_signals(self):
        html = '<html><title>Verify you are human</title><form id="challenge-form"><div class="g-recaptcha"></div></form></html>'
        result = classify_protection(html, http_status=200, headers={"cf-mitigated": "challenge"})
        self.assertEqual(result.status, ProtectionStatus.CHALLENGE_CONFIRMED)
        self.assertGreaterEqual(len(result.evidence), 2)


class FakeCookies(dict):
    def get_dict(self):
        return dict(self)


class FakeResponse:
    def __init__(self, status=200, url="https://example.test/", body=b"<html><body>ordinary page content ordinary page content ordinary page content ordinary page content</body></html>"):
        self.status_code = status
        self.url = url
        self.history = ()
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.cookies = FakeCookies()
        self.encoding = "utf-8"
        self.body = body

    def iter_content(self, chunk_size=16384):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index:index + chunk_size]


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.responses.pop(0)


class EndpointProbeTests(unittest.TestCase):
    def test_403_stops_whole_host(self):
        session = FakeSession([FakeResponse(403), FakeResponse(200, "https://example.test/support")])
        probe = AccessProbe(session, policy=ProbePolicy(min_interval_seconds=0))
        blocked = probe.probe("https://example.test/", allowed_hosts=("example.test",), capability="homepage")
        repeated = probe.probe("https://example.test/", allowed_hosts=("example.test",), capability="homepage")
        support = probe.probe("https://example.test/support", allowed_hosts=("example.test",), capability="support_page", sample_type="support_page")
        self.assertEqual(blocked.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(repeated.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(support.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(support.to_endpoint_record().capability, EndpointCapability.SUPPORT_PAGE)


class DiscoveryAndClusterTests(unittest.TestCase):
    def test_generic_discovery_primitives(self):
        kind, urls, truncated = parse_sitemap("<urlset><url><loc>https://e.test/p/1</loc></url></urlset>")
        self.assertEqual((kind, urls, truncated), ("urlset", ("https://e.test/p/1",), False))
        html = '<form action="/search"><input type="search" name="q"></form><script id="__NEXT_DATA__" type="application/json">{"props":{}}</script><script type="application/ld+json">{"@type":"Product","name":"P","sku":"M1"}</script>'
        self.assertEqual(len(json_ld_products(html)), 1)
        coverage = json_ld_field_coverage(html)
        self.assertTrue(coverage["name"])
        self.assertTrue(coverage["sku"])
        self.assertFalse(coverage["documents"])
        self.assertTrue(detect_embedded_state(html))
        self.assertEqual(detect_internal_search(html, "https://e.test/")[0]["action"], "https://e.test/search")
        identity = validate_product_candidate(html + " M1", expected_models=("M1",))
        self.assertGreaterEqual(identity.confidence, 0.9)

    def test_single_source_cluster_is_marked_and_not_auto_recommended(self):
        record = source_record(
            fingerprint_status="confirmed",
            fingerprint_layers=[{"engine": "adobe_experience_manager", "layer": "site_cms", "status": "confirmed", "confidence": 0.8, "sample_types": ["homepage"]}],
        )
        clusters = _clusters((record,), {"brand": 10})
        self.assertEqual(len(clusters), 1)
        self.assertTrue(clusters[0]["single_source_candidate"])
        self.assertFalse(clusters[0]["multi_site_cluster"])
        self.assertFalse(clusters[0]["adapter_candidate"])

    def test_json_ld_type_only_multi_site_cluster_is_downgraded(self):
        layer = [{"engine": "generic_json_ld_product", "layer": "product_data", "status": "confirmed", "confidence": 0.8, "sample_types": ["product_page"]}]
        endpoint = [{
            "url": "https://one.example/p/1", "capability": "product_page", "sample_type": "product_page",
            "access_status": "direct_access", "checked_at": "2026-09-22T00:00:00+00:00",
            "json_ld_product_count": 1, "json_ld_field_coverage": {"name": True, "brand": True},
        }]
        one = source_record("one", brands=["One"], fingerprint_status="confirmed", fingerprint_layers=layer, endpoints=endpoint)
        endpoint[0]["url"] = "https://two.example/p/1"
        two = source_record("two", brands=["Two"], fingerprint_status="confirmed", fingerprint_layers=layer, endpoints=endpoint)
        cluster = _clusters((one, two), {"one": 10, "two": 20})[0]
        self.assertTrue(cluster["multi_site_cluster"])
        self.assertFalse(cluster["structure_compatibility_validated"])
        self.assertFalse(cluster["adapter_candidate"])
        self.assertIn("insufficient", cluster["compatibility_evidence"])

    def test_v2_catalog_and_schema_are_machine_readable(self):
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads((root / "product_tool/config/source_catalog.v2.json").read_text(encoding="utf-8"))
        schema = json.loads((root / "product_tool/config/source_catalog.v2.schema.json").read_text(encoding="utf-8"))
        candidates = json.loads((root / "product_tool/config/source_candidates.v1.json").read_text(encoding="utf-8"))
        candidate_schema = json.loads((root / "product_tool/config/source_candidates.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(schema["properties"]["schema_version"]["const"], 2)
        self.assertEqual(len(load_source_catalog().records), len(catalog["sources"]))
        self.assertEqual(candidates["schema_version"], 1)
        self.assertEqual(candidate_schema["properties"]["schema_version"]["const"], 1)
        loaded_candidates = load_source_candidates()
        self.assertEqual(len(loaded_candidates.records), len(candidates["candidates"]))
        self.assertTrue(all(not item.enabled and item.evidence for item in loaded_candidates.records))
        source_ids = {item.source_id for item in load_source_catalog().records}
        self.assertTrue(all(item.candidate_id not in source_ids for item in loaded_candidates.records))
        self.assertTrue(loaded_candidates.for_brand("БИРЮСА", category_groups=("major_home_appliances",), catalog_market="unknown"))
        self.assertFalse(loaded_candidates.for_brand("БИРЮСА", category_groups=("computers_components",), catalog_market="unknown"))

    def test_candidate_cannot_be_enabled(self):
        value = json.loads((Path(__file__).resolve().parents[1] / "product_tool/config/source_candidates.v1.json").read_text(encoding="utf-8"))["candidates"][0]
        value["enabled"] = True
        with self.assertRaises(ValueError):
            SourceCandidate.from_dict(value)


if __name__ == "__main__":
    unittest.main()
