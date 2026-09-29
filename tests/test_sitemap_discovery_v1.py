from pathlib import Path
from types import SimpleNamespace
import gzip
import unittest

from product_tool.census.discovery import validate_structured_product_identity
from product_tool.census.endpoint_probe import ProbeResult
from product_tool.census.models import AccessStatus, EndpointCapability, ProtectionStatus
from product_tool.census.runner_v2 import _endpoint_flags
from product_tool.census.runner_v4 import _sample_products, _source_specs
from product_tool.census.catalog import load_catalog_coverage
from product_tool.census.sitemap_strategy import (
    DiscoveryBudget,
    SitemapCatalogStrategy,
    discovery_readiness,
    normalize_candidate_url,
    rank_candidate_url,
    safe_gzip_decompress,
)
from product_tool.identity import ProductIdentity, VariantAttributes, VerificationLevel

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage4"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def expected_identity(*, variants=True):
    return ProductIdentity(
        brand_raw="Demo", brand_canonical="demo", category_raw="Смартфоны",
        category_canonical="smartphone", seller_sku="ABC-123", wb_sku="",
        title_raw="Demo ABC-123 8 GB + 256 GB black",
        model_candidates=("ABC-123",),
        variant_attributes=VariantAttributes(
            {"color": "black", "ram": "8GB", "storage": "256GB"} if variants else {}
        ),
    )


class FakeProbe:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def probe(self, url, *, allowed_hosts, capability, sample_type):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, tuple):
            status, text = value
        else:
            status, text = 200, value
        access = AccessStatus.DIRECT_ACCESS
        protection = ProtectionStatus.ORDINARY_PAGE
        if status == 403:
            access = AccessStatus.CAPTCHA_OR_BLOCKED
            protection = ProtectionStatus.CHALLENGE_CONFIRMED
        elif status == 429:
            access = AccessStatus.RATE_LIMITED
            protection = ProtectionStatus.CHALLENGE_SUSPECTED
        elif status >= 400:
            access = AccessStatus.UNAVAILABLE
            protection = ProtectionStatus.INCONCLUSIVE
        return ProbeResult(
            url=url,
            capability=EndpointCapability(capability),
            sample_type=sample_type,
            access_status=access,
            http_status=status,
            redirect_chain=(url,),
            final_url=url,
            content_type="text/xml" if "sitemap" in url else "text/html",
            javascript_required=False,
            protection_status=protection,
            protection_evidence=(),
            product_search_available=False,
            fingerprints=(),
            evidence=(),
            checked_at="2026-09-22T00:00:00+00:00",
            diagnostic_text=text,
        )


class StructuredIdentityTests(unittest.TestCase):
    def test_body_only_is_insufficient(self):
        result = validate_structured_product_identity(
            fixture("product_body_only.html"), expected=expected_identity()
        )
        self.assertEqual(result.level, VerificationLevel.INSUFFICIENT)

    def test_url_match_ranks_high_but_is_not_identity(self):
        score, reasons, _, models = rank_candidate_url(
            "https://example.com/products/ABC-123",
            expected=expected_identity(), source_family="demo",
            allowed_hosts=("example.com",), sitemap_url="https://example.com/product-sitemap.xml",
        )
        result = validate_structured_product_identity(
            fixture("product_body_only.html"), expected=expected_identity()
        )
        self.assertGreaterEqual(score, 100)
        self.assertIn("ABC-123", models)
        self.assertEqual(result.level, VerificationLevel.INSUFFICIENT)
        self.assertTrue(any("model_token_in_url" in reason for reason in reasons))

    def test_structured_model_is_exact_model(self):
        result = validate_structured_product_identity(
            fixture("product_exact_model.html"), expected=expected_identity(variants=False)
        )
        self.assertEqual(result.level, VerificationLevel.EXACT_MODEL)

    def test_structured_model_and_variants_are_exact_variant(self):
        result = validate_structured_product_identity(
            fixture("product_exact_variant.html"), expected=expected_identity()
        )
        self.assertEqual(result.level, VerificationLevel.EXACT_VARIANT)

    def test_structured_variant_conflict_is_conflict(self):
        result = validate_structured_product_identity(
            fixture("product_conflict.html"), expected=expected_identity()
        )
        self.assertEqual(result.level, VerificationLevel.CONFLICT)

    def test_legacy_observation_cannot_raise_readiness(self):
        source = SimpleNamespace(
            endpoints=(),
            evidence=({
                "type": "product_identity_check",
                "observation": {"confidence": 1.0, "model": "ABC-123"},
            },),
        )
        flags = _endpoint_flags((source,))
        self.assertFalse(flags["exact_identity_validated"])
        self.assertFalse(flags["product_discovery_validated"])


class SitemapStrategyTests(unittest.TestCase):
    def setUp(self):
        self.pages = {
            "https://example.com/robots.txt": fixture("robots.txt"),
            "https://example.com/sitemap-index.xml": fixture("sitemap_index.xml"),
            "https://example.com/product-sitemap.xml": fixture("product_sitemap.xml"),
            "https://example.com/products/ABC-123": fixture("product_exact_variant.html"),
        }

    def test_bounded_discovery_is_deterministic_and_structured(self):
        probe = FakeProbe(self.pages)
        strategy = SitemapCatalogStrategy(
            budget=DiscoveryBudget(
                max_http_requests=6, max_sitemap_documents=2, max_sitemap_depth=2,
                max_urls_read=10, max_product_candidates=3, max_product_pages=1,
                min_interval_seconds=0, deadline_seconds=10,
            ),
            probe=probe,
        )
        result = strategy.run(
            source_family="demo", source_url="https://example.com/",
            allowed_hosts=("example.com",), expected=expected_identity(),
        )
        self.assertEqual(result.stop_reason, "complete")
        self.assertEqual(result.budget_used.http_requests, 4)
        self.assertEqual(result.budget_used.sitemap_documents, 2)
        self.assertEqual(result.budget_used.product_pages, 1)
        self.assertEqual(result.candidates[0].url, "https://example.com/products/ABC-123")
        self.assertEqual(result.candidates[0].identity_verification["level"], "exact_variant")
        self.assertNotIn("https://example.com/news-sitemap.xml", probe.calls)
        readiness = discovery_readiness(result, official_source_verified=True)
        self.assertTrue(readiness["discovery_reproducible"])
        self.assertTrue(readiness["exact_variant_validated"])
        self.assertFalse(readiness["production_ready"])

    def test_checkpoint_resume_does_not_repeat_requests(self):
        first_probe = FakeProbe(self.pages)
        strategy = SitemapCatalogStrategy(
            budget=DiscoveryBudget(
                max_http_requests=6, max_sitemap_documents=2, max_sitemap_depth=2,
                max_urls_read=10, max_product_candidates=3, max_product_pages=1,
                min_interval_seconds=0, deadline_seconds=10,
            ),
            probe=first_probe,
        )
        first = strategy.run(
            source_family="demo", source_url="https://example.com/",
            allowed_hosts=("example.com",), expected=expected_identity(),
        )
        resume_probe = FakeProbe({})
        resumed = SitemapCatalogStrategy(budget=strategy.budget, probe=resume_probe).run(
            source_family="demo", source_url="https://example.com/",
            allowed_hosts=("example.com",), expected=expected_identity(),
            checkpoint=first.checkpoint,
        )
        self.assertEqual(resume_probe.calls, [])
        self.assertEqual(resumed.candidates[0].identity_verification["level"], "exact_variant")

    def test_block_stops_source(self):
        probe = FakeProbe({"https://example.com/robots.txt": (403, "")})
        strategy = SitemapCatalogStrategy(
            budget=DiscoveryBudget(min_interval_seconds=0), probe=probe
        )
        result = strategy.run(
            source_family="demo", source_url="https://example.com/",
            allowed_hosts=("example.com",), expected=expected_identity(),
        )
        self.assertEqual(result.stop_reason, "captcha_or_blocked")
        self.assertEqual(len(probe.calls), 1)

    def test_url_normalization_removes_tracking(self):
        self.assertEqual(
            normalize_candidate_url("HTTPS://Example.com/p/ABC-123/?utm_source=x&b=2&a=1#part"),
            "https://example.com/p/ABC-123?a=1&b=2",
        )

    def test_gzip_is_bounded(self):
        payload = gzip.compress(b"x" * 20)
        self.assertEqual(safe_gzip_decompress(payload, max_output_bytes=20), b"x" * 20)
        with self.assertRaisesRegex(ValueError, "gzip_uncompressed_limit_exceeded"):
            safe_gzip_decompress(payload, max_output_bytes=19)

    def test_invalid_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            DiscoveryBudget(max_product_candidates=1, max_product_pages=2)

    def test_url_budget_is_never_exceeded(self):
        probe = FakeProbe(self.pages)
        strategy = SitemapCatalogStrategy(
            budget=DiscoveryBudget(
                max_http_requests=6, max_sitemap_documents=2, max_sitemap_depth=2,
                max_urls_read=1, max_product_candidates=1, max_product_pages=1,
                min_interval_seconds=0, deadline_seconds=10,
            ),
            probe=probe,
        )
        result = strategy.run(
            source_family="demo", source_url="https://example.com/",
            allowed_hosts=("example.com",), expected=expected_identity(),
        )
        self.assertLessEqual(result.budget_used.urls_read, 1)

    def test_dry_run_uses_five_real_catalog_families(self):
        census = load_catalog_coverage(Path(__file__).resolve().parents[1] / "data/catalog_2026-09-21_filtered.xlsx")
        specs = _source_specs()
        self.assertEqual([item.source_family for item in specs], [
            "bosch_home", "apple_kz", "karcher_global", "dreame", "hyperx",
        ])
        self.assertTrue(all(_sample_products(census, item, limit=1) for item in specs))


if __name__ == "__main__":
    unittest.main()
