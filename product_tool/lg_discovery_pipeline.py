"""Bounded sequential web search fallback for LG, after regional sitemap/search."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from urllib.parse import urlsplit

from . import jobs
from .adapters.common import SourceDocument
from .adapters.lg import LGAdapter, LGRUAdapter, lg_article_components, lg_base_model
from .adapters.lg_global import LGGlobalAdapter, official_product_url
from .adapters.lg_support import is_official_support_url

MAX_PRODUCT_FETCHES = 4
MAX_SUPPORT_CANDIDATES = 8


@dataclass(frozen=True)
class GoogleFallbackOutcome:
    product_document: SourceDocument | None = None
    support_urls: tuple[str, ...] = ()
    queries: tuple[str, ...] = ()
    stop_reason: str = ""


def _trace(browser, **event) -> None:
    callback = getattr(browser, "_trace", None)
    if callback is not None:
        callback(event="decision", timestamp=datetime.now(timezone.utc).isoformat(), **event)


def _candidate_document(candidate, full: str, *, kz, ru, global_adapter,
                        deadline: float) -> SourceDocument | None:
    url = candidate.url
    if not official_product_url(url):
        return None
    region = urlsplit(url).path.split("/")[1].casefold()
    if region == "kz" and isinstance(kz, LGAdapter):
        page = kz.fetch_page(url, deadline)
        return kz._document(page, full, lg_base_model(full))
    if region == "ru" and isinstance(ru, LGRUAdapter):
        return ru._document_at(url, full, lg_base_model(full), deadline)
    if region not in {"kz", "ru"} and global_adapter is not None:
        return global_adapter.fetch_candidate(url, full, deadline=deadline)
    return None


def run_web_fallback(database, job_id: str, product_id: int, article: str,
                        descriptive_name: str, browser, *, kz, ru,
                        global_adapter: LGGlobalAdapter | None, deadline: float,
                        stages: list[int], clock=time.monotonic) -> GoogleFallbackOutcome:
    """Sequential official web search after KZ/RU, with normal page validation."""
    if browser is None or not hasattr(browser, "search_google"):
        return GoogleFallbackOutcome(stop_reason="browser_search_not_available")
    multi = hasattr(browser, "search_provider")
    providers = ("google", "bing", "duckduckgo") if multi else ("google",)
    queries = (browser.provider_queries(article, descriptive_name=descriptive_name)
               if multi else browser.google_queries(article, descriptive_name=descriptive_name))
    checked = 0
    single_article = len(lg_article_components(article)) == 1
    support_urls: list[str] = []
    seen: set[str] = set()
    best_base: SourceDocument | None = None
    stop = ""
    for provider in providers:
        provider_stopped = False
        for query in queries:
            if clock() >= deadline or checked >= MAX_PRODUCT_FETCHES:
                stop = "deadline_or_candidate_budget_exhausted"
                break
            result = (browser.search_provider(provider, query) if multi
                      else browser.search_google(query))
            if result.outcome in {"host_stopped", "challenge_detected", "rate_limited",
                                  "http_denied", "navigation_error", "runtime_unavailable"}:
                stop = result.outcome
                provider_stopped = True
                # A stop on the LG host prevents validating every provider.
                if result.outcome == "host_stopped" and "LG access-stop" in result.note:
                    stop = "lg_access_stopped"
                break
            # Preserve search positions in diagnostics. KZ/RU product pages
            # have priority over equally ranked pages from other regions.
            candidates = sorted(result.candidates, key=lambda c: (
                0 if urlsplit(c.url).path.startswith(("/kz/", "/ru/")) else 1,
                c.position,
            ))
            for candidate in candidates:
                label = candidate.provider or provider + "_browser"
                if candidate.url in seen:
                    _trace(browser, provider=label, query=query, position=candidate.position,
                           title=candidate.label, snippet=candidate.snippet, url=candidate.url,
                           domain=urlsplit(candidate.url).hostname or "",
                           region=urlsplit(candidate.url).path.split("/")[1],
                           candidate_type=candidate.kind, opened=False,
                           decision="rejected", reason="duplicate_candidate", identity="unknown")
                    continue
                seen.add(candidate.url)
                region = urlsplit(candidate.url).path.split("/")[1].casefold()
                if candidate.kind == "support":
                    eligible = is_official_support_url(candidate.url)
                    reason = ("deferred_to_support_content_verification" if eligible else
                              "support_region_not_supported_by_existing_adapter")
                    if eligible and len(support_urls) < MAX_SUPPORT_CANDIDATES:
                        support_urls.append(candidate.url)
                    elif eligible:
                        reason = "support_candidate_limit"
                    _trace(browser, provider=label, query=query, position=candidate.position,
                           title=candidate.label, snippet=candidate.snippet, url=candidate.url,
                           domain=urlsplit(candidate.url).hostname or "", region=region,
                           candidate_type="support", opened=False,
                           decision="candidate" if reason == "deferred_to_support_content_verification" else "rejected",
                           reason=reason, identity="unverified")
                    continue
                if candidate.kind != "product" or not official_product_url(candidate.url):
                    _trace(browser, provider=label, query=query, position=candidate.position,
                           title=candidate.label, snippet=candidate.snippet, url=candidate.url,
                           domain=urlsplit(candidate.url).hostname or "", region=region,
                           candidate_type=candidate.kind, opened=False, decision="rejected",
                           reason="not_official_product_page", identity="unknown")
                    continue
                if checked >= MAX_PRODUCT_FETCHES or clock() >= deadline:
                    stop = "deadline_or_candidate_budget_exhausted"
                    break
                checked += 1
                document = None
                error = ""
                try:
                    document = _candidate_document(candidate, article, kz=kz, ru=ru,
                                                   global_adapter=global_adapter, deadline=deadline)
                except Exception as exc:
                    from .adapters.common import SourceError
                    if not isinstance(exc, SourceError):
                        raise
                    error = str(exc)
                if document is not None and document.error:
                    error = document.error
                level = document.match_level if document is not None else "unknown"
                accepted = bool(document and level == "full_sku" and not error)
                reason = ("exact_product_identity" if accepted else error or
                          "base_model_only" if level == "base_model" else
                          "product_identity_not_confirmed" if document is not None else
                          "regional_adapter_unavailable")
                _trace(browser, provider=label, query=query, position=candidate.position,
                       title=candidate.label, snippet=candidate.snippet, url=candidate.url,
                       final_url=document.url if document is not None else candidate.url,
                       domain=urlsplit(candidate.url).hostname or "", region=region,
                       candidate_type="product", opened=True,
                       decision="accepted" if accepted else "rejected", reason=reason,
                       identity=level)
                if accepted:
                    jobs.save_source_document(database, product_id, document,
                                              update_description=2 in stages,
                                              update_attributes=3 in stages,
                                              update_photos=4 in stages)
                    return GoogleFallbackOutcome(document, tuple(support_urls), queries)
                if document is not None and level == "base_model" and best_base is None:
                    best_base = document
                if any(marker in error for marker in ("policy_host_stopped", "HTTP 403", "HTTP 429", "challenge")):
                    stop = "lg_access_stopped"
                    break
            if stop in {"deadline_or_candidate_budget_exhausted", "lg_access_stopped"}:
                break
            # The broader second query for one model is allowed only when the
            # exact quoted query produced no candidates at all.
            if single_article and result.candidates:
                break
        if stop in {"deadline_or_candidate_budget_exhausted", "lg_access_stopped"}:
            break
        if provider_stopped:
            _trace(browser, provider=provider + "_browser", query="",
                   decision="skip_provider_remainder", reason=stop)
            continue
    if best_base is not None:
        jobs.save_source_document(database, product_id, best_base,
                                  update_description=2 in stages,
                                  update_attributes=3 in stages,
                                  update_photos=4 in stages)
    return GoogleFallbackOutcome(best_base, tuple(support_urls), queries,
                                 stop or "no_validated_exact_page")


@dataclass(frozen=True)
class SitemapFallbackOutcome:
    product_document: SourceDocument | None = None
    candidate_count: int = 0
    stop_reason: str = ""


def run_sitemap_fallback(database, job_id: str, product_id: int, article: str,
                         discovery, *, kz, ru, global_adapter,
                         deadline: float, stages: list[int], clock=time.monotonic) -> SitemapFallbackOutcome:
    """Validate sitemap URLs through the existing official PDP adapters."""
    if discovery is None:
        return SitemapFallbackOutcome(stop_reason="sitemap_discovery_unavailable")
    candidates = discovery.discover(article, deadline=deadline)
    checked = 0
    for candidate in candidates:
        if clock() >= deadline or checked >= MAX_PRODUCT_FETCHES:
            return SitemapFallbackOutcome(candidate_count=len(candidates),
                                          stop_reason="deadline_or_candidate_budget_exhausted")
        checked += 1
        document = None
        error = ""
        try:
            document = _candidate_document(candidate, article, kz=kz, ru=ru,
                                           global_adapter=global_adapter, deadline=deadline)
        except Exception as exc:
            from .adapters.common import SourceError
            if not isinstance(exc, SourceError):
                raise
            error = str(exc)
        if document is not None and document.error:
            error = document.error
        level = document.match_level if document is not None else "unknown"
        accepted = bool(document and level == "full_sku" and not error)
        discovery._trace(event="sitemap_validation", url=candidate.url,
                         sitemap_url=candidate.sitemap_url, chain=candidate.chain,
                         matched_key=candidate.matched_key, opened=True,
                         decision="accepted" if accepted else "rejected",
                         reason="exact_product_identity" if accepted else error or "product_identity_not_confirmed",
                         identity=level, final_url=document.url if document else candidate.url,
                         evidence=document.evidence if document else "",
                         specs_count=len(document.attributes) if document else 0,
                         photo_count=len(document.photo_candidates) if document else 0)
        if accepted:
            jobs.save_source_document(database, product_id, document,
                                      update_description=2 in stages,
                                      update_attributes=3 in stages,
                                      update_photos=4 in stages)
            return SitemapFallbackOutcome(document, len(candidates))
    return SitemapFallbackOutcome(candidate_count=len(candidates),
                                  stop_reason="no_validated_exact_sitemap_page")


# Keep the Stage 54.1 entry point for existing callers and offline fixtures.
run_google_fallback = run_web_fallback
