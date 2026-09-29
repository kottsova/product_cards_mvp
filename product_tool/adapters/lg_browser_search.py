"""Stage 43: bounded, production LG site-search discovery.

The sitemap-only lookup in `lg.py` misses a row whenever its article does
not appear under a recognizable slug in the KZ/RU sitemap. LG's own site
search can still find such a row, but a plain HTTP GET of its search URL
returns HTTP 200 with the results rendered client-side (empty static HTML)
-- confirmed again in this stage's own feasibility checks -- so a real
browser render is required to see them.

This module drives the project's EXISTING, already safety-reviewed headless
browser subprocess (`census/browser_runtime.py`'s `PlaywrightBrowser` /
`discover_runtime()`, the isolated `census/browser_worker.py` process --
plain headless Chromium, no stealth, no custom UA, no profile/cookie
import). It does not reuse `census/browser_strategy.py`'s heavier
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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlsplit
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

MAX_CANDIDATES = 3
DEFAULT_BUDGET = BrowserBudget(deadline_seconds=40)

OUTCOMES = frozenset({
    "candidates_found", "no_candidates", "runtime_unavailable", "host_stopped",
    "challenge_detected", "navigation_error", "route_not_available",
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
    kind: str  # "support" -- currently the only kind the real RU route yields
    label: str = ""


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
        self, log_path: Path, *, allowed_hosts: tuple[str, ...] = ("www.lg.com",),
        budget: BrowserBudget | None = None, runtime: BrowserRuntime | None = None,
        driver_factory: Callable | None = None, clock: Callable[[], float] = time.monotonic,
    ):
        self.log_path = Path(log_path)
        self.allowed_hosts = allowed_hosts
        self.budget = budget or DEFAULT_BUDGET
        self._runtime = runtime
        self._driver_factory = driver_factory or PlaywrightBrowser
        self.clock = clock
        self._driver = None
        self.session_id = uuid4().hex

    def _host_stopped(self, host: str) -> bool:
        return host in policy_fetch.stopped_hosts_from_fetch_log(policy_fetch.read_log(self.log_path))

    def _record_challenge(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").casefold()
        policy_fetch.append_log_entry(self.log_path, {
            "url": url, "status_code": 200, "final_url": url, "checked_at": _now(),
            "access_status": "captcha_or_blocked", "protection_status": "challenge_confirmed",
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
            try:
                state = driver.call("goto", url=url, queries=[query], render_mode="render_existing_search_result")
            except BrowserFailure as exc:
                reason = str(exc)
                if reason == "challenge_detected":
                    self._record_challenge(url)
                    return BrowserSearchResult(region, query, "challenge_detected",
                        note=f"LG показал проверку браузера при поиске «{query}» ({region}); поиск через браузер остановлен для этого хоста.")
                return BrowserSearchResult(region, query, "navigation_error", note=f"Ошибка браузера при поиске «{query}»: {reason}.")
            candidates = tuple(
                BrowserCandidate(fragment["url"], "support", fragment.get("title", ""))
                for fragment in state["projection"].get("fragments", [])
                if fragment.get("type") == "result_link" and is_lg_support_product_url(fragment.get("url", ""))
            )[:MAX_CANDIDATES]
            if candidates:
                return BrowserSearchResult(region, query, "candidates_found", candidates)
        return BrowserSearchResult(region, first_query, "no_candidates",
            note=f"Поиск LG ({region}) не нашёл результатов по артикулу и базовой модели.")

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
