"""
Selenium-bound wrapper for running axe-core accessibility checks.

Provides a clean interface to the axe-selenium-python library with proper
typing and result processing.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from axe_selenium_python import Axe  # type: ignore[import-untyped]
from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y.assertions import _generate_reports
from pytest_a11y.types import AxeResults, Results


@dataclass(frozen=True)
class PageReadiness:
    """Result of a best-effort check for whether a page can be analyzed."""

    ok: bool
    reason: str


class AxeRunner:
    """
    Wrapper for axe-core accessibility checker bound to a Selenium WebDriver.

    Manages axe-core injection and execution, providing typed result handling
    and convenience methods for processing violations.

    Attributes:
        _axe: Internal Axe instance from axe-selenium-python
        _driver: Selenium WebDriver instance
        _request: Optional pytest FixtureRequest forwarded from the fixture
    """

    def __init__(
        self,
        driver: WebDriver,
        request: pytest.FixtureRequest | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Initialize AxeRunner with a WebDriver instance and optional pytest
        `request` and accessibility standard tags.

        When provided the `request` will be forwarded to report generation so
        `axe.run()` can produce session-scoped reports when `--a11y` is enabled.

        Args:
            driver: Selenium WebDriver bound to the current browser context
            request: Optional pytest FixtureRequest forwarded from the fixture
            tags: Optional axe tag list such as ["wcag21a", "wcag21aa"]
        """
        self._driver = driver
        self._axe = Axe(driver)
        self._request = request
        self.tags = tags

    def inject(self) -> None:
        """
        Inject axe-core library into the current page.

        Must be called before run() to ensure axe-core is available.
        Safe to call multiple times (idempotent).

        Raises:
            Exception: If injection fails (e.g., page context lost)
        """
        self._axe.inject()

    def check_page_analyzable(self) -> PageReadiness:
        """
        Best-effort check to determine if the current page can be analyzed.

        Checks for common conditions that would prevent axe from running:
        - Browser error pages (chrome-error://)
        - Blank pages (about:blank)
        - Document not ready (readyState != complete)
        - Missing DOM (documentElement missing)
        - JavaScript execution failures

        This does not guarantee a page is correct, only that it's likely
        safe to run DOM-based analysis.

        Returns:
            PageReadiness with ok=True if page is analyzable,
            or ok=False with a reason string if not
        """
        url = (self._driver.current_url or "").strip()

        if url.startswith("chrome-error://"):
            return PageReadiness(False, f"Browser error page detected: {url}")
        if url == "" or url.startswith("about:blank"):
            return PageReadiness(False, f"Blank page detected: {url or 'about:blank'}")

        try:
            ready_state = self._driver.execute_script("return document.readyState")
            if ready_state != "complete":
                return PageReadiness(
                    False, f"Document not ready (readyState={ready_state!r})"
                )

            has_dom = self._driver.execute_script(
                "return !!document && !!document.documentElement"
            )
            if not bool(has_dom):
                return PageReadiness(
                    False, "DOM not available (documentElement missing)"
                )
        except Exception as exc:  # Selenium can throw if context is invalid
            return PageReadiness(
                False, f"JavaScript execution failed: {exc.__class__.__name__}"
            )

        return PageReadiness(True, "OK")

    def run(self) -> AxeResults:
        """
        Run axe-core accessibility checks against the current page.

        Automatically injects axe-core before running to handle full page
        navigations and context changes. Safe to call multiple times on
        different pages without manual injection.

        Returns:
            Complete AxeResults with violations, passes, incomplete, inapplicable

        Raises:
            Exception: If page context is lost or axe.run() fails

        Notes:
            - Injection happens before every run for robustness
            - Results include all check types (violations, passes, etc.)
            - Results are typed as AxeResults TypedDict
        """
        self._axe.inject()

        if self.tags:
            options = {
                "runOnly": {
                    "type": "tag",
                    "values": self.tags,
                }
            }
            axe_results = self._axe.run(options=options)
        else:
            axe_results = self._axe.run()

        # Forward the pytest request (if any) so report generation can use
        # `request.config` / `request.node` instead of relying on global state.
        _generate_reports(
            axe_results, self._driver, request=getattr(self, "_request", None)
        )

        return axe_results  # type: ignore[no-any-return]

    def violation_count(self, results: AxeResults) -> int:
        """
        Count the number of violations in axe results.

        Args:
            results: AxeResults from a run() call

        Returns:
            Total number of violations found
        """
        return len(results.get("violations", []))

    def pass_count(self, results: AxeResults) -> int:
        """
        Count the number of passed checks in axe results.

        Args:
            results: AxeResults from a run() call

        Returns:
            Total number of passed checks
        """
        return len(results.get("passes", []))

    def incomplete_count(self, results: AxeResults) -> int:
        """
        Count the number of incomplete checks in axe results.

        Incomplete checks need manual review to determine if they're violations.

        Args:
            results: AxeResults from a run() call

        Returns:
            Total number of incomplete checks
        """
        return len(results.get("incomplete", []))

    def has_violations(self, results: AxeResults) -> bool:
        """
        Check if results contain any violations.

        Convenience method for conditional checks.

        Args:
            results: AxeResults from a run() call

        Returns:
            True if any violations found, False otherwise
        """
        return self.violation_count(results) > 0

    def process_results(self, results: AxeResults) -> Results:
        """
        Convert raw axe-core results to structured Results.

        Normalizes and validates all result data, making it easier to work with
        in reports and assertions. All violations and test results are converted
        to their structured dataclass equivalents.

        Args:
            results: Raw AxeResults from run()

        Returns:
            Results with structured, typed data ready for processing

        Example:
            >>> axe_results = axe.run()
            >>> processed = axe.process_results(axe_results)
            >>> print(f"Found {processed.violation_count} violations")
            >>> for violation in processed.violations:
            ...     print(f"  - {violation.summary}")

        See Also:
            Results.from_axe() for the conversion implementation
        """
        return Results.from_axe(results)
