"""
Baseline comparison and regression testing for accessibility.

This module provides tools for managing baseline artifacts and comparing
current test results against stored baselines. This is useful for detecting
regressions in accessibility during development.

Baseline Comparison Strategies:

1. **Hash-based comparison (default):**
   - Exact match required
   - Fast and deterministic
   - Best for controlled environments
   - Good for HTML and JSON reports

2. **Tolerance-based comparison:**
   - Allows minor pixel variations in images
   - Useful for anti-aliasing and rendering differences
   - Configurable tolerance threshold
   - Good for screenshot comparisons

Main Class:
    BaselineManager: Manage and compare baseline artifacts

Typical Usage:

    from pytest_a11y import BaselineManager

    def test_homepage_baseline(axe):
        results = axe.run()

        mgr = BaselineManager("tests/a11y_baselines")
        mgr.store_baseline("homepage", results)  # First run
        mgr.compare_to_baseline("homepage", results)  # Later runs

    # With tolerance for images
    def test_with_tolerance(axe):
        mgr = BaselineManager("baselines", image_tolerance=5)
        results = axe.run()
        mgr.compare_to_baseline("mypage", results)

Workflow:

    1. First test run: Store baseline
       $ pytest --baseline-store
       → Saves baseline_hashes.json and artifacts

    2. Subsequent runs: Compare against baseline
       $ pytest
       → Compares current results to stored baseline
       → Fails if mismatch (regression detected)

See Also:
    BaselineManager: Full API for baseline operations
    pytest_a11y.types.Results: Results objects being compared
    pytest_a11y.assertions: Assertion helpers
"""

from pytest_a11y._internal.comparison.baseline_manager import BaselineManager

__all__ = ["BaselineManager"]
