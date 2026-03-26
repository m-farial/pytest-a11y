"""
Pytest fixtures for accessibility testing.

Provides fixture for axe-core runner with Selenium WebDriver integration.
Report generation is now integrated into assertion functions.
"""

from __future__ import annotations

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y.types import AxeRunnerProtocol

from ._runner import AxeRunner


@pytest.fixture
def axe(driver: WebDriver, request: pytest.FixtureRequest) -> AxeRunnerProtocol:
    """
    Provide a ready-to-run axe-core runner bound to the current WebDriver.

    The fixture forwards the active `request` to the `AxeRunner` so that
    calling `axe.run()` will generate reports when `--a11y` is enabled.

    Example usage (reports generated when --a11y provided):
        def test_homepage_a11y(driver, axe):
            driver.get("https://example.com")
            results = axe.run()  # will write reports if --a11y
    """
    tags = getattr(request.config, "a11y_tags", None)

    return AxeRunner(driver, request=request, tags=tags)
