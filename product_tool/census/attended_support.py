"""Explicit, attended capture of one observed official support page.

This is deliberately separate from unattended search.  It never submits a
challenge, retries a navigation, or clears a host stop.  The operator uses a
visible Chrome window; only page observation resumes after a manual check.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

from .browser_runtime import discover_runtime


LG_SUPPORT_HOST = "www.lg.com"
LG_DOCUMENT_HOST = "gscs-b2c.lge.com"
ALLOWED_RESOURCE_HOSTS = (LG_SUPPORT_HOST, LG_DOCUMENT_HOST)
RELEVANT_PATHS = ("/support/product-support/", "/ncms/api/v1/support/proxy/")
RELEVANT_ACTION_HEADER = "next-action"


def official_support_url(url: str) -> bool:
    parsed = urlsplit(url)
    parts = [part.casefold() for part in parsed.path.split("/") if part]
    return (parsed.scheme == "https" and parsed.hostname == LG_SUPPORT_HOST
            and not parsed.username and not parsed.password and parsed.port is None
            and not parsed.query and not parsed.fragment and len(parts) >= 3
            and parts[:2] == ["kz", "support"] and parts[2] == "product-support")


def resource_allowed(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname in ALLOWED_RESOURCE_HOSTS
            and not parsed.username and not parsed.password and parsed.port is None)


def response_relevant(url: str, method: str, next_action: bool) -> bool:
    parsed = urlsplit(url)
    if not resource_allowed(url):
        return False
    path = parsed.path.casefold()
    return (any(part in path for part in RELEVANT_PATHS)
            or (method == "POST" and next_action and official_support_url(url)))


def looks_like_challenge(url: str, html: str, status: int | None = None) -> bool:
    if any(part in url.casefold() for part in ("/xpvnsulc/", "/exhkqyad", "hcheck=")):
        return True
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script,style,noscript"):
        node.decompose()
    text = soup.get_text(" ", strip=True).casefold()
    marker = any(part in text for part in ("verify you are human", "checking your browser",
                                          "access denied", "unusual traffic"))
    marker |= bool(soup.select_one('iframe[src*="captcha"],iframe[src*="challenge"],.g-recaptcha,.h-captcha,#challenge-form'))
    # A prior 403 does not remain a permanent challenge after manual navigation.
    return marker or (status in {401, 403, 429} and not any(
        part in html for part in ("support-product-area", "manualSoftwareList", "product-registration")))


@dataclass(frozen=True)
class AttendedBudget:
    max_navigations: int = 4
    max_resources: int = 150
    max_wait_seconds: int = 480
    max_response_bytes: int = 2_000_000
    max_dom_bytes: int = 3_000_000
    max_saved_responses: int = 12


def capture(url: str, output_dir: Path, profile_dir: Path, *, budget: AttendedBudget = AttendedBudget(),
            playwright_factory=None, clock=time.monotonic, pause=time.sleep, announce=print) -> dict:
    """One navigation and passive observation. No challenge interaction is automated."""
    if not official_support_url(url):
        raise ValueError("An observed LG KZ support URL is required")
    if profile_dir.resolve() == output_dir.resolve():
        raise ValueError("Profile and capture paths must differ")
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    if playwright_factory is None:
        from playwright.sync_api import sync_playwright
        playwright_factory = sync_playwright
    counters = {"navigations": 0, "resources": 0, "blocked_resources": 0, "saved_responses": 0}
    records = []
    state = {"challenge_seen": False, "network_limit": False, "foreign_navigation": False,
             "last_document_status": None, "blocked_hosts": set()}
    started = clock()
    clean_started = None
    with playwright_factory() as playwright:
        # No stealth flags, custom user agent, proxy, extension, or cookie import.
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), channel="chrome", headless=False, accept_downloads=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        def route_request(route):
            request = route.request
            navigation = request.is_navigation_request() and request.frame == page.main_frame
            if navigation:
                counters["navigations"] += 1
                if not official_support_url(request.url):
                    state["foreign_navigation"] = True
                    route.abort()
                    return
                if counters["navigations"] > budget.max_navigations:
                    state["network_limit"] = True
                    route.abort()
                    return
            if not resource_allowed(request.url):
                state["blocked_hosts"].add(urlsplit(request.url).hostname or "")
                counters["blocked_resources"] += 1
                route.abort()
                return
            if counters["resources"] >= budget.max_resources:
                state["network_limit"] = True
                counters["blocked_resources"] += 1
                route.abort()
                return
            counters["resources"] += 1
            route.continue_()

        def finished(request):
            try:
                next_action = bool(request.header_value(RELEVANT_ACTION_HEADER))
                if not response_relevant(request.url, request.method, next_action):
                    return
                response = request.response()
                if response is None:
                    return
                if request.is_navigation_request() and request.frame == page.main_frame:
                    state["last_document_status"] = response.status
                if response.status in {401, 403, 429} and resource_allowed(response.url):
                    state["challenge_seen"] = True
                if counters["saved_responses"] >= budget.max_saved_responses:
                    return
                body = response.body()
                if len(body) > budget.max_response_bytes:
                    records.append({"url": response.url, "status": response.status,
                                    "method": request.method, "next_action": next_action,
                                    "bytes": len(body), "saved": False, "reason": "too_large"})
                    return
                digest = hashlib.sha256(body).hexdigest()
                filename = f"response_{counters['saved_responses'] + 1:02d}_{digest[:12]}.gz"
                with gzip.open(output_dir / filename, "wb") as handle:
                    handle.write(body)
                counters["saved_responses"] += 1
                records.append({"url": response.url, "status": response.status,
                                "method": request.method, "next_action": next_action,
                                "content_type": response.headers.get("content-type", ""),
                                "bytes": len(body), "sha256": digest, "saved": filename})
            except Exception as exc:
                records.append({"url": request.url, "saved": False,
                                "reason": type(exc).__name__})

        context.route("**/*", route_request)
        page.on("requestfinished", finished)
        page.on("download", lambda download: download.cancel())
        # A popup could introduce an unbudgeted browsing context.
        context.on("page", lambda opened: opened.close() if opened != page else None)
        result = {"url": url, "outcome": "", "rendered_dom": "", "responses": records}
        try:
            announce("Visible Chrome opened. One LG support navigation; manual challenge only.")
            try:
                page.goto(url, wait_until="commit", timeout=20_000)
            except Exception as exc:
                result["navigation_notice"] = type(exc).__name__
            challenge_reported = False
            while clock() - started < budget.max_wait_seconds:
                if state["network_limit"] or state["foreign_navigation"]:
                    result["outcome"] = "network_budget_exhausted" if state["network_limit"] else "foreign_navigation"
                    break
                try:
                    current_url = page.url
                    html = page.content()
                except Exception:
                    pause(1)
                    continue
                challenge = looks_like_challenge(current_url, html, state["last_document_status"])
                if challenge:
                    state["challenge_seen"] = True
                    if not challenge_reported:
                        announce("Challenge visible. Complete it yourself in this Chrome window; automation is paused.")
                        challenge_reported = True
                    # A successful navigation may have status 200; the old 403
                    # must not pin the state after the user completes a check.
                    pause(2)
                    continue
                if clean_started is None:
                    clean_started = clock()
                from product_tool.adapters.lg_support import (registration_component_codes,
                                                               support_manual_candidates)
                rendered_data = (registration_component_codes(html, current_url)
                                 and support_manual_candidates(html, current_url))
                action_data = any(record.get("next_action") and record.get("status") == 200
                                  for record in records)
                quiet_limit = 25
                if official_support_url(current_url) and (
                        rendered_data or action_data or clock() - clean_started >= quiet_limit):
                    # Save the actual rendered DOM even if the dynamic section did
                    # not arrive; the manifest then distinguishes timeout from data.
                    pause(2)
                    html = page.content()
                    if len(html.encode("utf-8")) <= budget.max_dom_bytes:
                        with gzip.open(output_dir / "rendered_dom.html.gz", "wt", encoding="utf-8") as handle:
                            handle.write(html)
                        result["rendered_dom"] = "rendered_dom.html.gz"
                        result["outcome"] = "captured" if rendered_data or action_data else "render_timeout"
                    else:
                        result["outcome"] = "dom_too_large"
                    break
                pause(2)
            if not result["outcome"]:
                result["outcome"] = "challenge_not_completed" if state["challenge_seen"] else "render_timeout"
            result["final_url"] = page.url
            result["challenge_seen"] = state["challenge_seen"]
            result["counts"] = counters
            result["blocked_hosts"] = sorted(state["blocked_hosts"])
        finally:
            context.close()
    (output_dir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Attended LG support capture; visible Chrome only")
    parser.add_argument("url")
    parser.add_argument("--attended", action="store_true", help="explicit user-assisted mode")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    if not args.attended:
        parser.error("--attended is required; background runs must keep the host stop")
    runtime = discover_runtime()
    if not runtime.available:
        parser.error(runtime.reason)
    result = capture(args.url, args.output, args.profile, announce=lambda message: print(message, flush=True))
    print(json.dumps({"outcome": result["outcome"], "counts": result["counts"]}), flush=True)
    return 0 if result["outcome"] == "captured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
