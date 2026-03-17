from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from PIL import Image

from pytest_a11y.axe._runner import AxeRunner
from pytest_a11y.types import Node, Results, Violation


class DummyConfig:
    """Simple config double for a11y option lookups."""

    def __init__(self, flag: bool, session_dir: Path | None = None) -> None:
        self._flag = flag
        if session_dir is not None:
            self.a11y_session_dir = session_dir

    def getoption(self, name: str) -> bool:
        """Return the configured a11y flag for the supported option."""
        if name == "--a11y":
            return self._flag
        raise ValueError(name)


class DummyNode:
    """Simple pytest node double."""

    def __init__(
        self, nodeid: str = "tests/test_file.py::test_case", name: str = "test_case"
    ) -> None:
        self.nodeid = nodeid
        self.name = name


class DummyRequest:
    """Simple pytest request double."""

    def __init__(
        self,
        config: DummyConfig,
        nodeid: str = "tests/test_file.py::test_case",
        name: str = "test_case",
        driver: Any | None = None,
    ) -> None:
        self.config = config
        self.node = DummyNode(nodeid=nodeid, name=name)
        self._driver = driver

    def getfixturevalue(self, name: str) -> Any:
        """Return the configured driver fixture when requested."""
        if name == "driver":
            if self._driver is None:
                raise pytest.FixtureLookupError(name, None)
            return self._driver
        raise pytest.FixtureLookupError(name, None)


class DummyDriver:
    """Simple Selenium driver double."""

    def __init__(self, current_url: str = "https://example.com") -> None:
        self.current_url = current_url


@pytest.fixture
def mock_driver() -> MagicMock:
    """Return a mock Selenium WebDriver."""
    driver = MagicMock()
    driver.current_url = "https://example.com"
    driver.save_screenshot.return_value = True
    return driver


@pytest.fixture
def mock_request() -> MagicMock:
    """Return a mock pytest FixtureRequest."""
    return MagicMock()


@pytest.fixture
def mock_axe_instance() -> MagicMock:
    """Return a mock axe-selenium-python Axe instance."""
    return MagicMock()


@pytest.fixture
def axe_results_factory() -> Callable[..., dict[str, Any]]:
    """Build axe-style results dictionaries for tests."""

    def _build(
        *,
        violations: list[dict[str, Any]] | None = None,
        passes: list[dict[str, Any]] | None = None,
        incomplete: list[dict[str, Any]] | None = None,
        inapplicable: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "violations": violations or [],
            "passes": passes or [],
            "incomplete": incomplete or [],
            "inapplicable": inapplicable or [],
        }

    return _build


@pytest.fixture
def axe_runner(mock_driver: MagicMock, mock_request: MagicMock) -> AxeRunner:
    """Create an AxeRunner instance for unit tests."""
    return AxeRunner(driver=mock_driver, request=mock_request)


@pytest.fixture
def mock_parser() -> MagicMock:
    """Return a mock pytest parser."""
    parser = MagicMock()
    parser.getgroup.return_value = MagicMock()
    return parser


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock pytest config object with mutable option attributes."""
    config = MagicMock()
    config.option = SimpleNamespace(
        a11y_reports=None,
        a11y_dir=".a11y_reports",
    )
    return config


@pytest.fixture
def raw_axe_results() -> dict[str, Any]:
    """Return representative raw axe-core results for conversion tests."""
    return {
        "url": "https://example.com",
        "timestamp": "2026-03-20T12:00:00",
        "violations": [
            {
                "id": "color-contrast",
                "description": "Insufficient color contrast",
                "impact": "serious",
                "help": "Fix contrast",
                "helpUrl": "https://example.com/help/color-contrast",
                "nodes": [
                    {
                        "target": ["#login-button"],
                        "html": '<button id="login-button">Login</button>',
                        "impact": "serious",
                        "failureSummary": "Element has insufficient contrast",
                    }
                ],
                "tags": ["wcag2aa", "cat.color"],
                "screenshot_path": "artifacts/contrast.png",
            }
        ],
        "passes": [
            {
                "id": "document-title",
                "description": "Document has a title",
                "impact": None,
                "help": "Add title",
                "helpUrl": "https://example.com/help/document-title",
                "nodes": [],
                "tags": ["wcag2a"],
                "screenshot_path": None,
            }
        ],
        "incomplete": [
            {
                "id": "landmark-one-main",
                "description": "Page should have one main landmark",
                "impact": "moderate",
                "help": "Check landmarks",
                "helpUrl": "https://example.com/help/landmark",
                "nodes": [],
                "tags": [],
                "screenshot_path": None,
            }
        ],
        "inapplicable": [
            {
                "id": "video-caption",
                "description": "Videos must have captions",
                "impact": None,
                "help": "Add captions",
                "helpUrl": "https://example.com/help/video-caption",
                "nodes": [],
                "tags": [],
                "screenshot_path": None,
            }
        ],
    }


@pytest.fixture
def minimal_axe_results() -> dict[str, Any]:
    """Return minimal axe-core results for default-value coverage."""
    return {
        "violations": [
            {
                "nodes": [
                    {
                        # intentionally sparse to exercise defaults
                    }
                ]
            }
        ]
    }


@pytest.fixture
def dummy_driver() -> DummyDriver:
    """Return a dummy Selenium driver."""
    return DummyDriver()


@pytest.fixture
def processed_violation() -> Violation:
    """Return a processed violation with one node and a screenshot path."""
    return Violation(
        id="color-contrast",
        description="Insufficient color contrast",
        impact="serious",
        help="Fix contrast",
        help_url="https://example.com/help/color-contrast",
        nodes=[
            Node(
                selector="#login-button",
                html='<button id="login-button">Login</button>',
                failure_summary="Element has insufficient contrast",
                impact="serious",
            )
        ],
        tags=["wcag2aa", "cat.color"],
        screenshot_path="violation_screenshots/serious_color-contrast_1.png",
    )


@pytest.fixture
def processed_results(processed_violation: Violation) -> Results:
    """Return processed results with one violation."""
    return Results(
        url="https://example.com",
        timestamp="2026-03-20T12:00:00",
        violations=[processed_violation],
    )


@pytest.fixture
def processed_results_no_violations() -> Results:
    """Return processed results with no violations."""
    return Results(url="https://example.com", timestamp="now", violations=[])


@pytest.fixture
def processed_results_with_minor() -> Results:
    """Return processed results with one non-critical violation."""
    return Results(
        url="https://example.com",
        timestamp="now",
        violations=[
            Violation(
                id="minor-rule",
                description="Minor issue",
                impact="minor",
                help="Fix it",
                help_url="https://example.com/help",
            )
        ],
    )


@pytest.fixture
def processed_results_with_critical() -> Results:
    """Return processed results with one critical violation."""
    return Results(
        url="https://example.com",
        timestamp="now",
        violations=[
            Violation(
                id="critical-rule",
                description="Critical issue",
                impact="critical",
                help="Fix it now",
                help_url="https://example.com/help",
            )
        ],
    )


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    """Create a simple text file for baseline tests."""
    path = tmp_path / "sample.txt"
    path.write_text("hello world", encoding="utf-8")
    return path


@pytest.fixture
def sample_html_file(tmp_path: Path) -> Path:
    """Create an HTML file containing dynamic-looking values."""
    path = tmp_path / "report.html"
    path.write_text(
        """
        <html>
          <body>
            Generated at 2026-03-20T12:00:00
            C:\\Users\\me\\project\\file.html
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_json_file(tmp_path: Path) -> Path:
    """Create a JSON file containing dynamic-looking values."""
    path = tmp_path / "report.json"
    path.write_text(
        """
        {
          "timestamp": "2026-03-20T12:00:00",
          "run": "run_20260320_120000",
          "path": "/tmp/project/file.json"
        }
        """,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def red_png(tmp_path: Path) -> Path:
    """Create a small red PNG image."""
    path = tmp_path / "red.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(path)
    return path


@pytest.fixture
def slightly_different_red_png(tmp_path: Path) -> Path:
    """Create a slightly different red PNG image."""
    path = tmp_path / "red2.png"
    image = Image.new("RGB", (4, 4), (255, 0, 0))
    image.putpixel((0, 0), (250, 0, 0))
    image.save(path)
    return path
