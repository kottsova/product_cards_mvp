"""`python -m tests [-v|-q] [pattern]` -- the recommended offline test command.

Activates the network guard first, then discovers with the repo root as the
top-level directory so every module is imported after the guard is on."""
import sys
import unittest

from . import _bootstrap

_bootstrap.activate("runner")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a.startswith("-")]
    patterns = [a for a in sys.argv[1:] if not a.startswith("-")]
    argv = ["unittest", "discover", "-s", "tests", "-t", "."] + args
    if patterns:
        argv += ["-p", patterns[0]]
    unittest.main(module=None, argv=argv)
