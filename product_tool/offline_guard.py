"""Process-level "no real network" guard shared by the test bootstrap and the
offline coverage tools.

Two layers, both raising `RealNetworkIOBlocked` before any I/O happens:
  * `requests.adapters.HTTPAdapter.send` (via endpoint_probe's existing guard);
  * `socket.getaddrinfo` / `socket.socket.connect(_ex)` for any non-loopback
    peer, so urllib, http.client, httpx and raw DNS lookups are covered too.

Loopback stays open (local fixtures, asyncio's self-pipe).
"""
from __future__ import annotations

import ipaddress
import socket
from contextlib import contextmanager
from typing import Iterator

from .census.endpoint_probe import RealNetworkIOBlocked, block_all_real_network_io


def is_loopback_host(host) -> bool:
    if host in (None, "", "localhost"):
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


_ORIGINALS: dict[str, object] = {}


def install_socket_guard() -> None:
    """Patch the socket module for the rest of the process (idempotent)."""
    if _ORIGINALS:
        return
    real_getaddrinfo = _ORIGINALS["getaddrinfo"] = socket.getaddrinfo
    real_connect = _ORIGINALS["connect"] = socket.socket.connect
    real_connect_ex = _ORIGINALS["connect_ex"] = socket.socket.connect_ex

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not is_loopback_host(host):
            raise RealNetworkIOBlocked(f"DNS lookup of {host!r} attempted while the offline guard is active")
        return real_getaddrinfo(host, *args, **kwargs)

    def _check(address):
        if isinstance(address, tuple) and address and not is_loopback_host(address[0]):
            raise RealNetworkIOBlocked(f"socket connect to {address[0]!r} attempted while the offline guard is active")

    def guarded_connect(self, address):
        _check(address)
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        _check(address)
        return real_connect_ex(self, address)

    guarded_getaddrinfo._offline_guard = True
    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex


def uninstall_socket_guard() -> None:
    """Undo install_socket_guard (scoped CLI use and tests of the guard itself)."""
    if not _ORIGINALS:
        return
    socket.getaddrinfo = _ORIGINALS.pop("getaddrinfo")
    socket.socket.connect = _ORIGINALS.pop("connect")
    socket.socket.connect_ex = _ORIGINALS.pop("connect_ex")


def guard_state() -> dict[str, bool]:
    import requests

    return {
        "http_blocked": requests.adapters.HTTPAdapter.send.__name__ == "_blocked_send",
        "dns_blocked": bool(getattr(socket.getaddrinfo, "_offline_guard", False)),
    }


@contextmanager
def offline_only() -> Iterator[None]:
    """Scoped guard for CLIs: real HTTP, DNS and non-loopback connects raise
    for the duration of the block, and the previous state is restored."""
    already_sockets = guard_state()["dns_blocked"]
    with block_all_real_network_io():
        install_socket_guard()
        try:
            yield
        finally:
            if not already_sockets:
                uninstall_socket_guard()
