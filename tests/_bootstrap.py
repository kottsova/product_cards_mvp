"""Test-process bootstrap: repo root on sys.path and real network I/O blocked.

`activate()` is idempotent and is called by, in order of strength:

  1. `python -m tests [args]`  (tests/__main__.py) -- before discovery starts.
  2. any run that imports the `tests` package: `python -m unittest discover
     -s tests -t .`, `python -m unittest tests.test_x` (tests/__init__.py).
  3. `test_000_network_safety.py` -- a fallback for the legacy command
     `python -m unittest discover -s tests`, which never imports the package;
     it only holds if that file is imported first (alphabetical order).

Only 1 and 2 are guarantees independent of import order. See
docs/COVERAGE_QUEUE_V17.md ("Test network guard") for the command matrix.

Two layers are blocked, so a forgotten fake session fails loudly and early:
  * `requests.adapters.HTTPAdapter.send` (see endpoint_probe);
  * `socket.getaddrinfo` / `socket.socket.connect(_ex)` for any non-loopback
    peer, which also covers urllib, http.client, httpx and raw DNS lookups.
Loopback stays open for local fixtures and asyncio's own self-pipe.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent

_STATE = {"activated_by": None}


def activate(source: str) -> str:
    """Enable the guard once per process; later calls only report who won."""
    for path in (str(ROOT), str(TESTS_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)
    if _STATE["activated_by"] is not None:
        return _STATE["activated_by"]
    marker = sys.modules.get("_stage17_network_guard")
    if marker is not None:  # activated through another import path of this file
        _STATE["activated_by"] = marker.activated_by
        return _STATE["activated_by"]
    from product_tool.census.endpoint_probe import block_all_real_network_io
    from product_tool.offline_guard import install_socket_guard

    guard = block_all_real_network_io()
    guard.__enter__()  # deliberately never exited: a test process is short-lived
    _STATE["http_guard"] = guard  # keep the generator alive, or GC would run its `finally`
    install_socket_guard()
    module = types.ModuleType("_stage17_network_guard")
    module.activated_by = source
    sys.modules["_stage17_network_guard"] = module
    _STATE["activated_by"] = source
    return source


def guard_status() -> dict:
    from product_tool.offline_guard import guard_state

    return {"activated_by": _STATE["activated_by"], **guard_state()}
