"""
pytest-a11y: Automated accessibility testing with axe-core.

A pytest plugin providing automated accessibility checks using axe-core,
with features for HTML/JSON reports, violation screenshots, and baseline comparisons.

Quick Start:
    In your test file:

        from selenium.webdriver.remote.webdriver import WebDriver
        from pytest_a11y import assert_no_axe_violations
        from pytest_a11y.types import AxeRunnerProtocol

        def test_homepage_accessible(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
            driver.get("https://www.saucedemo.com/")
            results = axe.run()
            assert_no_axe_violations(results)

    Run without reports:
        pytest tests/

    Run with reports:
        pytest tests/ --a11y

Key Features:
    - 🎯 Automated axe-core accessibility scans in pytest
    - 📊 HTML and JSON report generation (when --a11y enabled)
    - 📸 Visual violation highlighting in screenshots
    - 📋 Baseline comparison for regression testing
    - 🧵 xdist-safe for parallel test execution
    - 🔌 Works with any Selenium WebDriver-based test suite

Core API:
    - assert_no_axe_violations(): Assert no violations found
    - assert_no_critical_violations(): Assert no critical violations found
    - assert_results_no_violations(): Assert no violations in processed Results
    - assert_results_no_critical(): Assert no critical violations in processed Results

For more information, visit: https://github.com/m-farial/pytest-a11y

Module Organization:
    This package exports only the public API. Implementation details
    (modules starting with _ or in _internal/) are private and subject
    to change without notice.
"""

from __future__ import annotations

# ============================================================================
# Public Assertion Exports
# ============================================================================
from pytest_a11y.assertions import (
    assert_no_axe_violations,
    assert_no_critical_violations,
    assert_results_no_critical,
    assert_results_no_violations,
)

# ============================================================================
# Public Fixture Exports (via axe subpackage)
# ============================================================================
# Users access this via:
#   def test_example(axe: AxeRunnerProtocol):  # <-- pytest fixture
#       results = axe.run()
from pytest_a11y.axe.fixtures import axe

# ============================================================================
# Public Baseline Exports
# ============================================================================
from pytest_a11y.baselines import BaselineManager

# ============================================================================
# Public Type Exports
# ============================================================================
from pytest_a11y.types import (
    AxeNode,
    AxeResults,
    AxeRunnerProtocol,
    AxeViolationRaw,
    Node,
    Results,
    Severity,
    Violation,
    WCAGLevel,
    WCAGReference,
)

__all__ = [
    # Type definitions (TypedDicts, Literals, dataclasses)
    "AxeNode",
    "AxeResults",
    "AxeRunnerProtocol",
    "AxeViolationRaw",
    # Baseline management
    "BaselineManager",
    "Node",
    "Results",
    "Severity",
    "Violation",
    "WCAGLevel",
    "WCAGReference",
    # Assertion helpers
    "assert_no_axe_violations",
    "assert_no_critical_violations",
    "assert_results_no_critical",
    "assert_results_no_violations",
    # Fixtures (available via pytest automatically)
    "axe",
]

__version__ = "1.0.0"
__author__ = "Farial Mahbub"
__license__ = "MIT"
__homepage__ = "https://github.com/m-farial/pytest-a11y"


# ============================================================================
# Error Messages for Common Mistakes
# ============================================================================


def __getattr__(name: str) -> object:
    """
    Provide helpful error messages for common mistakes and typos.

    This catches cases where users try to import things that don't exist
    or are named differently, and suggests the correct usage.
    """
    # Help with fixture name mistakes
    if name in ("axe_runner", "runner", "accessibility_runner"):
        raise AttributeError(
            f"Fixture '{name}' not found. Did you mean 'a11y'?\n"
            "\n"
            "Example:\n"
            "    def test_page(driver: WebDriver, a11y: AxeRunnerProtocol) -> None:\n"
            "        results = a11y.run()\n"
            "        assert_no_axe_violations(results)\n"
        )

    # Help with assertion function typos
    if name in (
        "assert_violations",
        "assert_a11y",
        "assert_accessibility",
        "assert_no_violations",
    ):
        raise AttributeError(
            f"Function '{name}' not found. Did you mean one of these?\n"
            "\n"
            "Available assertions:\n"
            "  • assert_no_axe_violations(results)\n"
            "  • assert_no_critical_violations(results)\n"
            "  • assert_results_no_violations(results)\n"
            "  • assert_results_no_critical(results)\n"
            "\n"
            "Example:\n"
            "    results = axe.run()\n"
            "    assert_no_axe_violations(results)\n"
        )

    # Help with types
    if name in ("A11YRunResults", "CheckA11yResults", "ReportResults"):
        raise AttributeError(
            f"Type '{name}' is not available.\n"
            "\n"
            "You don't need it! Use these types instead:\n"
            "\n"
            "  • AxeResults: Raw axe-core results\n"
            "    from pytest_a11y.types import AxeResults\n"
            "    results: AxeResults = axe.run()\n"
            "\n"
            "  • Results: Processed, structured results\n"
            "    from pytest_a11y.types import Results\n"
            "    processed = Results.from_axe(axe_results)\n"
        )

    # Generic fallback
    raise AttributeError(
        f"module '{__name__}' has no attribute '{name}'\n"
        "\n"
        "Available exports:\n"
        f"  {', '.join(sorted(__all__))}\n"
    )


def __dir__() -> list[str]:
    """Return all public exports."""
    return sorted(__all__)
