"""
Generate HTML reports from axe-core results.

Entry point for creating interactive HTML reports from accessibility checks.
Integrates with captured violation screenshots for visual representation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pytest_a11y._internal.reporting.report_generator import A11yViolationsReport
from pytest_a11y._internal.visual.axe_overlay import get_relative_screenshot_path
from pytest_a11y.types import Results, Violation

if TYPE_CHECKING:
    from pytest_a11y.types import AxeResults

# ============================================================================
# Report generation
# ============================================================================


def generate_a11y_report(
    axe_results: AxeResults | None,
    page_url: str,
    output_path: str | Path,
    screenshot_dir: str | Path | None = None,
) -> None:
    """
    Generate an interactive HTML report from axe-core results.

    Creates a standalone HTML file with clickable violation cards,
    detailed node information, and optional per-violation screenshots.

    Screenshots are embedded using relative paths from the report file location,
    making the report portable and shareable.

    Args:
        axe_results: Complete AxeResults from axe.run() or None if not run
        page_url: URL of the page that was analyzed
        output_path: File path where HTML report will be written
        screenshot_dir: Directory containing per-violation screenshots
                       (optional, screenshots linked if provided)

    Example:
        >>> from pathlib import Path
        >>> generate_a11y_report(
        ...     axe_results=results,
        ...     page_url="https://example.com",
        ...     output_path="reports/a11y.html",
        ...     screenshot_dir="reports/violation_screenshots"
        ... )
    """
    # Convert string paths to Path objects
    output_path = Path(output_path) if isinstance(output_path, str) else output_path
    screenshot_dir = Path(screenshot_dir) if screenshot_dir else None

    # Create report generator
    report = A11yViolationsReport(
        output_path=output_path,
        page_url=page_url,
    )

    # Process violations if results exist
    if axe_results:
        # Convert raw results to typed Results object
        results = Results.from_axe(axe_results)

        # Add violations to report
        for violation in results.violations:
            _add_violation_to_report(
                report=report,
                violation=violation,
                screenshot_dir=screenshot_dir,
            )

    # Generate the HTML report
    report.generate()


def _add_violation_to_report(
    report: A11yViolationsReport,
    violation: Violation,
    screenshot_dir: Path | None = None,
) -> None:
    """
    Add a processed violation to the report.

    Handles screenshot path resolution and adds the violation to the report.

    Args:
        report: A11yViolationsReport instance to add to
        violation: Processed Violation object from Results
        screenshot_dir: Optional directory containing screenshot files
    """
    # Determine screenshot path if directory provided
    screenshot_path = ""
    if violation.screenshot_path and screenshot_dir:
        screenshot_path = get_relative_screenshot_path(
            violation.screenshot_path, report.output_path, fallback_to_filename=False
        )

    # Add to report (report will handle HTML generation)
    report.add_violation(
        name=violation.id,
        summary=violation.summary,
        help_text=violation.help,
        help_url=violation.help_url,
        nodes=violation.nodes,
        tags=violation.tags,
        screenshot=screenshot_path,
    )
