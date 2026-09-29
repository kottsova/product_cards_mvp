"""Shared policy-aware production fetch and auditable host-stop history.

Stage 51.1: a challenge or rate limit creates a timed domain cooldown.
Manual and fatal stops remain active until explicitly resolved. Historical
responses are never deleted; active stops are derived before each request.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

from . import access_stop

from ..census.endpoint_probe import (
    AccessProbe,
    EndpointCapability,
    ProbePolicy,
    ProbeResult,
)


# A page that answered HTTP 200 but IS a challenge (not merely resembling one) stops the host exactly like a 403/429.
# `challenge_suspected` is a heuristic hit that ordinary pages trigger too (every hyperx.com product page does): it is
# logged for the record and never stops anything.
CONFIRMED_CHALLENGE = access_stop.CONFIRMED_CHALLENGE


def stopped_hosts_from_fetch_log(entries: Iterable[Mapping[str, Any]], *,
                                 now: datetime | None = None) -> frozenset[str]:
    """Active host cooldowns; old responses remain in the audit log."""
    return access_stop.stopped_hosts(entries, now=now)


def _read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    return data if isinstance(data, list) else []


def _append_log(path: Path, entry: dict) -> None:
    entries = _read_log(path)
    if entry.get("event") not in {"stop", "stop_resolved"}:
        entry = {**entry, **access_stop.response_stop_fields(
            entry, source_session=str(entry.get("source_session") or ""))}
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


# Stage 43: public wrappers so a non-HTTP fetch path (adapters/lg_browser_search.py's browser-driven
# search) can share this exact same persisted log/format with PolicyAwareFetcher/PolicyAwareSession --
# a confirmed challenge recorded by either path stops both, this run and every future one.
def read_log(path: Path) -> list[dict]:
    return _read_log(path)


def append_log_entry(path: Path, entry: dict) -> None:
    _append_log(path, entry)


def migrate_legacy_stop_log(path: Path, *, now: datetime | None = None) -> int:
    """Append lifecycle audit records once; keep all original responses intact."""
    entries = _read_log(path)
    events = access_stop.legacy_migration_events(entries, now=now)
    if events:
        path.write_text(json.dumps([*entries, *events], ensure_ascii=False, indent=2), encoding="utf-8")
    return len(events)


def record_stop(path: Path, domain: str, reason: str, *, source_session: str = "") -> None:
    """Explicit manual/fatal or timed stop without rewriting history."""
    _append_log(path, access_stop.stop_event(domain, reason, source_session=source_session))


def resolve_attended_challenge(path: Path, domain: str, *, source_session: str = "") -> None:
    """Only a successful, user-attended browser capture may call this."""
    _append_log(path, access_stop.attended_success_event(domain, source_session=source_session))


class PolicyAwareFetcher:
    """Use the append-only fetch log to refresh active stops before each request."""

    def __init__(
        self, log_path: Path, *, session=None,
        policy: ProbePolicy | None = None,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], datetime] | None = None,
    ):
        self.log_path = log_path
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.session_id = uuid4().hex
        stopped = stopped_hosts_from_fetch_log(_read_log(log_path), now=self._wall_clock())
        probe_kwargs: dict = {"policy": policy, "initial_stopped_hosts": stopped}
        if clock is not None:
            probe_kwargs["clock"] = clock
        self._probe = AccessProbe(session, **probe_kwargs)

    def host_stopped(self, url: str) -> bool:
        """Refresh the probe's in-memory guard from the expiring audit log."""
        host = (urlsplit(url).hostname or "").casefold()
        active = host in stopped_hosts_from_fetch_log(_read_log(self.log_path), now=self._wall_clock())
        if active:
            self._probe._stopped_hosts.add(host)
        else:
            self._probe._stopped_hosts.discard(host)
            self._probe._stopped_endpoints = {
                endpoint for endpoint in self._probe._stopped_endpoints
                if (urlsplit(endpoint).hostname or "").casefold() != host
            }
        return active

    def set_policy(self, policy: ProbePolicy) -> None:
        self._probe.policy = policy

    def get(
        self, url: str, *, allowed_hosts: tuple[str, ...],
        capability: EndpointCapability | str = EndpointCapability.PRODUCT_PAGE,
        deadline: float | None = None,
    ) -> ProbeResult:
        self.host_stopped(url)
        result = self._probe.probe(
            url, allowed_hosts=allowed_hosts, capability=capability,
            sample_type="product_page", deadline=deadline,
        )
        if result.http_status is not None:
            # A genuine round trip happened this call (as opposed to the
            # host already being in _stopped_hosts, which short-circuits
            # probe() with http_status=None and no network I/O) -- only
            # a real outcome is worth persisting.
            _append_log(self.log_path, {
                "url": url, "status_code": result.http_status,
                "final_url": result.final_url, "checked_at": result.checked_at,
                "access_status": result.access_status.value, "protection_status": result.protection_status.value,
                "source_session": self.session_id,
            })
        return result
