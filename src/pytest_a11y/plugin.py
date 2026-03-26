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
_DEFAULT_A11Y_STANDARD = "wcag2aa"
_SUPPORTED_A11Y_TAGS: tuple[str, ...] = (
    "wcag2a",
    "wcag2aa",
    "wcag2aaa",
    "wcag21a",
    "wcag21aa",
    "wcag22aa",
    "section508",
)
_STANDARD_ALIASES: dict[str, list[str]] = {
    "wcag2.0:a": ["wcag2a"],
    "wcag2.0:aa": ["wcag2a", "wcag2aa"],
    "wcag2.0:aaa": ["wcag2a", "wcag2aa", "wcag2aaa"],
    "wcag2.1:a": ["wcag21a"],
    "wcag2.1:aa": ["wcag21a", "wcag21aa"],
    "wcag2.2:aa": ["wcag2aa", "wcag21aa", "wcag22aa"],
}
WCAG_STANDARD_MAP = {
    "wcag2a": ["wcag2a"],
    "wcag2aa": ["wcag2a", "wcag2aa"],
    "wcag2aaa": ["wcag2a", "wcag2aa", "wcag2aaa"],
    "wcag21a": ["wcag21a"],
    "wcag21aa": ["wcag21a", "wcag21aa"],
    "wcag22aa": ["wcag2aa", "wcag21aa", "wcag22aa"],
    "section508": ["section508"],
}


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

    group.addoption(
        "--a11y-standard",
        type=str,
        default=_DEFAULT_A11Y_STANDARD,
        help=(
            "Accessibility standard tag(s) to run against. Accepts a single axe tag "
            f"or a comma-separated list (supported tags: {', '.join(_SUPPORTED_A11Y_TAGS)}). "
            "Also accepts aliases: wcag2.0:a, wcag2.0:aa, wcag2.0:aaa, "
            "wcag2.1:a, wcag2.1:aa, wcag2.2:aa. "
            f"Default: {_DEFAULT_A11Y_STANDARD}"
        ),
    )

    parser.addini(
        "a11y_reports",
        type="string",
        default=_DEFAULT_A11Y_DIR,
        help="Directory to save a11y reports (can also use --a11y-dir CLI option)",
    )

    parser.addini(
        "a11y_standard",
        type="string",
        default=_DEFAULT_A11Y_STANDARD,
        help=(
            "Accessibility standard tag(s) to run against. Supports the same "
            "values as --a11y-standard."
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    """
    Configure pytest with a11y plugin settings.
    """
    config.a11y_enabled = config.getoption("--a11y")  # type: ignore[attr-defined]

    existing_session_dir = _coerce_pathlike(config.__dict__.get("a11y_session_dir"))

    if existing_session_dir is not None:
        resolved_session_dir = existing_session_dir.expanduser().resolve()
        config.a11y_session_dir = resolved_session_dir  # type: ignore[attr-defined]
        config.a11y_dir = resolved_session_dir.parent  # type: ignore[attr-defined]
    else:
        resolved_a11y_dir = _resolve_a11y_dir(config).expanduser().resolve()
        config.a11y_dir = resolved_a11y_dir  # type: ignore[attr-defined]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config.a11y_session_dir = resolved_a11y_dir / f"run_{timestamp}"  # type: ignore[attr-defined]

    standard = config.getoption("--a11y-standard")

    if standard not in WCAG_STANDARD_MAP:
        raise pytest.UsageError(
            f"Unsupported accessibility standard '{standard}'. "
            f"Supported: {', '.join(WCAG_STANDARD_MAP)}"
        )

    config.a11y_tags = WCAG_STANDARD_MAP[standard]  # type: ignore[attr-defined]
    config.a11y_standard = standard  # type: ignore[attr-defined]

    resolved_standards = _resolve_a11y_standard(config)
    config.a11y_standards = resolved_standards  # type: ignore[attr-defined]
    config.a11y_standard = ",".join(resolved_standards)  # type: ignore[attr-defined]

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

    path_value: str | os.PathLike[str] | None

    if isinstance(value, str):
        path_value = value
    elif isinstance(value, os.PathLike):
        path_value = value
    else:
        return None

    path_text = os.fspath(path_value)

    if isinstance(path_text, bytes):
        return None

    if not path_text:
        return None

    return Path(path_text)


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


def _resolve_a11y_standard(config: pytest.Config) -> list[str]:
    """
    Resolve the selected accessibility standard tags via CLI, ini, env, or default.

    Priority:
    1. config.option.a11y_standard (programmatic override)
    2. --a11y-standard CLI arg
    3. a11y_standard ini value
    4. A11Y_STANDARD env var
    5. default wcag2aa
    """
    raw_value: str | None = None

    configured_override = getattr(config.option, "a11y_standard", None)
    if configured_override:
        raw_value = str(configured_override)
    else:
        cli_standard = config.getoption("--a11y-standard")
        if cli_standard:
            raw_value = str(cli_standard)
        else:
            ini_standard = config.getini("a11y_standard")
            if ini_standard:
                raw_value = str(ini_standard)
            else:
                env_standard = os.environ.get("A11Y_STANDARD")
                if env_standard:
                    raw_value = str(env_standard)

    if not raw_value:
        raw_value = _DEFAULT_A11Y_STANDARD

    return _parse_a11y_standard_value(raw_value)


def _parse_a11y_standard_value(raw_value: str) -> list[str]:
    """
    Parse configured standard text into validated axe tag values.

    Supports:
    - single raw axe tag: ``wcag2aa``
    - comma-separated raw tags: ``wcag21a,wcag21aa``
    - friendly aliases: ``wcag2.1:aa``
    """
    normalized = raw_value.strip().lower()
    if not normalized:
        return [_DEFAULT_A11Y_STANDARD]

    if normalized in _STANDARD_ALIASES:
        return _STANDARD_ALIASES[normalized]

    values = [value.strip().lower() for value in normalized.split(",") if value.strip()]
    if not values:
        return [_DEFAULT_A11Y_STANDARD]

    invalid = [value for value in values if value not in _SUPPORTED_A11Y_TAGS]
    if invalid:
        supported = ", ".join(_SUPPORTED_A11Y_TAGS)
        raise pytest.UsageError(
            "Invalid value for --a11y-standard/a11y_standard: "
            f"{', '.join(invalid)}. Supported tags: {supported}. "
            "Supported aliases: wcag2.0:a, wcag2.0:aa, wcag2.0:aaa, "
            "wcag2.1:a, wcag2.1:aa, wcag2.2:aa."
        )

    return values


__all__ = [
    "pytest_addoption",
    "pytest_configure",
]
