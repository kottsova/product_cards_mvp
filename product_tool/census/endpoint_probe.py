"""Endpoint-level low-rate probing with evidence-based protection detection."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import functools
import re
import time
from typing import Any, Callable, Iterable, Iterator, Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from .fingerprint import PlatformFingerprint, fingerprint_platform
from .discovery import detect_embedded_state, detect_internal_search, json_ld_field_coverage, json_ld_products
from .models import (
    AccessStatus,
    EndpointCapability,
    EndpointRecord,
    ProtectionStatus,
)

# Captured at import time, before any guard below could ever patch the real
# method -- AccessProbe.probe() always calls through this reference (see
# _get_response), so it is never itself blocked by enforce_policy_aware_
# fetch_only(), no matter when that guard is installed.
_REAL_SESSION_GET = requests.Session.get


class DirectNetworkCallBlocked(RuntimeError):
    """Raised by a requests.Session.get() call made while
    enforce_policy_aware_fetch_only() is active, from code that is not
    AccessProbe.probe() itself. Stage 12 made four requests to a host
    AccessProbe would have already stopped, because it used raw
    requests.Session calls instead of AccessProbe -- this is what makes
    that mistake fail loudly instead of silently succeeding, for any
    research code (script or ad-hoc) that opts in by using the guard."""


@contextmanager
def enforce_policy_aware_fetch_only() -> Iterator[None]:
    """Research code (scripts or one-off investigation) should wrap its
    network-touching work in this context manager. While active, any
    requests.Session.get() call NOT made through AccessProbe.probe() raises
    DirectNetworkCallBlocked before any network I/O happens -- zero bytes
    leave the process. AccessProbe itself is unaffected (see
    _REAL_SESSION_GET above), so probe() keeps working normally inside the
    guard; only calls that bypass it are blocked.

    Stage 16: reentrant -- saves and restores whatever requests.Session.get
    WAS (not a hardcoded reference to the true original), so nesting this
    inside an already-active guard (e.g. tests/__init__.py's process-wide
    activation, see block_all_real_network_io() below) and letting the
    inner one exit does not silently disable the outer one. Without this,
    any test that itself calls this context manager -- and several already
    do, to prove the guard's own behavior -- would clear a process-wide
    guard on exit instead of leaving it active for the rest of the run."""
    previous = requests.Session.get

    def _blocked(self, *args, **kwargs):
        raise DirectNetworkCallBlocked(
            "Direct requests.Session.get() call blocked by "
            "enforce_policy_aware_fetch_only() -- research code must go "
            "through product_tool.census.endpoint_probe.AccessProbe.probe(), "
            "the only path that enforces the stop-after-block rule "
            "(see tests/test_stage13_host_stop_audit.py for why this matters)."
        )
    requests.Session.get = _blocked
    try:
        yield
    finally:
        requests.Session.get = previous


class RealNetworkIOBlocked(RuntimeError):
    """Raised by ANY real HTTP request -- including one made through
    AccessProbe's otherwise-legitimate real-session path -- while
    block_all_real_network_io() is active. Unlike DirectNetworkCallBlocked
    (which deliberately exempts AccessProbe, since AccessProbe IS the
    correct path for a real research/production call), this blocks
    everything: it exists for test-PROCESS safety, where no real network
    call is ever supposed to happen, not even a policy-compliant one.
    Stage 15's own incident -- a production adapter's default (real-
    session) fetch path reaching a real URL during an ordinary offline
    test run, caught only because an unrelated assertion happened to fail
    -- is exactly what this closes at the root."""


@contextmanager
def block_all_real_network_io() -> Iterator[None]:
    """Patches requests.adapters.HTTPAdapter.send -- the point AFTER
    Session.get()/AccessProbe._get() where a real connection is actually
    opened -- so every real HTTP call of any kind fails before any socket
    I/O, regardless of which higher-level path (raw Session, or AccessProbe
    itself) initiated it. A FakeSession/FakeResponse test double never
    reaches this method at all (it isn't a requests.Session), so this has
    no effect on any of this project's existing offline test doubles.
    Reentrant, the same way and for the same reason as
    enforce_policy_aware_fetch_only() above."""
    previous = requests.adapters.HTTPAdapter.send

    def _blocked_send(self, request, **kwargs):
        raise RealNetworkIOBlocked(
            f"A real HTTP request to {getattr(request, 'url', '?')!r} was "
            "attempted while block_all_real_network_io() is active (see "
            "tests/__init__.py, which activates this for the whole test "
            "process). Ordinary tests must never reach the real network -- "
            "inject a fake session/transport instead."
        )
    requests.adapters.HTTPAdapter.send = _blocked_send
    try:
        yield
    finally:
        requests.adapters.HTTPAdapter.send = previous


def guarded_entry_point(main_func: Callable[..., Any]) -> Callable[..., Any]:
    """Stage 15: wraps a research script's own main() so the guard is
    active for its entire real run -- the __main__ block a person actually
    invokes (`python -m product_tool.census.runner ...`) -- not just inside
    a test that calls the context manager directly. enforce_policy_aware_
    fetch_only() existing as a context manager that SOME code opts into is
    not the same guarantee as it being active at every place research code
    actually starts; this closes that gap for product_tool/census/runner.py,
    runner_v5.py, runner_v71.py and report_v71.py, the module's own four
    __main__ entry points, each decorating its main() with this."""
    @functools.wraps(main_func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        with enforce_policy_aware_fetch_only():
            return main_func(*args, **kwargs)
    return _wrapped


@dataclass(frozen=True)
class ProbePolicy:
    timeout_seconds: float = 10.0
    max_bytes: int = 512_000
    min_interval_seconds: float = 2.0
    max_rate_limits_per_host: int = 2
    user_agent: str = "ProductCardsSourceCensus/2.0 (bounded diagnostic probe)"


@dataclass(frozen=True)
class ProtectionAssessment:
    status: ProtectionStatus
    evidence: tuple[dict, ...]


@dataclass(frozen=True)
class ProbeResult:
    url: str
    capability: EndpointCapability
    sample_type: str
    access_status: AccessStatus
    http_status: int | None
    redirect_chain: tuple[str, ...]
    final_url: str
    content_type: str
    javascript_required: bool | None
    protection_status: ProtectionStatus
    protection_evidence: tuple[dict, ...]
    product_search_available: bool | None
    fingerprints: tuple[PlatformFingerprint, ...]
    evidence: tuple[dict, ...]
    checked_at: str
    error: str = ""
    diagnostic_text: str = ""

    @property
    def robots_status(self) -> str:
        return self.access_status.value if self.capability == EndpointCapability.ROBOTS else "not_checked"

    @property
    def sitemap_status(self) -> str:
        return self.access_status.value if self.capability == EndpointCapability.SITEMAP else "not_checked"

    @property
    def protection_status_value(self) -> str:
        return self.protection_status.value

    def to_dict(self) -> dict:
        result = asdict(self)
        result["capability"] = self.capability.value
        result["access_status"] = self.access_status.value
        result["protection_status"] = self.protection_status.value
        result["fingerprints"] = [item.to_dict() for item in self.fingerprints]
        result.pop("diagnostic_text", None)
        return result

    def to_endpoint_record(self) -> EndpointRecord:
        products = json_ld_products(self.diagnostic_text)
        states = detect_embedded_state(self.diagnostic_text)
        discovery = detect_internal_search(self.diagnostic_text, self.final_url or self.url)
        return EndpointRecord(
            url=self.url,
            capability=self.capability,
            sample_type=self.sample_type,
            access_status=self.access_status,
            http_status=self.http_status,
            redirect_chain=self.redirect_chain,
            final_url=self.final_url,
            content_type=self.content_type,
            protection_status=self.protection_status,
            protection_evidence=self.protection_evidence,
            javascript_required=self.javascript_required,
            product_search_available=self.product_search_available,
            json_ld_product_count=len(products),
            json_ld_field_coverage=json_ld_field_coverage(self.diagnostic_text),
            embedded_state_kinds=tuple(sorted({item.kind for item in states})),
            discovery_evidence=tuple(route.to_dict() for route in discovery),
            checked_at=self.checked_at,
            error=self.error,
        )


def classify_protection(
    html: str,
    *,
    http_status: int | None = None,
    headers: Mapping[str, str] | None = None,
    cookie_names: tuple[str, ...] = (),
) -> ProtectionAssessment:
    """Classify a challenge without retaining cookie values or tokens."""
    text = html or ""
    lowered = text.casefold()
    evidence: list[dict] = []
    strong_kinds: set[str] = set()

    if http_status in {403, 429}:
        evidence.append({"type": "http_status", "value": http_status, "strength": "weak"})
    if "captcha" in lowered:
        evidence.append({"type": "captcha_term", "strength": "weak"})

    strong_patterns = {
        "challenge_phrase": r"verify (?:that )?you are human|checking your browser|attention required|access denied|security check",
        "challenge_widget": r"(?:g-recaptcha|h-captcha|cf-chl-widget|challenge-form|captcha-container)[\"'\s=>]",
        "waf_path": r"/cdn-cgi/challenge-platform/|/akam/[\w/-]*challenge|imperva|datadome",
    }
    for kind, pattern in strong_patterns.items():
        if re.search(pattern, text, re.I):
            strong_kinds.add(kind)
            evidence.append({"type": kind, "strength": "strong"})

    normalized_headers = {str(key).casefold(): str(value) for key, value in (headers or {}).items()}
    if normalized_headers.get("cf-mitigated", "").casefold() == "challenge" or any(
        name in normalized_headers for name in ("x-datadome", "x-sucuri-block")
    ):
        strong_kinds.add("waf_header")
        evidence.append({"type": "waf_header", "names": sorted(name for name in normalized_headers if name in {"cf-mitigated", "x-datadome", "x-sucuri-block"}), "strength": "strong"})

    protected_cookie_names = sorted(
        name for name in cookie_names
        if name.casefold() in {"__cf_bm", "cf_clearance", "ak_bmsc", "bm_sz", "datadome", "incap_ses"}
    )
    if protected_cookie_names:
        strong_kinds.add("waf_cookie")
        evidence.append({"type": "waf_cookie", "names": protected_cookie_names, "strength": "strong"})

    visible_text = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<[^>]+>", " ", text, flags=re.I | re.S)
    visible_text = " ".join(visible_text.split())
    if strong_kinds and len(visible_text) < 160:
        strong_kinds.add("missing_ordinary_content")
        evidence.append({"type": "missing_ordinary_content", "visible_characters": len(visible_text), "strength": "strong"})

    browser_phrase = bool(re.search(r"enable (?:javascript|cookies)|javascript and cookies", lowered))
    if browser_phrase and strong_kinds:
        evidence.append({"type": "browser_verification_phrase", "strength": "strong"})
        return ProtectionAssessment(ProtectionStatus.BROWSER_VERIFICATION_REQUIRED, tuple(evidence))
    if len(strong_kinds) >= 2 or (http_status == 403 and strong_kinds):
        return ProtectionAssessment(ProtectionStatus.CHALLENGE_CONFIRMED, tuple(evidence))
    if evidence or strong_kinds:
        return ProtectionAssessment(ProtectionStatus.CHALLENGE_SUSPECTED, tuple(evidence))
    if http_status is not None and 200 <= http_status < 400 and len(visible_text) >= 80:
        return ProtectionAssessment(ProtectionStatus.ORDINARY_PAGE, ())
    return ProtectionAssessment(ProtectionStatus.INCONCLUSIVE, ())


def blocked_hosts_from_fetch_log(entries: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    """Given fetch-log-style records (each with at least 'url' and
    'status_code'), returns the hosts that returned a blocking status
    (401/403/429) -- i.e. the hosts a NEW AccessProbe/run must still treat
    as stopped, per the same rule that governs a single run: once a host
    responds with a block, no further request to it is authorized until a
    human deliberately clears it. Passing this set as `initial_stopped_hosts`
    is what makes that stop survive a fresh process/script invocation
    ("re-run"), not just the lifetime of one AccessProbe instance."""
    blocked: set[str] = set()
    for entry in entries:
        if entry.get("status_code") in (401, 403, 429):
            host = (urlsplit(str(entry.get("url", ""))).hostname or "").casefold()
            if host:
                blocked.add(host)
    return frozenset(blocked)


class AccessProbe:
    def __init__(
        self, session=None, *, policy: ProbePolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
        initial_stopped_hosts: Iterable[str] = (),
    ):
        self.session = session or requests.Session()
        self.policy = policy or ProbePolicy()
        self.clock = clock
        self._last_request_at: float | None = None
        self._stopped_endpoints: set[str] = set()
        self._stopped_hosts: set[str] = {host.casefold() for host in initial_stopped_hosts}
        self._rate_limit_counts: dict[str, int] = {}

    @staticmethod
    def _normalized_url(url: str) -> str:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path or "/", parsed.query, ""))

    @staticmethod
    def _allowed(host: str, allowed_hosts: tuple[str, ...]) -> bool:
        return bool(host) and any(host == allowed.casefold() or host.endswith("." + allowed.casefold()) for allowed in allowed_hosts)

    def _get(self, url: str, **kwargs):
        """The one place AccessProbe actually calls out. For a real
        requests.Session, always goes through the pre-captured
        _REAL_SESSION_GET reference, so this class is immune to
        enforce_policy_aware_fetch_only() no matter when that guard is
        installed. A test double's own .get() is called normally --
        never patched by the guard in the first place, since it is a
        different class entirely."""
        if isinstance(self.session, requests.Session):
            return _REAL_SESSION_GET(self.session, url, **kwargs)
        return self.session.get(url, **kwargs)

    def _wait_for_rate_limit(self, deadline: float | None = None) -> None:
        if self._last_request_at is None:
            return
        remaining = self.policy.min_interval_seconds - (self.clock() - self._last_request_at)
        if deadline is not None:
            remaining = min(remaining, max(0.0, deadline - self.clock()))
        if remaining > 0:
            time.sleep(remaining)

    def probe(
        self,
        url: str,
        *,
        allowed_hosts: tuple[str, ...],
        capability: EndpointCapability | str = EndpointCapability.HOMEPAGE,
        sample_type: str = "homepage",
        request_guard=None,
        deadline: float | None = None,
    ) -> ProbeResult:
        capability = EndpointCapability(capability)
        host = (urlsplit(url).hostname or "").casefold()
        if not self._allowed(host, allowed_hosts):
            raise ValueError(f"Probe URL host is not allowlisted: {host or '<missing>'}")
        endpoint_key = self._normalized_url(url)
        if endpoint_key in self._stopped_endpoints or host in self._stopped_hosts:
            return self._result(url, capability, sample_type, AccessStatus.CAPTCHA_OR_BLOCKED, None, (url,), url, error="Endpoint probing stopped after a protection response")

        history = []
        target = url
        try:
            while True:
                self._wait_for_rate_limit(deadline)
                timeout = self.policy.timeout_seconds
                if request_guard is not None:
                    timeout = min(timeout, request_guard(target))
                response = self._get(
                    target, timeout=timeout, allow_redirects=request_guard is None,
                    headers={"User-Agent": self.policy.user_agent, "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.1"},
                    stream=True,
                )
                self._last_request_at = self.clock()
                if request_guard is None or response.status_code not in {301, 302, 303, 307, 308}:
                    break
                history.append(response.url)
                location = response.headers.get("Location", "")
                target = urljoin(response.url, location)
                getattr(response, "close", lambda: None)()
                try:
                    parsed = urlsplit(target)
                except ValueError:
                    return self._result(url, capability, sample_type, AccessStatus.REGIONAL_REDIRECT, response.status_code, tuple(history), response.url, error="Malformed redirect rejected")
                if not location or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or not self._allowed(parsed.hostname or "", allowed_hosts):
                    return self._result(url, capability, sample_type, AccessStatus.REGIONAL_REDIRECT, response.status_code, tuple(history + [target]), target, error="Unsafe redirect rejected before request")
        except requests.RequestException:
            return self._result(url, capability, sample_type, AccessStatus.UNAVAILABLE, None, tuple(history + [target]), target, error="Network request failed")

        chain = tuple(history + [item.url for item in getattr(response, "history", ())] + [response.url])
        for target in chain:
            target_host = (urlsplit(target).hostname or "").casefold()
            if not self._allowed(target_host, allowed_hosts):
                return self._result(url, capability, sample_type, AccessStatus.REGIONAL_REDIRECT, response.status_code, chain, response.url, error=f"Redirected to non-allowlisted host: {target_host}")

        if response.status_code >= 400:
            getattr(response, "close", lambda: None)()
        if response.status_code == 429:
            self._stopped_endpoints.add(endpoint_key)
            # A confirmed rate-limit is a host-level stop signal.  The census
            # must not fan out to robots/sitemaps after the origin asks us to
            # slow down; a later checkpointed run may retry deliberately.
            self._stopped_hosts.update((host, (urlsplit(response.url).hostname or "").casefold()))
            count = self._rate_limit_counts.get(host, 0) + 1
            self._rate_limit_counts[host] = count
            if count >= self.policy.max_rate_limits_per_host:
                self._stopped_hosts.update((host, (urlsplit(response.url).hostname or "").casefold()))
            assessment = classify_protection("", http_status=429, headers=response.headers)
            return self._result(url, capability, sample_type, AccessStatus.RATE_LIMITED, 429, chain, response.url, protection=assessment)

        if response.status_code == 403:
            self._stopped_endpoints.add(endpoint_key)
            self._stopped_hosts.update((host, (urlsplit(response.url).hostname or "").casefold()))
            assessment = classify_protection("", http_status=403, headers=response.headers, cookie_names=tuple(response.cookies.get_dict()))
            return self._result(url, capability, sample_type, AccessStatus.CAPTCHA_OR_BLOCKED, 403, chain, response.url, protection=assessment)
        if response.status_code >= 400:
            return self._result(url, capability, sample_type, AccessStatus.UNAVAILABLE, response.status_code, chain, response.url, error=f"HTTP {response.status_code}")

        chunks: list[bytes] = []
        size = 0
        try:
            for chunk in response.iter_content(chunk_size=16_384):
                if deadline is not None and self.clock() >= deadline:
                    getattr(response, "close", lambda: None)()
                    return self._result(url, capability, sample_type, AccessStatus.UNAVAILABLE, response.status_code, chain, response.url, error="deadline_exhausted")
                if not chunk:
                    continue
                remaining = self.policy.max_bytes - size
                chunks.append(chunk[:remaining])
                size += min(len(chunk), remaining)
                if size >= self.policy.max_bytes:
                    break
        except requests.RequestException:
            return self._result(url, capability, sample_type, AccessStatus.UNAVAILABLE, response.status_code, chain, response.url, error="Response stream failed")
        finally:
            getattr(response, "close", lambda: None)()
        encoding = response.encoding or "utf-8"
        html = b"".join(chunks).decode(encoding, errors="replace")
        assessment = classify_protection(
            html,
            http_status=response.status_code,
            headers=response.headers,
            cookie_names=tuple(response.cookies.get_dict()),
        )
        javascript = bool(re.search(r"enable javascript|javascript is required|id=[\"']__next[\"'][^>]*>\s*</", html, re.I))
        search_available = bool(re.search(r"type=[\"']search[\"']|/search(?:[/?\"'])|поиск", html, re.I))
        content_type = response.headers.get("content-type", "")
        fingerprints = fingerprint_platform(html, headers=response.headers, cookies=response.cookies.get_dict(), content_type=content_type)
        access = AccessStatus.JAVASCRIPT_REQUIRED if javascript else AccessStatus.DIRECT_ACCESS
        if assessment.status in {ProtectionStatus.CHALLENGE_CONFIRMED, ProtectionStatus.BROWSER_VERIFICATION_REQUIRED}:
            access = AccessStatus.CAPTCHA_OR_BLOCKED
            self._stopped_endpoints.add(endpoint_key)
            self._stopped_hosts.update((host, (urlsplit(response.url).hostname or "").casefold()))
        evidence = (
            {"type": "bounded_get", "bytes_read": size, "url": response.url, "sample_type": sample_type},
            {"type": "response", "http_status": response.status_code, "content_type": content_type},
        )
        return ProbeResult(url, capability, sample_type, access, response.status_code, chain, response.url, content_type, javascript, assessment.status, assessment.evidence, search_available, fingerprints, evidence, self._now(), diagnostic_text=html)

    def _result(
        self,
        url: str,
        capability: EndpointCapability,
        sample_type: str,
        status: AccessStatus,
        http_status: int | None,
        chain: tuple[str, ...],
        final_url: str,
        *,
        protection: ProtectionAssessment | None = None,
        error: str = "",
    ) -> ProbeResult:
        assessment = protection or ProtectionAssessment(ProtectionStatus.INCONCLUSIVE, ())
        return ProbeResult(url, capability, sample_type, status, http_status, tuple(chain), final_url, "", None, assessment.status, assessment.evidence, None, (), (), self._now(), error)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
