# Usage Patterns & Advanced Tips

This guide shows practical patterns for using pytest-a11y beyond the basics.

**For the quickest start:** See the [README Quick Start](../README.md#quick-start) section.

---

## Basic Usage Patterns

### Pattern 1: Simple Assertion

```python
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page(axe: AxeRunnerProtocol) -> None:
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Pattern 2: Lenient Check (Critical Only)

```python
from pytest_a11y import assert_no_critical_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page_critical(axe: AxeRunnerProtocol) -> None:
    results: AxeResults = axe.run()
    assert_no_critical_violations(results)  # Ignores minor/moderate
```

### Pattern 3: With Analysis

```python
from pytest_a11y import Results, assert_results_no_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page_with_info(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    print(f"Found {results.violation_count} violations")
    for v in results.violations:
        print(f"  - {v.id}: {v.impact}")
    
    assert_results_no_violations(results)
```

### Pattern 4: Multiple Pages

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_multiple_pages(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    pages: list[str] = [
        "https://example.com",
        "https://example.com/about",
        "https://example.com/contact",
    ]
    
    for url in pages:
        driver.get(url)
        results: AxeResults = axe.run()
        assert_no_axe_violations(results)
```

---

## Advanced Patterns

### Pattern 5: Severity Filtering

```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults, Violation

def test_severity_report(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Group by severity
    by_severity: dict[str, list[Violation]] = {}
    for violation in results.violations:
        severity: str = violation.impact or "unknown"
        by_severity.setdefault(severity, []).append(violation)
    
    # Log summary
    for severity in ["critical", "serious", "moderate", "minor"]:
        count: int = len(by_severity.get(severity, []))
        print(f"{severity}: {count}")
    
    # Fail on critical only
    critical: list[Violation] = by_severity.get("critical", [])
    assert len(critical) == 0, f"Found {len(critical)} critical violations"
```

### Pattern 6: Custom Filtering by Rule

```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults, Violation

def test_specific_rules(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Check only for color contrast issues
    color_violations: list[Violation] = [
        v for v in results.violations 
        if v.id == "color-contrast"
    ]
    
    # Check only for form issues
    form_violations: list[Violation] = [
        v for v in results.violations 
        if "form" in v.id or "label" in v.id
    ]
    
    assert len(color_violations) == 0, f"Found color contrast issues"
    assert len(form_violations) == 0, f"Found form accessibility issues"
```

### Pattern 7: Tag-Based Filtering

```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults, Violation

def test_wcag_specific(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    # Find only WCAG 2.1 Level AAA violations
    wcag_aaa_violations: list[Violation] = [
        v for v in results.violations 
        if "wcag2aaa" in v.tags
    ]
    
    assert len(wcag_aaa_violations) == 0, "Found WCAG 2.1 AAA violations"
```

---

## Sample Report Output

After running with `--a11y`, view the generated report in your browser:

- `.a11y_reports/run_<timestamp>/test_<name>__<branch>__<hash>.html`
- `tests/integration/baselines/test_reporting_artifacts[bad]/report.html` (sample baseline)

Open with:

start .a11y_reports/run_<timestamp>/test_<name>__<branch>__<hash>.html
```

## Common Scenarios

### Scenario 1: Wait for Dynamic Content

```python
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_with_wait(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://example.com/dynamic-page")
    
    # Wait for content to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "loaded"))
    )
    
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Scenario 2: Debugging Violations

```python
from pytest_a11y import Results
from pytest_a11y.types import AxeRunnerProtocol, AxeResults, Node

def test_debug_violations(axe: AxeRunnerProtocol) -> None:
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)
    
    for violation in results.violations:
        print(f"\n{'='*60}")
        print(f"Rule: {violation.id}")
        print(f"Description: {violation.description}")
        print(f"Impact: {violation.impact}")
        print(f"Help: {violation.help}")
        print(f"More info: {violation.help_url}")
        print(f"Nodes affected: {len(violation.nodes)}")
        
        for i, node in enumerate(violation.nodes, 1):
            print(f"\n  Node {i}:")
            print(f"    Selector: {node.selector}")
            print(f"    Issue: {node.failure_summary}")
            print(f"    HTML: {node.html[:100]}...")
```

### Scenario 3: Mobile Testing

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_mobile_viewport(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    # iPhone 12 Pro dimensions
    driver.set_window_size(390, 844)
    
    driver.get("https://example.com")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Scenario 4: Landscape Orientation

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_landscape_viewport(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    # iPhone 12 Pro landscape
    driver.set_window_size(844, 390)
    
    driver.get("https://example.com")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Scenario 5: Tablet Testing

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_tablet_viewport(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    # iPad dimensions
    driver.set_window_size(768, 1024)
    
    driver.get("https://example.com")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Scenario 6: Dark Mode Testing

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_dark_mode(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://example.com")
    
    # Set dark mode preference
    driver.execute_script(
        "window.matchMedia('(prefers-color-scheme: dark)').matches = true"
    )
    
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Scenario 7: User Interaction Flow

```python
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_interaction_flow(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://example.com/form")
    
    # Initial state
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
    
    # After user interaction
    driver.find_element(By.ID, "email-input").send_keys("test@example.com")
    results = axe.run()
    assert_no_axe_violations(results)
    
    # After form submission
    driver.find_element(By.ID, "submit-btn").click()
    results = axe.run()
    assert_no_axe_violations(results)
```

### Scenario 8: Parametrized Testing

```python
import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

PAGES_TO_TEST = [
    "https://example.com",
    "https://example.com/about",
    "https://example.com/contact",
    "https://example.com/products",
]

@pytest.mark.parametrize("url", PAGES_TO_TEST)
def test_all_pages(driver: WebDriver, axe: AxeRunnerProtocol, url: str) -> None:
    driver.get(url)
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

---

## Command-Line Usage

### Run all accessibility tests

```bash
pytest --a11y
```

### Run with specific standard

```bash
pytest --a11y --a11y-standard wcag2aaa
```

### Generate reports in custom directory

```bash
pytest --a11y --a11y-dir reports/a11y/
```

### Run without reports (just assertions)

```bash
pytest  # Note: no --a11y flag
```

### Run specific test file

```bash
pytest tests/test_a11y.py --a11y
```

### Run with verbose output

```bash
pytest --a11y -v
```

### Run in parallel (with pytest-xdist)

```bash
pytest --a11y -n auto
```

---

## Best Practices

1. **Test Multiple Pages** - Don't just test the homepage
2. **Test User Workflows** - Test navigation, form submission, dynamic content
3. **Test Responsive Design** - Check mobile, tablet, and desktop views
4. **Use Type Hints** - All examples show typed code for IDE support
5. **Debug with Results** - Inspect violations before asserting
6. **Start with Critical** - Use `assert_no_critical_violations()` to start
7. **Gradually Increase Strictness** - Move to `assert_no_axe_violations()` over time
8. **CI/CD Integration** - Use `--a11y` flag only in CI, not local dev

---

## Getting More Help

- See [API Reference](api-reference.md) for complete API documentation
- Review [Installation Guide](installation.md) for setup help
- Check the main [README](../README.md) for configuration and advanced features
- Visit [GitHub Issues](https://github.com/m-farial/pytest-a11y/issues) for questions

---

Enjoying pytest-a11y? Star us on [GitHub](https://github.com/m-farial/pytest-a11y)! ⭐