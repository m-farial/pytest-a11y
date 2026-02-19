"""
JSON report generation for accessibility checks.

Generates JSON reports from axe-core results for integration with CI/CD,
archival, and programmatic access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pytest_a11y._internal.visual.axe_overlay import get_relative_screenshot_path
from pytest_a11y.types import AxeResults, Results


def write_a11y_json_report(
    *,
    axe_results: AxeResults | None,
    page_url: str,
    output_path: Path | str,
) -> Path:
    """
    Write a violations-only accessibility report in JSON format.

    Creates a JSON file containing metadata (URL, timestamp) and only
    violations from axe-core results for CI/CD integration and reporting.

    File Structure:
        {
            "url": "https://example.com",
            "violations": [
                {
                    "id": "label",
                    "description": "Ensures every form element has a label",
                    "impact": "critical",
                    "help": "Form elements must have labels",
                    "help_url": "https://dequeuniversity.com/...",
                    "nodes": [
                        {
                            "selector": "input[type='text']",
                            "html": "<input type='text' placeholder='Name'>",
                            "failure_summary": "..."
                        }
                    ],
                    "tags": ["cat.forms", "wcag2a", "wcag332"],
                    "screenshot_path": "violation_screenshots/critical_label_1.png"
                }
            ],
            "summary": {
                "total_violations": 5,
                "critical": 2,
                "serious": 1,
                "moderate": 2,
                "minor": 0,
                "timestamp": "2026-02-08T00:45:19.101042Z"
            }
        }

    Args:
        axe_results: Raw results from axe.run() or None if not run
        page_url: URL of the page that was analyzed
        output_path: File path where JSON report will be written

    Returns:
        The Path to the written report file

    Example:
        >>> from pathlib import Path
        >>> write_a11y_json_report(
        ...     axe_results=results,
        ...     page_url="https://example.com",
        ...     output_path="reports/a11y.json"
        ... )
        Path('reports/a11y.json')
    """

    out: Path = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    results: Results

    # Convert to typed Results for easier access
    if axe_results is None:
        results = Results(violations=[], url=page_url, timestamp="")
    else:
        results = Results.from_axe(axe_results)

    # Build violations list with only essential fields
    violations_data: list[dict[str, Any]] = []
    for violation in results.violations:
        violation_dict: dict[str, Any] = {
            "id": violation.id,
            "description": violation.description,
            "impact": violation.impact,
            "help": violation.help,
            "help_url": violation.help_url,
            "nodes": [
                {
                    "selector": node.selector,
                    "html": node.html,
                    "failure_summary": node.failure_summary,
                }
                for node in violation.nodes
            ],
            "tags": violation.tags,
        }

        # Only include screenshot path if it exists
        if violation.screenshot_path:
            violation_dict["screenshot_path"] = get_relative_screenshot_path(
                violation.screenshot_path,
                output_path,
                fallback_to_filename=True,  # Just filename if can't be relative
            )

        violations_data.append(violation_dict)

    # Build summary statistics
    impact_counts: dict[str, int] = {
        "critical": 0,
        "serious": 0,
        "moderate": 0,
        "minor": 0,
    }
    for violation in results.violations:
        impact: str = violation.impact or "unknown"
        if impact in impact_counts:
            impact_counts[impact] += 1

    summary: dict[str, Any] = {
        "total_violations": results.violation_count,
        "critical": impact_counts["critical"],
        "serious": impact_counts["serious"],
        "moderate": impact_counts["moderate"],
        "minor": impact_counts["minor"],
        # Use Z suffix for standard ISO 8601 UTC representation
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # Create final payload
    payload: dict[str, Any] = {
        "url": page_url,
        "violations": violations_data,
        "summary": summary,
    }

    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
