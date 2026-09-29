"""Generic bounded discovery primitives used before platform adapters exist."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import warnings
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree


@dataclass(frozen=True)
class SitemapPolicy:
    max_index_children: int = 3
    max_urls: int = 100
    max_depth: int = 1


@dataclass(frozen=True)
class SitemapDiscovery:
    sitemap_urls: tuple[str, ...]
    product_candidates: tuple[str, ...]
    truncated: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmbeddedStateEvidence:
    kind: str
    script_id: str
    keys: tuple[str, ...]


@dataclass(frozen=True)
class IdentityObservation:
    model: str = ""
    sku: str = ""
    mpn: str = ""
    product_name: str = ""
    variant: str = ""
    regional_product_code: str = ""
    confidence: float = 0.0
    evidence: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence"] = list(self.evidence)
        return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def parse_sitemap(xml_text: str, *, max_urls: int = 100) -> tuple[str, tuple[str, ...], bool]:
    """Return root kind, bounded loc values and whether values were truncated."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ValueError(f"Invalid sitemap XML: {exc}") from exc
    kind = _local_name(root.tag)
    if kind not in {"urlset", "sitemapindex"}:
        raise ValueError(f"Unsupported sitemap root: {kind}")
    locations = [
        (node.text or "").strip()
        for node in root.iter()
        if _local_name(node.tag) == "loc" and (node.text or "").strip()
    ]
    return kind, tuple(locations[:max_urls]), len(locations) > max_urls


def bounded_sitemap_discovery(
    start_url: str,
    *,
    fetch,
    allowed_hosts: tuple[str, ...],
    policy: SitemapPolicy | None = None,
) -> SitemapDiscovery:
    """Traverse a sitemap index with explicit depth and item caps.

    ``fetch(url)`` returns XML text. Network policy remains owned by the caller.
    """
    policy = policy or SitemapPolicy()
    sitemap_urls: list[str] = []
    product_candidates: list[str] = []
    errors: list[str] = []
    queue: list[tuple[str, int]] = [(start_url, 0)]
    seen: set[str] = set()
    truncated = False
    while queue and len(product_candidates) < policy.max_urls:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        host = (urlsplit(url).hostname or "").casefold()
        if not any(host == allowed.casefold() or host.endswith("." + allowed.casefold()) for allowed in allowed_hosts):
            errors.append(f"non_allowlisted_sitemap:{url}")
            continue
        try:
            kind, locations, was_truncated = parse_sitemap(fetch(url), max_urls=policy.max_urls)
        except Exception as exc:  # fetch failures are report data, not fatal to the queue
            errors.append(f"{url}:{exc}")
            continue
        sitemap_urls.append(url)
        truncated = truncated or was_truncated
        if kind == "sitemapindex":
            if depth >= policy.max_depth:
                truncated = truncated or bool(locations)
                continue
            children = locations[: policy.max_index_children]
            truncated = truncated or len(locations) > len(children)
            queue.extend((child, depth + 1) for child in children)
        else:
            room = policy.max_urls - len(product_candidates)
            product_candidates.extend(locations[:room])
            truncated = truncated or len(locations) > room
    return SitemapDiscovery(tuple(sitemap_urls), tuple(product_candidates), truncated, tuple(errors))


def json_ld_products(html: str) -> tuple[dict[str, Any], ...]:
    products: list[dict[str, Any]] = []
    for match in re.finditer(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html or "", re.I | re.S):
        try:
            value = json.loads(match.group(1).strip())
        except (TypeError, ValueError):
            continue
        nodes: Iterable[Any] = value if isinstance(value, list) else (value,)
        for node in nodes:
            graph = node.get("@graph", ()) if isinstance(node, dict) else ()
            candidates = tuple(graph) if isinstance(graph, list) else ()
            for candidate in ((node,) if isinstance(node, dict) else ()) + candidates:
                kind = candidate.get("@type") if isinstance(candidate, dict) else None
                kinds = {kind} if isinstance(kind, str) else {x for x in kind if isinstance(x, str)} if isinstance(kind, list) else set()
                if "Product" in kinds:
                    products.append(candidate)
    return tuple(products)


JSON_LD_PRODUCT_FIELDS = (
    "name", "sku", "mpn", "model", "gtin", "brand", "image", "description",
    "characteristics", "documents", "variant_data",
)


def json_ld_field_coverage(html: str) -> dict[str, bool]:
    """Report useful Product fields without retaining product payload values."""
    products = json_ld_products(html)
    coverage = {field: False for field in JSON_LD_PRODUCT_FIELDS}
    for product in products:
        coverage["name"] |= bool(product.get("name"))
        coverage["sku"] |= bool(product.get("sku"))
        coverage["mpn"] |= bool(product.get("mpn"))
        coverage["model"] |= bool(product.get("model"))
        coverage["gtin"] |= any(bool(product.get(key)) for key in ("gtin", "gtin8", "gtin12", "gtin13", "gtin14"))
        coverage["brand"] |= bool(product.get("brand"))
        coverage["image"] |= bool(product.get("image"))
        coverage["description"] |= bool(product.get("description"))
        coverage["characteristics"] |= any(bool(product.get(key)) for key in ("additionalProperty", "additionalProperties", "hasMeasurement"))
        coverage["documents"] |= any(bool(product.get(key)) for key in ("subjectOf", "associatedMedia", "documentation"))
        coverage["variant_data"] |= any(bool(product.get(key)) for key in ("isVariantOf", "hasVariant", "productGroupID", "inProductGroupWithID", "color", "size"))
    return coverage


def detect_embedded_state(html: str) -> tuple[EmbeddedStateEvidence, ...]:
    found: list[EmbeddedStateEvidence] = []
    patterns = (
        ("next_data", r"<script[^>]+id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>"),
        ("nuxt_state", r"<script[^>]*>\s*window\.__NUXT__\s*=\s*(\{.*?\})\s*</script>"),
        ("application_json", r"<script[^>]+type=[\"']application/json[\"'][^>]*>(.*?)</script>"),
    )
    for kind, pattern in patterns:
        for index, match in enumerate(re.finditer(pattern, html or "", re.I | re.S)):
            raw = match.group(1).strip()
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                continue
            keys = tuple(sorted(str(key) for key in value)[:20]) if isinstance(value, dict) else ()
            found.append(EmbeddedStateEvidence(kind, f"{kind}:{index}", keys))
    return tuple(found)


def detect_internal_search(html: str, base_url: str, *, allowed_hosts=None, configured_endpoints=()):
    """Return declarative SearchRoute evidence; execute nothing."""
    from .search_routes import detect_routes
    return detect_routes(html, base_url, allowed_hosts=allowed_hosts, configured_endpoints=configured_endpoints)


def _legacy_text_identity_observation(html: str, *, expected_models: Iterable[str]) -> IdentityObservation:
    """Legacy stage-2 observation. Never use for readiness or orchestration."""
    expected = tuple(str(value).strip() for value in expected_models if str(value).strip())
    products = json_ld_products(html)
    fields: dict[str, str] = {}
    evidence: list[dict[str, Any]] = []
    if products:
        product = products[0]
        for key in ("sku", "mpn", "name", "model"):
            value = product.get(key)
            if isinstance(value, (str, int, float)):
                fields[key] = str(value)
        evidence.append({"type": "json_ld_product", "fields": sorted(fields)})
    haystack = " ".join((html or "", *fields.values())).casefold()
    matched = [model for model in expected if model.casefold() in haystack]
    if matched:
        evidence.append({"type": "expected_model_match", "models": matched})
    confidence = 0.0
    if products:
        confidence += 0.45
    if matched:
        confidence += 0.5
    return IdentityObservation(
        model=fields.get("model", matched[0] if matched else ""),
        sku=fields.get("sku", ""),
        mpn=fields.get("mpn", ""),
        product_name=fields.get("name", ""),
        variant=fields.get("sku", ""),
        confidence=min(1.0, confidence),
        evidence=tuple(evidence),
    )


def validate_product_candidate(html: str, *, expected_models: Iterable[str]) -> IdentityObservation:
    """Deprecated compatibility wrapper for historical reports/tests only."""
    warnings.warn(
        "validate_product_candidate is legacy text evidence and cannot establish identity",
        DeprecationWarning,
        stacklevel=2,
    )
    return _legacy_text_identity_observation(html, expected_models=expected_models)


def validate_structured_product_identity(html: str, *, expected, source_url: str = ""):
    """Verify identity from JSON-LD Product fields only.

    Unlike the legacy census observation helper, this function never searches
    arbitrary page text.  Exact identity therefore requires a structured model
    or manufacturer SKU plus any significant expected variant fields.
    """
    from product_tool.identity import (
        IdentityVerifier,
        PageIdentity,
        VariantAttributes,
        extract_variant_attributes,
    )

    products = json_ld_products(html)
    if not products:
        return IdentityVerifier().verify(
            expected, PageIdentity(), source=source_url, extraction_method="json_ld_product"
        )
    product = products[0]
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    variant_values = {
        key: product.get(key)
        for key in ("color", "size")
        if product.get(key) not in (None, "")
    }
    identity_fields = {"memory": "storage", "storage": "storage", "ram": "ram",
                       "revision": "hardware_revision", "hardwareRevision": "hardware_revision",
                       "serviceIndex": "service_index", "region": "region", "configuration": "configuration"}
    for key, target in identity_fields.items():
        if isinstance(product.get(key), (str, int, float)):
            variant_values[target] = product[key]
    structured_name = str(product.get("name") or "")
    codes = tuple(str(product.get(key) or "") for key in ("sku", "mpn", "model"))
    inferred = extract_variant_attributes(structured_name, *codes).to_dict()
    inferred.update(variant_values)
    observed = PageIdentity(
        manufacturer_sku=str(product.get("mpn") or product.get("sku") or ""),
        model_code=str(product.get("model") or ""),
        family=str(product.get("productGroupID") or product.get("inProductGroupWithID") or ""),
        ean_gtin=str(next((product.get(k) for k in ("gtin", "gtin14", "gtin13", "gtin12", "gtin8") if product.get(k)), "")),
        variant_attributes=VariantAttributes(inferred),
    )
    result = IdentityVerifier().verify(
        expected, observed, source=source_url, extraction_method="json_ld_product"
    )
    return result
