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
from typing import Any, Final

import pytest

_DEFAULT_A11Y_DIR = ".a11y_reports"
_SUPPORTED_A11Y_TAGS: tuple[str, ...] = (
    "wcag2a",
    "wcag2aa",
    "wcag2aaa",
    "wcag21a",
    "wcag21aa",
    "wcag22aa",
    "section508",
)
_STANDARD_ALIASES: Final[dict[str, list[str]]] = {
    "wcag2.0:a": ["wcag2a"],
    "wcag2.0:aa": ["wcag2a", "wcag2aa"],
    "wcag2.0:aaa": ["wcag2a", "wcag2aa", "wcag2aaa"],
    "wcag2.1:a": ["wcag21a"],
    "wcag2.1:aa": ["wcag21a", "wcag21aa"],
    "wcag2.2:aa": ["wcag2aa", "wcag21aa", "wcag22aa"],
}

WCAG_STANDARD_MAP: Final[dict[str, list[str]]] = {
    "wcag2a": ["wcag2a"],
    "wcag2aa": ["wcag2a", "wcag2aa"],
    "wcag2aaa": ["wcag2a", "wcag2aa", "wcag2aaa"],
    "wcag21a": ["wcag21a"],
    "wcag21aa": ["wcag21a", "wcag21aa"],
    "wcag22aa": ["wcag2aa", "wcag21aa", "wcag22aa"],
    "section508": ["section508"],
}
WCAG_LEVEL_MAP: Final[dict[str, list[str]]] = {
    "A": ["wcag2a"],
    "AA": ["wcag2a", "wcag2aa"],
    "AAA": ["wcag2a", "wcag2aa", "wcag2aaa"],
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
        default=None,
        help=(
            "Accessibility standard tag(s) to run against. Accepts a single axe tag "
            f"(supported tags: {', '.join(_SUPPORTED_A11Y_TAGS)}). "
            "Also accepts aliases: wcag2.0:a, wcag2.0:aa, wcag2.0:aaa, "
            "wcag2.1:a, wcag2.1:aa, wcag2.2:aa. "
            "When omitted, no explicit standard is applied making axe-core default behavior active."
        ),
    )

    group.addoption(
        "--wcag-level",
        type=str,
        default=None,
        help="If set, map to corresponding WCAG level tags: A, AA, AAA.",
    )

    group.addoption(
        "--a11y-tags",
        type=str,
        default=None,
        help=(
            "Comma-separated list of raw axe tags (advanced mode). "
            "Plugin validates only tag shape and emptiness; full catalog is not maintained."
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
        default="",
        help=(
            "Accessibility standard tag(s) to run against. Supports the same "
            "values as --a11y-standard."
        ),
    )

    parser.addini(
        "wcag_level",
        type="string",
        default="",
        help="WCAG level to enforce (A, AA, AAA).",
    )

    parser.addini(
        "a11y_tags",
        type="string",
        default="",
        help="Raw axe tags to run in advanced mode (comma-separated).",
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

    config.a11y_tags = _resolve_a11y_tags(config)  # type: ignore[attr-defined]

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


def _parse_tag_list(value: str) -> list[str]:
    """
    Parse a comma-separated axe tag string into a normalized list.

    Args:
        value: Comma-separated tag string such as
            "wcag21a,wcag21aa,best-practice".

    Returns:
        A list of non-empty, trimmed axe tag names.

    Raises:
        pytest.UsageError: If no valid tags are provided.
    """
    tags: list[str] = [tag.strip() for tag in value.split(",") if tag.strip()]

    if not tags:
        raise pytest.UsageError("--a11y-tags must contain at least one non-empty tag.")

    return tags


def _normalize_config_value(value: object) -> str | None:
    """
    Normalize a config value to a non-empty string, otherwise None.

    This guards against MagicMock values returned by tests or unconfigured
    options so that falsy/non-string values are safely ignored.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _resolve_a11y_tags(config: pytest.Config) -> list[str] | None:
    """
    Resolve user-provided accessibility options into axe-core tag filters.

    Precedence is:

    1. --a11y-tags or a11y_tags ini
    2. --a11y-standard or a11y_standard ini
    3. --wcag-level or wcag_level ini
    4. None (use axe-core default rule set)

    Returning None is intentional. It means pytest-a11y should not set
    ``runOnly`` at all, allowing axe-core to execute its default enabled rules.

    Args:
        config: The active pytest configuration object.

    Returns:
        A list of axe-core tags to pass into ``runOnly``, or None to use
        axe-core defaults.

    Raises:
        pytest.UsageError: If an unsupported option value is supplied.
    """
    raw_tags = _normalize_config_value(config.getoption("--a11y-tags"))
    if raw_tags is None:
        raw_tags = _normalize_config_value(config.getini("a11y_tags"))

    if raw_tags is not None:
        return _parse_tag_list(raw_tags)

    explicit_standard = _normalize_config_value(config.getoption("--a11y-standard"))
    if explicit_standard is None:
        explicit_standard = _normalize_config_value(config.getini("a11y_standard"))

    if explicit_standard:
        resolved_standard = WCAG_STANDARD_MAP.get(explicit_standard)
        if resolved_standard is None:
            resolved_standard = _STANDARD_ALIASES.get(explicit_standard)

        if resolved_standard is None:
            supported_values = sorted(set(WCAG_STANDARD_MAP) | set(_STANDARD_ALIASES))
            supported = ", ".join(supported_values)
            raise pytest.UsageError(
                f"Invalid value for --a11y-standard/a11y_standard "
                f"'{explicit_standard}'. Supported values: {supported}"
            )

        return resolved_standard

    wcag_level = _normalize_config_value(config.getoption("--wcag-level"))
    if wcag_level is None:
        wcag_level = _normalize_config_value(config.getini("wcag_level"))

    if wcag_level:
        wcag_level = wcag_level.upper()
        resolved_level = WCAG_LEVEL_MAP.get(wcag_level)
        if resolved_level is None:
            supported_levels = ", ".join(sorted(WCAG_LEVEL_MAP))
            raise pytest.UsageError(
                f"Unsupported WCAG level '{wcag_level}'. "
                f"Supported values: {supported_levels}"
            )
        return resolved_level

    return None


__all__ = [
    "pytest_addoption",
    "pytest_configure",
]
