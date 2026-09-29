"""Bounded, CMS-neutral sitemap/catalog-feed discovery core v1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import gzip
import io
import math
import re
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

from product_tool.identity import IdentityVerification, ProductIdentity, VerificationLevel, normalize_identity_value

from .discovery import parse_sitemap, validate_structured_product_identity
from .endpoint_probe import AccessProbe, ProbePolicy, ProbeResult
from .models import AccessStatus, EndpointCapability, ProtectionStatus


TRACKING_PARAMETERS = frozenset({
    "fbclid", "gclid", "yclid", "_ga", "mc_cid", "mc_eid", "_sid", "_pos", "_ss",
})
BLOCKING_ACCESS = frozenset({AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED})
SUCCESS_ACCESS = frozenset({AccessStatus.DIRECT_ACCESS, AccessStatus.JAVASCRIPT_REQUIRED})


@dataclass(frozen=True)
class DiscoveryBudget:
    max_http_requests: int = 12
    max_sitemap_documents: int = 5
    max_sitemap_depth: int = 2
    max_urls_read: int = 500
    max_product_candidates: int = 25
    max_product_pages: int = 3
    min_interval_seconds: float = 1.0
    deadline_seconds: float = 60.0
    max_response_bytes: int = 1_000_000
    max_gzip_uncompressed_bytes: int = 2_000_000
    stop_host_on_protection: bool = True

    def __post_init__(self) -> None:
        numeric = (
            self.max_http_requests, self.max_sitemap_documents, self.max_sitemap_depth,
            self.max_urls_read, self.max_product_candidates, self.max_product_pages,
            self.deadline_seconds, self.max_response_bytes, self.max_gzip_uncompressed_bytes,
        )
        if any(not math.isfinite(value) or value <= 0 for value in numeric):
            raise ValueError("Discovery budget limits must be positive")
        if self.max_product_pages > self.max_product_candidates:
            raise ValueError("max_product_pages cannot exceed max_product_candidates")
        if any(not isinstance(value, int) or isinstance(value, bool) for value in numeric[:-3] + (self.max_response_bytes, self.max_gzip_uncompressed_bytes)):
            raise ValueError("Discovery count/size limits must be integers")
        if not math.isfinite(self.min_interval_seconds) or self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds cannot be negative")


@dataclass
class BudgetUsage:
    http_requests: int = 0
    sitemap_documents: int = 0
    valid_sitemap_documents: int = 0
    urls_read: int = 0
    product_pages: int = 0
    search_queries: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class CandidatePage:
    url: str
    final_url: str
    source_family: str
    strategy: str
    ranking_score: float
    ranking_reasons: tuple[str, ...]
    category_hints: tuple[str, ...] = ()
    model_token_hints: tuple[str, ...] = ()
    discovery_evidence: tuple[Mapping[str, Any], ...] = ()
    access_status: str = "not_checked"
    protection_status: str = "inconclusive"
    identity_verification: Mapping[str, Any] = field(default_factory=dict)
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("ranking_reasons", "category_hints", "model_token_hints", "discovery_evidence"):
            value[key] = list(value[key])
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidatePage":
        return cls(
            url=str(value["url"]),
            final_url=str(value.get("final_url", "")),
            source_family=str(value["source_family"]),
            strategy=str(value.get("strategy", "sitemap_catalog")),
            ranking_score=float(value.get("ranking_score", 0)),
            ranking_reasons=tuple(value.get("ranking_reasons") or ()),
            category_hints=tuple(value.get("category_hints") or ()),
            model_token_hints=tuple(value.get("model_token_hints") or ()),
            discovery_evidence=tuple(value.get("discovery_evidence") or ()),
            access_status=str(value.get("access_status", "not_checked")),
            protection_status=str(value.get("protection_status", "inconclusive")),
            identity_verification=dict(value.get("identity_verification") or {}),
            rejection_reason=str(value.get("rejection_reason", "")),
        )


@dataclass
class StrategyResult:
    source_family: str
    candidates: tuple[CandidatePage, ...]
    budget_used: BudgetUsage
    sitemap_feed_urls: tuple[str, ...]
    redirect_evidence: tuple[Mapping[str, Any], ...]
    errors: tuple[str, ...]
    truncated: bool
    stop_reason: str
    checkpoint: Mapping[str, Any]
    started_at: str
    finished_at: str
    strategy: str = "sitemap_catalog"
    strategy_evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "strategy_evidence": dict(self.strategy_evidence),
            "source_family": self.source_family,
            "candidates": [item.to_dict() for item in self.candidates],
            "budget_used": self.budget_used.to_dict(),
            "sitemap_feed_urls": list(self.sitemap_feed_urls),
            "redirect_evidence": list(self.redirect_evidence),
            "errors": list(self.errors),
            "truncated": self.truncated,
            "stop_reason": self.stop_reason,
            "checkpoint": dict(self.checkpoint),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def _host_allowed(host: str, allowed_hosts: Iterable[str]) -> bool:
    host = host.casefold().rstrip(".")
    return bool(host) and any(host == allowed.casefold() or host.endswith("." + allowed.casefold()) for allowed in allowed_hosts)


def normalize_candidate_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_PARAMETERS and not key.casefold().startswith("utm_")
    ]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, urlencode(sorted(query)), ""))


def safe_gzip_decompress(payload: bytes, *, max_output_bytes: int) -> bytes:
    """Bound gzip expansion and reject concatenated/oversized payloads."""
    if max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be positive")
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
        output = stream.read(max_output_bytes + 1)
    if len(output) > max_output_bytes:
        raise ValueError("gzip_uncompressed_limit_exceeded")
    return output


def robots_sitemap_declarations(text: str) -> tuple[str, ...]:
    values = re.findall(r"(?im)^\s*sitemap\s*:\s*(https?://\S+)\s*$", text or "")
    return tuple(dict.fromkeys(value.strip() for value in values))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def parse_catalog_document(text: str, *, max_urls: int) -> tuple[str, tuple[str, ...], bool]:
    """Parse sitemap XML or a bounded first-party RSS/Atom catalog feed."""
    try:
        return parse_sitemap(text, max_urls=max_urls)
    except ValueError:
        pass
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ValueError(f"invalid_xml:{exc}") from exc
    root_kind = _local_name(root.tag)
    if root_kind not in {"rss", "feed"}:
        raise ValueError(f"unsupported_catalog_root:{root_kind}")
    values: list[str] = []
    for node in root.iter():
        if _local_name(node.tag) != "link":
            continue
        value = (node.attrib.get("href") or node.text or "").strip()
        if value.startswith(("http://", "https://")):
            values.append(value)
    return "catalog_feed", tuple(values[:max_urls]), len(values) > max_urls


def _token_forms(value: str) -> tuple[str, ...]:
    raw = str(value or "").strip()
    if not raw:
        return ()
    forms = {raw.casefold(), re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-")}
    normalized = normalize_identity_value(raw).casefold()
    if len(normalized) >= 4:
        forms.add(normalized)
    return tuple(sorted(x for x in forms if len(x) >= 3))


def rank_sitemap_url(url: str, category_hints: Iterable[str] = ()) -> tuple[int, tuple[str, ...]]:
    value = url.casefold()
    score = 0
    reasons: list[str] = []
    for token, weight in (("product", 40), ("products", 40), ("catalog", 32), ("shop", 24), ("store", 20)):
        if token in value:
            score += weight
            reasons.append(f"sitemap_name:{token}+{weight}")
            break
    for token, weight in (("image", -45), ("news", -35), ("blog", -30), ("tag", -25), ("article", -25)):
        if token in value:
            score += weight
            reasons.append(f"service_sitemap:{token}{weight}")
    for hint in category_hints:
        form = re.sub(r"[^a-z0-9]+", "-", hint.casefold()).strip("-")
        if len(form) >= 3 and form in value:
            score += 15
            reasons.append(f"category_sitemap:{form}+15")
    return score, tuple(reasons)


def rank_candidate_url(
    url: str,
    *,
    expected: ProductIdentity,
    source_family: str,
    allowed_hosts: tuple[str, ...],
    sitemap_url: str = "",
    category_hints: Iterable[str] = (),
) -> tuple[float, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    normalized = normalize_candidate_url(url)
    parsed = urlsplit(normalized)
    value = normalized.casefold()
    reasons: list[str] = []
    models: list[str] = []
    categories: list[str] = []
    score = 0.0
    if _host_allowed(parsed.hostname or "", allowed_hosts):
        score += 15
        reasons.append("canonical_first_party_host:+15")
    else:
        return -1000.0, ("foreign_host:-1000",), (), ()
    compact_url = normalize_identity_value(value).casefold()
    for model in expected.model_candidates:
        forms = _token_forms(model)
        if any(form in value or normalize_identity_value(form).casefold() in compact_url for form in forms):
            score += 70
            models.append(model)
            reasons.append(f"model_token_in_url:{model}:+70")
            break
    product_like = re.search(r"/(?:product|products|p|shop|store|catalog|mkt-product)(?:/|-)", parsed.path, re.I)
    if product_like:
        score += 25
        reasons.append("product_like_path:+25")
    sitemap_score, sitemap_reasons = rank_sitemap_url(sitemap_url, category_hints)
    if sitemap_score > 0:
        score += min(20, sitemap_score)
        reasons.append("product_catalog_sitemap:+20")
    family_form = source_family.replace("_", "-").casefold()
    if family_form and family_form in value:
        score += 8
        reasons.append("source_family_in_url:+8")
    for hint in category_hints:
        forms = _token_forms(hint)
        if any(form in value for form in forms):
            score += 12
            categories.append(hint)
            reasons.append(f"category_hint:{hint}:+12")
    negatives = (
        (r"/(?:blog|news|article|tag|press)(?:/|$)", -35, "content_page"),
        (r"/(?:search|account|cart|checkout|login|signin)(?:/|$)", -80, "non_product_flow"),
        (r"\.(?:jpg|jpeg|png|gif|webp|svg|css|js)(?:$|\?)", -200, "asset"),
        (r"\.pdf(?:$|\?)", -90, "pdf_before_document_stage"),
        (r"/support/(?:article|content|faq)", -25, "support_article"),
    )
    for pattern, weight, reason in negatives:
        if re.search(pattern, value, re.I):
            score += weight
            reasons.append(f"{reason}:{weight}")
    if not models and re.search(r"/(?:category|collections?|catalog)(?:/|$)", parsed.path, re.I):
        score -= 25
        reasons.append("category_only_without_model:-25")
    return score, tuple(reasons), tuple(categories), tuple(models)


def _deduplicate_candidates(candidates: Iterable[CandidatePage], limit: int) -> tuple[CandidatePage, ...]:
    by_url: dict[str, CandidatePage] = {}
    for item in candidates:
        key = normalize_candidate_url(item.final_url or item.url)
        old = by_url.get(key)
        if old is None or item.ranking_score > old.ranking_score:
            by_url[key] = item
    ordered = sorted(by_url.values(), key=lambda item: (-item.ranking_score, normalize_candidate_url(item.url)))
    verified: dict[str, CandidatePage] = {}
    output: list[CandidatePage] = []
    for item in ordered:
        verification = item.identity_verification
        identity_key = ""
        if verification.get("level") in {"exact_model", "exact_variant"}:
            matched = [
                evidence.get("normalized_value", "")
                for evidence in verification.get("evidence", ())
                if evidence.get("evidence_type") == "model_code" and evidence.get("state") == "match"
            ]
            identity_key = next((value for value in matched if value), "")
        if identity_key:
            if identity_key in verified:
                continue
            verified[identity_key] = item
        output.append(item)
        if len(output) >= limit:
            break
    return tuple(output)


class SitemapCatalogStrategy:
    strategy_id = "sitemap_catalog"

    def __init__(
        self,
        *,
        budget: DiscoveryBudget | None = None,
        probe: AccessProbe | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.budget = budget or DiscoveryBudget()
        self.clock = clock
        self.probe = probe or AccessProbe(policy=ProbePolicy(
            timeout_seconds=min(15.0, self.budget.deadline_seconds),
            max_bytes=self.budget.max_response_bytes,
            min_interval_seconds=self.budget.min_interval_seconds,
        ), clock=clock)

    def run(
        self,
        *,
        source_family: str,
        source_url: str,
        allowed_hosts: tuple[str, ...],
        expected: ProductIdentity,
        sitemap_urls: tuple[str, ...] = (),
        category_hints: tuple[str, ...] = (),
        checkpoint: Mapping[str, Any] | None = None,
        refresh: bool = False,
    ) -> StrategyResult:
        started_at = datetime.now(timezone.utc).isoformat()
        started_clock = self.clock()
        prior = {} if refresh else dict(checkpoint or {})
        usage = BudgetUsage(**dict(prior.get("budget_used") or {}))
        candidates = [CandidatePage.from_dict(x) for x in prior.get("candidates", ())]
        completed = set(prior.get("completed_sitemaps", ()))
        pending = [tuple(x) for x in prior.get("pending_sitemaps", ())]
        sitemap_seen = list(prior.get("sitemap_feed_urls", ()))
        redirects = list(prior.get("redirect_evidence", ()))
        errors = list(prior.get("errors", ()))
        truncated = bool(prior.get("truncated", False))
        stop_reason = ""

        def exhausted() -> str:
            if usage.http_requests >= self.budget.max_http_requests:
                return "request_budget_exhausted"
            if self.clock() - started_clock >= self.budget.deadline_seconds:
                return "deadline_exhausted"
            return ""

        def do_probe(url: str, capability: EndpointCapability, sample_type: str) -> ProbeResult | None:
            nonlocal stop_reason
            reason = exhausted()
            if reason:
                stop_reason = reason
                return None
            usage.http_requests += 1
            result = self.probe.probe(url, allowed_hosts=allowed_hosts, capability=capability, sample_type=sample_type)
            if len(result.redirect_chain) > 1 or result.final_url != url:
                redirects.append({"url": url, "chain": list(result.redirect_chain), "final_url": result.final_url})
            if result.access_status in BLOCKING_ACCESS:
                stop_reason = result.access_status.value
            return result

        root = urlsplit(source_url)
        robots_url = urlunsplit((root.scheme or "https", root.netloc, "/robots.txt", "", ""))
        if not pending and not completed:
            robots = do_probe(robots_url, EndpointCapability.ROBOTS, "robots_txt")
            declared: tuple[str, ...] = ()
            if robots and robots.access_status in SUCCESS_ACCESS:
                declared = tuple(
                    url for url in robots_sitemap_declarations(robots.diagnostic_text)
                    if _host_allowed(urlsplit(url).hostname or "", allowed_hosts)
                )
            if stop_reason:
                pending = []
            else:
                defaults = sitemap_urls or declared or (
                    urlunsplit((root.scheme or "https", root.netloc, "/sitemap.xml", "", "")),
                )
                ranked = sorted(dict.fromkeys(defaults), key=lambda url: (-rank_sitemap_url(url, category_hints)[0], normalize_candidate_url(url)))
                pending = [(url, 0) for url in ranked]

        while pending and not stop_reason:
            if usage.sitemap_documents >= self.budget.max_sitemap_documents:
                truncated = True
                stop_reason = "sitemap_document_budget_exhausted"
                break
            url, depth = pending.pop(0)
            if url in completed:
                continue
            if not _host_allowed(urlsplit(url).hostname or "", allowed_hosts):
                errors.append(f"foreign_sitemap_rejected:{url}")
                completed.add(url)
                continue
            result = do_probe(url, EndpointCapability.SITEMAP, "sitemap_catalog")
            if result is None:
                break
            completed.add(url)
            usage.sitemap_documents += 1
            sitemap_seen.append(result.final_url or url)
            if result.access_status not in SUCCESS_ACCESS:
                errors.append(f"{url}:{result.access_status.value}")
                continue
            text = result.diagnostic_text
            remaining_urls = self.budget.max_urls_read - usage.urls_read
            if remaining_urls <= 0:
                truncated = True
                stop_reason = "url_budget_exhausted"
                break
            try:
                kind, locations, was_truncated = parse_catalog_document(
                    text, max_urls=max(remaining_urls, self.budget.max_sitemap_documents * 10)
                )
            except ValueError as exc:
                errors.append(f"{url}:{exc}")
                continue
            usage.valid_sitemap_documents += 1
            truncated = truncated or was_truncated
            if kind == "sitemapindex":
                if depth >= self.budget.max_sitemap_depth:
                    truncated = truncated or bool(locations)
                    continue
                ranked_children = sorted(
                    (child for child in locations if _host_allowed(urlsplit(child).hostname or "", allowed_hosts)),
                    key=lambda child: (-rank_sitemap_url(child, category_hints)[0], normalize_candidate_url(child)),
                )
                room = self.budget.max_sitemap_documents - usage.sitemap_documents - len(pending)
                selected = ranked_children[:max(0, room)]
                truncated = truncated or len(selected) < len(ranked_children)
                pending.extend((child, depth + 1) for child in selected)
                continue
            if len(locations) > remaining_urls:
                locations = locations[:remaining_urls]
                truncated = True
            usage.urls_read += len(locations)
            for location in locations:
                if usage.urls_read > self.budget.max_urls_read:
                    truncated = True
                    break
                score, reasons, categories, models = rank_candidate_url(
                    location,
                    expected=expected,
                    source_family=source_family,
                    allowed_hosts=allowed_hosts,
                    sitemap_url=url,
                    category_hints=category_hints,
                )
                if score <= 0:
                    continue
                candidates.append(CandidatePage(
                    url=normalize_candidate_url(location),
                    final_url="",
                    source_family=source_family,
                    strategy=self.strategy_id,
                    ranking_score=score,
                    ranking_reasons=reasons,
                    category_hints=categories,
                    model_token_hints=models,
                    discovery_evidence=({"type": "sitemap_loc", "sitemap_url": url},),
                ))
            candidates = list(_deduplicate_candidates(candidates, self.budget.max_product_candidates))

        candidates = list(_deduplicate_candidates(candidates, self.budget.max_product_candidates))
        hard_stop = stop_reason in {
            "captcha_or_blocked", "rate_limited", "request_budget_exhausted",
            "deadline_exhausted",
        }
        for candidate in candidates:
            if hard_stop or usage.product_pages >= self.budget.max_product_pages:
                break
            if candidate.identity_verification or candidate.access_status != "not_checked":
                continue
            result = do_probe(candidate.url, EndpointCapability.PRODUCT_PAGE, "sitemap_candidate")
            if result is None:
                candidate.rejection_reason = "budget_exhausted"
                break
            usage.product_pages += 1
            candidate.final_url = result.final_url
            candidate.access_status = result.access_status.value
            candidate.protection_status = result.protection_status.value
            if result.access_status in BLOCKING_ACCESS:
                candidate.rejection_reason = "blocked"
                break
            if result.access_status not in SUCCESS_ACCESS:
                candidate.rejection_reason = "unavailable"
                continue
            verification = validate_structured_product_identity(
                result.diagnostic_text, expected=expected, source_url=result.final_url or candidate.url
            )
            candidate.identity_verification = verification.to_dict()
            if verification.level == VerificationLevel.CONFLICT:
                candidate.rejection_reason = "structured_identity_conflict"
            elif verification.level == VerificationLevel.INSUFFICIENT:
                candidate.rejection_reason = "structured_identity_insufficient"

        candidates = list(_deduplicate_candidates(candidates, self.budget.max_product_candidates))
        if not stop_reason:
            if not sitemap_seen:
                stop_reason = "strategy_not_applicable"
            elif not candidates:
                stop_reason = "insufficient"
            elif usage.product_pages >= self.budget.max_product_pages and not any(
                item.identity_verification.get("level") in {"exact_model", "exact_variant"} for item in candidates
            ):
                stop_reason = "product_page_budget_exhausted"
            else:
                stop_reason = "complete"
        finished_at = datetime.now(timezone.utc).isoformat()
        checkpoint_value = {
            "version": 1,
            "status": "complete" if stop_reason in {"complete", "strategy_not_applicable", "insufficient"} else "stopped",
            "completed_sitemaps": sorted(completed),
            "pending_sitemaps": [list(x) for x in pending],
            "sitemap_feed_urls": list(dict.fromkeys(sitemap_seen)),
            "redirect_evidence": redirects,
            "errors": errors,
            "candidates": [item.to_dict() for item in candidates],
            "budget_used": usage.to_dict(),
            "truncated": truncated,
            "stop_reason": stop_reason,
            "updated_at": finished_at,
        }
        return StrategyResult(
            source_family=source_family,
            candidates=tuple(candidates),
            budget_used=usage,
            sitemap_feed_urls=tuple(dict.fromkeys(sitemap_seen)),
            redirect_evidence=tuple(redirects),
            errors=tuple(errors),
            truncated=truncated,
            stop_reason=stop_reason,
            checkpoint=checkpoint_value,
            started_at=started_at,
            finished_at=finished_at,
        )


def discovery_readiness(result: StrategyResult, *, official_source_verified: bool) -> dict[str, bool]:
    levels = {item.identity_verification.get("level") for item in result.candidates}
    product_found = any(item.access_status in {x.value for x in SUCCESS_ACCESS} for item in result.candidates)
    applicable = result.budget_used.valid_sitemap_documents > 0
    reproducible = bool(applicable and result.candidates and result.stop_reason not in {"strategy_not_applicable"})
    return {
        "official_source_verified": official_source_verified,
        "sitemap_strategy_applicable": applicable,
        "discovery_reproducible": reproducible,
        "product_page_found": product_found,
        "exact_model_validated": bool(levels & {"exact_model", "exact_variant"}),
        "exact_variant_validated": "exact_variant" in levels,
        "requires_other_strategy": not bool(levels & {"exact_model", "exact_variant"}),
        "requires_manual_browser_review": result.stop_reason in {"captcha_or_blocked", "rate_limited"} or any(
            item.access_status == "javascript_required" for item in result.candidates
        ),
        "production_ready": False,
    }
