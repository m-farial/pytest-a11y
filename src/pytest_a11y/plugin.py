"""
Public plugin entry point for pytest.

This module is automatically loaded by pytest via the entry point in pyproject.toml:
    [project.entry-points."pytest11"]
    a11y = "pytest_a11y.plugin"

All pytest hooks (pytest_addoption, pytest_configure) are defined here.
This is the standard pattern for pytest plugins.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# ============================================================================
# Pytest Hook Implementations
# ============================================================================
# These functions have special names that pytest recognizes and calls automatically.
# They MUST be in the module referenced by the entry point.
# ============================================================================


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register CLI options for the a11y plugin.

    This is a pytest hook that gets called during argument parsing.
    Adds the following options:
        --a11y: Enable accessibility checks and report generation
        --a11y-dir: Directory to save reports (default: .a11y_reports)

    Can also be configured via:
        - pytest.ini: [pytest] a11y_reports = /path/to/reports
        - conftest.py: config.option.a11y_reports = Path("/path/to/reports")
        - Environment: A11Y_DIR=/path/to/reports

    Args:
        parser: pytest argument parser object
    """
    group: Any = parser.getgroup("a11y", "Accessibility testing options")

    group.addoption(
        "--a11y",
        action="store_true",
        default=False,
        help="Enable accessibility checks and report generation.",
    )

    group.addoption(
        "--a11y-dir",
        type=str,
        default=".a11y_reports",
        help="Directory to save a11y reports (default: .a11y_reports)",
    )

    # Add INI file option for pytest.ini configuration
    parser.addini(
        "a11y_reports",
        type="string",
        default=".a11y_reports",
        help="Directory to save a11y reports (can also use --a11y-dir CLI option)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """
    Configure pytest with a11y plugin settings.

    This is a pytest hook called after command line options are parsed.
    Sets up the a11y directory if accessibility testing is enabled.

    Configuration priority (highest to lowest):
        1. conftest.py: config.option.a11y_reports = Path(...)
        2. CLI: --a11y-dir /path/to/reports
        3. pytest.ini: a11y_reports = /path/to/reports
        4. Environment: A11Y_DIR=/path/to/reports
        5. Default: .a11y_reports

    Args:
        config: pytest configuration object - we attach custom attributes to it
    """
    # Store a11y settings in config for access in assertions
    config.a11y_enabled = config.getoption("--a11y")  # type: ignore[attr-defined]

    # Resolve a11y directory with priority order
    a11y_dir: str | Path = _resolve_a11y_dir(config)

    # Support temp directories for CI/CD (e.g., /tmp, $TMPDIR)
    a11y_dir = Path(a11y_dir).expanduser().resolve()
    config.a11y_dir = a11y_dir  # type: ignore[attr-defined]

    # Create timestamped session directory for this test run
    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir: Path = a11y_dir / f"run_{timestamp}"
    config.a11y_session_dir = session_dir  # type: ignore[attr-defined]

    # Create directory if it doesn't exist and a11y is enabled
    if config.a11y_enabled:  # type: ignore[attr-defined]
        session_dir.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Utility Functions (private helpers)
# ============================================================================


def _resolve_a11y_dir(config: pytest.Config) -> Path:
    """
    Resolve a11y reports directory from all configuration sources.

    Checks multiple configuration sources in priority order:
        1. conftest.py: config.option.a11y_reports (if set programmatically)
        2. CLI: --a11y-dir /path/to/reports
        3. pytest.ini: a11y_reports = /path/to/reports
        4. Environment: A11Y_DIR=/path/to/reports
        5. Default: .a11y_reports

    Args:
        config: pytest configuration object

    Returns:
        Resolved Path object for the a11y reports directory
    """
    # Priority 1: Check if config.option.a11y_reports was set programmatically
    if hasattr(config.option, "a11y_reports") and config.option.a11y_reports:
        return Path(config.option.a11y_reports)

    # Priority 2: Check CLI --a11y-dir (only if not default)
    cli_dir: str | Any = config.getoption("--a11y-dir")
    if cli_dir and cli_dir != ".a11y_reports":
        return Path(cli_dir)

    # Priority 3: Check pytest.ini a11y_reports setting
    ini_dir: str | Any = config.getini("a11y_reports")
    if ini_dir and ini_dir != ".a11y_reports":
        return Path(ini_dir)

    # Priority 4: Check environment variable
    env_dir: str | None = os.environ.get("A11Y_DIR")
    if env_dir:
        return Path(env_dir)

    # Priority 5: Return default
    return Path(".a11y_reports")


# ============================================================================
# Public Exports
# ============================================================================

__all__ = [
    "pytest_addoption",
    "pytest_configure",
]
