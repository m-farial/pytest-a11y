# Quick Start

Get from zero to your first accessibility test in minutes.

---

## Prerequisites

Before you begin, make sure you have:

- Python 3.10+
- `pytest` 9.0+ installed
- `selenium` installed in your environment
- a browser driver available on `PATH` (for example, ChromeDriver or GeckoDriver)

---

## Installation

```bash
poetry add pytest-a11y
```

---

## Setup

Add a `driver` fixture to your `conftest.py`:

```python
import pytest
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver


@pytest.fixture
def driver() -> WebDriver:
    """Provide a Chrome WebDriver instance for tests."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run without opening a browser window
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()  # Clean up after each test
```

---

## Your First Test

Create a test file, e.g. `tests/test_a11y.py`:

```python
from selenium.webdriver.remote.webdriver import WebDriver

from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol


def test_homepage_accessibility(
    driver: WebDriver,
    axe: AxeRunnerProtocol,
) -> None:
    """Test that the page has no accessibility violations."""
    driver.get("https://www.saucedemo.com/")

    results = axe.run()

    assert_no_axe_violations(results)
```

---

## Run It

Run without reports (plain assertion only):

```bash
pytest tests/test_a11y.py -v
```

Run with HTML and JSON reports generated:

```bash
pytest tests/test_a11y.py --a11y -v
```

---

## Expected Output

A passing test looks like this:

```text
tests/test_a11y.py::test_homepage_accessibility PASSED
```

When run with `--a11y`, reports are written to:

```text
.a11y_reports/run_YYYYMMDD_HHMMSS/
├── violation_screenshots/
├── test_homepage_accessibility_saucedemo_home_abc123d.html
└── test_homepage_accessibility_saucedemo_home_abc123d.json
```

Open the `.html` file in your browser to view the full interactive report.

---

## Next Steps

- [README](../README.md) — full documentation, configuration options, and CI integration
- [docs/api-reference.md](api-reference.md) — available assertions and fixtures
- [docs/usage.md](usage.md) — more runnable examples and patterns
- [CHANGELOG](../CHANGELOG.md) — release history
- [Deque demo site](https://dequeuniversity.com/demo/mars) — a page with intentional violations to test against