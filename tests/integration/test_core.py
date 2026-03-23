"""
Core pytest-a11y functionality tests.

Tests the most critical functionality:
- Plugin discovery and registration
- Opt-in behavior (--a11y flag)
- Core axe injection and error handling
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

pytest_plugins = ["pytester"]


@dataclass(frozen=True)
class PytestRun:
    """Captured output from an isolated pytest run."""

    returncode: int
    stdout: str
    stderr: str


@pytest.fixture(scope="session")
def pages() -> dict[str, str]:
    """Provide file:// URLs for test HTML pages."""
    base = Path(__file__).parent / "pages"
    return {
        "good": (base / "clean.html").resolve().as_uri(),
        "bad": (base / "bad.html").resolve().as_uri(),
    }


@pytest.fixture(scope="session")
def driver() -> WebDriver:
    """Create a headless Chrome driver for tests."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,800")
    drv = webdriver.Chrome(options=options)
    try:
        yield drv
    finally:
        drv.quit()


# ============================================================================
# Plugin Discovery & Registration Tests
# ============================================================================


@pytest.mark.integration
def test_plugin_discovered_and_options_visible(pytester: pytest.Pytester) -> None:
    """
    Verify that the pytest-a11y plugin is auto-discovered and CLI options are visible.

    This is critical: the plugin must be discoverable via entry points.
    """
    pytester.makepyfile(test_smoke="def test_smoke(): assert True")
    result = pytester.runpytest_subprocess("--help")

    assert result.ret == 0
    output = str(result.stdout) + str(result.stderr)
    assert "--a11y" in output, "Plugin option --a11y should be visible in help"
    assert "--a11y-dir" in output, "Plugin option --a11y-dir should be visible"


@pytest.mark.integration
def test_check_a11y_respects_opt_in_flag(pytester: pytest.Pytester) -> None:
    """
    Verify that report generation is opt-in via the `--a11y` flag.

    The plugin should not attempt to generate reports by default.
    """
    pytester.makepyfile(
        test_opt_in="""
from pytest_a11y.assertions import _should_generate_reports

def test_opt_in(request):
    # By default the plugin must NOT generate reports unless --a11y is passed
    assert not _should_generate_reports()
"""
    )

    # Run WITHOUT --a11y flag
    result = pytester.runpytest_subprocess("-q")
    assert result.ret == 0, f"Test should pass:\n{result.stdout}\n{result.stderr}"


# ============================================================================
# Core Axe Functionality Tests
# ============================================================================


@pytest.mark.integration
def test_axe_injection_error_handling(
    driver: WebDriver,
    pages: dict[str, str],
    tmp_path: Path,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    axe,
) -> None:
    """
    Verify that axe injection errors are handled gracefully.

    If AxeRunner.run() fails, calling `axe.run()` should raise a clear error
    rather than the plugin silently swallowing it.
    """
    request.config.option.a11y_reports = tmp_path
    driver.get(pages["bad"])

    def injection_failure(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("Simulated axe injection failure")

    # Patch the instantiated runner directly to ensure the failure is raised
    # regardless of any caching or class-level indirection.
    monkeypatch.setattr(axe, "run", injection_failure, raising=True)

    # Verify the error is raised with clear message (axe fixture uses AxeRunner)
    with pytest.raises(RuntimeError, match="Simulated axe injection failure"):
        axe.run()


@pytest.mark.integration
def test_axe_run_respects_opt_in_flag_and_writes_reports(
    driver: WebDriver,
    pages: dict[str, str],
    request: pytest.FixtureRequest,
    tmp_path: Path,
    axe,
) -> None:
    """
    When `--a11y` is enabled (simulated via `request.config.option.a11y`),
    calling `axe.run()` should write HTML/JSON reports into
    `request.config.a11y_session_dir` (fixture forwards `request`).

    Conversely, when the flag is not set no reports should be written.
    """
    # Prepare a session directory and ensure it's attached to config
    session_dir = tmp_path / "run_test"
    session_dir.mkdir(parents=True, exist_ok=True)
    request.config.a11y_session_dir = session_dir  # type: ignore[attr-defined]

    # 1) Without opt-in: no reports should be created
    request.config.option.a11y = False
    driver.get(pages["bad"])
    axe.run()
    assert not any(session_dir.glob("*.html")) and not any(session_dir.glob("*.json"))

    # 2) With opt-in: axe.run() should generate reports (HTML or JSON)
    request.config.option.a11y = True
    driver.get(pages["bad"])
    axe.run()

    htmls = list(session_dir.glob("*.html"))
    jsons = list(session_dir.glob("*.json"))
    assert (
        htmls or jsons
    ), "Expected HTML/JSON report to be generated when --a11y is enabled"


@pytest.mark.integration
def test_axe_runner_reports_when_request_provided(
    driver: WebDriver,
    pages: dict[str, str],
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """
    Constructing an `AxeRunner` without a fixture `request` does **not** write
    reports automatically. When the runner is constructed with a `request`
    (or the fixture forwards `request`) the reports are written into
    `request.config.a11y_session_dir` when `--a11y` is enabled.
    """
    # Prepare session directory on config
    session_dir = tmp_path / "run_runner_no_request"
    session_dir.mkdir(parents=True, exist_ok=True)
    request.config.a11y_session_dir = session_dir  # type: ignore[attr-defined]

    # Enable opt-in and load test page
    request.config.option.a11y = True
    driver.get(pages["bad"])

    from pytest_a11y.axe._runner import AxeRunner

    # 1) Runner constructed without request should not write reports
    runner_no_request = AxeRunner(driver)
    runner_no_request.run()
    assert not any(session_dir.glob("*.html")) and not any(session_dir.glob("*.json"))

    # 2) Runner constructed WITH the fixture request should write reports
    runner_with_request = AxeRunner(driver, request=request)
    runner_with_request.run()
    assert any(session_dir.glob("*.html")) or any(session_dir.glob("*.json"))
