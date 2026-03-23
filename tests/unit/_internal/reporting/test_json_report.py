from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

json_report_module = importlib.import_module(
    "pytest_a11y._internal.reporting.json_report"
)


class TestJsonReportModuleImport:
    """Tests for import-time execution."""

    def test_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(json_report_module)

        assert reloaded is json_report_module
        assert reloaded.__name__ == "pytest_a11y._internal.reporting.json_report"


class TestWriteA11yJsonReport:
    """Tests for JSON report generation."""

    @patch.object(json_report_module, "datetime")
    def test_write_report_with_none_results(
        self,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Write an empty violations report when no axe results are provided."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2026-03-20T12:00:00+00:00"
        )

        output_path = tmp_path / "reports" / "a11y.json"
        result = json_report_module.write_a11y_json_report(
            axe_results=None,
            page_url="https://example.com",
            output_path=output_path,
        )

        assert result == output_path
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["url"] == "https://example.com"
        assert payload["violations"] == []
        assert payload["summary"]["total_violations"] == 0
        assert payload["summary"]["timestamp"].endswith("Z")

    @patch.object(json_report_module, "get_relative_screenshot_path")
    @patch.object(json_report_module, "datetime")
    @patch.object(json_report_module.Results, "from_axe")
    def test_write_report_with_real_results(
        self,
        mock_from_axe: MagicMock,
        mock_datetime: MagicMock,
        mock_relative_path: MagicMock,
        tmp_path: Path,
        raw_axe_results: dict[str, object],
        processed_results: object,
    ) -> None:
        """Convert results, include screenshot paths, and write summary counts."""
        mock_from_axe.return_value = processed_results
        mock_relative_path.return_value = "violation_screenshots/one.png"
        mock_datetime.now.return_value.isoformat.return_value = (
            "2026-03-20T12:00:00+00:00"
        )

        output_path = tmp_path / "reports" / "a11y.json"
        result = json_report_module.write_a11y_json_report(
            axe_results=raw_axe_results,
            page_url="https://example.com",
            output_path=output_path,
        )

        assert result == output_path
        mock_from_axe.assert_called_once_with(raw_axe_results)
        mock_relative_path.assert_called_once()

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["url"] == "https://example.com"
        assert len(payload["violations"]) == 1
        assert payload["violations"][0]["id"] == "color-contrast"
        assert (
            payload["violations"][0]["screenshot_path"]
            == "violation_screenshots/one.png"
        )
        assert payload["summary"]["total_violations"] == 1
        assert payload["summary"]["critical"] == 0
        assert payload["summary"]["serious"] == 1
        assert payload["summary"]["moderate"] == 0
        assert payload["summary"]["minor"] == 0
        assert payload["summary"]["timestamp"].endswith("Z")

    @patch.object(json_report_module, "datetime")
    @patch.object(json_report_module.Results, "from_axe")
    def test_write_report_omits_screenshot_path_when_absent(
        self,
        mock_from_axe: MagicMock,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Skip screenshot_path when a violation has no screenshot."""
        violation = MagicMock()
        violation.id = "rule1"
        violation.description = "desc"
        violation.impact = "critical"
        violation.help = "help"
        violation.help_url = "https://example.com/help"
        violation.nodes = []
        violation.tags = []
        violation.screenshot_path = None

        results = MagicMock()
        results.violations = [violation]
        results.violation_count = 1
        mock_from_axe.return_value = results
        mock_datetime.now.return_value.isoformat.return_value = (
            "2026-03-20T12:00:00+00:00"
        )

        output_path = tmp_path / "reports" / "a11y.json"
        json_report_module.write_a11y_json_report(
            axe_results={"violations": []},
            page_url="https://example.com",
            output_path=output_path,
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert "screenshot_path" not in payload["violations"][0]

    @patch.object(json_report_module, "datetime")
    @patch.object(json_report_module.Results, "from_axe")
    def test_write_report_ignores_unknown_impact_in_summary(
        self,
        mock_from_axe: MagicMock,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Ignore non-standard impacts in the summary counts."""
        violation = MagicMock()
        violation.id = "rule1"
        violation.description = "desc"
        violation.impact = "unknown"
        violation.help = "help"
        violation.help_url = "https://example.com/help"
        violation.nodes = []
        violation.tags = []
        violation.screenshot_path = None

        results = MagicMock()
        results.violations = [violation]
        results.violation_count = 1
        mock_from_axe.return_value = results
        mock_datetime.now.return_value.isoformat.return_value = (
            "2026-03-20T12:00:00+00:00"
        )

        output_path = tmp_path / "reports" / "a11y.json"
        json_report_module.write_a11y_json_report(
            axe_results={"violations": []},
            page_url="https://example.com",
            output_path=output_path,
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["summary"]["critical"] == 0
        assert payload["summary"]["serious"] == 0
        assert payload["summary"]["moderate"] == 0
        assert payload["summary"]["minor"] == 0
