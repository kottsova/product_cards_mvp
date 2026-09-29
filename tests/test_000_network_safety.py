"""Offline guard for the test process (Stage 16, made import-order independent
in Stage 17).

The guard lives in tests/_bootstrap.py and is switched on by the `tests`
package import (`python -m tests`, `unittest discover -s tests -t .`,
`unittest tests.test_x`) BEFORE any test module loads. This file is only the
fallback for the legacy command `unittest discover -s tests`, which never
imports the package: there the guard holds only if this file is imported
first (its name sorts before every other test_*.py). The matrix of commands
and what each one guarantees is in docs/COVERAGE_QUEUE_V17.md.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from _bootstrap import ROOT, activate, guard_status

activate("module-order-fallback")


class NetworkSafetyActivationTests(unittest.TestCase):
    def test_the_guard_is_active_for_this_process(self):
        status = guard_status()
        self.assertTrue(status["http_blocked"], status)
        self.assertTrue(status["dns_blocked"], status)
        self.assertIn(status["activated_by"], {"package", "runner", "module-order-fallback"})

    def test_dns_lookup_of_a_public_name_fails_before_any_lookup(self):
        from product_tool.census.endpoint_probe import RealNetworkIOBlocked
        import socket

        with self.assertRaises(RealNetworkIOBlocked):
            socket.getaddrinfo("example.invalid", 443)

    def test_loopback_stays_available_for_local_fixtures(self):
        import socket

        self.assertTrue(socket.getaddrinfo("127.0.0.1", 80))


class OrderIndependenceTests(unittest.TestCase):
    """The package route must not depend on which test module loads first."""

    def _run(self, code: str) -> str:
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        return proc.stdout.strip().splitlines()[-1]

    def test_importing_a_late_sorting_module_first_still_finds_the_guard_on(self):
        out = self._run(
            "import tests.test_structural_census_v9_1 as late\n"
            "from tests import _bootstrap\n"
            "print(_bootstrap.guard_status())"
        )
        self.assertIn("'activated_by': 'package'", out)
        self.assertIn("'http_blocked': True", out)
        self.assertIn("'dns_blocked': True", out)

    def test_the_module_runner_activates_before_discovery(self):
        out = self._run(
            "import sys; sys.argv=['tests']\n"
            "import tests.__main__ as m\n"
            "from tests import _bootstrap\n"
            "print(_bootstrap.guard_status()['http_blocked'])"
        )
        self.assertEqual(out, "True")

    def test_without_the_package_only_the_fallback_protects(self):
        # legacy command shape: tests/ is start dir and top level, package not imported
        out = self._run(
            "import sys; sys.path.insert(0, 'tests'); sys.path.insert(0, '.')\n"
            "import _bootstrap\n"
            "print('tests' in sys.modules, _bootstrap.guard_status()['activated_by'])"
        )
        self.assertEqual(out, "False None")


if __name__ == "__main__":
    unittest.main()
