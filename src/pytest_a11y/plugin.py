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

_DEFAULT_A11Y_DIR = ".a11y_reports"


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register CLI options for the a11y plugin.
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
        default=_DEFAULT_A11Y_DIR,
        help=f"Directory to save a11y reports (default: {_DEFAULT_A11Y_DIR})",
    )

    parser.addini(
        "a11y_reports",
        type="string",
        default=_DEFAULT_A11Y_DIR,
        help="Directory to save a11y reports (can also use --a11y-dir CLI option)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """
    Configure pytest with a11y plugin settings.
    """
    config.a11y_enabled = config.getoption("--a11y")  # type: ignore[attr-defined]

    existing_session_dir = _coerce_pathlike(getattr(config, "a11y_session_dir", None))

    if existing_session_dir is not None:
        resolved_session_dir = existing_session_dir.expanduser().resolve()
        config.a11y_session_dir = resolved_session_dir  # type: ignore[attr-defined]
        config.a11y_dir = resolved_session_dir.parent  # type: ignore[attr-defined]
    else:
        resolved_a11y_dir = _resolve_a11y_dir(config).expanduser().resolve()
        config.a11y_dir = resolved_a11y_dir  # type: ignore[attr-defined]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config.a11y_session_dir = resolved_a11y_dir / f"run_{timestamp}"  # type: ignore[attr-defined]

    if config.a11y_enabled:  # type: ignore[attr-defined]
        Path(config.a11y_session_dir).mkdir(  # type: ignore[attr-defined]
            parents=True,
            exist_ok=True,
        )


def _coerce_pathlike(value: object) -> Path | None:
    """
    Convert a supported path-like value into a Path.

    Returns None for values that should not be treated as real paths,
    including None, empty strings, and unittest.mock objects used in tests.
    """
    if value is None:
        return None

    if _is_mock_object(value):
        return None

    path_value: str | os.PathLike[str] | None

    if isinstance(value, str):
        path_value = value
    elif isinstance(value, os.PathLike):
        path_value = value
    else:
        return None

    path_text = os.fspath(path_value)
    if not path_text:
        return None

    return Path(path_text)


def _is_mock_object(value: object) -> bool:
    """
    Check whether a value is a unittest.mock object.
    """
    value_type = type(value)
    return getattr(value_type, "__module__", "") == "unittest.mock"


def _resolve_a11y_dir(config: pytest.Config) -> Path:
    """
    Resolve a11y reports directory from all configuration sources.
    """
    configured_override = _coerce_pathlike(getattr(config.option, "a11y_reports", None))
    if configured_override is not None:
        return configured_override

    cli_dir = _coerce_pathlike(config.getoption("--a11y-dir"))
    if cli_dir is not None and cli_dir != Path(_DEFAULT_A11Y_DIR):
        return cli_dir

    ini_dir = _coerce_pathlike(config.getini("a11y_reports"))
    if ini_dir is not None and ini_dir != Path(_DEFAULT_A11Y_DIR):
        return ini_dir

    env_dir = _coerce_pathlike(os.environ.get("A11Y_DIR"))
    if env_dir is not None:
        return env_dir

    return Path(_DEFAULT_A11Y_DIR)


__all__ = [
    "pytest_addoption",
    "pytest_configure",
]
