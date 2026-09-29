"""Expiring, auditable host stops shared by policy HTTP and browser paths.

Historical fetch-log entries stay immutable.  A stop is effective only while
its reason-specific cooldown is active; an attended success resolves only
challenge stops.  Manual and fatal stops require an explicit operator action.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


CHALLENGE = "challenge"
RATE_LIMIT = "rate_limit"
HTTP_DENIED = "http_access_denied"
MANUAL = "manual"
FATAL = "fatal"
TIMED_TTL = {
    CHALLENGE: timedelta(minutes=30),
    RATE_LIMIT: timedelta(hours=1),
    HTTP_DENIED: timedelta(hours=6),
}
CONFIRMED_CHALLENGE = frozenset({"challenge_confirmed", "browser_verification_required"})


def _utc(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed)


def _domains(entry: Mapping[str, Any]) -> tuple[str, ...]:
    domains = [str(entry.get("domain") or "").casefold()]
    for key in ("url", "final_url"):
        domains.append((urlsplit(str(entry.get(key) or "")).hostname or "").casefold())
    return tuple(dict.fromkeys(host for host in domains if host))


def stop_reason(entry: Mapping[str, Any]) -> str:
    explicit = str(entry.get("reason") or "")
    if explicit in {CHALLENGE, RATE_LIMIT, HTTP_DENIED, MANUAL, FATAL}:
        return explicit
    if entry.get("protection_status") in CONFIRMED_CHALLENGE:
        return CHALLENGE
    status = entry.get("status_code")
    if status == 429:
        return RATE_LIMIT
    if status in {401, 403}:
        return HTTP_DENIED
    return ""


def stop_event(domain: str, reason: str, *, at: datetime | None = None,
               source_session: str = "", scope: str = "domain") -> dict[str, Any]:
    """Create an explicit stop record; never hide or delete earlier records."""
    domain = (urlsplit(domain).hostname or domain).casefold().strip()
    if not domain or reason not in {CHALLENGE, RATE_LIMIT, HTTP_DENIED, MANUAL, FATAL}:
        raise ValueError("A domain and recognized stop reason are required")
    created = _utc(at) or datetime.now(timezone.utc)
    ttl = TIMED_TTL.get(reason)
    return {"event": "stop", "domain": domain, "reason": reason,
            "created_at": created.isoformat(), "last_attempt_at": created.isoformat(),
            "scope": scope, "expires_at": (created + ttl).isoformat() if ttl else None,
            "source_session": source_session}


def response_stop_fields(entry: Mapping[str, Any], *, source_session: str = "") -> dict[str, Any]:
    """Add lifecycle fields to a blocking response without losing response evidence."""
    reason = stop_reason(entry)
    if not reason:
        return {}
    at = _utc(entry.get("checked_at")) or datetime.now(timezone.utc)
    domain = _domains(entry)[0]
    event = stop_event(domain, reason, at=at, source_session=source_session)
    return {key: value for key, value in event.items() if key != "event"}


def attended_success_event(domain: str, *, at: datetime | None = None,
                           source_session: str = "") -> dict[str, Any]:
    domain = (urlsplit(domain).hostname or domain).casefold().strip()
    if not domain:
        raise ValueError("A domain is required")
    created = _utc(at) or datetime.now(timezone.utc)
    return {"event": "stop_resolved", "domain": domain, "reason": CHALLENGE,
            "created_at": created.isoformat(), "last_attempt_at": created.isoformat(),
            "scope": "domain", "expires_at": None,
            "source_session": source_session}


def active_stops(entries: Iterable[Mapping[str, Any]], *, now: datetime | None = None) -> dict[str, tuple[dict, ...]]:
    """Replay history in order, then return only unexpired stops per host."""
    current = _utc(now) or datetime.now(timezone.utc)
    state: dict[tuple[str, str], dict] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        reason = stop_reason(entry)
        if not reason:
            continue
        for domain in _domains(entry):
            key = (domain, reason)
            if entry.get("event") == "stop_resolved":
                # A successful attended session may resolve a challenge;
                # it cannot clear a rate limit, manual stop, or fatal stop.
                if reason == CHALLENGE:
                    state.pop(key, None)
                continue
            state[key] = dict(entry)
    active: dict[str, list[dict]] = {}
    for (domain, reason), entry in state.items():
        expiry = _utc(entry.get("expires_at"))
        if expiry is None and reason in TIMED_TTL:
            created = _utc(entry.get("created_at") or entry.get("checked_at"))
            if created is not None:
                expiry = created + TIMED_TTL[reason]
            elif reason == CHALLENGE:
                # An undated legacy challenge is audit history, not an
                # everlasting prohibition on future browser sessions.
                continue
            # Undated legacy HTTP block/rate-limit remains conservative.
        if expiry is not None and expiry <= current:
            continue
        record = dict(entry)
        record.setdefault("reason", reason)
        record.setdefault("domain", domain)
        record.setdefault("scope", "domain")
        record.setdefault("created_at", entry.get("checked_at"))
        record.setdefault("last_attempt_at", entry.get("checked_at"))
        record["expires_at"] = expiry.isoformat() if expiry else None
        active.setdefault(domain, []).append(record)
    return {domain: tuple(items) for domain, items in active.items()}


def stopped_hosts(entries: Iterable[Mapping[str, Any]], *, now: datetime | None = None) -> frozenset[str]:
    return frozenset(active_stops(entries, now=now))
