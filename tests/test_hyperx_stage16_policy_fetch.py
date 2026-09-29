"""Stage 16: closes the network vulnerability Stage 15 found and fixed
only at the test level -- HyperXAdapter's ordinary fetch path went through
a bare requests.Session(), so the test substitution (urls={}/an injected
fake session) was the ONLY thing standing between an ordinary offline test
and a real outbound request. This file proves the root-cause fix instead:

  * HyperXAdapter's ordinary fetch path now goes through
    adapters/policy_fetch.py's PolicyAwareFetcher (ProbePolicy, host
    allowlist, redirect-chain checks, ...), not a bare Session;
  * a fetch log persisted to disk makes a host-stop survive a fresh
    HyperXAdapter instance/process ("a new run"), not just one instance's
    lifetime;
  * the Stage 15 incident's exact scenario -- worker.run_once() with a
    real KNOWN_URLS entry and no factory override -- is now caught by
    product_tool.census.endpoint_probe.block_all_real_network_io() before
    any socket I/O, proven here explicitly (not merely relying on
    tests/__init__.py's ambient, process-wide activation of the same
    guard, so this test is correct no matter how it is invoked);
  * the productID/sku identity fix (Stage 15) still reports a REAL sku
    conflict as a conflict -- it only stopped a false one.

No new HTTP requests are made anywhere in this file.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from product_tool import jobs, worker
from product_tool.adapters.hyperx import HyperXAdapter, check_identity
from product_tool.adapters.policy_fetch import PolicyAwareFetcher
from product_tool.adapters.structured_page import ExtractedField, ROLE_JSON_LD
from product_tool.census.endpoint_probe import (
    AccessStatus,
    RealNetworkIOBlocked,
    block_all_real_network_io,
)

MICROPHONE_URL = "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone"


class FakeResponse:
    def __init__(self, url: str, text: str = "", status: int = 200, headers=None):
        self.url, self.text, self.status_code = url, text, status
        self.history = ()
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self.text.encode("utf-8"),))


class FakeSession:
    def __init__(self, pages: dict[str, FakeResponse]):
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected call to {url!r}")
        return self.pages[url]


class RefusingSession:
    """Proves zero calls happen -- any .get() at all is itself a failure,
    unlike FakeSession which only fails on an unregistered URL."""
    def get(self, url, **kwargs):
        raise AssertionError(f"a request was made to {url!r} when none should have been attempted")


def _tmp_log_path(case: unittest.TestCase) -> Path:
    tmp = TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    return Path(tmp.name) / "hyperx_fetch_log.json"


def seed_product(database: Path, *, sku: str, name: str = "Тест") -> int:
    jobs.initialize(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO batches (id, filename, sheet_name, mapping_json, confirmed_at) VALUES ('b1','fixture.xlsx','Товары','{}','2026-01-01')"
        )
        cursor = connection.execute(
            "INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) "
            "VALUES ('b1',2,?,?,?, '', 'Микрофоны',0,'[]','{}')",
            (name, "HYPERX", sku),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


class NoOpDnsAdapter:
    source_key = "dns"
    site_name = "DNS"
    document_urls: dict[str, str] = {}

    def find_source(self, search_code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
        from product_tool.adapters.common import SourceDocument
        return SourceDocument("dns", "DNS", "", match_level="unknown", evidence="not checked in this test")

    def find_documents(self, search_code, *, deadline, **kwargs):
        return [], "not checked in this test"


# --------------------------------------------------------------------------
# 1. The Stage 15 incident's exact scenario -- fixed at the root
# --------------------------------------------------------------------------

class Stage15IncidentRegressionTests(unittest.TestCase):
    def test_run_once_with_real_known_url_and_no_factory_override_does_not_make_an_unaccounted_request(self):
        """This is deliberately self-contained (activates the guard itself,
        not relying on tests/__init__.py's ambient process-wide guard) so
        it is correct no matter how this file is invoked.

        worker.run_once() wraps its whole job-processing body in a broad
        except Exception (a pre-existing, general safety net so one bad
        adapter/job never crashes the worker loop -- unrelated to this
        stage, unchanged here), so RealNetworkIOBlocked does not propagate
        out of run_once() itself. What this proves instead: (a) the job
        ends in "error", never "done"/exact_variant, which only a real
        successful response could have produced, and (b) the swallowed
        exception the worker logged really was RealNetworkIOBlocked, not
        some unrelated failure -- i.e. the guard is what stopped it."""
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database = Path(tmp.name) / "batches.sqlite3"
        product = seed_product(database, sku="9A273AA", name="Микрофон для пк игровой QuadCast 2S Black")
        jobs.enqueue(database, product, [1, 3, 4, 6])

        with block_all_real_network_io():
            # No hyperx_adapter_factory override -- exactly worker.py's own
            # default, exactly what Stage 15's incident hit.
            with self.assertLogs("product_tool.worker", level="ERROR") as logs:
                worker.run_once(database, clock=lambda: 0, dns_adapter_factory=lambda: NoOpDnsAdapter())

        self.assertTrue(any("RealNetworkIOBlocked" in message for message in logs.output))
        job = jobs.list_jobs(database, product)[0]
        self.assertEqual(job["status"], "error")

    def test_the_ordinary_test_run_itself_is_already_guarded_no_wrapper_needed(self):
        """Does NOT call block_all_real_network_io() itself, and never
        attempts a real .get() either -- this checks, by introspection
        only, that test_000_network_safety.py's module-level activation
        (which sorts first among test_*.py files and runs at import time,
        before any test anywhere runs) has already replaced requests.
        adapters.HTTPAdapter.send by the time THIS, a different file's
        test, runs -- proving the activation really is process-wide and
        durable across file boundaries, not just true inside its own file.
        (A test that instead made a real .get() call to prove this would
        itself be an unguarded real connection attempt if this file were
        ever run outside -s tests discovery -- introspection avoids that
        risk entirely.)"""
        import requests
        self.assertEqual(requests.adapters.HTTPAdapter.send.__name__, "_blocked_send")

    def test_the_adapters_own_default_construction_is_also_covered(self):
        """Even a bare HyperXAdapter() (no session, no fetch_log_path
        override) -- constructed directly, not through worker.py at all --
        is covered, since the guard blocks at the transport layer, below
        every one of AccessProbe's own callers."""
        with block_all_real_network_io():
            adapter = HyperXAdapter(clock=lambda: 0)
            with self.assertRaises(RealNetworkIOBlocked):
                adapter.find_source("9A273AA", deadline=100)


# --------------------------------------------------------------------------
# 2. Persisted fetch log -- host-stop survives a fresh instance ("a new run")
# --------------------------------------------------------------------------

class PersistedHostStopTests(unittest.TestCase):
    def test_403_then_a_fresh_instance_still_refuses_the_host_and_makes_zero_calls(self):
        log_path = _tmp_log_path(self)
        first_session = FakeSession({MICROPHONE_URL: FakeResponse(MICROPHONE_URL, status=403)})
        first = PolicyAwareFetcher(log_path, session=first_session, clock=lambda: 0)
        result = first.get(MICROPHONE_URL, allowed_hosts=("hyperx.com", "www.hyperx.com"), deadline=100)
        self.assertEqual(result.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertEqual(first_session.calls, [MICROPHONE_URL])
        self.assertTrue(log_path.exists())

        # A brand-new instance -- the ONLY thing carried over is the file
        # at log_path, simulating a fresh process/run, not the same
        # AccessProbe's in-memory _stopped_hosts.
        second_session = RefusingSession()
        second = PolicyAwareFetcher(log_path, session=second_session, clock=lambda: 0)
        second_result = second.get(MICROPHONE_URL, allowed_hosts=("hyperx.com", "www.hyperx.com"), deadline=100)
        self.assertEqual(second_result.access_status, AccessStatus.CAPTCHA_OR_BLOCKED)
        self.assertIsNone(second_result.http_status)  # short-circuited, no real call

    def test_the_full_hyperx_adapter_also_refuses_after_a_new_instance(self):
        log_path = _tmp_log_path(self)
        blocked_session = FakeSession({MICROPHONE_URL: FakeResponse(MICROPHONE_URL, status=403)})
        first_adapter = HyperXAdapter(blocked_session, clock=lambda: 0, urls={"9A273AA": MICROPHONE_URL}, fetch_log_path=log_path)
        first_doc = first_adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(first_doc.match_level, "blocked")

        second_adapter = HyperXAdapter(RefusingSession(), clock=lambda: 0, urls={"9A273AA": MICROPHONE_URL}, fetch_log_path=log_path)
        second_doc = second_adapter.find_source("9A273AA", deadline=100)
        self.assertEqual(second_doc.match_level, "blocked")
        self.assertIn("recorded", second_doc.error.lower())

    def test_a_successful_fetch_is_logged_too_but_does_not_stop_the_host(self):
        log_path = _tmp_log_path(self)
        session = FakeSession({MICROPHONE_URL: FakeResponse(MICROPHONE_URL, "<html>ok</html>", status=200)})
        fetcher = PolicyAwareFetcher(log_path, session=session, clock=lambda: 0)
        fetcher.get(MICROPHONE_URL, allowed_hosts=("hyperx.com", "www.hyperx.com"), deadline=100)
        entries = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["status_code"], 200)

        second_session = FakeSession({MICROPHONE_URL: FakeResponse(MICROPHONE_URL, "<html>ok again</html>", status=200)})
        second = PolicyAwareFetcher(log_path, session=second_session, clock=lambda: 0)
        second_result = second.get(MICROPHONE_URL, allowed_hosts=("hyperx.com", "www.hyperx.com"), deadline=100)
        self.assertEqual(second_result.access_status, AccessStatus.DIRECT_ACCESS)
        self.assertEqual(second_session.calls, [MICROPHONE_URL])  # a 200 never stops the host


# --------------------------------------------------------------------------
# 3. The Stage 15 productID fix does not hide a real conflict
# --------------------------------------------------------------------------

class IdentityFixDoesNotHideRealConflictsTests(unittest.TestCase):
    def test_a_genuinely_different_sku_is_still_a_mismatch_even_with_an_unrelated_productid(self):
        # Shaped like a real Shopify page: sku for a completely different
        # product, plus a productID that (as on every real page sampled)
        # does not equal the sku either way -- the fix must not turn this
        # into "unresolved"/pass just because productID exists.
        fields = [
            ExtractedField("sku", "A1KY6AA", MICROPHONE_URL, "JSON-LD Product.sku", ROLE_JSON_LD, "confirmed"),
            ExtractedField("productID", "9988776655", MICROPHONE_URL, "JSON-LD Product.productID", ROLE_JSON_LD, "confirmed"),
        ]
        result = check_identity(fields, catalog_code="9A273AA")
        self.assertEqual(result.level, "mismatch")

    def test_a_genuine_region_suffix_conflict_is_still_base_code_confirmed_not_exact(self):
        fields = [
            ExtractedField("sku", "7G7A4AA#ABA", MICROPHONE_URL, "JSON-LD Product.sku", ROLE_JSON_LD, "confirmed"),
            ExtractedField("productID", "1122334455", MICROPHONE_URL, "JSON-LD Product.productID", ROLE_JSON_LD, "confirmed"),
        ]
        result = check_identity(fields, catalog_code="7G7A4AA#ACB")
        self.assertEqual(result.level, "base_code_confirmed")
        self.assertNotEqual(result.level, "exact_variant")

    def test_multiple_disagreeing_sku_values_are_still_unresolved(self):
        # Two JSON-LD blocks disagreeing on sku itself (not sku vs
        # productID) must still be treated as unresolved -- the fix only
        # changed which FIELD is the anchor, not this safety property.
        fields = [
            ExtractedField("sku", "9A273AA", MICROPHONE_URL, "JSON-LD block 1", ROLE_JSON_LD, "confirmed"),
            ExtractedField("sku", "A1KY6AA", MICROPHONE_URL, "JSON-LD block 2", ROLE_JSON_LD, "confirmed"),
        ]
        result = check_identity(fields, catalog_code="9A273AA")
        self.assertEqual(result.level, "mismatch")
        self.assertEqual(result.page_base, "")


if __name__ == "__main__":
    unittest.main()
