from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

report_generator_module = importlib.import_module(
    "pytest_a11y._internal.reporting.report_generator"
)

A11yViolationsReport = report_generator_module.A11yViolationsReport


class _DummyNode:
    """Simple node test double for report input."""

    def __init__(
        self,
        *,
        selector: str,
        html: str,
        failure_summary: str,
        impact: str | None,
    ) -> None:
        """Initialize a dummy node with the expected report attributes."""
        self.selector = selector
        self.html = html
        self.failure_summary = failure_summary
        self.impact = impact


class TestReportGeneratorModuleImport:
    """Tests for import-time execution in the report generator module."""

    def test_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(report_generator_module)

        assert reloaded is report_generator_module
        assert reloaded.__name__ == "pytest_a11y._internal.reporting.report_generator"


class TestA11yViolationsReportInitialization:
    """Tests for report object initialization."""

    @pytest.mark.parametrize(
        ("output_path", "expected_type"),
        [
            ("report.html", Path),
            (Path("report.html"), Path),
        ],
    )
    def test_init_stores_output_path_page_url_and_empty_violations(
        self,
        output_path: str | Path,
        expected_type: type[Path],
    ) -> None:
        """Store normalized output path, page URL, and empty violations list."""
        report = A11yViolationsReport(
            output_path=output_path,
            page_url="https://example.com",
        )

        assert isinstance(report.output_path, expected_type)
        assert report.output_path == Path("report.html")
        assert report.page_url == "https://example.com"
        assert report.violations == []


class TestAddViolation:
    """Tests for adding violations to the report."""

    def test_add_violation_appends_structured_violation_with_screenshot(self) -> None:
        """Append a normalized violation payload including screenshot data."""
        report = A11yViolationsReport(
            output_path="report.html",
            page_url="https://example.com",
        )
        nodes = [
            _DummyNode(
                selector="#login-button",
                html='<button id="login-button">Login</button>',
                failure_summary="Element has insufficient contrast",
                impact="serious",
            )
        ]

        report.add_violation(
            name="color-contrast",
            summary="[SERIOUS] Insufficient contrast (rule: color-contrast, nodes: 1)",
            help_text="Fix contrast",
            help_url="https://example.com/help/color-contrast",
            nodes=nodes,
            tags=["wcag2aa", "cat.color"],
            screenshot="shots/one.png",
        )

        assert len(report.violations) == 1
        assert report.violations[0] == {
            "name": "color-contrast",
            "summary": "[SERIOUS] Insufficient contrast (rule: color-contrast, nodes: 1)",
            "help": "Fix contrast",
            "help_url": "https://example.com/help/color-contrast",
            "nodes": [
                {
                    "target": "#login-button",
                    "html": '<button id="login-button">Login</button>',
                    "failureSummary": "Element has insufficient contrast",
                    "impact": "serious",
                }
            ],
            "tags": ["wcag2aa", "cat.color"],
            "screenshot": "shots/one.png",
        }

    def test_add_violation_uses_empty_string_when_screenshot_is_none(self) -> None:
        """Store an empty screenshot string when no screenshot is provided."""
        report = A11yViolationsReport(
            output_path="report.html",
            page_url="https://example.com",
        )

        report.add_violation(
            name="rule-id",
            summary="[UNKNOWN] Example summary (rule: rule-id, nodes: 0)",
            help_text="Help text",
            help_url="https://example.com/help",
            nodes=[],
            tags=[],
            screenshot=None,
        )

        assert report.violations[0]["screenshot"] == ""


class TestGenerate:
    """Tests for final HTML generation and severity ordering."""

    @patch.object(A11yViolationsReport, "_render_html")
    def test_generate_creates_parent_directory_and_writes_rendered_html(
        self,
        mock_render_html,
        tmp_path: Path,
    ) -> None:
        """Create parent dirs, render HTML, and write the output file."""
        mock_render_html.return_value = "<html>generated</html>"
        output_path = tmp_path / "nested" / "report.html"
        report = A11yViolationsReport(
            output_path=output_path,
            page_url="https://example.com",
        )

        report.generate()

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>generated</html>"
        mock_render_html.assert_called_once()

    @patch.object(A11yViolationsReport, "_render_html")
    def test_generate_sorts_violations_by_severity_before_rendering(
        self,
        mock_render_html,
        tmp_path: Path,
    ) -> None:
        """Sort violations by severity extracted from summary before rendering."""
        mock_render_html.return_value = "<html>sorted</html>"
        report = A11yViolationsReport(
            output_path=tmp_path / "report.html",
            page_url="https://example.com",
        )
        report.violations = [
            {"summary": "[MINOR] minor", "name": "minor"},
            {"summary": "[CRITICAL] critical", "name": "critical"},
            {"summary": "[SERIOUS] serious", "name": "serious"},
            {"summary": "[MODERATE] moderate", "name": "moderate"},
            {"summary": "no severity markers", "name": "unknown"},
        ]

        report.generate()

        violations_json = mock_render_html.call_args.args[0]
        parsed = json.loads(violations_json)

        assert [item["name"] for item in parsed] == [
            "critical",
            "serious",
            "moderate",
            "minor",
            "unknown",
        ]

    @patch.object(A11yViolationsReport, "_render_html")
    def test_generate_treats_unknown_severity_as_lowest_priority(
        self,
        mock_render_html,
        tmp_path: Path,
    ) -> None:
        """Treat unknown severity labels as lowest priority in sorting."""
        mock_render_html.return_value = "<html>sorted</html>"
        report = A11yViolationsReport(
            output_path=tmp_path / "report.html",
            page_url="https://example.com",
        )
        report.violations = [
            {"summary": "[WEIRD] custom", "name": "custom"},
            {"summary": "[CRITICAL] critical", "name": "critical"},
        ]

        report.generate()

        violations_json = mock_render_html.call_args.args[0]
        parsed = json.loads(violations_json)

        assert [item["name"] for item in parsed] == ["critical", "custom"]


class TestRenderHtml:
    """Tests for top-level HTML rendering."""

    @patch.object(report_generator_module, "datetime")
    @patch.object(A11yViolationsReport, "_render_css")
    @patch.object(A11yViolationsReport, "_render_javascript")
    def test_render_html_embeds_css_javascript_url_and_timestamp(
        self,
        mock_render_javascript,
        mock_render_css,
        mock_datetime,
    ) -> None:
        """Embed CSS, JavaScript, escaped URL, and formatted timestamp in HTML."""
        mock_render_css.return_value = "/* css */"
        mock_render_javascript.return_value = "// js"
        mock_datetime.now.return_value.strftime.return_value = "2026-03-20 12:00:00"

        report = A11yViolationsReport(
            output_path="report.html",
            page_url='https://example.com/?q=<unsafe>&x="1"',
        )

        html = report._render_html("[]")

        assert "<style>" in html
        assert "/* css */" in html
        assert "<script>" in html
        assert "// js" in html
        assert "2026-03-20 12:00:00" in html
        assert "https://example.com/?q=&lt;unsafe&gt;&amp;x=&quot;1&quot;" in html
        assert (
            'href="https://example.com/?q=&lt;unsafe&gt;&amp;x=&quot;1&quot;"' in html
        )

    def test_render_html_contains_expected_structure(self) -> None:
        """Include the expected top-level report containers and modal markup."""
        report = A11yViolationsReport(
            output_path="report.html",
            page_url="https://example.com",
        )

        html = report._render_html("[]")

        assert "<!DOCTYPE html>" in html
        assert 'id="violationsContainer"' in html
        assert 'id="fullscreenModal"' in html
        assert 'id="fullscreenImage"' in html
        assert "A11y Violations Report" in html


class TestRenderCss:
    """Tests for CSS rendering."""

    def test_render_css_contains_key_selectors(self) -> None:
        """Return stylesheet content containing core layout and state selectors."""
        css = A11yViolationsReport._render_css()

        assert ".violation-card" in css
        assert ".violation-header.impact-critical" in css
        assert ".fullscreen.show" in css
        assert "@media (max-width: 968px)" in css
        assert ".no-violations" in css


class TestRenderJavascript:
    """Tests for JavaScript rendering."""

    def test_render_javascript_embeds_json_and_expected_functions(self) -> None:
        """Embed the violations JSON and interactive helper functions."""
        violations_json = '[{"name":"rule1","summary":"[CRITICAL] issue"}]'

        javascript = A11yViolationsReport._render_javascript(violations_json)

        assert "const violations =" in javascript
        assert violations_json in javascript
        assert "function renderViolations()" in javascript
        assert "function toggleViolationDetails(header)" in javascript
        assert "function openFullscreen(event)" in javascript
        assert "function closeFullscreen()" in javascript
        assert "function escapeHtml(text)" in javascript
        assert "renderViolations();" in javascript

    def test_render_javascript_contains_no_violations_and_screenshot_logic(
        self,
    ) -> None:
        """Include branches for no violations, screenshots, and HTML expansion."""
        javascript = A11yViolationsReport._render_javascript("[]")

        assert "No Violations Found" in javascript
        assert "const hasScreenshot = violation.screenshot" in javascript
        assert "View HTML" in javascript
        assert "Violation screenshot" in javascript
        assert "fullscreenModal" in javascript
