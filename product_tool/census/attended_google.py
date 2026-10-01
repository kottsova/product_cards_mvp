"""Visible persistent Chrome transport for a single user-attended Google search.

The existing LGBrowserSearch owns query generation and result parsing. This
module only supplies its browser-driver contract. It never solves a challenge,
retries navigation, imports cookies, or changes the user agent.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from .browser_runtime import BrowserFailure
from ..adapters.access_stop import FATAL, HTTP_DENIED, MANUAL, RATE_LIMIT, active_stops
from ..adapters.policy_fetch import append_log_entry, read_log, resolve_attended_challenge

PROJECTION_SCRIPT = Path(__file__).with_name("browser_projection.js").read_text(encoding="utf-8-sig")
GOOGLE_HOST = "www.google.com"


def google_search_url(url: str) -> bool:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query).get("q", [""])[0]
    return (parsed.scheme == "https" and parsed.hostname == GOOGLE_HOST
            and not parsed.username and not parsed.password and parsed.port is None
            and parsed.path == "/search" and query.startswith("site:lg.com "))


class AttendedGoogleBrowser:
    """A PlaywrightBrowser-compatible driver for one visible, bounded search."""

    def __init__(self, runtime, budget, allowed_hosts, *, profile_dir: Path,
                 output_dir: Path, fetch_log_path: Path,
                 max_wait_seconds: int = 480, max_navigations: int = 6,
                 max_resources: int = 150, playwright_factory=None,
                 clock=time.monotonic, pause=time.sleep, announce=print):
        self.runtime = runtime
        self.budget = budget
        self.allowed_hosts = tuple(allowed_hosts)
        self.profile_dir = Path(profile_dir)
        self.output_dir = Path(output_dir)
        self.fetch_log_path = Path(fetch_log_path)
        self.max_wait_seconds = max_wait_seconds
        self.max_navigations = max_navigations
        self.max_resources = max_resources
        self.playwright_factory = playwright_factory
        self.clock = clock
        self.pause = pause
        self.announce = announce
        self._playwright_cm = None
        self._playwright = None
        self.context = None
        self.page = None
        self.counts = {"navigations": 0, "network_requests": 0, "blocked_requests": 0}
        self.blocked_hosts: set[str] = set()
        self.challenge_seen = False
        self.last_document_status = None
        self.last_document_url = ""
        self.rate_limit_url = ""
        self.rate_limit_recorded = False
        self.session_id = "attended_google:" + uuid4().hex

    def _allowed(self, url: str) -> bool:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        return (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port is None and any(host == allowed or host.endswith("." + allowed)
                                             for allowed in self.allowed_hosts))

    def start(self):
        active = active_stops(read_log(self.fetch_log_path)).get(GOOGLE_HOST, ())
        if any(stop["reason"] in {MANUAL, FATAL, RATE_LIMIT, HTTP_DENIED} for stop in active):
            raise BrowserFailure("host_stopped", self.counts)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.playwright_factory is None:
            from playwright.sync_api import sync_playwright
            self.playwright_factory = sync_playwright
        self._playwright_cm = self.playwright_factory()
        self._playwright = self._playwright_cm.__enter__()
        try:
            self.context = self._playwright.chromium.launch_persistent_context(
                str(self.profile_dir), channel="chrome", headless=False,
                accept_downloads=False, viewport={"width": 1400, "height": 900})
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.context.route("**/*", self._route)
            self.page.on("response", self._response)
            self.page.on("download", lambda download: download.cancel())
            self.context.on("page", lambda opened: opened.close() if opened != self.page else None)
            return {"runtime_version": self.runtime.browser_version, "counts": dict(self.counts)}
        except Exception:
            self.close()
            raise

    def _route(self, route):
        request = route.request
        url = request.url
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        navigation = request.is_navigation_request() and request.frame == self.page.main_frame
        if navigation:
            self.counts["navigations"] += 1
            if host not in {"www.google.com", "google.com", "consent.google.com"}:
                self.blocked_hosts.add(host)
                self.counts["blocked_requests"] += 1
                route.abort()
                return
            if self.counts["navigations"] > self.max_navigations:
                self.counts["blocked_requests"] += 1
                route.abort()
                return
        if not self._allowed(url) or self.counts["network_requests"] >= self.max_resources:
            self.blocked_hosts.add(host)
            self.counts["blocked_requests"] += 1
            route.abort()
            return
        if request.method not in {"GET", "HEAD"} and not (
                self.challenge_seen and host.endswith("google.com") and request.method == "POST"):
            self.counts["blocked_requests"] += 1
            route.abort()
            return
        self.counts["network_requests"] += 1
        route.continue_()

    def _response(self, response):
        request = response.request
        if request.is_navigation_request() and request.frame == self.page.main_frame:
            self.last_document_status = response.status
            self.last_document_url = response.url
        if response.status == 429 and self._allowed(response.url):
            self.rate_limit_url = response.url

    def _projection(self, *, query_term: str):
        # Projection may read official LG result URLs; the route still admits
        # network traffic only to the explicitly allowed Google hosts.
        result_hosts = tuple(dict.fromkeys((*self.allowed_hosts, "www.lg.com")))
        policy = {**asdict(self.budget), "allowed_hosts": result_hosts,
                  "queries": [query_term], "search_result_hosts": ["www.lg.com"],
                  "render_mode": "render_existing_search_result"}
        return self.page.evaluate(PROJECTION_SCRIPT, policy)

    def call(self, command: str, **args):
        if command == "close":
            self.close()
            return {"closed": True, "counts": dict(self.counts)}
        if command != "goto" or self.page is None or not google_search_url(args.get("url", "")):
            raise BrowserFailure("interaction_blocked", self.counts)
        url = args["url"]
        term = (args.get("queries") or [""])[0]
        self.announce("Visible Chrome opened for one Google search. Complete any challenge manually in this window.")
        started = self.clock()
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        except Exception:
            # A challenge may interrupt navigation. Observe the same page only.
            pass
        reported = False
        empty_projections = 0
        while self.clock() - started < self.max_wait_seconds:
            if self.rate_limit_url:
                if not self.rate_limit_recorded:
                    append_log_entry(self.fetch_log_path, {
                        "url": self.rate_limit_url,
                        "final_url": self.rate_limit_url,
                        "status_code": 429,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "access_status": "rate_limited",
                        "protection_status": "ordinary_page",
                        "source_session": self.session_id,
                    })
                    self.rate_limit_recorded = True
                self.counts["rate_limit_url"] = self.rate_limit_url
                self.counts["rate_limit_recorded"] = True
                raise BrowserFailure("rate_limited", self.counts)
            try:
                projection = self._projection(query_term=term)
                current = self.page.url
            except Exception:
                self.pause(2)
                continue
            if projection.get("protection") or "/sorry/" in current:
                self.challenge_seen = True
                if not reported:
                    self.announce("Google challenge is visible. Automation is paused; complete it yourself in Chrome.")
                    reported = True
                self.pause(2)
                continue
            if self.last_document_status in {401, 403}:
                append_log_entry(self.fetch_log_path, {
                    "url": self.last_document_url,
                    "final_url": self.last_document_url,
                    "status_code": self.last_document_status,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "access_status": "blocked",
                    "protection_status": "ordinary_page",
                    "source_session": self.session_id,
                })
                self.counts["http_denied_url"] = self.last_document_url
                raise BrowserFailure("http_denied", self.counts)
            if not google_search_url(current):
                self.pause(2)
                continue
            if projection.get("overflow"):
                raise BrowserFailure("projection_budget_exhausted", self.counts)
            if not any(item.get("type") == "result_link" for item in projection.get("fragments", ())):
                empty_projections += 1
                if empty_projections < 3:
                    self.pause(2)
                    continue
            if self.challenge_seen:
                resolve_attended_challenge(self.fetch_log_path, GOOGLE_HOST,
                                           source_session=self.session_id)
            saved = {"url": current, "query": parse_qs(urlsplit(url).query).get("q", [""])[0],
                     "captured_at": datetime.now(timezone.utc).isoformat(),
                     "challenge_seen": self.challenge_seen,
                     "counts": dict(self.counts), "blocked_hosts": sorted(self.blocked_hosts),
                     "projection": projection}
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "search_projection.json").write_text(
                json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"url": current, "projection": projection,
                    "counts": dict(self.counts), "javascript_errors": 0}
        raise BrowserFailure("challenge_detected" if self.challenge_seen else "render_timeout", self.counts)

    def close(self):
        if self.context is not None:
            self.context.close()
            self.context = None
        if self._playwright_cm is not None:
            self._playwright_cm.__exit__(None, None, None)
            self._playwright_cm = None
            self._playwright = None
