"""
Assertion and validation utilities for a11y testing with integrated reporting.

This module provides helper functions for validating axe-core accessibility
testing results within pytest tests. When --a11y flag is enabled, these
assertions automatically generate HTML/JSON reports and violation screenshots.

All functions operate on AxeResults (raw output from axe-core) or Results
(processed typed versions). Choose the assertion that matches your use case:

1. **Strict assertions (fail on any violation):**
   - assert_no_axe_violations() - For raw AxeResults
   - assert_results_no_violations() - For processed Results

2. **Lenient assertions (fail on critical only):**
   - assert_no_critical_violations() - For raw AxeResults
   - assert_results_no_critical() - For processed Results

Common Usage Pattern:
    from pytest_a11y import assert_no_axe_violations
    from selenium.webdriver.remote.webdriver import WebDriver
    from pytest_a11y.types import AxeRunnerProtocol

    def test_page_accessibility(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
        '''Check accessibility.'''
        driver.get("https://example.com")
        results = axe.run()
        assert_no_axe_violations(results)
        # If --a11y flag: reports auto-generated in .a11y_reports/
        # If no flag: simple assertion, no reports

Reports (when --a11y enabled):
    - HTML: .a11y_reports/run_YYYYMMDD_HHMMSS/test_name__worker__hash.html
    - JSON: .a11y_reports/run_YYYYMMDD_HHMMSS/test_name__worker__hash.json
    - Screenshots: .a11y_reports/run_YYYYMMDD_HHMMSS/violation_screenshots/

See Also:
    - pytest_a11y.types.AxeResults: Raw results TypedDict
    - pytest_a11y.types.Results: Processed results class
    - pytest_a11y.types.Violation: Individual violation class
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from pytest_a11y.types import AxeResults, Results

logger = logging.getLogger(__name__)

REPORT_ARTIFACT_NAME_MAX_LEN = 150
REPORT_ARTIFACT_FALLBACK_NAME_MAX_LEN = 60
SLUG_COMPONENT_MAX_LEN: int = 50
SLUG_PAGE_MAX_LEN: int = 75

# ============================================================================
# Report Generation (only when --a11y flag enabled)
# ============================================================================


def _should_generate_reports() -> bool:
    """
    Check whether report generation is enabled for the current pytest run.

    Prefers the active `request` (when available) and falls back to the
    global `pytest.config`. Returns True only when `--a11y` was passed.
    """
    # Prefer the active FixtureRequest when running under pytest
    try:
        request = pytest.current_request  # type: ignore[attr-defined]
        if request and getattr(request, "config", None):
            return bool(request.config.getoption("--a11y"))
    except Exception:
        logger.warning("Warning: Could not access pytest request to check --a11y flag.")
        pass

    # Fallback to pytest.config when available (older pytest embed cases)
    try:
        config = getattr(pytest, "config", None)
        if config:
            return bool(config.getoption("--a11y"))
    except Exception:
        logger.warning("Warning: Could not access pytest config to check --a11y flag.")
        pass

    return False


def _safe_slug(text: str, max_len: int | None = SLUG_COMPONENT_MAX_LEN) -> str:
    """
    Convert a string into a filesystem-friendly slug.

    Args:
        text: Input text (typically pytest test name)
        max_len: Optional maximum length of the output slug. If None,
            the full slug is returned.

    Returns:
        Filesystem-safe slug string
    """
    keep: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    slug: str = "".join(keep).strip("_")
    if max_len is None:
        return slug or "a11y"
    return slug[:max_len].strip("_") or "a11y"


def _safe_filename_suffix(suffix: str, max_len: int = SLUG_COMPONENT_MAX_LEN) -> str:
    """
    Normalize a filename suffix for use in screenshot filenames.

    This prevents nested paths, relative-path sequences, and invalid
    filesystem characters from appearing in screenshot filenames.
    """
    safe_chars: list[str] = []
    prev_sep = False

    for ch in suffix:
        if ch.isalnum() or ch in ("-", "_"):
            safe_chars.append(ch)
            prev_sep = False
        else:
            if not prev_sep:
                safe_chars.append("_")
                prev_sep = True

    safe = "".join(safe_chars).strip("_.")
    if not safe:
        return "suffix"

    safe = safe[:max_len].strip("_.")
    return safe or "suffix"


def _report_output_paths(request: Any, driver: Any) -> tuple[Path, Path, Path, str]:
    """
    Compute deterministic output paths for HTML, JSON, screenshots, and suffix.

    Args:
        request: pytest request object containing node and config state.
        driver: Selenium WebDriver instance with a current_url property.

    Returns:
        Tuple containing (html_path, json_path, screenshot_dir, filename_suffix).
    """
    config = request.config if request is not None else getattr(pytest, "config", None)
    if not config or not hasattr(config, "a11y_session_dir"):
        raise RuntimeError("Missing a11y_session_dir in pytest config")

    session_dir: Path = Path(config.a11y_session_dir)
    raw_worker_id: str = os.environ.get("PYTEST_XDIST_WORKER", "master")
    worker_id: str = (
        _safe_filename_suffix(raw_worker_id, max_len=SLUG_COMPONENT_MAX_LEN)
        if raw_worker_id != "master"
        else "master"
    )
    if worker_id == "":
        worker_id = "worker"
    nodeid: str = (
        request.node.nodeid if request and getattr(request, "node", None) else "unknown"
    )
    raw_name: str = (
        request.node.name if request and getattr(request, "node", None) else "test"
    )
    name: str = _safe_slug(raw_name, max_len=SLUG_COMPONENT_MAX_LEN)
    page_url = getattr(driver, "current_url", "about:blank")
    page_slug = _page_slug_from_url(page_url, max_len=SLUG_PAGE_MAX_LEN)
    suffix: str = _nodeid_hash(nodeid)

    base_parts = [name]
    if "[" not in raw_name and page_slug:
        base_parts.append(page_slug)
    if worker_id != "master":
        base_parts.append(worker_id)
    base_parts.append(suffix)

    base: str = "_".join(base_parts)
    if len(base) > REPORT_ARTIFACT_NAME_MAX_LEN:
        fallback_name = _safe_slug(
            raw_name, max_len=REPORT_ARTIFACT_FALLBACK_NAME_MAX_LEN
        )
        fallback_hash = _nodeid_hash(nodeid, length=10)
        if worker_id != "master":
            base = f"{fallback_name}_{worker_id}_{fallback_hash}"
        else:
            base = f"{fallback_name}_{fallback_hash}"

    html_path: Path = session_dir / f"{base}.html"
    json_path: Path = session_dir / f"{base}.json"
    screenshot_dir: Path = session_dir / "violation_screenshots"

    return html_path, json_path, screenshot_dir, suffix


def _nodeid_hash(nodeid: str, length: int = 10) -> str:
    """
    Generate a stable hash for pytest nodeid.

    Args:
        nodeid: pytest nodeid (file::test_name[params])
        length: Length of hex string to return

    Returns:
        Hex digest string truncated to requested length
    """
    digest_size: int = max(4, length // 2 + 1)
    return hashlib.blake2b(
        nodeid.encode("utf-8"),
        digest_size=digest_size,
    ).hexdigest()[:length]


def _page_slug_from_url(page_url: str, max_len: int | None = None) -> str:
    """
    Convert a page URL into a filesystem-safe slug.

    Args:
        page_url: URL of the analyzed page
        max_len: Optional maximum length of the final slug.

    Returns:
        A slug derived from the hostname and path.
    """
    parsed = urlparse(page_url)
    hostname = parsed.netloc.lower().split("@")[-1]
    if hostname.startswith("www."):
        hostname = hostname[4:]

    path = parsed.path or "/"
    if parsed.scheme == "file":
        page_part = Path(path).stem or "file"
        raw_slug = page_part
        if max_len is None:
            max_len = SLUG_PAGE_MAX_LEN
    else:
        common_tlds = {
            "com",
            "net",
            "org",
            "io",
            "app",
            "dev",
            "ai",
            "info",
            "tech",
            "site",
            "xyz",
            "me",
            "co",
        }
        host_parts = hostname.split(".") if hostname else []
        if len(host_parts) > 1 and host_parts[-1] in common_tlds:
            host_parts = host_parts[:-1]
        hostname = "_".join(host_parts)

        if path in ("/", ""):
            page_part = "home"
        else:
            page_part = "_".join([segment for segment in path.split("/") if segment])

        raw_slug = f"{hostname}_{page_part}" if hostname else page_part

    return _safe_slug(raw_slug, max_len=max_len)


def _generate_reports(
    axe_results: AxeResults | None,
    driver: Any,
    request: pytest.FixtureRequest | None = None,
) -> None:
    """
    Generate HTML/JSON reports and violation screenshots.

    If provided, `request` is used to access `request.config` and `request.node`
    (preferred). When `request` is not supplied the function falls back to the
    global `pytest.config` so existing call sites remain functional.

    Args:
        axe_results: Raw axe-core results
        driver: Selenium WebDriver instance
        request: Optional pytest FixtureRequest (used to resolve session dir)
    """
    if axe_results is None:
        return

    # Prefer the explicit `request` (forwarded from fixtures/runners). If a
    # request is provided use its config to decide whether reports are enabled;
    # otherwise fall back to the global check.
    if request is not None:
        try:
            if not bool(request.config.getoption("--a11y")):
                return
        except Exception:
            return
    else:
        if not _should_generate_reports():
            return

    try:
        # Import reporting modules only when needed
        from pytest_a11y._internal.reporting.html_report import (
            generate_a11y_report,
        )
        from pytest_a11y._internal.reporting.json_report import (
            write_a11y_json_report,
        )
        from pytest_a11y._internal.screenshots import capture_violation_screenshots
    except ImportError as e:
        # If reporting modules unavailable, skip report generation
        logger.warning(f"Warning: Could not generate reports: {e}")
        return

    try:
        # Prefer request.config when available (has session dir + node info)
        config = (
            request.config if request is not None else getattr(pytest, "config", None)
        )

        if not config or not hasattr(config, "a11y_session_dir"):
            return

        html_path, json_path, screenshot_dir, filename_suffix = _report_output_paths(
            request, driver
        )

        # Capture screenshots (if any) and write reports
        if axe_results.get("violations"):
            capture_violation_screenshots(
                driver=driver,
                axe_results=axe_results,
                output_dir=screenshot_dir,
                filename_suffix=filename_suffix,
            )

        generate_a11y_report(
            axe_results=axe_results,
            page_url=getattr(driver, "current_url", "about:blank"),
            output_path=html_path,
            screenshot_dir=screenshot_dir,
        )
        write_a11y_json_report(
            axe_results=axe_results,
            page_url=getattr(driver, "current_url", "about:blank"),
            output_path=json_path,
        )
    except Exception:
        # Silently fail if report generation has issues - do not break tests
        logger.warning("Warning: Exception during report generation", exc_info=True)
        return


# ============================================================================
# Assertions for Raw Results
# ============================================================================


def assert_no_axe_violations(results: AxeResults) -> None:
    """
    Assert that no violations exist in axe-core results.

    If --a11y flag is enabled, automatically generates:
        - HTML report with screenshots
        - JSON report for CI integration
        - Individual violation screenshots

    Reports are saved to: .a11y_reports/run_YYYYMMDD_HHMMSS/

    Fails the test with a formatted summary of violations if any are found.
    Operates on raw AxeResults from axe.run(). Use this for strict checks
    where any violation should fail the test.

    This is the most common assertion function for basic accessibility testing.
    It provides a quick way to ensure a page has no accessibility issues.

    Args:
        results: Complete AxeResults dictionary from axe.run()

    Raises:
        AssertionError: If any violations are found. The error message includes
                       a summary of violation IDs and affected node counts.

    Example:
        Basic usage in a test:

            from selenium.webdriver.remote.webdriver import WebDriver
            from pytest_a11y import assert_no_axe_violations
            from pytest_a11y.types import AxeRunnerProtocol

            def test_homepage_accessibility(
                driver: WebDriver,
                axe: AxeRunnerProtocol,
            ) -> None:
                '''Ensure homepage has no accessibility violations.'''
                driver.get("https://www.saucedemo.com/")
                results = axe.run()
                assert_no_axe_violations(results)

        With --a11y flag:
            Reports auto-generated in .a11y_reports/run_YYYYMMDD_HHMMSS/

        Checking multiple pages:

            def test_site_structure(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
                '''Check multiple pages for violations.'''
                urls = [
                    "https://example.com/",
                    "https://example.com/about",
                    "https://example.com/contact",
                ]
                for url in urls:
                    driver.get(url)
                    results = axe.run()
                    assert_no_axe_violations(results)

    Note:
        For less strict checks (fail only on critical), use
        assert_no_critical_violations() instead.

    See Also:
        assert_no_critical_violations: Less strict assertion
        assert_results_no_violations: For processed Results objects
    """
    # Try to get driver for report generation
    driver: Any = None
    request = None
    try:
        request = pytest.current_request  # type: ignore[attr-defined]
        driver = request.getfixturevalue("driver")
    except (AttributeError, RuntimeError, pytest.FixtureLookupError):
        request = None
        driver = None

    # Generate reports if --a11y enabled and driver available
    if driver:
        _generate_reports(results, driver, request=request)

    # Perform assertion
    violations = results.get("violations", [])
    if violations:
        messages = [
            f"{v.get('id', 'unknown')} ({len(v.get('nodes', []))} nodes)"
            for v in violations
        ]
        raise AssertionError("axe violations found:\n" + "\n".join(messages))


def assert_no_critical_violations(results: AxeResults) -> None:
    """
    Assert that no critical-severity violations exist in axe-core results.

    If --a11y flag is enabled, automatically generates reports (same as
    assert_no_axe_violations).

    Less strict than assert_no_axe_violations() - only fails on violations
    with "critical" impact level. Useful for CI pipelines that want to warn
    on serious/moderate issues but fail hard on critical ones.

    This is useful when you want to be lenient about minor accessibility issues
    while catching severe problems that significantly impact usability.

    Args:
        results: Complete AxeResults dictionary from axe.run()

    Raises:
        AssertionError: If any critical-severity violations are found.
                       Serious and moderate violations are ignored.

    Example:
        Lenient CI check allowing minor issues:

            def test_page_critical_only(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
                '''Allow minor/moderate issues, fail on critical.'''
                driver.get("https://example.com")
                results = axe.run()
                assert_no_critical_violations(results)

        Useful in staged compliance:

            # Phase 1: Focus on critical issues
            def test_critical_resolved(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
                results = axe.run()
                assert_no_critical_violations(results)

            # Phase 2: Once critical is fixed, add stricter checks
            # def test_all_violations(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
            #     results = axe.run()
            #     assert_no_axe_violations(results)

    Note:
        Severity levels in axe-core:
        - critical: Causes complete obstruction to access
        - serious: Causes significant difficulty
        - moderate: Makes content harder to access
        - minor: Slightly inconvenient to access

    See Also:
        assert_no_axe_violations: Strict assertion (fail on any violation)
        assert_results_no_critical: For processed Results objects
    """
    # Try to get driver for report generation
    driver: Any = None
    request = None
    try:
        request = pytest.current_request  # type: ignore[attr-defined]
        driver = request.getfixturevalue("driver")
    except (AttributeError, RuntimeError, pytest.FixtureLookupError):
        request = None
        driver = None

    # Generate reports if --a11y enabled and driver available
    if driver:
        _generate_reports(results, driver, request=request)

    # Perform assertion
    violations = results.get("violations", [])
    critical = [v for v in violations if v.get("impact") == "critical"]

    if critical:
        messages = [
            f"{v.get('id', 'unknown')} ({len(v.get('nodes', []))} nodes)"
            for v in critical
        ]
        raise AssertionError("critical axe violations found:\n" + "\n".join(messages))


# ============================================================================
# Assertions for Processed Results
# ============================================================================


def assert_results_no_violations(results: Results) -> None:
    """
    Assert that processed Results contain no violations.

    If --a11y flag is enabled, automatically generates reports.

    Works with Results objects (processed and typed) rather than raw AxeResults.
    Provides cleaner assertions for code that uses Results.from_axe() for
    data transformation.

    This is useful when you want to work with fully typed, structured data
    rather than raw dictionaries. The Results class provides properties like
    violation_count and has_violations for easier inspection.

    Args:
        results: Results object from Results.from_axe(axe_results)

    Raises:
        AssertionError: If any violations found. Includes formatted summary
                       of all violations with their impact levels.

    Example:
        Using processed Results for structured access:

            from pytest_a11y import Results, assert_results_no_violations

            def test_with_results(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
                driver.get("https://example.com")
                axe_results = axe.run()
                results = Results.from_axe(axe_results)

                # Can inspect before asserting
                if results.has_violations:
                    print(f"Found {results.violation_count} violations")
                    for violation in results.violations:
                        print(f"- {violation.id}: {violation.description}")

                assert_results_no_violations(results)

    See Also:
        Results: Processed results class with properties and type hints
        Results.from_axe: Convert AxeResults to Results
        assert_no_axe_violations: For raw AxeResults
    """
    if results.has_violations:
        messages = [v.summary for v in results.violations]
        raise AssertionError("violations found:\n" + "\n".join(messages))


def assert_results_no_critical(results: Results) -> None:
    """
    Assert that processed Results contain no critical-severity violations.

    Works with Results objects (processed and typed). Only fails on violations
    with critical impact. Useful for lenient accessibility checks.

    Less strict than assert_results_no_violations(). Allows serious and moderate
    issues while catching only the most severe problems.

    Args:
        results: Results object from Results.from_axe(axe_results)

    Raises:
        AssertionError: If any critical violations found.
                       Serious/moderate violations are ignored.

    Example:
        Lenient check with processed results:

            from pytest_a11y import Results, assert_results_no_critical

            def test_critical_only(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
                driver.get("https://example.com")
                axe_results = axe.run()
                results = Results.from_axe(axe_results)

                # Can log all issues before asserting
                if results.has_violations:
                    for v in results.violations:
                        print(f"({v.impact}) {v.id}: {v.description}")

                # Only fail on critical
                assert_results_no_critical(results)

    See Also:
        assert_results_no_violations: Strict assertion (fail on any)
        assert_no_critical_violations: For raw AxeResults
        Results.violations: Access all violations
    """
    critical = [v for v in results.violations if v.impact == "critical"]

    if critical:
        messages = [v.summary for v in critical]
        raise AssertionError("critical violations found:\n" + "\n".join(messages))
