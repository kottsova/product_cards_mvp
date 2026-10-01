"""The default LG adapters the worker builds when nothing is injected (Stage 20): the same LGAdapter, LGRUAdapter
and SulpakAdapter, but every network call goes through PolicyAwareSession with one persisted log
(`<data dir>/lg_fetch_log.json`), so a host stop (401/403/429 or a confirmed challenge) outlives the process."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import requests

from .lg import LGAdapter, lg_session
from .lg_browser_search import LGBrowserSearch
from .lg_documents import BinarySafeSession
from .lg_documents_adapter import LGRUDocumentAdapter
from .policy_session import PolicyAwareSession
from .sulpak import SulpakAdapter

LG_HOSTS = ("www.lg.com", "lg.com")
BROWSER_HOSTS = ("www.lg.com", "lg.com", "www.google.com", "google.com", "gstatic.com",
                 "www.bing.com", "bing.com", "duckduckgo.com")
DOCUMENT_HOSTS = ("lg.com", "lge.com")  # the support page (lg.com) and the official document host printed on it (gscs-b2c.lge.com)
DOCUMENT_MAX_BYTES = 25_000_000
SULPAK_HOSTS = ("www.sulpak.kz", "sulpak.kz")
LOG_NAME = "lg_fetch_log.json"


def lg_log_path(directory: Path) -> Path:
    return Path(directory) / LOG_NAME


def default_lg_adapters(directory: Path, *, clock: Callable[[], float] = time.monotonic, underlying_lg=None, underlying_sulpak=None, min_interval_seconds: float | None = None, browser_search=True):
    """(lg_kz, lg_ru, sulpak, browser_search). `underlying_*` are for tests: a transport double instead of a real requests.Session. `min_interval_seconds`
    replaces the sessions' default pacing (a caller that paces real requests itself, e.g. a replay over saved responses, passes 0). `browser_search=True`
    (the default, used by the worker) builds a real Stage 43 `LGBrowserSearch` sharing this same fetch log, so a confirmed challenge from either the
    plain-HTTP or the browser path stops both; pass an already-built object (or False/None) for tests that must never launch a real browser."""
    pacing = {} if min_interval_seconds is None else {"min_interval_seconds": min_interval_seconds}
    log = lg_log_path(directory)
    lg_http = PolicyAwareSession(log, allowed_hosts=LG_HOSTS, underlying=underlying_lg if underlying_lg is not None else lg_session(), **pacing)
    sulpak_http = PolicyAwareSession(log, allowed_hosts=SULPAK_HOSTS, underlying=underlying_sulpak if underlying_sulpak is not None else requests.Session(), **pacing)
    document_http = PolicyAwareSession(log, allowed_hosts=DOCUMENT_HOSTS, underlying=BinarySafeSession(underlying_lg if underlying_lg is not None else lg_session()), max_bytes=DOCUMENT_MAX_BYTES, **pacing)
    search = LGBrowserSearch(log, allowed_hosts=BROWSER_HOSTS, clock=clock) if browser_search is True else (browser_search or None)
    return (
        LGAdapter(lg_http, clock=clock, browser_search=search),
        LGRUDocumentAdapter(lg_http, documents_http=document_http, clock=clock, browser_search=search),
        SulpakAdapter(sulpak_http, clock=clock),
        search,
    )
