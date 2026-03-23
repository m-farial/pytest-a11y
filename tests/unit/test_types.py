from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest_a11y.types as types_module
from pytest_a11y.types import (
    AxeNode,
    AxeResults,
    AxeRunnerProtocol,
    AxeViolationRaw,
    Node,
    Results,
    Violation,
)


class TestTypeModuleImport:
    """Tests for import-time execution in the types module."""

    def test_types_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time declarations execute under coverage."""
        reloaded = importlib.reload(types_module)

        assert reloaded is types_module
        assert reloaded.__name__ == "pytest_a11y.types"


class TestTypeDeclarations:
    """Smoke tests for runtime-visible type declarations."""

    def test_typed_dicts_are_importable(self) -> None:
        """Import the exported TypedDict declarations successfully."""
        assert AxeNode is not None
        assert AxeViolationRaw is not None
        assert AxeResults is not None

    def test_protocol_exposes_expected_methods(self) -> None:
        """Expose the expected protocol method names."""
        assert hasattr(AxeRunnerProtocol, "run")
        assert hasattr(AxeRunnerProtocol, "violation_count")
        assert hasattr(AxeRunnerProtocol, "pass_count")
        assert hasattr(AxeRunnerProtocol, "process_results")


class TestViolation:
    """Tests for the Violation dataclass."""

    def test_summary_uses_uppercase_impact_and_node_count(self) -> None:
        """Build a formatted summary using the impact, rule id, and node count."""
        violation = Violation(
            id="color-contrast",
            description="Insufficient contrast",
            impact="serious",
            help="Fix contrast",
            help_url="https://example.com/help",
            nodes=[
                Node(
                    selector="#login-button",
                    html="<button>Login</button>",
                    failure_summary="Contrast too low",
                    impact="serious",
                )
            ],
        )

        assert (
            violation.summary
            == "[SERIOUS] Insufficient contrast (rule: color-contrast, nodes: 1)"
        )

    def test_summary_uses_unknown_when_impact_is_none(self) -> None:
        """Default the summary label to UNKNOWN when impact is missing."""
        violation = Violation(
            id="rule-id",
            description="Issue description",
            impact=None,
            help="Help text",
            help_url="https://example.com/help",
        )

        assert (
            violation.summary == "[UNKNOWN] Issue description (rule: rule-id, nodes: 0)"
        )


class TestResultsProperties:
    """Tests for Results convenience properties."""

    def test_violation_count_returns_number_of_violations(self) -> None:
        """Return the number of violations."""
        results = Results(
            url="https://example.com",
            timestamp="2026-03-20T12:00:00",
            violations=[
                Violation(
                    id="rule-1",
                    description="Issue 1",
                    impact="minor",
                    help="Help",
                    help_url="https://example.com/help1",
                ),
                Violation(
                    id="rule-2",
                    description="Issue 2",
                    impact="serious",
                    help="Help",
                    help_url="https://example.com/help2",
                ),
            ],
        )

        assert results.violation_count == 2

    def test_pass_count_returns_number_of_passes(self) -> None:
        """Return the number of passes."""
        results = Results(
            url="https://example.com",
            timestamp="2026-03-20T12:00:00",
            passes=[
                Violation(
                    id="pass-1",
                    description="Pass 1",
                    impact=None,
                    help="Help",
                    help_url="https://example.com/help1",
                )
            ],
        )

        assert results.pass_count == 1

    def test_pass_count_returns_zero_when_no_passes_exist(self) -> None:
        """Return zero when no passed checks exist."""
        results = Results(
            url="https://example.com",
            timestamp="2026-03-20T12:00:00",
            passes=[],
        )

        assert results.pass_count == 0

    def test_has_violations_returns_true_when_violations_exist(self) -> None:
        """Return True when at least one violation exists."""
        results = Results(
            url="https://example.com",
            timestamp="2026-03-20T12:00:00",
            violations=[
                Violation(
                    id="rule-1",
                    description="Issue 1",
                    impact="minor",
                    help="Help",
                    help_url="https://example.com/help1",
                )
            ],
        )

        assert results.has_violations is True

    def test_has_violations_returns_false_when_no_violations_exist(self) -> None:
        """Return False when no violations exist."""
        results = Results(
            url="https://example.com",
            timestamp="2026-03-20T12:00:00",
            violations=[],
        )

        assert results.has_violations is False


class TestResultsFromAxe:
    """Tests for Results.from_axe()."""

    def test_from_axe_converts_full_results_structure(self) -> None:
        """Convert rich axe-core data into typed Results, Violation, and Node objects."""
        raw_axe_results: dict[str, Any] = {
            "url": "https://example.com",
            "timestamp": "2026-03-20T12:00:00",
            "violations": [
                {
                    "id": "color-contrast",
                    "description": "Insufficient color contrast",
                    "impact": "serious",
                    "help": "Fix contrast",
                    "helpUrl": "https://example.com/help/color-contrast",
                    "nodes": [
                        {
                            "target": ["#login-button"],
                            "html": '<button id="login-button">Login</button>',
                            "impact": "serious",
                            "failureSummary": "Element has insufficient contrast",
                        }
                    ],
                    "tags": ["wcag2aa", "cat.color"],
                    "screenshot_path": "artifacts/contrast.png",
                }
            ],
            "passes": [
                {
                    "id": "document-title",
                    "description": "Document has a title",
                    "impact": None,
                    "help": "Add title",
                    "helpUrl": "https://example.com/help/document-title",
                    "nodes": [],
                    "tags": ["wcag2a"],
                    "screenshot_path": None,
                }
            ],
            "incomplete": [
                {
                    "id": "landmark-one-main",
                    "description": "Page should have one main landmark",
                    "impact": "moderate",
                    "help": "Check landmarks",
                    "helpUrl": "https://example.com/help/landmark",
                    "nodes": [],
                    "tags": [],
                    "screenshot_path": None,
                }
            ],
            "inapplicable": [
                {
                    "id": "video-caption",
                    "description": "Videos must have captions",
                    "impact": None,
                    "help": "Add captions",
                    "helpUrl": "https://example.com/help/video-caption",
                    "nodes": [],
                    "tags": [],
                    "screenshot_path": None,
                }
            ],
        }

        results = Results.from_axe(raw_axe_results)

        assert results.url == "https://example.com"
        assert results.timestamp == "2026-03-20T12:00:00"

        assert len(results.violations) == 1
        violation = results.violations[0]
        assert violation.id == "color-contrast"
        assert violation.description == "Insufficient color contrast"
        assert violation.impact == "serious"
        assert violation.help == "Fix contrast"
        assert violation.help_url == "https://example.com/help/color-contrast"
        assert violation.tags == ["wcag2aa", "cat.color"]
        assert violation.screenshot_path == "artifacts/contrast.png"

        assert len(violation.nodes) == 1
        node = violation.nodes[0]
        assert node.selector == "#login-button"
        assert node.html == '<button id="login-button">Login</button>'
        assert node.failure_summary == "Element has insufficient contrast"
        assert node.impact == "serious"

        assert len(results.passes) == 1
        assert results.passes[0].id == "document-title"

        assert len(results.incomplete) == 1
        assert results.incomplete[0].id == "landmark-one-main"

        assert len(results.inapplicable) == 1
        assert results.inapplicable[0].id == "video-caption"

    def test_from_axe_uses_defaults_for_missing_fields(self) -> None:
        """Fill in default values when optional raw axe fields are missing."""
        minimal_axe_results: dict[str, Any] = {
            "violations": [
                {
                    "nodes": [{}],
                }
            ]
        }

        results = Results.from_axe(minimal_axe_results)

        assert results.url == ""
        assert results.timestamp == ""
        assert len(results.violations) == 1

        violation = results.violations[0]
        assert violation.id == "unknown"
        assert violation.description == ""
        assert violation.impact is None
        assert violation.help == ""
        assert violation.help_url == ""
        assert violation.tags == []
        assert violation.screenshot_path is None

        node = violation.nodes[0]
        assert node.selector == "unknown"
        assert node.html == ""
        assert node.failure_summary == ""
        assert node.impact is None

    def test_from_axe_uses_unknown_selector_when_target_list_is_empty(self) -> None:
        """Use 'unknown' when a raw node has an empty target list."""
        raw_results: dict[str, Any] = {
            "url": "https://example.com",
            "timestamp": "2026-03-20T12:00:00",
            "violations": [
                {
                    "id": "label",
                    "nodes": [
                        {
                            "target": [],
                            "html": "<input />",
                            "failureSummary": "Missing label",
                            "impact": "critical",
                        }
                    ],
                }
            ],
            "passes": [],
            "incomplete": [],
            "inapplicable": [],
        }

        results = Results.from_axe(raw_results)
        node = results.violations[0].nodes[0]

        assert node.selector == "unknown"
        assert node.html == "<input />"
        assert node.failure_summary == "Missing label"
        assert node.impact == "critical"


class TestAxeRunnerProtocol:
    """Tests for protocol stub method coverage."""

    def test_protocol_stub_methods_are_callable(self) -> None:
        """Execute protocol stub method bodies directly for coverage."""
        dummy = SimpleNamespace()
        raw_results: AxeResults = {
            "violations": [],
            "passes": [],
            "incomplete": [],
            "inapplicable": [],
            "timestamp": "2026-03-20T12:00:00",
            "url": "https://example.com",
        }

        assert AxeRunnerProtocol.run(dummy) is None
        assert AxeRunnerProtocol.violation_count(dummy, raw_results) is None
        assert AxeRunnerProtocol.pass_count(dummy, raw_results) is None
        assert AxeRunnerProtocol.process_results(dummy, raw_results) is None
