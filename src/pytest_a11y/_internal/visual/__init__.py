"""Visual overlay functionality for pytest-a11y.

This module handles creating visual overlays on web pages to highlight
accessibility violations detected by axe-core.
"""

from pytest_a11y._internal.visual.axe_overlay import ViolationScreenshot

__all__: list[str] = ["ViolationScreenshot"]
