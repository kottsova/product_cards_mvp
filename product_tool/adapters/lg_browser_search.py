"""Stage 43: bounded, production LG site-search discovery.

The sitemap-only lookup in `lg.py` misses a row whenever its article does
not appear under a recognizable slug in the KZ/RU sitemap. LG's own site
search can still find such a row, but a plain HTTP GET of its search URL
returns HTTP 200 with the results rendered client-side (empty static HTML)
-- confirmed again in this stage's own feasibility checks -- so a real
browser render is required to see them.

By default this module drives the project's existing headless
browser subprocess (`census/browser_runtime.py`'s `PlaywrightBrowser` /
`discover_runtime()`, the isolated `census/browser_worker.py` process --
plain headless Chromium, no stealth, no custom UA, no profile/cookie
import). An explicitly supplied attended transport can reuse the same search
and candidate parser in visible persistent Chrome after manual challenge handling. It does not reuse `census/browser_strategy.py`'s heavier
eligibility/checkpoint machinery, built for research provenance tracking;
it drives the browser directly at a known, safe URL.

Two real routes were checked live in this stage, with results that shaped
this module (see `reports/lg_live_batch_2026-09-28_stage43/report.md`):

  * `www.lg.com/kz/...` -- ANY navigation (even the plain homepage) is met
    with a confirmed browser-verification challenge under a plain,
    non-stealth headless session. This is recorded, honestly, exactly like
    a 401/403/429 from the plain-HTTP path -- never retried, never worked
    around with a different driver.
  * `www.lg.com/ru/...` -- the guessed `.../ru/search/?search=<query>` GET
    renders an empty "no results" shell for ANY query (a static page
    shell, not a live search) -- so it is *not* used here. The REAL route,
    captured from an actual client-driven search submission (the header
    search box, typed and submitted, in a plain headless session), is
    `.../ru/search/search-support?search=<query>&...`. It returns
    `/ru/support/product/lg-<code>` result links -- LG's *support*
    catalog, not commerce product pages. Following such a link often
    redirects to the shared base model's support page, which prints only
    ONE (not necessarily our target) variant's own sales code -- so a
    search hit is real, verifiable evidence, but it is evidence *about
    the printed content of the candidate page*, never about the search
    result's own URL/label alone (the project's existing rule for support
    pages, see `lg.py`'s document lookup and Stage 23 rules).

Discovery only: this module never extracts attributes/photos/description.
Every candidate it returns is handed back to the ordinary plain-HTTP
adapter code (`lg.py`) for verification through the same, already-tested
extraction path used for sitemap-found pages.
"""
from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, quote_plus, urlsplit
from uuid import uuid4

from ..census.browser_contracts import BrowserBudget
from ..census.browser_runtime import BrowserFailure, BrowserRuntime, PlaywrightBrowser, discover_runtime
from . import policy_fetch

# Stage 43: the real, observed LG Russia support-catalog search route -- captured from an actual
# client-driven search submission (header search box, typed and submitted) in a plain, non-stealth
# headless session, not guessed. `{q}` is filled twice (search + oldTerm); every other parameter is
# exactly as the site's own client JS constructed it. No equivalent working route is known for KZ: any
# navigation there is met with a confirmed challenge (see module docstring and the Stage 43 report).
_RU_SEARCH_SUPPORT_TEMPLATE = (
    "https://www.lg.com/ru/search/search-support?search={q}&type=B2C&accessoryCategoryList=&stockOnlyFlag=N"
    "&b2clist=&productCount=0&promotionslist=&discoverlist=&keypromotionlist=&reqUrl=https%3A%2F%2Fwww.lg.com"
    "&skuCompare=&userId=&loginState=true&limitSaleUseFlag=N&reStockFuncFlag=N&obsLoginFlag=N&oldTerm={q}"
    "&obsBuynowFlag=N&energyLabelFlag=N&energyLabelUpperTextUseFlag=N&localeCode=ru"
    "&mobileCheck=false&reviewType=SP&obsCalculatorUseFlag=N&obsInstallmentPromotionUseFlag=N&labelUseFlag=Y"
    "&repairabilityIndexFlag=N&obsInstallmentPriceDisableLink=N&obsSubscriptionCtaUseFlag=N&guestFlag=Y"
    "&guestPriceMessageUseFlag=N"
)
# KZ intentionally has no entry: there is no verified working search route for it (see module docstring).
# `search()` still accepts region="kz" -- it correctly reports `route_not_available` for it rather than
# silently doing nothing, so a caller/log always shows *why* nothing was searched.
SEARCH_ROUTES: dict[str, str] = {"ru": _RU_SEARCH_SUPPORT_TEMPLATE}

MAX_CANDIDATES = 8
MAX_GOOGLE_QUERIES = 4
DEFAULT_BUDGET = BrowserBudget(deadline_seconds=60, operation_timeout_seconds=10)
SEARCH_PROVIDERS = ("google", "bing", "duckduckgo")
PROVIDER_HOSTS = {"google": "www.google.com", "bing": "www.bing.com",
                  "duckduckgo": "duckduckgo.com"}
PROVIDER_URLS = {
    "google": "https://www.google.com/search?q={q}&hl=en",
    "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
}

OUTCOMES = frozenset({
    "candidates_found", "no_candidates", "runtime_unavailable", "host_stopped",
    "challenge_detected", "navigation_error", "route_not_available", "rate_limited", "http_denied",
})


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def is_lg_support_product_url(url: str) -> bool:
    """Observed regional LG support routes; a URL remains only a candidate."""
    p = urlsplit(url)
    parts = [x for x in p.path.lower().split("/") if x]
    return (p.scheme == "https" and p.netloc.lower() == "www.lg.com" and len(parts) >= 4
            and parts[1] == "support" and
            ((parts[0] == "ru" and parts[2] == "product" and parts[3].startswith("lg-")) or
             (parts[0] == "kz" and parts[2] == "product-support" and parts[3].startswith("cs-"))))


@dataclass(frozen=True)
class BrowserCandidate:
    url: str
    kind: str  # regional search yields support; Google may yield product or support
    label: str = ""
    position: int = 0
    query: str = ""
    provider: str = "lg_regional"
    snippet: str = ""


@dataclass(frozen=True)
class BrowserSearchResult:
    region: str
    query: str
    outcome: str
    candidates: tuple[BrowserCandidate, ...] = ()
    note: str = ""

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown browser search outcome: {self.outcome!r}")


class LGBrowserSearch:
    """One instance is safe to reuse across every region/query tried for a single product; its browser
    subprocess (if any was needed) is opened lazily on first use and must be closed by the caller."""

    def __init__(
        self, log_path: Path, *, allowed_hosts: tuple[str, ...] = (
            "www.lg.com", "lg.com", "www.google.com", "google.com", "gstatic.com",
            "www.bing.com", "bing.com", "duckduckgo.com"),
        budget: BrowserBudget | None = None, runtime: BrowserRuntime | None = None,
        driver_factory: Callable | None = None, clock: Callable[[], float] = time.monotonic,
        allow_attended_challenge: bool = False,
        preloaded_google_results: dict[str, BrowserSearchResult] | None = None,
        official_host: str = "www.lg.com",
        official_hosts: tuple[str, ...] | None = None,
    ):
        self.log_path = Path(log_path)
        self.official_host = official_host
        self.official_hosts = official_hosts or (official_host,)
        self.allowed_hosts = allowed_hosts
        self.budget = budget or DEFAULT_BUDGET
        self._runtime = runtime
        self._driver_factory = driver_factory or PlaywrightBrowser
        # The default production Google route uses the actual old parser's
        # persistent browser/profile. Injected driver factories keep the
        # existing isolated test/browser path.
        from ..census.old_parser_google import OldParserGoogleBrowser
        self._legacy_driver_factory = OldParserGoogleBrowser if driver_factory is None else None
        self._legacy_driver = None
        self.clock = clock
        self._driver = None
        self.session_id = uuid4().hex
        self.trace_callback = None
        self.allow_attended_challenge = allow_attended_challenge
        self.preloaded_google_results = dict(preloaded_google_results or {})

    def _trace(self, **event) -> None:
        if self.trace_callback is not None:
            self.trace_callback({"timestamp": _now(), **event})

    def _host_stopped(self, host: str) -> bool:
        from .access_stop import CHALLENGE, active_stops

        active = active_stops(policy_fetch.read_log(self.log_path))
        roots = {"www.google.com": ("google.com", "gstatic.com"),
                 "www.bing.com": ("bing.com",),
                 "duckduckgo.com": ("duckduckgo.com",)}.get(host)
        records = [item for domain, items in active.items()
                   if (any(domain == root or domain.endswith("." + root) for root in roots)
                       if roots else domain == host)
                   for item in items]
        if host == "www.google.com" and self.allow_attended_challenge:
            return any(item["reason"] != CHALLENGE for item in records)
        return bool(records)

    def _record_challenge(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").casefold()
        policy_fetch.append_log_entry(self.log_path, {
            "url": url, "status_code": 200, "final_url": url, "checked_at": _now(),
            "access_status": "captcha_or_blocked", "protection_status": "challenge_confirmed",
            "source_session": self.session_id,
        })

    def _record_rate_limit(self, url: str) -> None:
        policy_fetch.append_log_entry(self.log_path, {
            "url": url, "status_code": 429, "final_url": url, "checked_at": _now(),
            "access_status": "rate_limited", "protection_status": "ordinary_page",
            "source_session": self.session_id,
        })

    def _ensure_driver(self):
        if self._driver is not None:
            return self._driver
        if self._runtime is None:
            self._runtime = discover_runtime()
        if not self._runtime.available:
            return None
        driver = self._driver_factory(self._runtime, self.budget, self.allowed_hosts)
        driver.start()
        self._driver = driver
        return self._driver

    def _ensure_legacy_driver(self):
        if self._legacy_driver is None:
            driver = self._legacy_driver_factory()
            driver.start()
            self._legacy_driver = driver
        return self._legacy_driver

    def _reset_legacy_driver(self) -> None:
        if self._legacy_driver is not None:
            self._legacy_driver.close()
            self._legacy_driver = None

    def search(self, region: str, queries: list[str]) -> BrowserSearchResult:
        queries = [q for q in dict.fromkeys(queries) if q]
        first_query = queries[0] if queries else ""
        template = SEARCH_ROUTES.get(region)
        if not template:
            return BrowserSearchResult(region, first_query, "route_not_available",
                note=f"Для региона LG «{region}» нет проверенного маршрута браузерного поиска.")
        host = "www.lg.com"
        if self._host_stopped(host):
            return BrowserSearchResult(region, first_query, "host_stopped",
                note=f"Хост {host} ранее остановлен (подтверждённая проверка браузера); браузерный поиск не выполнялся.")
        driver = self._ensure_driver()
        if driver is None:
            return BrowserSearchResult(region, first_query, "runtime_unavailable",
                note="Браузерный поиск недоступен в этом окружении: не найден установленный Playwright/Chromium.")
        for query in queries:
            url = template.format(q=quote(query))
            self._trace(event="query", provider="lg_regional", query=query, url=url, region=region)
            try:
                state = driver.call("goto", url=url, queries=[query], render_mode="render_existing_search_result")
            except BrowserFailure as exc:
                self._trace(event="query_outcome", provider="lg_regional", query=query,
                            url=url, region=region, outcome=str(exc))
                reason = str(exc)
                if reason == "challenge_detected":
                    self._record_challenge(url)
                    return BrowserSearchResult(region, query, "challenge_detected",
                        note=f"LG показал проверку браузера при поиске «{query}» ({region}); поиск через браузер остановлен для этого хоста.")
                if reason == "rate_limited":
                    if not exc.counts.get("rate_limit_recorded"):
                        self._record_rate_limit(str(exc.counts.get("rate_limit_url") or url))
                    return BrowserSearchResult(region, query, "rate_limited",
                        note="LG regional browser search stopped after HTTP 429.")
                return BrowserSearchResult(region, query, "navigation_error", note=f"Ошибка браузера при поиске «{query}»: {reason}.")
            fragments = [fragment for fragment in state["projection"].get("fragments", [])
                         if fragment.get("type") == "result_link"]
            candidates = []
            for position, fragment in enumerate(fragments, 1):
                candidate_url = fragment.get("url", "")
                accepted = is_lg_support_product_url(candidate_url)
                self._trace(event="result", provider="lg_regional", query=query,
                            position=position, title=fragment.get("title", ""), snippet="",
                            url=candidate_url, domain=urlsplit(candidate_url).hostname or "",
                            region=region, candidate_type="support" if accepted else "unknown",
                            decision="candidate" if accepted else "rejected",
                            reason="" if accepted else "unsupported_result_url", opened=False)
                if accepted and len(candidates) < MAX_CANDIDATES:
                    candidates.append(BrowserCandidate(candidate_url, "support",
                                                       fragment.get("title", ""), position,
                                                       query, "lg_regional"))
            self._trace(event="query_outcome", provider="lg_regional", query=query,
                        url=url, region=region, outcome="candidates_found" if candidates else "no_candidates")
            if candidates:
                return BrowserSearchResult(region, query, "candidates_found", tuple(candidates))
        return BrowserSearchResult(region, first_query, "no_candidates",
            note=f"Поиск LG ({region}) не нашёл результатов по артикулу и базовой модели.")

    @staticmethod
    def google_queries(article: str, *, descriptive_name: str = "") -> tuple[str, ...]:
        """Reuse the old generic parser's site:lg.com search, with bounded LG article variants."""
        from .lg import lg_article_components, lg_base_model, normalize_lg_sku
        parts = lg_article_components(article)
        terms = []
        def add(value):
            value = " ".join(str(value or "").split()).strip()
            if value and value.casefold() not in {x.casefold() for x in terms}:
                terms.append(value)
        for part in parts:
            add(part)
        if len(parts) == 1:
            add(normalize_lg_sku(article))
            for part in parts:
                if "." in part or "-" in part:
                    add(re.sub(r"[.\-]", " ", part))
        add(lg_base_model(article))
        compact = re.sub(r"[\s.\-]", "", normalize_lg_sku(article))
        words = re.findall(r"[A-Za-z0-9]+", descriptive_name or "")
        for start in range(len(words)):
            for end in range(start + 2, min(len(words), start + 4) + 1):
                value = " ".join(words[start:end])
                if re.sub(r"[\s.\-]", "", value).upper() == compact:
                    add(value)
        return tuple(f'site:lg.com "{term}"' for term in terms[:MAX_GOOGLE_QUERIES])

    @staticmethod
    def _google_target(url: str) -> str:
        parsed = urlsplit(url)
        if (parsed.hostname or "").casefold() in {"www.google.com", "google.com"} and parsed.path == "/url":
            return parse_qs(parsed.query).get("q", [""])[0]
        return url

    @staticmethod
    def provider_queries(article: str, *, descriptive_name: str = "") -> tuple[str, ...]:
        """A small shared query plan, independent of any known product URL."""
        exact = LGBrowserSearch.google_queries(article, descriptive_name=descriptive_name)
        if not exact:
            return ()
        from .lg import lg_article_components, normalize_lg_sku
        # For one code, a less restrictive query is useful when the quoted
        # search has no candidates. Kits retain each component and base query.
        if len(lg_article_components(article)) == 1:
            term = normalize_lg_sku(article)
            return (exact[0], f"site:lg.com {term} LG")
        return exact[:3]

    def _reset_driver(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def search_provider(self, provider: str, query: str) -> BrowserSearchResult:
        """Search one provider once; result links are untrusted candidates."""
        if provider not in SEARCH_PROVIDERS:
            raise ValueError("unknown search provider")
        host = PROVIDER_HOSTS[provider]
        legacy_google = provider == "google" and self._legacy_driver_factory is not None
        label = "google_old_parser" if legacy_google else provider + "_browser"
        url = (f"https://www.google.com/search?q={quote_plus(query)}&hl=en"
               if legacy_google else PROVIDER_URLS[provider].format(q=quote(query)))
        cached = self.preloaded_google_results.get(query) if provider == "google" else None
        if cached is not None:
            self._trace(event="query", provider=label, query=query,
                        url=url, region="global", observation="attended_session_replay")
            for candidate in cached.candidates:
                parsed = urlsplit(candidate.url)
                self._trace(event="result", provider=label, query=query,
                            position=candidate.position, title=candidate.label,
                            snippet=candidate.snippet, url=candidate.url,
                            domain=parsed.hostname or "",
                            region=parsed.path.split("/")[1] if "/" in parsed.path else "",
                            candidate_type=candidate.kind, decision="candidate",
                            reason="observed_in_attended_session", opened=False)
            self._trace(event="query_outcome", provider=label, query=query,
                        url=url, outcome=cached.outcome,
                        observation="attended_session_replay")
            return cached
        if self._host_stopped(host):
            self._trace(event="query_outcome", provider=label, query=query,
                        url=url, outcome="host_stopped", reason="provider_access_stop")
            return BrowserSearchResult("global", query, "host_stopped",
                                       note=provider + " access-stop is active.")
        if self._host_stopped(self.official_host):
            self._trace(event="query_outcome", provider=label, query=query,
                        url=url, outcome="host_stopped", reason="lg_access_stop")
            return BrowserSearchResult("global", query, "host_stopped",
                                       note="LG access-stop is active.")
        # Regional LG search has finished by this point. Close its isolated
        # worker before starting the old parser's persistent Chromium context.
        if legacy_google:
            self._reset_driver()
        try:
            driver = self._ensure_legacy_driver() if legacy_google else self._ensure_driver()
        except Exception as exc:
            self._trace(event="query_outcome", provider=label, query=query,
                        url=url, outcome="runtime_unavailable",
                        reason=type(exc).__name__)
            return BrowserSearchResult("global", query, "runtime_unavailable",
                                       note=type(exc).__name__)
        if driver is None:
            self._trace(event="query_outcome", provider=label, query=query,
                        url=url, outcome="runtime_unavailable")
            return BrowserSearchResult("global", query, "runtime_unavailable")
        term = query.rsplit('"', 2)[1] if '"' in query else query
        self._trace(event="query", provider=label, query=query, url=url, region="global",
                    mechanism="old_parser_general_search" if legacy_google else "browser_projection",
                    old_parser_source=getattr(driver, "source_kind", "") if legacy_google else "")
        try:
            state = driver.call("goto", url=url, queries=[term],
                                search_result_hosts=list(self.official_hosts),
                                render_mode="render_existing_search_result")
        except BrowserFailure as exc:
            outcome = str(exc)
            if outcome == "challenge_detected":
                self._record_challenge(url)
            elif outcome == "rate_limited" and not exc.counts.get("rate_limit_recorded"):
                self._record_rate_limit(str(exc.counts.get("rate_limit_url") or url))
            blocked_host = str(exc.counts.get("last_blocked_host", ""))
            self._trace(event="query_outcome", provider=label, query=query,
                        url=url, outcome=outcome, blocked_host=blocked_host,
                        response_url_path=urlsplit(str(exc.counts.get("rate_limit_url") or "")).path,
                        old_parser_source=exc.counts.get("old_parser_source", ""),
                        old_parser_called=exc.counts.get("old_parser_called", False),
                        old_parser_completed=exc.counts.get("old_parser_completed", False))
            # The isolated browser worker retains its failure signal. A later
            # provider must start a clean browser without reissuing this query.
            if legacy_google:
                self._reset_legacy_driver()
            else:
                self._reset_driver()
            result_outcome = outcome if outcome in {
                "challenge_detected", "rate_limited", "http_denied"} else "navigation_error"
            return BrowserSearchResult("global", query, result_outcome,
                                       note=outcome + (" at " + blocked_host if blocked_host else ""))
        candidates = []
        for position, fragment in enumerate(state["projection"].get("fragments", []), 1):
            if fragment.get("type") != "result_link":
                continue
            candidate_url = self._google_target(fragment.get("url", ""))
            parsed = urlsplit(candidate_url)
            result_host = (parsed.hostname or "").casefold()
            parts = [part for part in parsed.path.lower().split("/") if part]
            region = parts[0] if parts else ""
            official = parsed.scheme == "https" and result_host in self.official_hosts
            is_support = official and len(parts) >= 3 and "support" in parts
            is_product = (official and len(parts) >= 3 and not any(
                part in {"support", "search", "sitemap", "blog", "news"} for part in parts))
            if self.official_host != "www.lg.com" and official:
                is_support = result_host in {"pcsupport.lenovo.com", "support.lenovo.com"} and "products" in parts
                is_product = (result_host == "psref.lenovo.com" and parts and parts[0] in {"detail", "product"}) or (result_host == "www.lenovo.com" and "p" in parts)
            kind = "support" if is_support else "product" if is_product else "unknown"
            old_rejected = legacy_google and fragment.get("old_parser_candidate") is False
            admitted = kind in {"support", "product"} and not old_rejected
            self._trace(event="result", provider=label, query=query,
                        position=position, title=fragment.get("title", ""),
                        snippet=fragment.get("snippet", ""),
                        url=candidate_url, domain=result_host, region=region,
                        candidate_type=kind,
                        decision="candidate" if admitted else "rejected",
                        reason="" if admitted else ("old_parser_result_not_exact" if old_rejected
                                                    else "not_official_lg_product_or_support"),
                        opened=False)
            if admitted and len(candidates) < MAX_CANDIDATES:
                candidates.append(BrowserCandidate(candidate_url, kind,
                                                   fragment.get("title", ""), position,
                                                   query, label,
                                                   fragment.get("snippet", "")))
        outcome = "candidates_found" if candidates else "no_candidates"
        counts = state.get("counts", {})
        capped = bool(counts.get("capped_requests"))
        self._trace(event="query_outcome", provider=label, query=query,
                    url=url, region="global", final_url=state.get("url", ""),
                    outcome=outcome, resource_capped=capped,
                    network_requests=counts.get("network_requests", 0),
                    old_parser_source=state.get("old_parser_source", ""),
                    old_parser_called=counts.get("old_parser_called", False),
                    old_parser_completed=counts.get("old_parser_completed", False))
        result = BrowserSearchResult("global", query, outcome, tuple(candidates),
                                     note="resource_capped" if capped else "")
        if provider == "google":
            self.preloaded_google_results[query] = result
        if not legacy_google:
            self._reset_driver()
        return result

    def search_google(self, query: str) -> BrowserSearchResult:
        return self.search_provider("google", query)

    def close(self) -> None:
        self._reset_driver()
        self._reset_legacy_driver()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
