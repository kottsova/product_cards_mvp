"""A requests-Session-shaped client on top of PolicyAwareFetcher (Stage 20).

The LG adapters (lg.py, sulpak.py) were written against a plain `requests.Session`: they call
`fetch_with_retry(session, url, ...)`, which calls `session.get(url, timeout=...)` and reads
`.status_code`, `.text`, `.content`, `.url`, `.raise_for_status()`. Those files are protected pipeline
files, so instead of rewriting them this class *is* the session they are given:

  * every request goes through PolicyAwareFetcher (host allowlist, redirect-chain check, 401/403/429 and
    confirmed-challenge detection) and is written to a persisted JSON log, so a stopped host stays stopped in the
    NEXT run and in a NEW instance -- `challenge_suspected` alone never stops anything;
  * a stopped host is refused without any I/O (a 403-shaped response with the marker `[policy_host_stopped]`), and a
    confirmed challenge that arrived with HTTP 200 is never handed to the adapter as a page;
  * an optional request budget (per row and in total) refuses the request before it is made
    (`[policy_budget_exhausted]`), and pacing is shared by every instance in the process;
  * a GET of a sitemap is answered from a short in-process cache, so a batch of rows reads a huge sitemap once;
  * the underlying `requests.Session` keeps the adapter's own headers (User-Agent, Accept-Language): `.headers`
    is that session's dict, so `session.headers.update(...)` in an adapter constructor still works.

Everything else -- what the adapters search for, parse and extract -- is untouched.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import requests

from ..census.endpoint_probe import AccessStatus, ProbePolicy
from ..census.models import EndpointCapability, ProtectionStatus
from .policy_fetch import CONFIRMED_CHALLENGE, PolicyAwareFetcher

STOPPED = "[policy_host_stopped]"
BUDGET = "[policy_budget_exhausted]"
NOT_ALLOWED = "[policy_host_not_allowed]"
DEFAULT_MIN_INTERVAL = 1.0
DEFAULT_MAX_BYTES = 25_000_000
SITEMAP_CACHE_SECONDS = 600.0

_LAST_REQUEST_AT: list[float] = [0.0]  # process-wide pacing, shared by every session instance


class RequestBudget:
    """At most `max_per_row` real requests for the current row and `max_total` in all. A cache hit or a refusal is not a request."""

    def __init__(self, max_per_row: int | None = None, max_total: int | None = None):
        self.max_per_row, self.max_total = max_per_row, max_total
        self.total = self.row = 0
        self.row_key = ""
        self.log: list[dict] = []

    def begin_row(self, key: str) -> None:
        self.row_key, self.row = key, 0

    def allows(self) -> bool:
        return (self.max_per_row is None or self.row < self.max_per_row) and (self.max_total is None or self.total < self.max_total)

    def spend(self, url: str) -> None:
        self.total += 1
        self.row += 1
        self.log.append({"row": self.row_key, "n_in_row": self.row, "n_total": self.total, "url": url})


# Sitemap answers, shared by every session instance of the process that writes the same log (the worker builds a new
# session per job; a sitemap is read once for a whole batch). Keyed by (log path, url): a different log is a different run.
_SITEMAP_CACHE: dict[tuple[str, str], tuple[float, "PolicyResponse"]] = {}
_ACTIVE: list[RequestBudget | None] = [None]
_RECORD: list[Path | None] = [None]


@contextmanager
def record_responses(directory: Path) -> Iterator[Path]:
    """Save every real response body (gzip) with an index.jsonl while active -- fixtures for offline diagnosis."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    previous, _RECORD[0] = _RECORD[0], directory
    try:
        yield directory
    finally:
        _RECORD[0] = previous


def _record(url: str, response: "PolicyResponse", row: str) -> None:
    directory = _RECORD[0]
    if directory is None:
        return
    index = directory / "index.jsonl"
    n = 1
    if index.exists():
        with index.open(encoding="utf-8") as handle:
            n = sum(1 for _ in handle) + 1
    digest = hashlib.sha256(response.content).hexdigest()
    name = f"{n:03d}_{digest[:10]}.gz" if response.text else ""
    if name:
        with gzip.open(directory / name, "wt", encoding="utf-8", newline="") as handle:
            handle.write(response.text)
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"n": n, "row": row, "url": url, "final_url": response.url, "status": response.status_code, "marker": response.marker, "bytes": len(response.content),
                                 "sha256": digest, "saved_as": name, "truncated": response.truncated}, ensure_ascii=False) + "\n")


@contextmanager
def request_budget(budget: RequestBudget) -> Iterator[RequestBudget]:
    previous, _ACTIVE[0] = _ACTIVE[0], budget
    try:
        yield budget
    finally:
        _ACTIVE[0] = previous


class PolicyResponse:
    """The subset of requests.Response the adapters use."""

    def __init__(self, url: str, status_code: int, text: str = "", content_type: str = "", *, marker: str = "", truncated: bool = False):
        self.url, self.status_code, self.text = url, status_code, text
        self.content = text.encode("utf-8")
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.encoding, self.history, self.marker, self.truncated = "utf-8", (), marker, truncated

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            reason = f" {self.marker}" if self.marker else ""
            raise requests.HTTPError(f"HTTP {self.status_code}{reason}", response=None)

    def json(self):
        import json
        return json.loads(self.text)


class PolicyAwareSession:
    def __init__(
        self, log_path: Path, *, allowed_hosts: tuple[str, ...], underlying=None, clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep, min_interval_seconds: float = DEFAULT_MIN_INTERVAL, max_bytes: int = DEFAULT_MAX_BYTES,
        cache_suffixes: tuple[str, ...] = ("sitemap.xml",), cache_seconds: float = SITEMAP_CACHE_SECONDS,
    ):
        self.log_path, self.allowed_hosts = Path(log_path), tuple(allowed_hosts)
        self.underlying = underlying if underlying is not None else requests.Session()
        self.clock, self._sleep, self.min_interval = clock, sleep, min_interval_seconds
        self.max_bytes, self.cache_suffixes, self.cache_seconds = max_bytes, cache_suffixes, cache_seconds
        # The probe's own pacing is off: pacing is process-wide (see _LAST_REQUEST_AT).
        self._fetcher = PolicyAwareFetcher(self.log_path, session=self.underlying, policy=ProbePolicy(min_interval_seconds=0.0, max_bytes=max_bytes))
        self.request_count = 0
        self.refusals: list[dict] = []

    @property
    def headers(self):
        return self.underlying.headers

    def _refuse(self, url: str, status: int, marker: str) -> PolicyResponse:
        self.refusals.append({"url": url, "marker": marker})
        return PolicyResponse(url, status, marker=marker)

    def get(self, url: str, timeout: float | None = None, **_ignored) -> PolicyResponse:
        cacheable = any(url.split("?", 1)[0].endswith(suffix) for suffix in self.cache_suffixes)
        if cacheable:
            hit = _SITEMAP_CACHE.get((str(self.log_path), url))
            if hit and self.clock() - hit[0] < self.cache_seconds:
                return hit[1]
        if self._fetcher.host_stopped(url):
            return self._refuse(url, 403, STOPPED)
        budget = _ACTIVE[0]
        if budget is not None and not budget.allows():
            return self._refuse(url, 429, BUDGET)
        gap = self.min_interval - (time.monotonic() - _LAST_REQUEST_AT[0])
        if _LAST_REQUEST_AT[0] and gap > 0:
            self._sleep(gap)
        user_agent = str(self.headers.get("User-Agent", "")) or ProbePolicy.user_agent
        self._fetcher.set_policy(ProbePolicy(timeout_seconds=float(timeout or 10.0), max_bytes=self.max_bytes, min_interval_seconds=0.0, user_agent=user_agent))
        capability = EndpointCapability.SITEMAP if cacheable else EndpointCapability.PRODUCT_PAGE
        try:
            result = self._fetcher.get(url, allowed_hosts=self.allowed_hosts, capability=capability)
        except ValueError:
            return self._refuse(url, 403, NOT_ALLOWED)
        _LAST_REQUEST_AT[0] = time.monotonic()
        if result.http_status is not None:  # a round trip happened
            self.request_count += 1
            if budget is not None:
                budget.spend(url)
        elif result.access_status == AccessStatus.CAPTCHA_OR_BLOCKED:
            return self._refuse(url, 403, STOPPED)
        if result.access_status in (AccessStatus.REGIONAL_REDIRECT,):
            return self._refuse(result.final_url or url, 403, NOT_ALLOWED)
        if result.http_status is None:  # network failure: raise like requests would (fetch_with_retry retries once)
            raise requests.ConnectionError(result.error or "Network request failed")
        blocked = result.access_status == AccessStatus.CAPTCHA_OR_BLOCKED or result.protection_status.value in CONFIRMED_CHALLENGE
        if blocked:
            status = result.http_status if result.http_status in (401, 403, 429) else 403
            blocked_response = PolicyResponse(result.final_url or url, status, marker="[policy_challenge_confirmed]" if result.http_status == 200 else STOPPED)
            _record(url, blocked_response, budget.row_key if budget is not None else "")
            return blocked_response
        text = result.diagnostic_text or ""
        response = PolicyResponse(result.final_url or url, result.http_status, text, result.content_type,
                                  truncated=bool(result.evidence and result.evidence[0].get("bytes_read", 0) >= self.max_bytes))
        _record(url, response, budget.row_key if budget is not None else "")
        if cacheable and response.ok:
            _SITEMAP_CACHE[(str(self.log_path), url)] = (self.clock(), response)
        return response
