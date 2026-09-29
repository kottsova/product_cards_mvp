"""Importing the `tests` package activates the offline guard before any test
module is loaded (`unittest discover -s tests -t .`, `unittest tests.test_x`,
`python -m tests`). See tests/_bootstrap.py for the full command matrix."""
from . import _bootstrap

_bootstrap.activate("package")
