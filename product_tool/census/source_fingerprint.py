"""Aggregate platform evidence across endpoint samples and separate platform layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from .fingerprint import fingerprint_platform
from .models import FingerprintStatus


ENGINE_LAYERS = {
    "shopify": "commerce_search",
    "magento": "commerce_search",
    "salesforce_commerce_cloud": "commerce_search",
    "woocommerce": "commerce_search",
    "adobe_experience_manager": "site_cms",
    "sitecore": "site_cms",
    "next_js": "site_cms",
    "nuxt": "site_cms",
    "generic_json_ld_product": "product_data",
    "sitemap_catalog_feed": "catalog_feed",
    "custom_unknown": "unknown",
}


@dataclass(frozen=True)
class FingerprintSample:
    sample_type: str
    html: str
    headers: Mapping[str, str] | None = None
    cookies: Mapping[str, str] | None = None
    content_type: str = ""


@dataclass(frozen=True)
class SourceFingerprint:
    engine: str
    layer: str
    status: FingerprintStatus
    confidence: float
    sample_types: tuple[str, ...]
    evidence: tuple[dict, ...]

    def to_dict(self) -> dict:
        result = asdict(self)
        result["status"] = self.status.value
        result["sample_types"] = list(self.sample_types)
        result["evidence"] = list(self.evidence)
        return result


def fingerprint_source(samples: tuple[FingerprintSample, ...]) -> tuple[SourceFingerprint, ...]:
    endpoint_results = tuple(
        (sample.sample_type, fingerprint_platform(
            sample.html,
            headers=sample.headers,
            cookies=sample.cookies,
            content_type=sample.content_type,
        ))
        for sample in samples
    )
    return aggregate_endpoint_fingerprints(endpoint_results)


def aggregate_endpoint_fingerprints(endpoint_results) -> tuple[SourceFingerprint, ...]:
    grouped: dict[tuple[str, str], dict] = {}
    all_sample_types: set[str] = set()
    for sample_type, results in endpoint_results:
        all_sample_types.add(sample_type)
        for result in results:
            if result.engine == "custom_unknown":
                continue
            layer = ENGINE_LAYERS[result.engine]
            item = grouped.setdefault((result.engine, layer), {"confidence": 0.0, "sample_types": set(), "evidence": []})
            item["confidence"] = max(item["confidence"], result.confidence)
            item["sample_types"].add(sample_type)
            item["evidence"].extend(
                {
                    "sample_type": sample_type,
                    "source": evidence.source,
                    "signal": evidence.signal,
                    "strength": evidence.strength,
                    "weight": evidence.weight,
                }
                for evidence in result.evidence
            )

    output: list[SourceFingerprint] = []
    for (engine, layer), item in grouped.items():
        sample_types = tuple(sorted(item["sample_types"]))
        product_level = bool({"product_page", "internal_search", "structured_api"} & set(sample_types))
        intrinsic_product_data = engine == "generic_json_ld_product" and "product_page" in sample_types
        intrinsic_feed = engine == "sitemap_catalog_feed" and "sitemap" in sample_types
        confirmed = len(sample_types) >= 2 or product_level or intrinsic_product_data or intrinsic_feed
        status = FingerprintStatus.CONFIRMED if confirmed else FingerprintStatus.PROBABLE
        confidence = item["confidence"] if confirmed else min(item["confidence"], 0.69)
        output.append(SourceFingerprint(engine, layer, status, round(confidence, 2), sample_types, tuple(item["evidence"])))

    if not output:
        return (SourceFingerprint("custom_unknown", "unknown", FingerprintStatus.INSUFFICIENT, 0.0, tuple(sorted(all_sample_types)), ()),)
    return tuple(sorted(output, key=lambda item: (-item.confidence, item.layer, item.engine)))
