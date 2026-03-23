from __future__ import annotations

import importlib

import pytest_a11y.conftest as conftest_module


def test_conftest_module_importable_and_reloadable() -> None:
    """Ensure the package-level conftest imports fixtures without errors.

    The module exists solely to expose fixtures (via import) to pytest's
    discovery machinery. Reloading it also runs the import and improves
    coverage.
    """

    reloaded = importlib.reload(conftest_module)

    assert reloaded is conftest_module
