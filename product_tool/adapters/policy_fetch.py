"""Stage 16: the shared policy-aware fetch client production adapters use
for their ordinary (non-test) fetch path.

Stage 15 found that HyperXAdapter's default fetch path was a bare
`requests.Session().get(url, timeout=...)` -- no ProbePolicy, no allowlist
enforcement beyond one manual host check, no redirect-chain check beyond
one manual pass, no persisted memory of a prior block, and (critically) no
protection against an accidental real call in an offline test that forgot
to inject a fake session. This module closes that at the root: it wraps
product_tool.census.endpoint_probe.AccessProbe (the same policy-aware
client the project's own research scripts use -- ProbePolicy, host
allowlist, redirect-chain host checks, 403/429/challenge detection,
in-process host-stop) with a small JSON-file-backed fetch log, so a host
stop survives a fresh process/adapter instance ("a new run"), not just one
instance's lifetime -- exactly the guarantee AccessProbe's own
initial_stopped_hosts/blocked_hosts_from_fetch_log() already gives research
code, now available to a production adapter's ordinary fetch path too.

The log is intentionally a plain JSON file, not a database table: a host
stop is adapter-wide, global state, not scoped to one product/job row, and
this keeps the mechanism usable by a future adapter without threading a
database handle and product_id through code that has neither.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit

from ..census.endpoint_probe import (
    AccessProbe,
    EndpointCapability,
    ProbePolicy,
    ProbeResult,
    blocked_hosts_from_fetch_log,
)


# A page that answered HTTP 200 but IS a challenge (not merely resembling one) stops the host exactly like a 403/429.
# `challenge_suspected` is a heuristic hit that ordinary pages trigger too (every hyperx.com product page does): it is
# logged for the record and never stops anything.
CONFIRMED_CHALLENGE = frozenset({"challenge_confirmed", "browser_verification_required"})


def stopped_hosts_from_fetch_log(entries: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    """Hosts a new fetcher must treat as stopped: everything blocked_hosts_from_fetch_log() returns (401/403/429)
    plus every host whose logged response was a confirmed challenge, whatever its HTTP status."""
    entries = [entry for entry in entries if isinstance(entry, Mapping)]
    hosts = set(blocked_hosts_from_fetch_log(entries))
    for entry in entries:
        if entry.get("protection_status") in CONFIRMED_CHALLENGE:
            for key in ("url", "final_url"):
                host = (urlsplit(str(entry.get(key, ""))).hostname or "").casefold()
                if host:
                    hosts.add(host)
    return frozenset(hosts)


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


class PolicyAwareFetcher:
    """One instance per adapter construction. The on-disk log at `log_path`
    -- not this instance's own in-memory AccessProbe state -- is what makes
    a host-stop survive a fresh instance/process ("a new run"): __init__
    reads it and seeds a fresh AccessProbe with every host that log has
    ever recorded a 401/403/429 for, then every real fetch through .get()
    appends its outcome back to the same file."""

    def __init__(
        self, log_path: Path, *, session=None,
        policy: ProbePolicy | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.log_path = log_path
        stopped = stopped_hosts_from_fetch_log(_read_log(log_path))
        probe_kwargs: dict = {"policy": policy, "initial_stopped_hosts": stopped}
        if clock is not None:
            probe_kwargs["clock"] = clock
        self._probe = AccessProbe(session, **probe_kwargs)

    def host_stopped(self, url: str) -> bool:
        """True when a request to this url's host would be refused without I/O (persisted or in-process stop)."""
        return (urlsplit(url).hostname or "").casefold() in self._probe._stopped_hosts

    def set_policy(self, policy: ProbePolicy) -> None:
        self._probe.policy = policy

    def get(
        self, url: str, *, allowed_hosts: tuple[str, ...],
        capability: EndpointCapability | str = EndpointCapability.PRODUCT_PAGE,
        deadline: float | None = None,
    ) -> ProbeResult:
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
            })
        return result
