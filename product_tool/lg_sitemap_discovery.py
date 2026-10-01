"""Official LG sitemap discovery after KZ/RU misses.

Only URLs linked by LG robots.txt and its sitemap index are traversed. A
sitemap entry is an untrusted candidate until the existing PDP validator opens
it and establishes the requested model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import zlib
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

import requests

from .adapters.lg import lg_article_components, lg_article_key, lg_base_model
from .adapters.lg_global import official_product_url
from .adapters.policy_fetch import append_log_entry

ROBOTS_URL = "https://www.lg.com/robots.txt"
CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_REQUESTS = 8
MAX_REGIONS = 5
MAX_CANDIDATES = 8
MAX_XML_BYTES = 25_000_000
# General coverage order for international LG pages, after KZ/RU were tried.
PREFERRED_REGIONS = ("uk", "au", "ca_en", "ca_fr", "de", "fr")


@dataclass(frozen=True)
class SitemapCandidate:
    url: str
    sitemap_url: str
    chain: tuple[str, ...]
    matched_key: str


def official_sitemap_url(url: str) -> bool:
    p = urlsplit(url)
    return (p.scheme == "https" and p.hostname == "www.lg.com"
            and not p.username and not p.password and p.port is None and not p.query
            and (p.path.endswith(".xml") or p.path.endswith(".xml.gz")))


def parse_sitemap(content: bytes, source_url: str) -> tuple[str, list[str]]:
    if source_url.endswith(".gz") or content[:2] == b"\x1f\x8b":
        if len(content) > MAX_XML_BYTES:
            raise ValueError("compressed_sitemap_too_large")
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        content = decoder.decompress(content, MAX_XML_BYTES + 1)
        if len(content) > MAX_XML_BYTES or not decoder.eof:
            raise ValueError("sitemap_too_large_or_incomplete")
    if len(content) > MAX_XML_BYTES:
        raise ValueError("sitemap_too_large")
    root = ET.fromstring(content)
    kind = root.tag.rsplit("}", 1)[-1]
    if kind not in {"sitemapindex", "urlset"}:
        raise ValueError("unexpected_sitemap_root")
    locs = [(n.text or "").strip() for n in root.iter()
            if n.tag.rsplit("}", 1)[-1] == "loc" and (n.text or "").strip()]
    return kind, locs


def normalized_slug(url: str) -> str:
    slug = unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]).casefold()
    if slug.startswith("lg-"):
        slug = slug[3:]
    return "".join(ch for ch in slug if ch.isalnum())


def model_keys(article: str) -> tuple[str, ...]:
    values = [*lg_article_components(article), lg_base_model(article)]
    return tuple(dict.fromkeys(lg_article_key(value) for value in values if value))


class LGOfficialSitemapDiscovery:
    def __init__(self, http, cache_dir: Path, *, clock=time.monotonic,
                 wall_clock=time.time, max_requests=MAX_REQUESTS,
                 trace_callback=None):
        self.http = http
        self.cache_dir = Path(cache_dir)
        self.clock = clock
        self.wall_clock = wall_clock
        self.max_requests = max_requests
        self.requests = 0
        self.trace_callback = trace_callback

    def _trace(self, **event):
        if self.trace_callback:
            self.trace_callback({"timestamp": datetime.now(timezone.utc).isoformat(),
                                 "provider": "lg_sitemap", **event})

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json.gz")

    def _load(self, url: str):
        path = self._cache_path(url)
        if path.is_file():
            try:
                with gzip.open(path, "rt", encoding="utf-8") as handle:
                    saved = json.load(handle)
                if saved.get("url") == url and self.wall_clock() - saved.get("fetched_at", 0) < CACHE_TTL_SECONDS:
                    self._trace(event="sitemap_cache_hit", url=url,
                                kind=saved.get("kind"), loc_count=saved.get("loc_count"))
                    return saved
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return None

    def _save(self, url: str, kind: str, locs: list[str]):
        index = {}
        if kind == "urlset":
            for loc in locs:
                if official_product_url(loc):
                    index.setdefault(normalized_slug(loc), []).append(loc)
        saved = {"url": url, "fetched_at": self.wall_clock(), "kind": kind,
                 "loc_count": len(locs), "children": locs if kind == "sitemapindex" else [],
                 "index": index}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(url)
        pending = path.with_suffix(path.suffix + ".tmp")
        with gzip.open(pending, "wt", encoding="utf-8") as handle:
            json.dump(saved, handle, ensure_ascii=False)
        pending.replace(path)
        return saved

    def _gzip_get(self, url: str, timeout: float) -> bytes:
        """Bounded binary GET for .gz, with the same host-stop audit as LG HTTP."""
        fetcher = getattr(self.http, "_fetcher", None)
        if fetcher is None or fetcher.host_stopped(url):
            raise ValueError("host_stopped_or_unavailable")
        session = self.http.underlying
        response = session.get(url, timeout=timeout, allow_redirects=False, stream=True)
        final = response.url
        status = response.status_code
        append_log_entry(self.http.log_path, {"url": url, "final_url": final,
                         "status_code": status, "checked_at": datetime.now(timezone.utc).isoformat(),
                         "access_status": "accessible" if status == 200 else "blocked",
                         "protection_status": "ordinary_page", "source_session": fetcher.session_id})
        if status != 200 or final != url:
            response.close()
            raise ValueError("gzip_http_or_redirect")
        chunks, total = [], 0
        try:
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > MAX_XML_BYTES:
                    raise ValueError("compressed_sitemap_too_large")
                chunks.append(chunk)
        finally:
            response.close()
        return b"".join(chunks)

    def _fetch(self, url: str, deadline: float):
        saved = self._load(url)
        if saved is not None:
            return saved
        if self.requests >= self.max_requests or self.clock() >= deadline:
            self._trace(event="sitemap_skip", url=url, reason="network_or_time_budget")
            return None
        remaining = deadline - self.clock()
        if remaining < 1:
            return None
        self.requests += 1
        try:
            if url.endswith(".xml.gz"):
                content = self._gzip_get(url, min(15, remaining))
            else:
                response = self.http.get(url, timeout=min(15, remaining))
                if not response.ok or response.truncated:
                    raise ValueError(f"http_{response.status_code}_or_truncated")
                content = response.content
            kind, locs = parse_sitemap(content, url)
            saved = self._save(url, kind, locs)
            self._trace(event="sitemap_fetch", url=url, outcome="parsed", kind=kind,
                        loc_count=len(locs), bytes=len(content))
            return saved
        except (OSError, requests.RequestException, ET.ParseError, ValueError) as exc:
            self._trace(event="sitemap_fetch", url=url, outcome="failed",
                        reason=type(exc).__name__ + ":" + str(exc)[:100])
            return None

    def _robots_sitemaps(self, deadline: float) -> list[str]:
        path = self.cache_dir / "robots.json"
        if path.is_file():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if self.wall_clock() - saved.get("fetched_at", 0) < CACHE_TTL_SECONDS:
                    self._trace(event="robots_cache_hit", url=ROBOTS_URL)
                    return saved["sitemaps"]
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if self.requests >= self.max_requests or self.clock() >= deadline:
            return []
        self.requests += 1
        try:
            response = self.http.get(ROBOTS_URL, timeout=min(15, deadline-self.clock()))
            if not response.ok or response.truncated:
                raise ValueError(f"robots_http_{response.status_code}")
            urls = [line.split(":", 1)[1].strip() for line in response.text.splitlines()
                    if line.casefold().startswith("sitemap:")]
            urls = [url for url in urls if official_sitemap_url(url)]
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fetched_at": self.wall_clock(), "sitemaps": urls}), encoding="utf-8")
            self._trace(event="robots_fetch", url=ROBOTS_URL, outcome="parsed", sitemap_refs=urls)
            return urls
        except (OSError, requests.RequestException, ValueError) as exc:
            self._trace(event="robots_fetch", url=ROBOTS_URL, outcome="failed", reason=str(exc)[:100])
            return []

    def discover(self, article: str, *, deadline: float) -> tuple[SitemapCandidate, ...]:
        keys = model_keys(article)
        if not keys:
            return ()
        roots = self._robots_sitemaps(deadline)
        if not roots:
            return ()
        results = []
        seen = set()
        for root_url in roots[:2]:
            root = self._fetch(root_url, deadline)
            if not root:
                continue
            children = [u for u in root["children"] if official_sitemap_url(u)] if root["kind"] == "sitemapindex" else [root_url]
            def rank(url):
                region = urlsplit(url).path.strip("/").split("/", 1)[0]
                return (PREFERRED_REGIONS.index(region) if region in PREFERRED_REGIONS else len(PREFERRED_REGIONS), url)
            for region_url in sorted(children, key=rank)[:MAX_REGIONS]:
                region = self._fetch(region_url, deadline)
                if not region:
                    continue
                leaves = ([u for u in region["children"] if official_sitemap_url(u)
                           and (urlsplit(u).path.endswith("/sitemap.xml") or
                                "product" in u.casefold() or "pdp" in u.casefold())]
                          if region["kind"] == "sitemapindex" else [region_url])
                # Plain regional URL lists precede larger alternate/hreflang maps.
                leaves.sort(key=lambda u: (not urlsplit(u).path.endswith("/sitemap.xml"), len(urlsplit(u).path.strip("/").split("/")), u))
                for leaf_url in leaves[:3]:
                    leaf = self._fetch(leaf_url, deadline)
                    if not leaf or leaf["kind"] != "urlset":
                        continue
                    for key in keys:
                        for url in leaf["index"].get(key, ()):
                            if url in seen:
                                continue
                            seen.add(url)
                            candidate = SitemapCandidate(url, leaf_url,
                                                         (ROBOTS_URL, root_url, region_url, leaf_url), key)
                            results.append(candidate)
                            self._trace(event="sitemap_result", url=url, sitemap_url=leaf_url,
                                        chain=candidate.chain, matched_key=key,
                                        decision="candidate", opened=False)
                            if len(results) >= MAX_CANDIDATES:
                                return tuple(results)
                    if results:
                        return tuple(results)
        return tuple(results)
