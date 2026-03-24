"""
Report generation tests for pytest-a11y.

Tests that the core reporting functionality works:
- HTML reports are generated correctly
- JSON reports are generated correctly
- Reports have valid content
"""

import pytest


@pytest.mark.regression
@pytest.mark.parametrize("page_key", ["clean", "bad"])
def test_reporting_artifacts(
    run_a11y,
    axe,
    baseline_artifacts,
    cleanup_violation_screenshots_before_test,
    request: pytest.FixtureRequest,
    page_key: str,
) -> None:
    """
    Verify reporting artifacts match baselines for each test page.

    Parameterized to test all page variants:
    - bad: Multiple violation types
    - clean: No violations

    Creates/updates baselines with: pytest --create-baselines or --update-baselines
    Compares against baselines with: pytest (default)
    """
    artifacts = run_a11y(page_key)

    # Ensure reports were actually generated (prevent false-positive baseline pass)
    assert artifacts.html_report.exists(), "HTML report was not generated"
    assert artifacts.html_report.stat().st_size > 0, "HTML report is empty"
    assert artifacts.json_report.exists(), "JSON report was not generated"
    assert artifacts.json_report.stat().st_size > 0, "JSON report is empty"

    # Ensure reports were written into the pytest-configured session directory
    assert artifacts.html_report.parent == request.config.a11y_session_dir, (
        "Reports were not written into `request.config.a11y_session_dir`"
    )

    test_artifacts = {
        "report.html": artifacts.html_report,
        "report.json": artifacts.json_report,
    }

    # Include any violation screenshots
    for png in artifacts.screenshots_dir.glob("*.png"):
        test_artifacts[f"violation_screenshots/{png.name}"] = png

    # Verify all artifacts match baseline
    results = baseline_artifacts(test_artifacts)

    # Collect all failures first before asserting, so we see the full picture
    failures: list[str] = []
    for name, result in results.items():
        if result.get("match") is False:
            if result.get("comparison_method") == "hash":
                failures.append(
                    f"  ✗ {name}\n"
                    f"      Expected: {result.get('baseline_hash')}\n"
                    f"      Got:      {result.get('current_hash')}"
                )
            if result.get("comparison_method") == "pixel_tolerance":
                failures.append(
                    f"  ✗ {name}\n"
                    f"      Expected: 0 pixels tolerance {result.get('tolerance')}\n"
                    f"      Got:      {result.get('diff_pixels')} pixels"
                )

    # Build a summary of all results for context (passed + failed)
    passed: list[str] = [
        name for name, result in results.items() if result.get("match") is True
    ]

    assert not failures, (
        f"Baseline comparison failed for page '{page_key}' "
        f"({len(failures)} failed, {len(passed)} passed)\n\n"
        f"Passed:\n" + "\n".join(f"  ✓ {name}" for name in passed) + "\n\n"
        "Failed:\n" + "\n".join(failures)
    )
