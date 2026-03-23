from __future__ import annotations

import builtins
import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestAxeFixture:
    """Tests for the axe pytest fixture."""

    def test_axe_returns_runner_bound_to_driver_and_request(
        self,
        mock_driver: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """Return an AxeRunner created with the active driver and pytest request."""
        # Import and resolve the fixture at runtime so coverage measures the
        # fixture module import and fixture body execution.
        import pytest_a11y.conftest  # noqa: F401 - ensure conftest fixture discovery code runs under coverage

        fixtures_module = importlib.reload(
            importlib.import_module("pytest_a11y.axe.fixtures")
        )
        axe = fixtures_module.axe

        expected_runner = MagicMock()
        with patch.object(fixtures_module, "AxeRunner") as mock_axe_runner:
            mock_axe_runner.return_value = expected_runner

            result = axe.__wrapped__(mock_driver, mock_request)

            assert result is expected_runner
            mock_axe_runner.assert_called_once_with(mock_driver, request=mock_request)

    def test_axe_package_import_branch_covered_by_import_error(self) -> None:
        """Cover the import error branch in pytest_a11y.axe package."""
        original_import = builtins.__import__

        def failing_import(
            name: str, _globals=None, _locals=None, fromlist=(), level=0
        ):
            if name == "pytest_a11y.axe.fixtures":
                raise ImportError("simulated failure")
            return original_import(name, _globals, _locals, fromlist, level)

        importlib.reload(importlib.import_module("pytest_a11y.axe"))

        try:
            builtins.__import__ = failing_import  # type: ignore[assignment]
            with pytest.raises(ImportError):
                importlib.reload(importlib.import_module("pytest_a11y.axe"))
        finally:
            builtins.__import__ = original_import
