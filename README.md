# pytest-a11y

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![pytest](https://img.shields.io/badge/pytest-%3E%3D8.0-green.svg)](https://pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **pytest plugin** for automated accessibility testing with [axe-core](https://github.com/dequelabs/axe-core), providing:

- 🎯 **Automated Scans** - Run axe-core accessibility checks on every page load
- 📊 **Rich Reports** - HTML, JSON, and screenshot reports (when `--a11y` flag enabled)
- 📸 **Visual Overlays** - Screenshot highlights showing exactly where violations occur
- 🧵 **Parallel-Safe** -  Compatible with `pytest-xdist` for parallel test execution 
- 🔌 **Framework Agnostic** - Works with any Selenium-based test suite
- ✅ **Optional** - Run accessibility checks or regular tests without the flag  

Perfect for teams that want to **shift accessibility testing left** and catch issues early in the development process.

*Sample pytest-a11y report:*

[![Sample pytest-a11y report](docs/sample_a11y_report.gif)](docs/sample_a11y_report.gif)
---

## Quick Start

### 1. Install

```bash
pip install pytest-a11y
```

Or with Poetry:

```bash
poetry add pytest-a11y
```

```toml
[tool.poetry.dependencies]
pytest-a11y = "^0.1.0"
```

### 2. Write a Test

```python
from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol


def test_homepage_accessibility(
    driver: WebDriver,
    axe: AxeRunnerProtocol,
) -> None:
    """Test that the homepage has no accessibility violations."""
    driver.get("https://www.saucedemo.com/")
    
    # Run accessibility checks
    results = axe.run()
    
    # Assert no violations found
    assert_no_axe_violations(results)
```

### 2.1 Configure Standards and Aliases

`pytest-a11y` accepts both canonical and alias values for `--a11y-standard` / `a11y_standard`:

- canonical: `wcag2a`, `wcag2aa`, `wcag2aaa`, `wcag21a`, `wcag21aa`, `wcag22aa`, `section508`
- aliases: `wcag2.0:a`, `wcag2.0:aa`, `wcag2.0:aaa`, `wcag2.1:a`, `wcag2.1:aa`, `wcag2.2:aa`

Example:

```bash
pytest tests/test_a11y.py --a11y --a11y-standard wcag2.1:aa -v
```

Invalid values raise `pytest.UsageError` and include supported options in the message.

### 2.2 Configure custom axe tags

You can also pass [raw axe tags](https://github.com/dequelabs/axe-core/blob/develop/doc/API.md#axe-core-tags) via `--a11y-tags` instead of a standard mapping:

```bash
pytest tests/test_a11y.py --a11y --a11y-tags best-practice,cat.forms -v
```

### 3. Run Without Reports

```bash
pytest tests/test_a11y.py -v
```

**Output:**
```
tests/test_a11y.py::test_homepage_accessibility PASSED
```

Simple assertion - no reports generated.

### 4. Run With Reports

```bash
pytest tests/test_a11y.py --a11y -v
```

**Output:**
```
tests/test_a11y.py::test_homepage_accessibility PASSED
```

Reports automatically generated in `.a11y_reports/run_YYYYMMDD_HHMMSS/`:
- `test_homepage_accessibility__master__abc123d.html` - Interactive HTML report with screenshots
- `test_homepage_accessibility__master__abc123d.json` - Machine-readable JSON report
- `violation_screenshots/` - Individual screenshots of each violation

[![Sample report structure](docs/a11y_report_structure.png)](docs/a11y_report_structure.png)
---

## Design & Key Concepts

### One Fixture: `axe`

The `axe` fixture provides an accessibility checker bound to your WebDriver:

```python
def test_page(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://example.com")
    results = axe.run()
    # results is AxeResults - dict-like structure from axe-core
```

**That's it.** No special fixture for reports, no fixture selection needed.

### Simple Assertions

Choose the assertion that matches your needs:

```python
# Fail on ANY violation
from pytest_a11y import assert_no_axe_violations

results = axe.run()
assert_no_axe_violations(results)
```

```python
# Fail on CRITICAL violations only (allow minor issues)
from pytest_a11y import assert_no_critical_violations

results = axe.run()
assert_no_critical_violations(results)
```

```python
# Use structured Results for inspection first
from pytest_a11y import Results, assert_results_no_violations

results = axe.run()
processed = Results.from_axe(results)

print(f"Found {processed.violation_count} violations")
for violation in processed.violations:
    print(f"  - {violation.id}: {violation.impact}")

assert_results_no_violations(processed)
```

### Optional Reports

Reports are **only generated when you use the `--a11y` flag**:

```bash
# No reports - just assertions
pytest tests/ -v

# With reports - HTML, JSON, screenshots
pytest tests/ --a11y -v
```

The assertion functions automatically detect the `--a11y` flag and generate reports if enabled.

**No fixture selection needed. Same code works both ways.**

### Configuring report output directory

You can control where reports are written using multiple configuration layers (highest precedence first):

- `config.option.a11y_reports` (programmatic override, e.g. in `conftest.py`)
- `--a11y-dir` CLI option
- `a11y_reports` in `pytest.ini`
- `A11Y_DIR` environment variable
- default: `.a11y_reports`

When `pytest_configure` runs:

1. If `config.a11y_session_dir` exists (set externally), that path is used directly and normalized.
2. Otherwise, the directory is resolved using the configuration priority above and a timestamped subfolder is created:
   - `<a11y_dir>/run_YYYYMMDD_HHMMSS`
3. `config.a11y_dir` is the root folder and `config.a11y_session_dir` is the specific run folder.

Only when `--a11y` is enabled does the plugin create the session directory and generate reports.

### a11y standard tags and alias support

The `--a11y-standard` CLI option and `a11y_standard` `pytest.ini` value accept both canonical and aliased WCAG standard tags.

Supported canonical values:

- `wcag2a`
- `wcag2aa`
- `wcag2aaa`
- `wcag21a`
- `wcag21aa`
- `wcag22aa`
- `section508`

Supported aliases:

- `wcag2.0:a` → `wcag2a`
- `wcag2.0:aa` → `wcag2a, wcag2aa`
- `wcag2.0:aaa` → `wcag2a, wcag2aa, wcag2aaa`
- `wcag2.1:a` → `wcag21a`
- `wcag2.1:aa` → `wcag21a, wcag21aa`
- `wcag2.2:aa` → `wcag2aa, wcag21aa, wcag22aa`

When the value is invalid, pytest-a11y raises a `pytest.UsageError` with a clear message:

- `Invalid value for --a11y-standard/a11y_standard '<value>'. Supported values: ...`

---

## API Reference

### Fixtures

#### `axe: AxeRunnerProtocol`

Provides an accessibility checker bound to the WebDriver.

**Methods:**

```python
# Run axe-core checks on current page
results: AxeResults = axe.run()

# Count violations
count: int = axe.violation_count(results)

# Count passed checks
count: int = axe.pass_count(results)

# Count incomplete checks (need manual review)
count: int = axe.incomplete_count(results)

# Check if any violations exist
has_issues: bool = axe.has_violations(results)

# Convert to structured Results
structured: Results = axe.process_results(results)
```

### Assertions

#### `assert_no_axe_violations(results: AxeResults) -> None`

Assert that no violations exist in the results.

- **Reports:** Auto-generated if `--a11y` flag enabled
- **Fails on:** Any violation
- **Use when:** You want strict accessibility compliance

```python
results = axe.run()
assert_no_axe_violations(results)
# Reports auto-generated to .a11y_reports/ if --a11y used
```

#### `assert_no_critical_violations(results: AxeResults) -> None`

Assert that no critical-severity violations exist.

- **Reports:** Auto-generated if `--a11y` flag enabled
- **Fails on:** Only critical violations (allows serious, moderate, minor)
- **Use when:** You're working on compliance gradually

```python
results = axe.run()
assert_no_critical_violations(results)
# Only fails on critical issues; reports still generated
```

#### `assert_results_no_violations(results: Results) -> None`

Assert that a processed Results object has no violations.

- **Reports:** Not auto-generated (use with raw results for reports)
- **Input:** Results object (from `Results.from_axe()`)
- **Use when:** You're inspecting results before asserting

```python
axe_results = axe.run()
results = Results.from_axe(axe_results)

if results.has_violations:
    print(f"Found {results.violation_count} violations")

assert_results_no_violations(results)
```

#### `assert_results_no_critical(results: Results) -> None`

Assert that no critical violations exist in a Results object.

```python
axe_results = axe.run()
results = Results.from_axe(axe_results)
assert_results_no_critical(results)
```

### Types

All types are fully typed for IDE autocompletion and type checking.

#### `AxeResults`

Raw output from axe-core (TypedDict):

```python
from pytest_a11y.types import AxeResults

results: AxeResults = axe.run()

# Available keys
violations: list = results["violations"]
passes: list = results["passes"]
incomplete: list = results["incomplete"]
inapplicable: list = results["inapplicable"]
timestamp: str = results["timestamp"]
url: str = results["url"]
```

#### `Results`

Processed, structured results (dataclass):

```python
from pytest_a11y.types import Results

axe_results: AxeResults = axe.run()
results: Results = Results.from_axe(axe_results)

# Properties
print(results.violation_count)  # int
print(results.pass_count)       # int
print(results.has_violations)   # bool
print(results.url)              # str
print(results.timestamp)        # str

# Lists of violations
for violation in results.violations:
    print(violation.id)          # rule ID like "color-contrast"
    print(violation.description) # human-readable description
    print(violation.impact)      # "critical", "serious", "moderate", "minor"
    
    for node in violation.nodes:
        print(node.selector)     # CSS selector
        print(node.html)         # element HTML
```

#### `AxeRunnerProtocol`

Interface for the axe fixture:

```python
from pytest_a11y.types import AxeRunnerProtocol

def test_example(axe: AxeRunnerProtocol) -> None:
    results = axe.run()
    # Full type hints for IDE autocompletion
```

---

## Configuration

### Custom Report Directory

```bash
pytest tests/ --a11y --a11y-dir ./my_reports -v
```

Or set via environment variable:

```bash
export A11Y_DIR=./my_reports
pytest tests/ --a11y -v
```

Or in `pytest.ini`:

```ini
[pytest]
a11y_reports = ./my_reports
```

Or in `conftest.py`:

```python
def pytest_configure(config):
    config.option.a11y_reports = "./my_reports"
```

**Configuration Priority** (highest to lowest):
1. conftest.py
2. CLI `--a11y-dir`
3. pytest.ini
4. Environment variable `A11Y_DIR`
5. Default `.a11y_reports`

### Parallel Testing with xdist

Works seamlessly with `pytest-xdist`:

```bash
pytest tests/ --a11y -n auto -v
```

Filenames are automatically safeguarded for parallel execution.

### Accessibility Standards

Supports multiple accessibility standards:

- **wcag2a** - WCAG 2.0 Level A (minimum compliance)
- **wcag2aa** - WCAG 2.0 Level AA (standard compliance) - **Default**
- **wcag2aaa** - WCAG 2.0 Level AAA (enhanced compliance)
- **section508** - Section 508 Amendment (US federal requirement)

Specify in config or CLI:

```bash
pytest --a11y --a11y-standard wcag2aa
pytest --a11y --wcag-level AA
pytest --a11y --a11y-tags wcag21a,wcag21aa,ACT,cat.forms
```

---

## Examples

### Basic Test

```python
from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol


def test_homepage(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    """Simple accessibility test."""
    driver.get("https://www.saucedemo.com/")
    results = axe.run()
    assert_no_axe_violations(results)
```

Run:
```bash
pytest tests/test_a11y.py -v                # No reports
pytest tests/test_a11y.py --a11y -v         # With reports
```

### Multiple Pages

```python
def test_all_pages(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    """Test multiple pages for accessibility."""
    pages = [
        "https://www.saucedemo.com/",
        "https://www.saucedemo.com/inventory.html",
        "https://www.saucedemo.com/cart.html",
    ]
    
    for page_url in pages:
        driver.get(page_url)
        results = axe.run()
        assert_no_axe_violations(results)
```

Each page gets its own report (if `--a11y` enabled).

### Lenient Checking

```python
from pytest_a11y import assert_no_critical_violations

def test_allow_minor_issues(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    """Allow minor issues, fail on critical."""
    driver.get("https://www.saucedemo.com/")
    results = axe.run()
    assert_no_critical_violations(results)  # Only critical failures
```

Useful when fixing accessibility incrementally.

### Inspecting Violations

```python
def test_with_inspection(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    """Inspect violations before asserting."""
    driver.get("https://www.saucedemo.com/")
    
    axe_results = axe.run()
    results = Results.from_axe(axe_results)
    
    # Inspect first
    if results.has_violations:
        print(f"\nFound {results.violation_count} violations:")
        for violation in results.violations:
            print(f"  {violation.id} ({violation.impact})")
            print(f"    {violation.description}")
            print(f"    Affected nodes: {len(violation.nodes)}")
    
    # Then assert
    assert_results_no_violations(results)
```

### Severity Filtering

```python
def test_severity_report(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    """Report violations by severity."""
    driver.get("https://www.saucedemo.com/")
    
    axe_results = axe.run()
    results = Results.from_axe(axe_results)
    
    # Group by severity
    by_severity = {}
    for violation in results.violations:
        severity = violation.impact or "unknown"
        by_severity.setdefault(severity, []).append(violation)
    
    # Log summary
    for severity in ["critical", "serious", "moderate", "minor"]:
        count = len(by_severity.get(severity, []))
        print(f"{severity}: {count}")
    
    # Fail on critical
    critical = by_severity.get("critical", [])
    assert len(critical) == 0, f"Found {len(critical)} critical violations"
```

---

## Reports

When using `--a11y`, reports are generated to `.a11y_reports/run_YYYYMMDD_HHMMSS/`:

### HTML Report

Interactive report with:
- ✓ Violation list with details
- ✓ Screenshots of affected areas
- ✓ WCAG references
- ✓ Pass/fail/incomplete breakdown
- ✓ Timestamp and URL

Open in browser: `open .a11y_reports/run_*/test_*.html`

### JSON Report

Machine-readable report for CI/CD integration:

```json
{
  "test_name": "test_homepage",
  "timestamp": "2026-02-14T15:30:22",
  "url": "https://example.com",
  "violation_count": 3,
  "violations": [
    {
      "id": "color-contrast",
      "impact": "serious",
      "description": "...",
      "nodes": [...]
    }
  ]
}
```

### Violation Screenshots

Individual screenshots for each violation in `violation_screenshots/`:
- `0_color-contrast.png`
- `1_alt-text.png`
- etc.

---

## CLI Options

```bash
# Enable accessibility checks and report generation
pytest tests/ --a11y -v

# Custom report directory
pytest tests/ --a11y --a11y-dir ./my_reports -v

# Parallel execution (compatible with xdist)
pytest tests/ --a11y -n auto -v

# Only show certain markers
pytest tests/ -m "a11y" -v

# Don't capture output (for debugging)
pytest tests/ --a11y -s -v
```

---

## Debugging

### See All Available Fixtures

```bash
pytest --fixtures | grep axe
```

Should show:
```
axe -- pytest_a11y/axe/fixtures.py:X: Provide a ready-to-run axe-core runner.
```

### Debug with pdb

Add breakpoint to your test:

```python
def test_page(driver, axe):
    driver.get("https://example.com")
    import pdb; pdb.set_trace()  # Pauses here
    results = axe.run()
```

Run with `-s` flag:

```bash
pytest tests/test_a11y.py -s -v
```

### Debug on Failure

```bash
pytest tests/test_a11y.py --pdb -v
```

Automatically breaks in pdb when test fails.

### See Logs

```bash
pytest tests/test_a11y.py -v --log-cli-level=DEBUG
```

Shows detailed logging output during test execution.

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Accessibility Tests

on: [push, pull_request]

jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      
      - run: pip install -e ".[dev]"
      - run: pytest --a11y
      
      - name: Upload Reports
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: a11y-reports
          path: .a11y_reports/
```

### GitLab CI

```yaml
accessibility:
  image: python:3.10
  script:
    - pip install -e ".[dev]"
    - pytest --a11y
  artifacts:
    paths:
      - .a11y_reports/
    when: always
```

---

## Development

### Local Development Setup

Clone the repository and install in editable mode:

```bash
git clone https://github.com/m-farial/pytest-a11y.git
cd pytest-a11y
poetry install

# In your test project
poetry add pytest-a11y = {path = "../pytest-a11y", develop = true}
poetry install
```

### Running Tests

```bash
poetry run pytest tests/ -v              # Run tests
poetry run pytest tests/ --a11y -v       # Run with reports
poetry run poe check                     # Format, lint, type-check
```

### Code Quality

```bash
poetry run ruff format .                 # Format code
poetry run ruff check . --fix            # Lint and fix
poetry run mypy src                      # Type check
```

---

## Troubleshooting

### "fixture 'axe' not found"

Make sure `pytest_a11y/conftest.py` exists in the pytest-a11y package:

```python
# pytest_a11y/conftest.py
from pytest_a11y.axe.fixtures import axe  # noqa: F401
```

Then rebuild:

```bash
poetry lock --no-update
poetry install
```

### Reports not generating

Make sure you use the `--a11y` flag:

```bash
pytest tests/ --a11y -v    # ✓ Reports generated
pytest tests/ -v           # ✗ No reports
```

### "driver fixture not found"

You need to provide a WebDriver fixture. Example:

```python
# conftest.py
import pytest
from selenium import webdriver


@pytest.fixture
def driver():
    """Provide a Selenium WebDriver."""
    driver = webdriver.Chrome()
    yield driver
    driver.quit()
```

---

## License

MIT - See LICENSE file

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests
4. Submit a pull request

## See Also

- [axe-core](https://github.com/dequelabs/axe-core) - The accessibility checker
- [axe-selenium-python](https://github.com/dequelabs/axe-selenium-python) - Python wrapper
- [pytest](https://pytest.org) - The testing framework
- [Selenium](https://www.selenium.dev) - Web browser automation

## Support

For issues and questions, please see [GitHub Issues](https://github.com/m-farial/pytest-a11y/issues).
