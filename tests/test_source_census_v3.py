import json
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory

from product_tool.census.brands import load_brand_normalization
from product_tool.census.catalog import load_catalog_coverage
from product_tool.census.discovery import validate_structured_product_identity
from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.research import load_source_research
from product_tool.census.runner_v3 import build_stage3
from product_tool.identity import ProductIdentity, VariantAttributes, VerificationLevel

ROOT = Path(__file__).resolve().parents[1]


class NormalizationTests(unittest.TestCase):
    def test_registry_complete_and_special_cases_conservative(self):
        registry = load_brand_normalization()
        catalog = load_catalog_coverage(ROOT / "data/catalog_2026-09-21_filtered.xlsx")
        registry.validate_catalog_labels(catalog.brands)
        self.assertEqual(len(registry.records), 289)
        self.assertEqual(len(registry.canonical_brands), 284)
        self.assertEqual(len(registry.source_families), 283)
        self.assertEqual(registry.get("WD").source_family_id, "wd")
        self.assertEqual(registry.get("Western Digital").source_family_id, "wd")
        self.assertEqual(registry.get("POCO").canonical_brand, "POCO")
        self.assertEqual(registry.get("POCO").source_family_id, "xiaomi_global")
        self.assertEqual(registry.get("QUMAN").review_status, "requires_human_review")
        self.assertEqual(registry.get("Qumann").review_status, "requires_human_review")
        self.assertEqual(registry.get("Xiaom").review_status, "requires_human_review")
        self.assertEqual({x["source_family_id"] for x in registry.get("BOSCH").source_family_routes}, {"bosch_home", "bosch_tools"})

    def test_research_registry_and_priority_batch(self):
        data = load_source_research()
        schema = json.loads((ROOT / "product_tool/config/source_research.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(len(data["families"]), 50)
        self.assertEqual(sum(x["research_status"] == "official_verified" for x in data["families"]), 49)
        negative = next(x for x in data["families"] if x["source_family_id"] == "accesstyle")
        self.assertEqual(negative["research_status"], "official_source_not_found")
        self.assertEqual(negative["candidate_url"], "")

    def test_normalized_coverage_has_explicit_outcome_for_every_label(self):
        with TemporaryDirectory() as tmp:
            result = build_stage3(
                ROOT / "data/catalog_2026-09-21_filtered.xlsx",
                ROOT / "reports/source_census_2026-09-22_stage2",
                tmp,
            )
        self.assertEqual(len(result["labels"]), 289)
        self.assertTrue(all(item["final_status"] for item in result["labels"]))
        ambiguous = {item["original_brand_label"]: item for item in result["labels"]}
        self.assertFalse(ambiguous["QUMAN"]["official_coverage_inherited"])
        self.assertFalse(ambiguous["Xiaom"]["official_coverage_inherited"])


class FakeResponse:
    def __init__(self, status):
        self.status_code = status
        self.url = "https://example.com/a"
        self.history = []
        self.headers = {}
        self.encoding = "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()
    def iter_content(self, chunk_size):
        return iter((b"<html><body>ordinary content " + b"x" * 100 + b"</body></html>",))


class FakeSession:
    def __init__(self, status):
        self.status = status
        self.calls = 0
    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse(self.status)


class SafetyAndIdentityTests(unittest.TestCase):
    def test_probe_stops_whole_host_after_403_or_429(self):
        for status in (403, 429):
            with self.subTest(status=status):
                session = FakeSession(status)
                probe = AccessProbe(session, policy=ProbePolicy(min_interval_seconds=0))
                probe.probe("https://example.com/a", allowed_hosts=("example.com",))
                second = probe.probe("https://example.com/b", allowed_hosts=("example.com",), capability=EndpointCapability.ROBOTS)
                self.assertEqual(session.calls, 1)
                self.assertIsNone(second.http_status)

    def test_strict_identity_ignores_body_text_and_checks_variants(self):
        expected = ProductIdentity(
            brand_raw="Demo", brand_canonical="demo", category_raw="smartphone",
            category_canonical="smartphone", seller_sku="ABC-123", wb_sku="",
            title_raw="", model_candidates=("ABC-123",),
            variant_attributes=VariantAttributes({"color": "black"}),
        )
        weak = validate_structured_product_identity("<html>ABC-123 black</html>", expected=expected)
        self.assertEqual(weak.level, VerificationLevel.INSUFFICIENT)
        exact = validate_structured_product_identity(
            '<script type="application/ld+json">{"@type":"Product","mpn":"ABC-123","color":"black"}</script>',
            expected=expected,
        )
        self.assertEqual(exact.level, VerificationLevel.EXACT_VARIANT)


if __name__ == "__main__":
    unittest.main()
