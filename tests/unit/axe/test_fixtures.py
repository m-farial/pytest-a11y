from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y.axe import fixtures
from pytest_a11y.axe.fixtures import axe


class TestAxeFixture:
    """Tests for the axe pytest fixture."""

    @patch.object(fixtures, "AxeRunner")
    def test_axe_returns_runner_bound_to_driver_and_request(
        self,
        mock_axe_runner: MagicMock,
    ) -> None:
        """Return an AxeRunner created with the active driver and pytest request."""
        driver = MagicMock(spec=WebDriver)
        request = MagicMock(spec=pytest.FixtureRequest)
        expected_runner = MagicMock()
        mock_axe_runner.return_value = expected_runner

        result = axe.__wrapped__(driver, request)

        assert result is expected_runner
        mock_axe_runner.assert_called_once_with(driver, request=request)
