"""
Per-violation screenshot capture for a11y violations.

Captures individual screenshots for each violation with visual highlighting
of affected elements instead of capturing one screenshot with all violations.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y.assertions import _safe_filename_suffix
from pytest_a11y.types import AxeNode, AxeResults, AxeViolationRaw

logger = logging.getLogger(__name__)

# ============================================================================
# Data Types
# ============================================================================


@dataclass
class ViolationScreenshot:
    """Result of capturing a single violation screenshot."""

    violation_id: str
    violation_index: int
    screenshot_path: Path
    marked_count: int


# ============================================================================
# Private Utilities
# ============================================================================


def _iter_violation_selectors(
    violation: AxeViolationRaw,
    *,
    max_nodes: int | None = None,
) -> Iterable[str]:
    """
    Yield CSS selectors for nodes affected by this violation.

    Filters out non-list targets and global selectors (html, body, *).

    Args:
        violation: Single violation from axe results
        max_nodes: Maximum number of nodes to yield (default: no limit)

    Yields:
        CSS selector strings for affected elements
    """
    nodes: list[AxeNode] = violation.get("nodes", [])

    if max_nodes is not None:
        nodes = nodes[:max_nodes]

    for node in nodes:
        targets = node.get("target")
        if not isinstance(targets, list):
            continue
        for sel in targets:
            if isinstance(sel, str) and sel.strip() and not _is_global_selector(sel):
                yield sel.strip()


def _has_global_selector_only(violation: AxeViolationRaw) -> bool:
    """
    Check if violation only targets global/root elements.

    Some violations like landmark-one-main target html/body/* and have no
    specific elements to mark. This helper identifies those cases.

    Args:
        violation: Single violation from axe results

    Returns:
        True if all selectors are global or no nodes exist
    """
    nodes: list[AxeNode] = violation.get("nodes", [])

    if not nodes:
        return True

    for node in nodes:
        targets = node.get("target")
        if not isinstance(targets, list):
            continue
        for sel in targets:
            if isinstance(sel, str) and sel.strip() and not _is_global_selector(sel):
                return False

    return True


def _is_global_selector(selector: str) -> bool:
    """
    Check if selector is a global/root element.

    Global selectors (html, body, *) don't help with visual highlighting.

    Args:
        selector: CSS selector string

    Returns:
        True if selector is html, body, or *
    """
    s = selector.strip().lower()
    return s in ("html", "body", "*")


def _severity_color(impact: str | None) -> str:
    """
    Map impact severity to a display color.

    Uses hex colors that are stable across browsers and headless environments.

    Args:
        impact: Impact level from axe (critical, serious, moderate, minor)

    Returns:
        Hex color code string
    """
    impact_lower = (impact or "unknown").lower().strip()
    return {
        "critical": "#b00020",  # deep red
        "serious": "#e65100",  # orange
        "moderate": "#f9a825",  # amber
        "minor": "#1565c0",  # blue
        "unknown": "#616161",  # gray
    }.get(impact_lower, "#616161")


def _mark_selector_on_page(
    driver: WebDriver,
    selector: str,
    label: str,
    color: str,
    badge_offset_y: int = 0,
) -> bool:
    """
    Mark a single selector on the current page with outline and badge.

    Adds a colored outline around the element and a fixed-position badge label
    near the element's top-left corner.

    Args:
        driver: Selenium WebDriver instance
        selector: CSS selector to mark
        label: Text label for the badge
        color: Hex color code for the outline and badge
        badge_offset_y: Vertical offset for badge positioning (default: 0)

    Returns:
        True if element was found and marked, False if not found
    """
    result = driver.execute_script(
        """
        const sel = arguments[0];
        const label = arguments[1];
        const color = arguments[2];
        const offsetY = arguments[3];

        const el = document.querySelector(sel);
        if (!el) return false;

        // Add outline
        el.style.outline = `3px solid ${color}`;
        el.style.outlineOffset = '2px';

        // Add badge
        const badge = document.createElement('div');
        badge.textContent = label;
        badge.style.position = 'fixed';
        badge.style.top = (el.getBoundingClientRect().top + offsetY) + 'px';
        badge.style.left = (el.getBoundingClientRect().right + 10) + 'px';
        badge.style.background = color;
        badge.style.color = 'white';
        badge.style.padding = '4px 8px';
        badge.style.borderRadius = '3px';
        badge.style.fontSize = '11px';
        badge.style.fontWeight = 'bold';
        badge.style.zIndex = '999999';
        badge.style.whiteSpace = 'nowrap';
        badge.className = 'a11y-violation-badge';
        document.body.appendChild(badge);

        return true;
        """,
        selector,
        label,
        color,
        badge_offset_y,
    )
    return bool(result)


def _add_page_level_banner(
    driver: WebDriver,
    violation_id: str,
    impact: str,
    color: str,
) -> None:
    """
    Add a banner at the top of the page for page-level violations.

    For violations that don't target specific elements (like landmark-one-main),
    this adds a prominent banner explaining the issue.

    Args:
        driver: Selenium WebDriver instance
        violation_id: ID of the violation
        impact: Impact level
        color: Hex color code
    """
    driver.execute_script(
        """
        const violationId = arguments[0];
        const impact = arguments[1];
        const color = arguments[2];

        const banner = document.createElement('div');
        banner.textContent = `⚠️ Page-level violation: ${violationId} (${impact})`;
        banner.style.position = 'fixed';
        banner.style.top = '0';
        banner.style.left = '0';
        banner.style.right = '0';
        banner.style.background = color;
        banner.style.color = 'white';
        banner.style.padding = '12px 16px';
        banner.style.fontSize = '14px';
        banner.style.fontWeight = 'bold';
        banner.style.zIndex = '999998';
        banner.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
        banner.className = 'a11y-violation-banner';
        document.body.appendChild(banner);

        // Shift page down to show banner
        document.body.style.marginTop = '50px';
        """,
        violation_id,
        impact,
        color,
    )


def _cleanup_violation_marks(driver: WebDriver) -> None:
    """
    Remove all violation badges, banners and outlines from the page.

    Cleans up visual markers added by _mark_selector_on_page() and
    _add_page_level_banner().
    This is best-effort - some styles may persist if set via classes.

    Args:
        driver: Selenium WebDriver instance
    """
    driver.execute_script(
        """
        // Remove badges
        document.querySelectorAll('.a11y-violation-badge').forEach(el => el.remove());

        // Remove banners
        document.querySelectorAll('.a11y-violation-banner').forEach(el => el.remove());

        // Reset body margin
        document.body.style.marginTop = '';

        // Remove outlines (best-effort)
        document.querySelectorAll('[style*="outline"]').forEach(el => {
            el.style.outline = '';
            el.style.outlineOffset = '';
        });
        """
    )


# ============================================================================
# Public API
# ============================================================================


def capture_violation_screenshots(
    driver: WebDriver,
    axe_results: AxeResults,
    output_dir: Path | str,
    *,
    filename_suffix: str = "",
    scroll_into_view: bool = True,
    max_nodes_per_violation: int | None = 10,
) -> dict[str, str]:
    """
    Capture individual screenshots for each violation in results.

    Iterates through all violations, marks affected elements with colored
    outlines and badges, captures a screenshot for each one, then cleans up.
    Updates violation dicts with screenshot_path in-place for report generation.

    For violations with no specific target elements (e.g., landmark-one-main
    with target=['html']), captures a screenshot with a page-level banner
    instead of skipping.

    Args:
        driver: Selenium WebDriver instance
        axe_results: Complete AxeResults from axe.run()
        output_dir: Directory to save screenshot files
        filename_suffix: Optional suffix appended to screenshot filenames
        scroll_into_view: Whether to scroll elements into view (default: True)
        max_nodes_per_violation: Limit elements marked per violation (default: 10)

    Returns:
        Dict mapping violation_id -> screenshot file path string

    Example:
        >>> screenshot_paths = capture_violation_screenshots(
        ...     driver=driver,
        ...     axe_results=results,
        ...     output_dir=Path("screenshots")
        ... )
        >>> for rule_id, path in screenshot_paths.items():
        ...     print(f"{rule_id}: {path}")
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_paths: dict[str, str] = {}

    violations = axe_results.get("violations", [])

    for v_index, violation in enumerate(violations, start=1):
        violation_id = violation.get("id", "unknown")
        violation_impact = violation.get("impact", "unknown")
        color = _severity_color(violation.get("impact"))
        nodes: list[AxeNode] = violation.get("nodes", [])

        # Skip violations with no nodes and no impact
        if not nodes or not violation_impact or violation_impact == "unknown":
            logger.debug(
                f"[capture] skipping violation {v_index} id={violation_id} (no nodes/impact)"
            )
            continue

        logger.debug(
            f"[capture] processing violation {v_index} id={violation_id} nodes={len(nodes)} impact={violation_impact}"
        )

        # Mark all selectors for this violation
        marked_count = 0
        badge_offset_y = 0

        for selector in _iter_violation_selectors(
            violation, max_nodes=max_nodes_per_violation
        ):
            if scroll_into_view:
                driver.execute_script(
                    """
                    const el = document.querySelector(arguments[0]);
                    if (el) el.scrollIntoView({block:'center', inline:'center'});
                    """,
                    selector,
                )

            label = f"{v_index}: {violation_id}"
            marked = False
            try:
                marked = _mark_selector_on_page(
                    driver, selector, label, color, badge_offset_y
                )
            except Exception as _exc:
                logger.warning(
                    f"[capture] marking selector failed: {selector!r} -> {_exc}"
                )

            if marked:
                marked_count += 1
                badge_offset_y = (badge_offset_y + 14) % 56

        # If no specific elements were marked but violation has global selectors,
        # add a page-level banner instead
        if marked_count == 0 and _has_global_selector_only(violation):
            _add_page_level_banner(driver, violation_id, violation_impact, color)
            marked_count += 1

        # Skip if still no elements were marked
        if marked_count == 0:
            logger.debug(
                f"[capture] no elements marked for violation {violation_id}; skipping screenshot"
            )
            continue

        # Sync repaint before screenshot
        driver.execute_script(
            "return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
        )

        # Capture screenshot
        safe_suffix = _safe_filename_suffix(filename_suffix) if filename_suffix else ""
        suffix = f"_{safe_suffix}" if safe_suffix else ""
        screenshot_path = (
            output_dir / f"{violation_impact}_{violation_id}_{v_index}{suffix}.png"
        )
        try:
            saved_ok = driver.save_screenshot(str(screenshot_path))
        except Exception as exc:
            saved_ok = False
            logger.warning(
                f"[capture] save_screenshot raised for {screenshot_path}: {exc}"
            )

        logger.debug(f"[capture] screenshot saved? {saved_ok} -> {screenshot_path}")

        # Cleanup badges and outlines
        _cleanup_violation_marks(driver)

        # Track screenshot path
        screenshot_path_str = str(screenshot_path)
        screenshot_paths[violation_id] = screenshot_path_str
        # Update violation dict in-place with screenshot path
        # This is picked up when converting to Results type
        violation["screenshot_path"] = screenshot_path_str

    return screenshot_paths


def get_relative_screenshot_path(
    screenshot_path: str | Path,
    output_path: str | Path,
    fallback_to_filename: bool = True,
) -> str:
    """
    Get relative screenshot path for cross-platform compatibility.

    Args:
        screenshot_path: Full path to screenshot
        output_path: Output file path (to compute relative from)
        fallback_to_filename: If relative path can't be computed, use filename only

    Returns:
        Relative path with forward slashes (cross-platform safe)
    """
    try:
        screenshot_obj = Path(screenshot_path)
        output_obj = Path(output_path)
        relative = screenshot_obj.relative_to(output_obj.parent)
        return relative.as_posix()
    except ValueError:
        # Can't compute relative path
        if fallback_to_filename:
            return Path(screenshot_path).name
        else:
            return Path(screenshot_path).as_posix()
