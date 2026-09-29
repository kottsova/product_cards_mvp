"""Evidence-based platform fingerprinting for bounded diagnostic samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Iterable, Mapping

from .models import FingerprintStatus


@dataclass(frozen=True)
class FingerprintEvidence:
    source: str
    signal: str
    strength: str
    weight: float


@dataclass(frozen=True)
class PlatformFingerprint:
    engine: str
    status: FingerprintStatus
    confidence: float
    evidence: tuple[FingerprintEvidence, ...]

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "status": self.status.value,
            "confidence": self.confidence,
            "evidence": [asdict(item) for item in self.evidence],
        }


SIGNALS: dict[str, tuple[tuple[str, str, str, float], ...]] = {
    "shopify": (
        ("html", r"cdn\.shopify\.com|Shopify\.theme|shopify-section", "strong", .75),
        ("headers", r"x-shopid|x-shopify", "strong", .8),
        ("cookies", r"_shopify|cart_sig", "weak", .35),
    ),
    "magento": (
        ("html", r"/static/version\d+|Magento_[A-Za-z]+|mage-cache-storage", "strong", .75),
        ("headers", r"x-magento", "strong", .8),
        ("cookies", r"private_content_version|mage-cache", "weak", .4),
    ),
    "salesforce_commerce_cloud": (
        ("html", r"/on/demandware\.store/|dwcont=|Demandware", "strong", .85),
        ("cookies", r"dwsid|dwsecuretoken|dwac_", "strong", .8),
    ),
    "woocommerce": (
        ("html", r"wp-content/plugins/woocommerce|wc-ajax=|woocommerce_params", "strong", .8),
        ("cookies", r"woocommerce_|wp_woocommerce", "weak", .4),
        ("html", r"/wp-content/", "weak", .25),
    ),
    "adobe_experience_manager": (
        ("html", r"/etc\.clientlibs/|/content/dam/|granite\.utils|cq:Page", "strong", .75),
        ("headers", r"x-aem|dispatcher", "weak", .35),
    ),
    "sitecore": (
        ("html", r"/-/media/|sitecore|sc_mode", "strong", .7),
        ("cookies", r"SC_ANALYTICS|sitecore", "weak", .4),
    ),
    "next_js": (
        ("html", r"__NEXT_DATA__|/_next/static/", "strong", .8),
        ("headers", r"x-powered-by\s*[:=]?\s*next\.js", "strong", .8),
    ),
    "nuxt": (
        ("html", r"__NUXT__|/_nuxt/|__nuxt", "strong", .8),
        ("headers", r"x-powered-by\s*[:=]?\s*nuxt", "strong", .8),
    ),
}


def _json_ld_product(html: str) -> list[FingerprintEvidence]:
    evidence: list[FingerprintEvidence] = []
    for match in re.finditer(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html, re.I | re.S):
        raw = match.group(1).strip()
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            continue
        nodes: Iterable = value if isinstance(value, list) else (value,)
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Product":
                evidence.append(FingerprintEvidence("json_ld", "@type=Product", "strong", .8))
                return evidence
            if isinstance(node, dict) and isinstance(node.get("@graph"), list) and any(
                isinstance(item, dict) and item.get("@type") == "Product" for item in node["@graph"]
            ):
                evidence.append(FingerprintEvidence("json_ld", "@graph contains Product", "strong", .8))
                return evidence
    return evidence


def fingerprint_platform(
    html: str,
    *,
    headers: Mapping[str, str] | None = None,
    cookies: Mapping[str, str] | None = None,
    content_type: str = "",
) -> tuple[PlatformFingerprint, ...]:
    haystacks = {
        "html": html or "",
        "headers": "\n".join(f"{key}: {value}" for key, value in (headers or {}).items()),
        "cookies": "\n".join(f"{key}={value}" for key, value in (cookies or {}).items()),
    }
    found: list[PlatformFingerprint] = []
    for engine, rules in SIGNALS.items():
        evidence = tuple(
            FingerprintEvidence(source, pattern, strength, weight)
            for source, pattern, strength, weight in rules
            if re.search(pattern, haystacks[source], re.I)
        )
        if not evidence:
            continue
        total = min(1.0, sum(item.weight for item in evidence))
        has_strong = any(item.strength == "strong" for item in evidence)
        status = FingerprintStatus.CONFIRMED if has_strong or (len(evidence) >= 2 and total >= .7) else FingerprintStatus.PROBABLE
        confidence = total if status == FingerprintStatus.CONFIRMED else min(total, .69)
        found.append(PlatformFingerprint(engine, status, round(confidence, 2), evidence))

    json_ld = _json_ld_product(html or "")
    if json_ld:
        found.append(PlatformFingerprint("generic_json_ld_product", FingerprintStatus.CONFIRMED, .8, tuple(json_ld)))
    if re.search(r"(?i)(application/(?:rss\+xml|xml)|text/xml)", content_type) and re.search(r"<(?:urlset|sitemapindex|rss|feed)\b", html or "", re.I):
        found.append(PlatformFingerprint(
            "sitemap_catalog_feed", FingerprintStatus.CONFIRMED, .9,
            (FingerprintEvidence("content", "XML catalog/sitemap root", "strong", .9),),
        ))
    if not found:
        return (PlatformFingerprint("custom_unknown", FingerprintStatus.INSUFFICIENT, 0.0, ()),)
    return tuple(sorted(found, key=lambda item: (-item.confidence, item.engine)))
