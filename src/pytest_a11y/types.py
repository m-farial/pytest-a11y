"""
Type definitions for pytest-a11y accessibility testing.

This module defines all TypedDicts, dataclasses, and type aliases used throughout
the plugin. It serves as the single source of truth for data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict

WCAGLevel = Literal["A", "AA", "AAA"]
Severity = Literal["critical", "serious", "moderate", "minor", "unknown"]


class WCAGReference(TypedDict):
    """WCAG criterion reference."""

    criterion: str  # e.g. "1.1.1"
    level: WCAGLevel
    url: str | None


# ============================================================================
# Raw axe-core result types (from axe.run())
# ============================================================================


class AxeNode(TypedDict, total=False):
    """A single affected DOM node from axe-core."""

    target: list[str]
    html: str
    impact: Severity | None
    failureSummary: str


class AxeViolationRaw(TypedDict, total=False):
    """A raw violation or test result from axe-core."""

    id: str
    description: str
    impact: Severity | None
    help: str
    helpUrl: str
    nodes: list[AxeNode]
    tags: list[str]
    screenshot_path: str | None


class AxeResults(TypedDict):
    """Complete results from axe.run() - raw, unprocessed."""

    violations: list[AxeViolationRaw]
    passes: list[AxeViolationRaw]
    incomplete: list[AxeViolationRaw]
    inapplicable: list[AxeViolationRaw]
    timestamp: str
    url: str


# ============================================================================
# Processed types (fully typed, ready for application use)
# ============================================================================


@dataclass
class Node:
    """Processed DOM node affected by a violation."""

    selector: str  # Primary CSS selector
    html: str  # Element HTML
    failure_summary: str  # Why it failed
    impact: Severity | None


@dataclass
class Violation:
    """
    Processed accessibility violation - ready for reporting or assertions.

    A Violation represents a single type of accessibility issue that affects
    one or more DOM nodes on a page. It includes the rule that was violated,
    description of the issue, and all affected nodes.
    """

    id: str
    description: str
    impact: Severity | None
    help: str
    help_url: str
    nodes: list[Node] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    screenshot_path: str | None = None

    @property
    def summary(self) -> str:
        """
        Generate formatted summary line for display.

        Returns:
            Summary string like "[CRITICAL] Issue description (rule: id, nodes: N)"
        """
        impact_str = (self.impact or "unknown").upper()
        return (
            f"[{impact_str}] {self.description} "
            f"(rule: {self.id}, nodes: {len(self.nodes)})"
        )


@dataclass
class Results:
    """
    Fully processed and typed axe-core accessibility test results.

    This is the primary entry point for working with accessibility test data.
    It provides a clean, typed API over the raw AxeResults from axe-core.
    """

    url: str
    timestamp: str
    violations: list[Violation] = field(default_factory=list)
    passes: list[Violation] = field(default_factory=list)
    incomplete: list[Violation] = field(default_factory=list)
    inapplicable: list[Violation] = field(default_factory=list)

    @property
    def violation_count(self) -> int:
        """Total number of violations found."""
        return len(self.violations)

    @property
    def pass_count(self) -> int:
        """Total number of passed checks."""
        return len(self.passes)

    @property
    def has_violations(self) -> bool:
        """Whether any violations were found."""
        return self.violation_count > 0

    @classmethod
    def from_axe(cls, axe: AxeResults) -> Results:
        """
        Convert raw axe-core results to fully processed format.

        This is the ONLY entry point for processing AxeResults.

        Args:
            axe: Raw results dict from axe.run()

        Returns:
            Results with all data structured and typed
        """

        def _process_node(node: AxeNode) -> Node:
            """Convert raw AxeNode to typed Node."""
            targets = node.get("target", [])
            return Node(
                selector=targets[0] if targets else "unknown",
                html=node.get("html", ""),
                failure_summary=node.get("failureSummary", ""),
                impact=node.get("impact"),
            )

        def _process_violation(raw: AxeViolationRaw) -> Violation:
            """Convert raw violation to typed Violation."""
            return Violation(
                id=raw.get("id", "unknown"),
                description=raw.get("description", ""),
                impact=raw.get("impact"),
                help=raw.get("help", ""),
                help_url=raw.get("helpUrl", ""),
                nodes=[_process_node(n) for n in raw.get("nodes", [])],
                tags=raw.get("tags", []),
                screenshot_path=raw.get("screenshot_path"),
            )

        return cls(
            url=axe.get("url", ""),
            timestamp=axe.get("timestamp", ""),
            violations=[_process_violation(v) for v in axe.get("violations", [])],
            passes=[_process_violation(p) for p in axe.get("passes", [])],
            incomplete=[_process_violation(i) for i in axe.get("incomplete", [])],
            inapplicable=[_process_violation(ia) for ia in axe.get("inapplicable", [])],
        )


# ============================================================================
# Protocols (type hints for external interfaces)
# ============================================================================


class AxeRunnerProtocol(Protocol):
    """
    Protocol (interface) for axe-core runner implementations.

    This protocol defines what methods an axe runner must have.
    The real implementation is in AxeRunner class.
    """

    def run(self) -> AxeResults:
        """
        Run axe-core accessibility checks.

        Returns:
            Complete AxeResults from the check run
        """
        pass

    def violation_count(self, results: AxeResults) -> int:
        """
        Count violations in results.

        Args:
            results: AxeResults from a run

        Returns:
            Total number of violations
        """
        pass

    def pass_count(self, results: AxeResults) -> int:
        """
        Count passed checks in results.

        Args:
            results: AxeResults from a run

        Returns:
            Total number of passed checks
        """
        pass

    def process_results(self, results: AxeResults) -> Results:
        """
        Convert raw axe-core results to structured Results.

        Args:
            results: Raw AxeResults from run()

        Returns:
            Results with structured, typed data
        """
        pass
