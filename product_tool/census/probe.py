"""Low-rate, fail-closed access probing. No protection bypass is attempted."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
import time
from typing import Callable
from urllib.parse import urlsplit

import requests

from .fingerprint import PlatformFingerprint, fingerprint_platform
from .models import AccessStatus


@dataclass(frozen=True)
class ProbePolicy:
    timeout_seconds: float = 10.0
    max_bytes: int = 512_000
    min_interval_seconds: float = 2.0
    user_agent: str = "ProductCardsSourceCensus/1.0 (diagnostic; one request per configured source)"


@dataclass(frozen=True)
class ProbeResult:
    access_status: AccessStatus
    http_status: int | None
    redirect_chain: tuple[str, ...]
    final_url: str
    content_type: str
    javascript_required: bool | None
    protection_status: str
    product_search_available: bool | None
    robots_status: str
    sitemap_status: str
    fingerprints: tuple[PlatformFingerprint, ...]
    evidence: tuple[dict, ...]
    checked_at: str
    error: str = ""

    def to_dict(self) -> dict:
        result = asdict(self)
        result["access_status"] = self.access_status.value
        result["fingerprints"] = [item.to_dict() for item in self.fingerprints]
        return result


class AccessProbe:
    def __init__(self, session=None, *, policy: ProbePolicy | None = None, clock: Callable[[], float] = time.monotonic):
        self.session = session or requests.Session()
        self.policy = policy or ProbePolicy()
        self.clock = clock
        self._last_request_at: float | None = None
        self._stopped_hosts: set[str] = set()

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.policy.min_interval_seconds - (self.clock() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def probe(self, url: str, *, allowed_hosts: tuple[str, ...]) -> ProbeResult:
        host = (urlsplit(url).hostname or "").casefold()
        if not host or not any(host == allowed.casefold() or host.endswith("." + allowed.casefold()) for allowed in allowed_hosts):
            raise ValueError(f"Probe URL host is not allowlisted: {host or '<missing>'}")
        if host in self._stopped_hosts:
            return self._result(AccessStatus.CAPTCHA_OR_BLOCKED, None, (url,), url, error="Host probing stopped after a protection response")
        self._wait_for_rate_limit()
        try:
            response = self.session.get(
                url, timeout=self.policy.timeout_seconds, allow_redirects=True,
                headers={"User-Agent": self.policy.user_agent, "Accept": "text/html,application/xhtml+xml"},
                stream=True,
            )
            self._last_request_at = self.clock()
        except requests.RequestException as exc:
            return self._result(AccessStatus.UNAVAILABLE, None, (url,), url, error=str(exc))

        chain = tuple([item.url for item in getattr(response, "history", ())] + [response.url])
        for target in chain:
            target_host = (urlsplit(target).hostname or "").casefold()
            if not any(target_host == allowed.casefold() or target_host.endswith("." + allowed.casefold()) for allowed in allowed_hosts):
                return self._result(AccessStatus.REGIONAL_REDIRECT, response.status_code, chain, response.url, error=f"Redirected to non-allowlisted host: {target_host}")
        if response.status_code == 429:
            self._stopped_hosts.add(host)
            return self._result(AccessStatus.RATE_LIMITED, 429, chain, response.url, protection="429")
        if response.status_code == 403:
            self._stopped_hosts.add(host)
            return self._result(AccessStatus.CAPTCHA_OR_BLOCKED, 403, chain, response.url, protection="403")
        if response.status_code >= 400:
            return self._result(AccessStatus.UNAVAILABLE, response.status_code, chain, response.url, error=f"HTTP {response.status_code}")

        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=16_384):
            if not chunk:
                continue
            remaining = self.policy.max_bytes - size
            chunks.append(chunk[:remaining])
            size += min(len(chunk), remaining)
            if size >= self.policy.max_bytes:
                break
        encoding = response.encoding or "utf-8"
        html = b"".join(chunks).decode(encoding, errors="replace")
        lowered = html.casefold()
        protection = "captcha" if re.search(r"captcha|verify you are human|cloudflare challenge", lowered) else "none_observed"
        if protection == "captcha":
            self._stopped_hosts.add(host)
            return self._result(AccessStatus.CAPTCHA_OR_BLOCKED, response.status_code, chain, response.url, protection=protection)
        javascript = bool(re.search(r"enable javascript|javascript is required|id=[\"']__next[\"'][^>]*>\s*</", html, re.I))
        search_available = bool(re.search(r"type=[\"']search[\"']|/search(?:[/?\"'])|поиск", html, re.I))
        content_type = response.headers.get("content-type", "")
        fingerprints = fingerprint_platform(html, headers=response.headers, cookies=response.cookies.get_dict(), content_type=content_type)
        access = AccessStatus.JAVASCRIPT_REQUIRED if javascript else AccessStatus.DIRECT_ACCESS
        evidence = (
            {"type": "bounded_get", "bytes_read": size, "url": response.url},
            {"type": "response", "http_status": response.status_code, "content_type": content_type},
        )
        return ProbeResult(access, response.status_code, chain, response.url, content_type, javascript, protection, search_available, "not_checked", "not_checked", fingerprints, evidence, self._now())

    def _result(self, status, http_status, chain, final_url, *, protection="none_observed", error="") -> ProbeResult:
        return ProbeResult(status, http_status, tuple(chain), final_url, "", None, protection, None, "not_checked", "not_checked", (), (), self._now(), error)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Compatibility import: callers keep the original module path while the v2
# implementation records endpoint capability and evidence-based protection.
from .endpoint_probe import AccessProbe, ProbePolicy, ProbeResult, classify_protection  # noqa: E402,F401
