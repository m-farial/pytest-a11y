"""
HTML report generation for a11y violations.

Generates interactive, clickable HTML reports for accessibility violations
with support for per-violation screenshots and detailed node information.
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_a11y.types import Node


# ============================================================================
# Report generation
# ============================================================================


class A11yViolationsReport:
    """
    Generates interactive HTML report for accessibility violations.

    Creates a standalone HTML file with clickable violation cards,
    detailed node information, and optional per-violation screenshots.
    """

    def __init__(self, output_path: str | Path, page_url: str) -> None:
        """
        Initialize report generator.

        Args:
            output_path: File path where HTML report will be written
            page_url: URL of the page that was analyzed
        """
        self.output_path = (
            Path(output_path) if isinstance(output_path, str) else output_path
        )
        self.page_url = page_url
        self.violations: list[dict[str, Any]] = []

    def add_violation(
        self,
        name: str,
        summary: str,
        help_text: str,
        help_url: str,
        nodes: list[Node],
        tags: list[str],
        screenshot: str | None = None,
    ) -> None:
        """
        Add a violation to the report.

        Args:
            name: Violation rule ID (e.g., 'aria-allowed-role')
            summary: Formatted summary (e.g., '[CRITICAL] Description (rule: id, nodes: 5)')
            help: Explanation of the issue
            help_url: URL to detailed documentation
            nodes: List of affected Node objects
            tags: Categorization tags
            screenshot: Path or URL to violation screenshot (optional)
        """
        violation_data = {
            "name": name,
            "summary": summary,
            "help": help_text,
            "help_url": help_url,
            "nodes": [
                {
                    "target": node.selector,
                    "html": node.html,
                    "failureSummary": node.failure_summary,
                    "impact": node.impact,
                }
                for node in nodes
            ],
            "tags": tags,
            "screenshot": screenshot or "",
        }
        self.violations.append(violation_data)

    def generate(self) -> None:
        """
        Generate the interactive HTML report file.

        Creates a standalone HTML file with all violations as clickable cards,
        detailed node information, screenshots (if available), and full interactivity.

        Raises:
            IOError: If file cannot be written to output_path
        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        # ========================================================================
        # SORT VIOLATIONS BY SEVERITY
        # ========================================================================
        # Define severity order mapping
        severity_order = {
            "critical": 0,
            "serious": 1,
            "moderate": 2,
            "minor": 3,
            "unknown": 4,
        }

        # Sort violations by extracting impact level from summary and ordering by severity
        sorted_violations = sorted(
            self.violations,
            key=lambda v: severity_order.get(
                v["summary"].split("[")[1].split("]")[0].lower()
                if "[" in v["summary"] and "]" in v["summary"]
                else "unknown",
                4,
            ),
        )
        # Convert violations to JSON for embedding in HTML
        violations_json = json.dumps(sorted_violations)

        html_content = self._render_html(violations_json)

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _render_html(self, violations_json: str) -> str:
        """
        Render complete HTML document with embedded JavaScript.

        Creates a self-contained HTML file with all CSS and JavaScript
        necessary to display and interact with the report.

        Args:
            violations_json: JSON string of violations data

        Returns:
            Complete HTML document string
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A11y Violations Report</title>
    <style>
        {self._render_css()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>A11y Violations Report</h1>
            <div class="header-meta">
                <div class="header-meta-item">
                    <strong>URL:</strong>
                    <a href="{escape(self.page_url)}" target="_blank" rel="noopener">{escape(self.page_url)}</a>
                </div>
                <div class="header-meta-item">
                    <strong>Generated:</strong>
                    {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                </div>
            </div>
            <div class="summary">
                <div class="summary-card">
                    <strong>Total Violations</strong>
                    <div class="value" id="totalViolations">0</div>
                </div>
            </div>
        </header>

        <div id="violationsContainer"></div>
    </div>

    <div id="fullscreenModal" class="fullscreen">
        <button class="fullscreen-close" onclick="closeFullscreen()">✕</button>
        <img id="fullscreenImage" src="data:," alt="Full size screenshot">
    </div>

    <script>
        {self._render_javascript(violations_json)}
    </script>
</body>
</html>
"""

    @staticmethod
    def _render_css() -> str:
        """
        Render CSS styles for report.

        Returns:
            CSS stylesheet string for the HTML report
        """
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        #violationsContainer {
            padding-left: 30px;
        }

        header {
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        h1 {
            font-size: 2em;
            margin-bottom: 10px;
            color: #222;
        }

        .header-meta {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #e0e0e0;
        }

        .header-meta-item {
            font-size: 0.95em;
            color: #666;
        }

        .header-meta-item strong {
            color: #333;
            margin-right: 8px;
        }

        .header-meta-item a {
            color: #0066cc;
            text-decoration: none;
            word-break: break-all;
        }

        .header-meta-item a:hover {
            text-decoration: underline;
        }

        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
            max-width: 300px;
        }

        .summary-card {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #dc3545;
        }

        .summary-card strong {
            display: block;
            font-size: 0.85em;
            color: #666;
            margin-bottom: 5px;
        }

        .summary-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #222;
        }

        .violation-card {
            background: white;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .violation-header {
            width: 100%;
            font: inherit;
            border: none;
            padding: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background-color 0.2s;
            border-left: 4px solid transparent;
            background: #f9f9f9;
        }

        /* Severity-specific styling */
        .violation-header.impact-critical { border-left-color: #dc3545; } /* red */
        .violation-header.impact-serious  { border-left-color: #fd7e14; } /* orange */
        .violation-header.impact-moderate { border-left-color: #ffc107; } /* amber */
        .violation-header.impact-minor    { border-left-color: #0d6efd; } /* blue */
        .violation-header.impact-unknown  { border-left-color: #6c757d; } /* gray */

        .violation-header:hover {
            background: #f0f0f0;
        }

        .violation-info {
            flex: 1;
        }

        .violation-name {
            font-weight: 600;
            font-size: 1.1em;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .violation-summary {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
            text-align: left;
        }

        .violation-tags {
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
            align-items: flex-start;
        }

        .tag {
            display: inline-block;
            background-color: #e7f3ff;
            color: #0066cc;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 500;
        }

        .toggle {
            display: inline-block;
            width: 6px;
            height: 6px;
            background: #0066cc;
            border-radius: 2px;
            transition: transform 0.3s;
            margin-right: 5px;
        }

        .violation-header.expanded .toggle {
            transform: rotate(90deg);
        }

        .violation-details {
            display: none;
            border-top: 1px solid #e0e0e0;
        }

        .violation-details.show {
            display: block;
        }

        .details-content {
            padding: 30px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }

        .details-text {
            overflow-y: auto;
            max-height: 700px;
        }

        .details-section {
            margin-bottom: 25px;
        }

        .details-section h3 {
            font-size: 0.95em;
            font-weight: 600;
            color: #222;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #666;
        }

        .help-content {
            background: #e8f4f8;
            border-left: 3px solid #0066cc;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 15px;
            line-height: 1.6;
        }

        .learn-more {
            background: #f0f8ff;
            border-left: 3px solid #0066cc;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 15px;
        }

        .learn-more a {
            color: #0066cc;
            text-decoration: none;
            word-break: break-all;
            font-size: 0.9em;
        }

        .learn-more a:hover {
            text-decoration: underline;
        }

        .nodes-list {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .node-item {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            border-left: 3px solid #ffc107;
        }

        .node-item strong {
            display: block;
            margin-bottom: 8px;
            color: #333;
        }

        .node-selector {
            background-color: #e9ecef;
            padding: 8px 12px;
            border-radius: 3px;
            font-family: monospace;
            color: #d63384;
            font-size: 0.85em;
            word-break: break-all;
            margin-bottom: 8px;
        }

        .node-issue {
            color: #666;
            font-size: 0.9em;
            line-height: 1.5;
            margin-bottom: 8px;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .node-html-details {
            margin-top: 8px;
        }

        .node-html-details summary {
            cursor: pointer;
            font-weight: 500;
            color: #0066cc;
            padding: 8px 0;
            user-select: none;
        }

        .node-html-details summary:hover {
            text-decoration: underline;
        }

        .node-html-details pre {
            background-color: #2d2d2d;
            color: #f8f8f2;
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.8em;
            line-height: 1.4;
            margin-top: 8px;
        }

        .node-html-details code {
            font-family: 'Courier New', monospace;
        }

        .details-screenshot {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .screenshot-container {
            position: relative;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
        }

        .screenshot-container img {
            width: 100%;
            height: auto;
            display: block;
            cursor: zoom-in;
            transition: transform 0.2s;
        }

        .screenshot-container img:hover {
            transform: scale(1.02);
        }

        .screenshot-label {
            font-size: 0.85em;
            color: #666;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #e0e0e0;
        }

        .fullscreen {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .fullscreen.show {
            display: flex;
        }

        .fullscreen img {
            max-width: 90vw;
            max-height: 90vh;
            object-fit: contain;
        }

        .fullscreen-close {
            position: absolute;
            top: 20px;
            right: 20px;
            background: white;
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 4px;
            font-size: 24px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1001;
        }

        .no-violations {
            background: white;
            padding: 40px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .no-violations h2 {
            color: #28a745;
            margin-bottom: 10px;
        }

        @media (max-width: 968px) {
            .details-content {
                grid-template-columns: 1fr;
            }

            .violation-tags {
                flex-direction: column;
            }
        }
        """

    @staticmethod
    def _render_javascript(violations_json: str) -> str:
        """
        Render JavaScript for interactive report functionality.

        Provides rendering logic, event handlers, and HTML escaping.

        Args:
            violations_json: JSON string of violations data

        Returns:
            JavaScript code string
        """
        # Note: Using regular string concatenation to avoid f-string complexity
        # with nested template literals in JavaScript
        javascript = (
            """
        const violations = """
            + violations_json
            + r""";

        function renderViolations() {
            const container = document.getElementById('violationsContainer');

            if (violations.length === 0) {
                container.innerHTML = `
                    <div class="no-violations">
                        <h2>✓ No Violations Found</h2>
                        <p>Great! The page passed all accessibility checks.</p>
                    </div>
                `;
                document.getElementById('totalViolations').textContent = '0';
                return;
            }

            violations.forEach((violation, index) => {
                const violationElement = document.createElement('div');
                violationElement.className = 'violation-card';
                const hasScreenshot = violation.screenshot && violation.screenshot.trim() !== '';
                const impactClass = `impact-${violation.summary.match(/\[(.*?)\]/)?.[1]?.toLowerCase() || 'unknown'}`;

                const nodesHtml = violation.nodes.map((node, nodeIdx) => `
                    <div class="node-item">
                        <strong>Node ${nodeIdx + 1}</strong>
                        <div class="node-selector">${escapeHtml(node.target || 'unknown')}</div>
                        <div class="node-issue">${escapeHtml(node.failureSummary || 'No details available')}</div>
                        ${node.html ? `<div class="node-html-details">
                            <details>
                                <summary>View HTML</summary>
                                <pre><code>${escapeHtml(node.html)}</code></pre>
                            </details>
                        </div>` : ''}
                    </div>
                `).join('');

                violationElement.innerHTML = `
                    <button class="violation-header ${impactClass}" onclick="toggleViolationDetails(this)"aria-expanded="false">
                        <div class="violation-info">
                            <div class="violation-name">
                                <span class="toggle"></span>
                                <strong>${escapeHtml(violation.name)}</strong>
                            </div>
                            <div class="violation-summary">${escapeHtml(violation.summary)}</div>
                            <div class="violation-tags">
                                ${violation.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                            </div>
                        </div>
                    </button>
                    <div class="violation-details">
                        <div class="details-content" style="grid-template-columns: ${hasScreenshot ? '1fr 1fr' : '1fr'};">
                            <div class="details-text">
                                <div class="details-section">
                                    <h3>Help</h3>
                                    <div class="help-content">
                                        ${escapeHtml(violation.help)}
                                    </div>
                                </div>

                                <div class="details-section">
                                    <h3>Learn More</h3>
                                    <div class="learn-more">
                                        <a href="${escapeHtml(violation.help_url)}" target="_blank" rel="noopener noreferrer">
                                            ${escapeHtml(violation.help_url)}
                                        </a>
                                    </div>
                                </div>

                                <div class="details-section">
                                    <h3>Affected Nodes (${violation.nodes.length})</h3>
                                    <div class="nodes-list">
                                        ${nodesHtml}
                                    </div>
                                </div>
                            </div>
                            ${hasScreenshot ? `<div class="details-screenshot">
                                <div class="screenshot-container">
                                    <img src="${escapeHtml(violation.screenshot)}" alt="Violation screenshot" onclick="openFullscreen(event)">
                                </div>
                                <div class="screenshot-label">
                                    Screenshot of violation
                                </div>
                            </div>` : ''}
                        </div>
                    </div>
                `;
                container.appendChild(violationElement);
            });

            document.getElementById('totalViolations').textContent = violations.length;
        }

        function toggleViolationDetails(header) {
            const isExpanded = header.classList.toggle('expanded');
            header.setAttribute('aria-expanded', isExpanded);
            const details = header.nextElementSibling;
            details.classList.toggle('show');
        }

        function openFullscreen(event) {
            event.stopPropagation();
            const modal = document.getElementById('fullscreenModal');
            const img = document.getElementById('fullscreenImage');
            img.src = event.target.src;
            modal.classList.add('show');
        }

        function closeFullscreen() {
            document.getElementById('fullscreenModal').classList.remove('show');
        }

        function escapeHtml(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return String(text).replace(/[&<>"']/g, m => map[m]);
        }

        renderViolations();

        document.getElementById('fullscreenModal').addEventListener('click', (e) => {
            if (e.target.id === 'fullscreenModal') {
                closeFullscreen();
            }
        });
        """
        )
        return javascript
