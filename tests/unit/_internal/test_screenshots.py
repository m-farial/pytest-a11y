from __future__ import annotations

import importlib

from pytest_a11y._internal.visual.axe_overlay import (
    capture_violation_screenshots as internal_capture,
)


def test_screenshots_module_reexports_capture_function() -> None:
    """Ensure the public screenshots module re-exports the underlying function."""

    screenshots = importlib.import_module("pytest_a11y._internal.screenshots")

    assert screenshots.capture_violation_screenshots is internal_capture
    assert screenshots.__all__ == ["capture_violation_screenshots"]
