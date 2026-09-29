"""Regression checks for the shared multi-brand pipeline foundation."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from product_tool import storage
from product_tool.fetch_history import latest_source_snapshot, record_fetch_attempt, save_source_snapshot
from product_tool.identity import (
    CategorySchema, IdentityVerifier, PageIdentity, ProductIdentity,
    VariantAttributes, VerificationLevel, bosch_service_identity,
)
from product_tool.policy import ResolutionPolicy, SourceValue
from product_tool.sources import SourceRole, UnknownSourceHost, default_source_registry, route_bosch_category


def identity(*, model="MODEL-1", category="smartphone", variants=None, title="Product"):
    return ProductIdentity(
        brand_raw="Brand", brand_canonical="brand",
        category_raw=category, category_canonical=category,
        seller_sku="SELLER-42", wb_sku="WB-42", title_raw=title,
        model_candidates=(model,), variant_attributes=VariantAttributes(variants or {}), market="KZ",
    )


class IdentityVerifierTests(unittest.TestCase):
    def setUp(self):
        self.verifier = IdentityVerifier()

    def test_01_missing_seller_sku_is_not_rejection_when_variant_matches(self):
        result = self.verifier.verify(
            identity(variants={"color": "black", "storage": "256GB"}),
            PageIdentity(model_code="MODEL-1", variant_attributes=VariantAttributes({"color": "black", "storage": "256GB"})),
            source="manufacturer",
        )
        self.assertEqual(result.level, VerificationLevel.EXACT_VARIANT)

    def test_02_missing_color_caps_result_at_exact_model(self):
        result = self.verifier.verify(
            identity(variants={"color": "black"}), PageIdentity(model_code="MODEL-1"), source="manufacturer",
        )
        self.assertEqual(result.level, VerificationLevel.EXACT_MODEL)

    def test_03_different_screen_sizes_do_not_merge(self):
        schema = CategorySchema("display", significant_variant_fields=("screen_size",))
        result = self.verifier.verify(
            identity(category="display", variants={"screen_size": "55"}),
            PageIdentity(model_code="MODEL-1", variant_attributes=VariantAttributes({"screen_size": "65"})),
            source="manufacturer", schema=schema,
        )
        self.assertEqual(result.level, VerificationLevel.CONFLICT)

    def test_04_graphics_cards_with_different_model_codes_do_not_merge(self):
        result = self.verifier.verify(identity(model="GV-N4070-12GD", category="graphics card"), PageIdentity(manufacturer_sku="GV-N4070-12GD-V2"), source="manufacturer")
        self.assertEqual(result.level, VerificationLevel.CONFLICT)

    def test_05_gigabyte_revisions_are_distinct(self):
        result = self.verifier.verify(
            identity(model="GPU-1", category="graphics card", variants={"hardware_revision": "V1.1"}),
            PageIdentity(model_code="GPU-1", variant_attributes=VariantAttributes({"hardware_revision": "V2"})),
            source="support",
        )
        self.assertEqual(result.level, VerificationLevel.CONFLICT)

    def test_06_tp_link_revisions_do_not_share_support_identity(self):
        result = self.verifier.verify(
            identity(model="ARCHER-C6", category="router", variants={"hardware_revision": "V1"}),
            PageIdentity(model_code="ARCHER-C6", variant_attributes=VariantAttributes({"hardware_revision": "V2"})),
            source="support",
        )
        self.assertEqual(result.level, VerificationLevel.CONFLICT)

    def test_07_bosch_base_and_service_identity_keep_service_index(self):
        self.assertEqual(bosch_service_identity("HBF512BB1T"), ("HBF512BB1T", ""))
        self.assertEqual(bosch_service_identity("HBF512BB1T/01"), ("HBF512BB1T", "01"))

    def test_15_family_only_never_becomes_exact(self):
        result = self.verifier.verify(identity(model="SERIES-8"), PageIdentity(family="SERIES-8"), source="manufacturer")
        self.assertEqual(result.level, VerificationLevel.FAMILY_ONLY)

    def test_16_bundle_is_not_confirmed_as_single_product(self):
        schema = CategorySchema("generic", significant_variant_fields=("bundle_components",))
        result = self.verifier.verify(
            identity(model="MODEL-1", variants={"bundle_components": "MODEL-1 + CASE"}),
            PageIdentity(model_code="MODEL-1"), source="retailer", schema=schema,
        )
        self.assertEqual(result.level, VerificationLevel.EXACT_MODEL)


class RegistryTests(unittest.TestCase):
    def test_08_bosch_home_category_routing(self):
        self.assertEqual(route_bosch_category("Built-in oven / Духовой шкаф"), "bosch_home")

    def test_09_bosch_tools_category_routing(self):
        self.assertEqual(route_bosch_category("Аккумуляторная дрель"), "bosch_tools")

    def test_10_ambiguous_bosch_category_requires_review(self):
        self.assertEqual(route_bosch_category("Bosch accessory"), "review")

    def test_12_redirect_to_unknown_host_is_blocked(self):
        registry = default_source_registry()
        with self.assertRaises(UnknownSourceHost):
            registry.validate_redirect_chain("bosch_home", ["https://www.bosch-home.com/", "https://evil.example/item"])


class FetchHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "test.sqlite3"
        storage.initialize(self.db)
        with storage._connection(self.db) as connection:
            connection.execute("INSERT INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('b','x.xlsx','S','{}','now')")
            connection.execute("INSERT INTO products(batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('b',1,'P','Brand','M','','C',0,'[]','[]')")
            self.product_id = connection.execute("SELECT id FROM products").fetchone()[0]

    def test_11_failed_attempt_preserves_last_successful_snapshot(self):
        success = record_fetch_attempt(self.db, self.product_id, "source", status="success", final_url="https://example.test/p")
        snapshot_id = save_source_snapshot(self.db, self.product_id, "source", success, source_url="https://example.test/p", content="good")
        failed = record_fetch_attempt(self.db, self.product_id, "source", status="error", error="timeout")
        with self.assertRaises(ValueError):
            save_source_snapshot(self.db, self.product_id, "source", failed, source_url="", content="")
        self.assertEqual(latest_source_snapshot(self.db, self.product_id, "source")["id"], snapshot_id)


class ResolutionPolicyTests(unittest.TestCase):
    def value(self, field, value, source, role):
        return SourceValue(field, value, source, role, VerificationLevel.EXACT_VARIANT, "variant-a", {"source": source})

    def test_13_manufacturer_has_priority_over_conflicting_retailer(self):
        result = ResolutionPolicy().resolve([
            self.value("color", "black", "maker", SourceRole.MANUFACTURER),
            self.value("color", "white", "shop", SourceRole.RETAILER),
        ], target_variant_key="variant-a")
        self.assertEqual(result.fields[0].value, "black")

    def test_14_retailer_supplements_missing_variant_evidence(self):
        result = ResolutionPolicy().resolve([
            self.value("weight", "1kg", "maker", SourceRole.MANUFACTURER),
            self.value("color", "black", "shop", SourceRole.RETAILER),
        ], target_variant_key="variant-a")
        self.assertEqual({field.field_name: field.value for field in result.fields}, {"color": "black", "weight": "1kg"})


if __name__ == "__main__":
    unittest.main()
