from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

html_report_module = importlib.import_module(
    "pytest_a11y._internal.reporting.html_report"
)


class TestHtmlReportModuleImport:
    """Tests for import-time execution."""

    def test_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(html_report_module)

        assert reloaded is html_report_module
        assert reloaded.__name__ == "pytest_a11y._internal.reporting.html_report"


class TestGenerateA11yReport:
    """Tests for HTML report generation."""

    @patch.object(html_report_module, "A11yViolationsReport")
    def test_generate_report_without_results(
        self,
        mock_report_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Create and generate a report even when axe results are missing."""
        report = MagicMock()
        mock_report_class.return_value = report

        html_report_module.generate_a11y_report(
            axe_results=None,
            page_url="https://example.com",
            output_path=tmp_path / "report.html",
        )

        mock_report_class.assert_called_once()
        report.generate.assert_called_once()

    @patch.object(html_report_module, "_add_violation_to_report")
    @patch.object(html_report_module.Results, "from_axe")
    @patch.object(html_report_module, "A11yViolationsReport")
    def test_generate_report_processes_each_violation(
        self,
        mock_report_class: MagicMock,
        mock_from_axe: MagicMock,
        mock_add_violation: MagicMock,
        raw_axe_results: dict[str, object],
        processed_results: object,
        tmp_path: Path,
    ) -> None:
        """Convert raw results and add every violation to the report."""
        report = MagicMock()
        mock_report_class.return_value = report
        mock_from_axe.return_value = processed_results

        html_report_module.generate_a11y_report(
            axe_results=raw_axe_results,
            page_url="https://example.com",
            output_path=str(tmp_path / "report.html"),
            screenshot_dir=str(tmp_path / "shots"),
        )

        mock_from_axe.assert_called_once_with(raw_axe_results)
        mock_add_violation.assert_called_once()
        report.generate.assert_called_once()

    @patch.object(html_report_module, "get_relative_screenshot_path")
    def test_add_violation_to_report_with_screenshot(
        self,
        mock_relative_path: MagicMock,
        processed_violation: object,
        tmp_path: Path,
    ) -> None:
        """Resolve and include a screenshot path when one exists."""
        mock_relative_path.return_value = "shots/one.png"
        report = MagicMock()
        report.output_path = tmp_path / "report.html"

        html_report_module._add_violation_to_report(
            report=report,
            violation=processed_violation,
            screenshot_dir=tmp_path / "shots",
        )

        mock_relative_path.assert_called_once()
        report.add_violation.assert_called_once()
        assert report.add_violation.call_args.kwargs["screenshot"] == "shots/one.png"

    def test_add_violation_to_report_without_screenshot_dir(
        self,
        processed_violation: object,
        tmp_path: Path,
    ) -> None:
        """Use an empty screenshot string when no screenshot directory is provided."""
        report = MagicMock()
        report.output_path = tmp_path / "report.html"

        html_report_module._add_violation_to_report(
            report=report,
            violation=processed_violation,
            screenshot_dir=None,
        )

        report.add_violation.assert_called_once()
        assert report.add_violation.call_args.kwargs["screenshot"] == ""
