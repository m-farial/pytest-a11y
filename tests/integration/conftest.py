"""
Integration test fixtures for pytest-axe-a11y.

Provides fixtures for running accessibility checks against test pages,
normalizing results, and analyzing reports.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import pytest
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from pytest_a11y._internal.comparison.baseline_manager import BaselineManager
from pytest_a11y.types import AxeRunnerProtocol

logger = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI options for baseline tests."""
    group = parser.getgroup("baselines", "Baseline artifact options")

    group.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="Update baseline artifacts after approved changes",
    )

    group.addoption(
        "--create-baselines",
        action="store_true",
        default=False,
        help="Create baseline artifacts for the first time",
    )


# ============================================================================
# Type Definitions
# ============================================================================


class A11yRunResult(TypedDict, total=False):
    """
    Shape of the result dict returned by check_a11y() fixture.

    The plugin may use either "screenshot_dir" or "violation_screenshots"
    for the screenshot directory path.
    """

    axe: dict[str, Any]
    html_report: str
    json_report: str
    screenshot_dir: str
    violation_screenshots: str


@dataclass(frozen=True)
class Pages:
    """File:// URLs for local deterministic HTML test pages."""

    clean: str
    bad: str


@dataclass(frozen=True)
class A11yArtifacts:
    """
    Normalized artifact bundle for a single check_a11y() run.

    Contains both raw axe results and paths to all generated files.
    """

    axe: dict[str, Any]
    html_report: Path
    json_report: Path
    screenshots_dir: Path


# ============================================================================
# WebDriver Fixture
# ============================================================================


@pytest.fixture
def driver() -> Generator[WebDriver, None, None]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-gpu")
    options.add_argument("--force-device-scale-factor=1")
    # Hide scrollbars so they don't consume viewport width on Linux
    options.add_argument("--hide-scrollbars")
    drv = webdriver.Chrome(options=options)
    try:
        # Explicitly set the *content* viewport after driver starts,
        # overriding any OS-level window chrome adjustments
        drv.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 1280,
                "height": 800,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        yield drv
    finally:
        drv.quit()


# Preserve `config.option.a11y` across tests so a test that temporarily
# toggles the flag does not affect other tests when the whole suite runs.
# This is a pure-test fix for intermittent/ordering-related failures.
@pytest.fixture(autouse=True)
def preserve_a11y_flag(request: pytest.FixtureRequest):
    """Save and restore the `--a11y` CLI/config option for each test."""
    opt = getattr(request.config, "option", None)
    orig = False
    if opt is not None:
        orig = getattr(opt, "a11y", False)
    try:
        yield
    finally:
        if opt is not None:
            opt.a11y = orig


# ============================================================================
# Test Pages Fixture
# ============================================================================


@pytest.fixture(scope="session")
def pages() -> Pages:
    """
    Provide file:// URLs for the integration HTML test pages.

    Returns:
        Pages dataclass with URLs to clean, serious, critical, and bad pages
    """
    base = Path(__file__).parent / "pages"
    return Pages(
        clean=(base / "clean.html").resolve().as_uri(),
        bad=(base / "bad.html").resolve().as_uri(),
    )


# ============================================================================
# Utility Functions
# ============================================================================


def _latest_file(dir_path: Path, pattern: str) -> Path:
    """
    Return the most recently modified file matching a glob pattern.

    Args:
        dir_path: Directory to search
        pattern: Glob pattern (e.g., "*.html")

    Returns:
        Path to the newest file

    Raises:
        FileNotFoundError: If no files match the pattern
    """
    matches = list(dir_path.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No files matched {pattern} in {dir_path}")
    return max(matches, key=lambda p: p.stat().st_mtime)


def _normalize_screenshots_dir(result: A11yRunResult) -> Path:
    """
    Normalize the screenshot directory key from plugin result.

    Handles both "screenshot_dir" and "violation_screenshots" keys.

    Args:
        result: Raw result dict from check_a11y()

    Returns:
        Path to the screenshots directory

    Raises:
        KeyError: If neither key is present
    """
    raw = result.get("screenshot_dir") or result.get("violation_screenshots")
    if not raw:
        raise KeyError("check_a11y() result missing screenshots directory key")
    return Path(raw)


def _read_text(path: Path) -> str:
    """
    Read a file as UTF-8 text (best effort with error replacement).

    Args:
        path: File path to read

    Returns:
        File contents as a string
    """
    return path.read_text(encoding="utf-8", errors="replace")


def extract_screenshot_refs_from_html(html_text: str) -> list[str]:
    """
    Extract screenshot file references from generated HTML report.

    Only extracts from the embedded violations JSON data, not from
    JavaScript source code (which may contain unrendered template literals).

    Args:
        html_text: Full HTML content from report file

    Returns:
        List of unique screenshot paths (deduplicated, preserving order)
    """
    refs = []

    # Extract from embedded violations JSON ONLY
    # Do not use img src regex as it can match unrendered template literals
    # in the JavaScript source code
    match = re.search(r"const violations = (\[.*?\]);", html_text, re.DOTALL)
    if match:
        try:
            violations = json.loads(match.group(1))
            for v in violations:
                if isinstance(v, dict) and v.get("screenshot"):
                    screenshot = v.get("screenshot", "").strip()
                    # Only add non-empty screenshot paths
                    if screenshot and not screenshot.startswith("${"):
                        refs.append(screenshot)
        except json.JSONDecodeError:
            pass

    # Deduplicate while preserving order
    return list(dict.fromkeys(refs))


def load_axe_json(json_report_path: Path) -> dict[str, Any]:
    """
    Load and parse the JSON report produced by the plugin.

    Args:
        json_report_path: Path to the JSON report file

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If JSON is invalid
    """
    return json.loads(_read_text(json_report_path))


def assert_artifacts_exist(artifacts: A11yArtifacts) -> None:
    """
    Assert that all expected artifacts exist on disk with content.

    HTML and JSON reports are always required. Screenshots directory
    is optional (only created if violations were found).

    Args:
        artifacts: Normalized artifact bundle

    Raises:
        AssertionError: If any required artifact is missing or empty
    """
    for report_path in [artifacts.html_report, artifacts.json_report]:
        assert report_path.exists(), f"Missing report: {report_path}"
        assert report_path.stat().st_size > 0, f"Empty report: {report_path}"

    if artifacts.screenshots_dir.exists():
        assert artifacts.screenshots_dir.is_dir(), "Screenshots path is not a directory"


def is_redish(pixel: tuple[int, int, int, int] | tuple[int, int, int]) -> bool:
    """
    Check if a pixel is "red-ish" (used for overlay detection).

    Uses heuristic: R >= 180, G <= 90, B <= 90

    Args:
        pixel: A 3-tuple (RGB) or 4-tuple (RGBA)

    Returns:
        True if pixel matches red-ish heuristic
    """
    r, g, b = pixel[0], pixel[1], pixel[2]
    return r >= 180 and g <= 90 and b <= 90


def count_redish_pixels(image_path: Path) -> int:
    """
    Count red-ish pixels in an image.

    Useful for verifying that violation overlays were properly drawn.

    Args:
        image_path: Path to a PNG/JPG screenshot

    Returns:
        Number of pixels matching the red-ish heuristic
    """
    img = Image.open(image_path).convert("RGBA")
    data = img.tobytes()

    # Extract RGBA tuples from bytes (4 bytes per pixel)
    pixels = [
        (data[i], data[i + 1], data[i + 2], data[i + 3])
        for i in range(0, len(data), 4)
        if data[i + 3] > 0  # Only non-transparent pixels
    ]

    return sum(1 for p in pixels if is_redish(p))


# ============================================================================
# Report Viewer Fixture
# ============================================================================


@pytest.fixture
def open_report(driver: WebDriver) -> Callable[[Path], None]:
    """
    Open a generated HTML report file in the current WebDriver session.

    Waits for JavaScript to render the violations container before returning.

    Args:
        driver: Selenium WebDriver

    Returns:
        Callable that takes a Path to an HTML report and opens it
    """

    def _open(report_path: Path) -> None:
        driver.get(report_path.resolve().as_uri())
        # Wait for JS to render the report
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.ID, "violationsContainer") is not None
        )

    return _open


# ============================================================================
# Test runner helper: run_a11y
# ============================================================================


@pytest.fixture
def run_a11y(
    request: pytest.FixtureRequest,
    driver: WebDriver,
    axe: AxeRunnerProtocol,
    pages: Pages,
) -> Callable[[str], A11yArtifacts]:
    """Run axe against a named test page, generate reports, and return artifacts.

    This helper centralizes the logic used by integration tests to:
    - navigate to a deterministically located test page
    - run the axe runner
    - trigger report generation (without failing the test)
    - locate the generated HTML/JSON files and screenshots directory

    Returns:
        Callable that accepts a page key ("clean" or "bad") and returns
        an A11yArtifacts dataclass with paths to the generated files.
    """

    def _run(page_key: str) -> A11yArtifacts:
        # Navigate to the requested deterministic test page
        url = getattr(pages, page_key)
        driver.get(url)

        # Wait for the page to be fully loaded before running axe
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, 5).until(lambda d: url in (d.current_url or ""))

        # Execute axe and capture raw results
        axe_results = axe.run()

        # Trigger report generation via the plugin helper (best-effort).
        # We still write deterministic files below to guarantee artifacts exist
        # and reflect the current `axe_results` for the test comparison.
        try:
            from pytest_a11y.assertions import _generate_reports

            _generate_reports(axe_results, driver, request=request)
        except Exception:
            logger.warning(
                "Warning: Report generation failed during test run_a11y helper."
            )
            raise

        # Always write deterministic artifact files for the test run so the
        # test can rely on exact, current files rather than racey "latest" files.
        session_dir: Path = request.config.a11y_session_dir  # type: ignore[attr-defined]
        screenshot_dir = session_dir / "violation_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Deterministic filenames (include page key to aid debugging)
        safe_name = re.sub(
            r"[^A-Za-z0-9_.-]+", "_", f"{request.node.name}__{page_key}"
        ).strip("_")
        html_path = session_dir / f"{safe_name}.html"
        json_path = session_dir / f"{safe_name}.json"

        # Directly call reporting writers (raise on error so tests fail noisily)
        from pytest_a11y._internal.reporting.html_report import generate_a11y_report
        from pytest_a11y._internal.reporting.json_report import write_a11y_json_report
        from pytest_a11y._internal.screenshots import capture_violation_screenshots

        # Capture violation screenshots when present
        if axe_results.get("violations"):
            capture_violation_screenshots(
                driver=driver, axe_results=axe_results, output_dir=screenshot_dir
            )

        generate_a11y_report(
            axe_results=axe_results,
            page_url=url,
            output_path=html_path,
            screenshot_dir=screenshot_dir,
        )
        write_a11y_json_report(
            axe_results=axe_results,
            page_url=url,
            output_path=json_path,
        )

        return A11yArtifacts(
            axe=axe_results,
            html_report=html_path,
            json_report=json_path,
            screenshots_dir=screenshot_dir,
        )

    return _run


# ============================================================================
# Screenshot Cleanup Fixture
# ============================================================================


@pytest.fixture
def cleanup_violation_screenshots_before_test(request: pytest.FixtureRequest) -> None:
    """
    Clean violation screenshots before each test.

    Only removes the violation_screenshots subdirectory, preserving HTML/JSON
    reports. This ensures each test starts clean without stale screenshots
    interfering with assertions.

    Runs only when --a11y flag is provided.
    """
    if request.config.getoption("--a11y"):
        session_dir = request.config.a11y_session_dir  # type: ignore[attr-defined]
        screenshots_dir = session_dir / "violation_screenshots"

        if screenshots_dir.exists():
            shutil.rmtree(screenshots_dir)


# ============================================================================
# Regression Test Fixture
# ============================================================================


@pytest.fixture
def baseline_artifacts(request: pytest.FixtureRequest):
    """
    Fixture for managing baseline artifacts.

    Provides functions to compare, create, and update baselines.
    Baselines are stored in: tests/integration/baselines/{test_name}/

    Usage:
        def test_example(baseline_artifacts):
            artifacts = {
                "report.html": Path("test_output.html"),
                "violation_screenshots/critical.png": Path("screenshots/critical.png"),
            }
            results = baseline_artifacts(artifacts)
            assert all(r["match"] for r in results.values())
    """
    update = request.config.getoption("--update-baselines")
    create = request.config.getoption("--create-baselines")

    test_name = request.node.name
    baseline_dir = Path(__file__).parent / "integration" / "baselines" / test_name

    # image_tolerance allows minor pixel differences between OS/rendering environments
    # 0 = exact match, 1-10 = minor variations (anti-aliasing, font rendering, etc.)
    # Screenshots captured on different OS (Windows vs Linux) will have small differences
    manager = BaselineManager(baseline_dir, image_tolerance=10)

    def verify_artifacts(artifacts: dict[str, Path]) -> dict:
        """
        Verify or manage baseline artifacts.

        Args:
            artifacts: Dict mapping artifact names to their file paths
                      E.g., {"report.html": Path(...), "screenshots/1.png": Path(...)}

        Returns:
            Dict mapping artifact names to comparison/update results
        """
        results = {}

        for artifact_name, artifact_path in artifacts.items():
            artifact_path = Path(artifact_path)

            # Determine artifact type from extension
            suffix = artifact_path.suffix.lower()
            if suffix == ".png" or suffix == ".jpg":
                artifact_type = "image"
            elif suffix == ".html":
                artifact_type = "html"
            elif suffix == ".json":
                artifact_type = "json"
            else:
                artifact_type = "text"

            if create:
                # Create new baseline
                result = manager.create_baseline(
                    artifact_name, artifact_path, artifact_type
                )
            elif update:
                # Update existing baseline
                result = manager.update_baseline(artifact_name, artifact_path)
            else:
                # Compare against baseline
                result = manager.compare_artifact(artifact_name, artifact_path)

            results[artifact_name] = result

        return results

    return verify_artifacts
