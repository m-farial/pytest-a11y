"""
Screenshot capture utilities for accessibility violations.

This module re-exports the main screenshot capture function from axe_overlay.
It provides a clear public interface for the plugin to use.
"""

from __future__ import annotations

from pytest_a11y._internal.visual.axe_overlay import capture_violation_screenshots

__all__ = ["capture_violation_screenshots"]
