"""
Axe-core runner fixtures and utilities.

This subpackage provides pytest fixtures for running axe-core accessibility
checks within your tests.

Main Fixture:
    axe: Provides an AxeRunner instance bound to the current WebDriver.

Usage:
    def test_page_accessibility(axe):
        # axe is automatically provided by pytest
        results = axe.run()
        from pytest_a11y import assert_no_axe_violations
        assert_no_axe_violations(results)

See Also:
    - pytest_a11y.types.AxeRunnerProtocol: Interface for the axe fixture
    - pytest_a11y.assertions: Helper functions for validating results
"""

from pytest_a11y.axe.fixtures import axe

from ._runner import AxeRunner

__all__ = ["axe", "AxeRunner"]
