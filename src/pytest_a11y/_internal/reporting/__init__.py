"""Report generation functionality for pytest-a11y.

This module handles creating HTML and JSON reports of accessibility
test results.
"""

from pytest_a11y._internal.reporting.report_generator import A11yViolationsReport

__all__: list[str] = ["A11yViolationsReport"]
