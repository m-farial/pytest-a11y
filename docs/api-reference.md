# API Reference

Complete reference for all public APIs in pytest-a11y.

---

## Fixtures

### `axe`

Provides an AxeRunner instance for running accessibility checks.

**Signature:**
```python
def axe(driver: WebDriver) -> AxeRunnerProtocol
```

**Parameters:**
- `driver` (WebDriver): A Selenium WebDriver instance (required fixture)

**Returns:**
- `AxeRunnerProtocol`: An accessibility check runner

**Methods:**

#### `run() -> AxeResults`

Run an accessibility scan on the current page.

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y.types import AxeRunnerProtocol

def test_page(axe: AxeRunnerProtocol) -> None:
    results = axe.run()
    assert isinstance(results, dict)
    assert "violations" in results
```

**Returns:** `AxeResults` - Raw results dictionary from axe-core

#### `violation_count(results: AxeResults) -> int`

Count the total number of violations in results.

```python
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_count(axe: AxeRunnerProtocol) -> None:
    results: AxeResults = axe.run()
    count: int = axe.violation_count(results)
    print(f"Violations: {count}")
```

**Parameters:**
- `results` (AxeResults): Results from `axe.run()`

**Returns:** `int` - Total violation count

**Example:**
```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_homepage(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    # The axe fixture is auto-injected by pytest
    driver.get("https://example.com")
    results: AxeResults = axe.run()
    
    # Check raw violation count
    if axe.violation_count(results) > 0:
        print("Found violations")
    
    # Or use assertions
    assert_no_axe_violations(results)
```

---

## Assertion Functions

All assertions raise `AssertionError` if the check fails. Use in your test functions to validate accessibility.

### `assert_no_axe_violations(results: AxeResults) -> None`

**Purpose:** Assert that no violations exist in raw AxeResults

**Parameters:**
- `results` (AxeResults): Results from `axe.run()`

**Raises:**
- `AssertionError`: If any violations are found

**Behavior:** STRICT - Fails on any violation at any severity level

**Example:**
```python
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_homepage(axe: AxeRunnerProtocol) -> None:
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)  # Raises if violations exist
```

**Use When:**
- You want strict accessibility compliance
- Any violation should block deployment
- Testing critical pages that must be fully accessible

---

### `assert_no_critical_violations(results: AxeResults) -> None`

**Purpose:** Assert that no critical violations exist in raw AxeResults

**Parameters:**
- `results` (AxeResults): Results from `axe.run()`

**Raises:**
- `AssertionError`: If any critical-level violations are found

**Behavior:** LENIENT - Only fails on "critical" impact level. Ignores serious, moderate, and minor violations.

**Example:**
```python
from pytest_a11y import assert_no_critical_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page_lenient(axe: AxeRunnerProtocol) -> None:
    results: AxeResults = axe.run()
    assert_no_critical_violations(results)  # Only critical fails test
```

**Use When:**
- You're starting your a11y testing journey
- Your codebase has many minor issues to fix
- You want to enforce critical accessibility only
- Testing in CI with a phased approach

**Severity Levels:**
- `critical` - Causes complete obstruction to access (FAILS)
- `serious` - Causes significant difficulty (ignored)
- `moderate` - Makes content harder to access (ignored)
- `minor` - Slightly inconvenient to access (ignored)

---

### `assert_results_no_violations(results: Results) -> None`

**Purpose:** Assert that no violations exist in processed Results

**Parameters:**
- `results` (Results): Results from `Results.from_axe(axe_results)`

**Raises:**
- `AssertionError`: If any violations are found

**Behavior:** STRICT - Fails on any violation

**Example:**
```python
from pytest_a11y import Results, assert_results_no_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_with_results(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Can inspect before asserting
    print(f"Violations: {results.violation_count}")
    print(f"Passed: {results.pass_count}")
    
    assert_results_no_violations(results)
```

**Use When:**
- Working with processed, typed Results objects
- You want IDE autocomplete for violation properties
- You need to inspect violations before asserting

---

### `assert_results_no_critical(results: Results) -> None`

**Purpose:** Assert that no critical violations exist in processed Results

**Parameters:**
- `results` (Results): Results from `Results.from_axe(axe_results)`

**Raises:**
- `AssertionError`: If any critical violations are found

**Behavior:** LENIENT - Only fails on critical severity

**Example:**
```python
from pytest_a11y import Results, assert_results_no_critical
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_lenient_with_results(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Log all violations
    if results.has_violations:
        for v in results.violations:
            print(f"{v.id}: {v.impact}")
    
    # Only fail on critical
    assert_results_no_critical(results)
```

**Use When:**
- Using processed Results with critical-only policy
- Need detailed logging before assertion
- Want typed access to violation properties

---

## Types

All types are fully typed for IDE autocompletion and type checking.

### `AxeResults` (TypedDict)

Raw, unprocessed results directly from axe-core.

**Fields:**
- `violations` (list): Violations found
- `passes` (list): Tests that passed
- `incomplete` (list): Tests needing manual review
- `inapplicable` (list): Tests not applicable to page
- `timestamp` (str): ISO 8601 scan timestamp
- `url` (str): URL that was scanned

**Example:**
```python
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_raw_results(axe: AxeRunnerProtocol) -> None:
    results: AxeResults = axe.run()
    
    # Access raw structure
    violations: list = results.get("violations", [])
    passes: list = results.get("passes", [])
    
    print(f"Violations: {len(violations)}")
    print(f"Passed checks: {len(passes)}")
```

---

### `Results` (Dataclass)

Processed, fully typed accessibility test results. Recommended for most use cases.

**Attributes:**
- `url` (str): URL that was scanned
- `timestamp` (str): ISO 8601 scan timestamp
- `violations` (list[Violation]): Violations found
- `passes` (list[Violation]): Tests that passed
- `incomplete` (list[Violation]): Tests needing manual review
- `inapplicable` (list[Violation]): Tests not applicable to page

**Properties:**
- `violation_count` (int): Total violations
- `pass_count` (int): Total passed checks
- `has_violations` (bool): Whether any violations exist

**Class Methods:**

#### `from_axe(axe: AxeResults) -> Results`

Convert raw AxeResults to processed Results.

```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_process(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    print(f"Violations: {results.violation_count}")
    print(f"Passed: {results.pass_count}")
    print(f"Has issues: {results.has_violations}")
```

**Example:**
```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_with_results(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Access properties
    print(f"Page: {results.url}")
    print(f"Tested: {results.timestamp}")
    print(f"Violations: {results.violation_count}")
    print(f"Passed: {results.pass_count}")
    
    # Iterate violations with type hints
    for violation in results.violations:
        print(f"- {violation.id}: {violation.description}")
        
        # Access violation properties with IDE support
        for node in violation.nodes:
            print(f"  Selector: {node.selector}")
```

---

### `Violation` (Dataclass)

Individual accessibility violation with complete details.

**Attributes:**
- `id` (str): Axe rule ID (e.g., "color-contrast")
- `description` (str): Human-readable description
- `impact` (Severity): Severity level
- `help` (str): Help text on how to fix
- `help_url` (str): Link to detailed documentation
- `nodes` (list[Node]): Affected DOM nodes
- `tags` (list[str]): Categorization tags
- `screenshot_path` (str | None): Optional screenshot path

**Properties:**

#### `summary` (str)

Formatted one-line summary of the violation.

```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_summary(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    for v in results.violations:
        print(v.summary)
        # Output: "[CRITICAL] Color contrast is too low (rule: color-contrast, nodes: 5)"
```

**Example:**
```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_violations(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    for violation in results.violations:
        print(f"ID: {violation.id}")
        print(f"Description: {violation.description}")
        print(f"Impact: {violation.impact}")
        print(f"Help: {violation.help}")
        print(f"Affected nodes: {len(violation.nodes)}")
        
        # Access affected elements
        for node in violation.nodes:
            print(f"  - {node.selector}")
            print(f"    HTML: {node.html}")
            print(f"    Why: {node.failure_summary}")
```

---

### `Node` (Dataclass)

Individual DOM node affected by a violation.

**Attributes:**
- `selector` (str): CSS selector for the element
- `html` (str): Element's HTML
- `failure_summary` (str): Why it failed
- `impact` (Severity | None): Impact level

**Example:**
```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_nodes(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    for violation in results.violations:
        for node in violation.nodes:
            print(f"Selector: {node.selector}")
            print(f"HTML: {node.html}")
            print(f"Failed because: {node.failure_summary}")
```

---

### `Severity` (Type Alias)

```python
Severity = Literal["critical", "serious", "moderate", "minor", "unknown"]
```

Impact level of a violation. Use for filtering and categorization.

**Values:**
- `"critical"` - Causes complete obstruction
- `"serious"` - Causes significant difficulty
- `"moderate"` - Makes content harder to access
- `"minor"` - Slightly inconvenient
- `"unknown"` - Unknown impact

**Example:**
```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_severity(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Filter by severity
    critical: list = [v for v in results.violations 
                      if v.impact == "critical"]
    serious: list = [v for v in results.violations 
                     if v.impact == "serious"]
    
    print(f"Critical: {len(critical)}")
    print(f"Serious: {len(serious)}")
```

---

### `WCAGLevel` (Type Alias)

```python
WCAGLevel = Literal["A", "AA", "AAA"]
```

WCAG compliance level.

**Values:**
- `"A"` - Basic accessibility
- `"AA"` - Standard compliance (default)
- `"AAA"` - Enhanced compliance

---

## Protocols

### `AxeRunnerProtocol`

Interface for axe-core runner implementations.

**Methods:**

```python
def run(self) -> AxeResults:
    """Run accessibility checks and return results."""
    ...

def violation_count(self, results: AxeResults) -> int:
    """Count violations in results."""
    ...
```

This is implemented by the `axe` fixture. You typically don't need to implement this yourself.

---

## Complete Example

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import (
    assert_no_axe_violations,
    assert_no_critical_violations,
    Results,
)
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_complete_example(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    """Demonstrate all API features."""
    
    # 1. Navigate to page
    driver.get("https://example.com")
    
    # 2. Run scan
    axe_results: AxeResults = axe.run()
    
    # 3. Use raw results with assertions
    assert_no_axe_violations(axe_results)
    
    # 4. Process to typed Results
    results: Results = Results.from_axe(axe_results)
    
    # 5. Access properties
    print(f"Page: {results.url}")
    print(f"Violations: {results.violation_count}")
    print(f"Passed: {results.pass_count}")
    
    # 6. Inspect violations
    for violation in results.violations:
        print(f"- {violation.id}: {violation.impact}")
        for node in violation.nodes:
            print(f"  {node.selector}")
```

---

For more information, see the [main README](../README.md) for usage patterns, configuration, and advanced examples.