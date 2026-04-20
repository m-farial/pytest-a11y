# Usage Patterns & Advanced Tips

This guide contains consolidated runnable examples and best practices for using `pytest-a11y`.

> Note: `test_multiple_pages` is best written as a parameterized pytest test so each URL is reported separately. The recommended pattern is shown below.

---

## Driver Fixture

The examples on this page assume a `driver` fixture that provides a Selenium `WebDriver` instance.

```python
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

@pytest.fixture
def driver() -> WebDriver:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-gpu")
    options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=options)
    try:
        yield driver
    finally:
        driver.quit()
```

---

## Runnable Examples

### Simple accessibility scan

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://www.saucedemo.com/")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Critical-only scan

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_critical_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page_critical(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://www.saucedemo.com/")
    results: AxeResults = axe.run()
    assert_no_critical_violations(results)
```

### Inspecting violations before asserting

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import Results, assert_results_no_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_page_with_info(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://www.saucedemo.com/")
    axe_results: AxeResults = axe.run()
    results: Results = Results.from_axe(axe_results)

    if results.has_violations:
        print(f"\nFound {results.violation_count} violations:")
        for violation in results.violations:
            print(f"  {violation.id} ({violation.impact})")
            print(f"    {violation.description}")
            print(f"    Affected nodes: {len(violation.nodes)}")

    assert_results_no_violations(results)
```

### Multiple pages

```python
import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

PAGES_TO_TEST = [
    "https://www.saucedemo.com/",
    "https://www.saucedemo.com/inventory.html",
    "https://www.saucedemo.com/cart.html",
]

@pytest.mark.parametrize("url", PAGES_TO_TEST, ids=["home", "inventory", "cart"])
def test_multiple_pages(driver: WebDriver, axe: AxeRunnerProtocol, url: str) -> None:
    driver.get(url)
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

> Note: Parameterizing page URLs ensures each page is reported as a separate pytest item, which works better for CI and diagnostics.

### Wait for dynamic content

```python
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_with_wait(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://www.saucedemo.com/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.TAG_NAME, "body"))
    )
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Debugging violations

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import Results, assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults, Node

def test_debug_violations(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://www.saucedemo.com/")
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

    assert_no_axe_violations(axe_results)
```

### Viewport testing

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_mobile_viewport(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.set_window_size(390, 844)
    driver.get("https://www.saucedemo.com/")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)


def test_landscape_viewport(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.set_window_size(844, 390)
    driver.get("https://www.saucedemo.com/")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)


def test_tablet_viewport(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.set_window_size(768, 1024)
    driver.get("https://www.saucedemo.com/")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Dark mode testing

```python
from selenium.webdriver.remote.webdriver import WebDriver
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_dark_mode(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    driver.get("https://www.saucedemo.com/")
    driver.execute_script("window.matchMedia('(prefers-color-scheme: dark)').matches = true")
    results: AxeResults = axe.run()
    assert_no_axe_violations(results)
```

### Interaction flow

```python
from pathlib import Path
from selenium.webdriver.common.by import By
from pytest_a11y import assert_no_axe_violations
from pytest_a11y.types import AxeRunnerProtocol, AxeResults

def test_interaction_flow(driver: WebDriver, axe: AxeRunnerProtocol) -> None:
    local_page = Path(__file__).resolve().parent / "integration" / "pages" / "bad.html"
    driver.get(local_page.as_uri())

    results: AxeResults = axe.run()
    assert_no_axe_violations(results)

    driver.find_element(By.CSS_SELECTOR, "input[type='text']").send_keys("test@example.com")
    results = axe.run()
    assert_no_axe_violations(results)

    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    results = axe.run()
    assert_no_axe_violations(results)
```

---

## Sample Report Output

After running with `--a11y`, reports are generated to `.a11y_reports/run_<timestamp>/`.

- `test_<name>_<page_slug>_<hash>.html`
- `test_<name>_<page_slug>_<hash>.json`
- `test_<name>_<page_slug>_<worker_id>_<hash>.html` (when running under `pytest-xdist`, for example `gw0`)
- `test_<name>_<page_slug>_<worker_id>_<hash>.json` (when running under `pytest-xdist`)
- `test_<name>_<hash>.html` / `test_<name>_<worker_id>_<hash>.html` (possible for parameterized test names such as `test_page[...]`, where the page slug segment may be omitted)
- `test_<name>_<hash>.json` / `test_<name>_<worker_id>_<hash>.json` (possible for parameterized test names such as `test_page[...]`)
- `violation_screenshots/`

Report filenames use a normalized page slug derived from the current URL when available, such as `saucedemo_home`, and always include a stable hash suffix to keep names unique. When tests run in parallel with `pytest-xdist`, the worker id is inserted before the hash (for example, `test_login_saucedemo_home_gw0_ab12cd34.html`). For some parameterized pytest item names, the page slug segment may be omitted, so look for both slugged and non-slugged forms when locating artifacts.

---

## Best Practices

- Keep the `driver` fixture reusable and browser-agnostic so tests stay portable.
- Prefer explicit assertions like `assert_no_axe_violations()` for page-level checks and `assert_results_no_violations()` when you want to inspect violations first.
- Parameterize multi-page tests so each URL becomes a separate pytest item and report entry.
- Use stable test URLs or local pages for repeatable CI runs.
- Run `pytest --a11y` only when you need reports; plain `pytest` still executes your Selenium tests without generating HTML/JSON artifacts.

## Getting More Help

- Read `docs/usage.md` for consolidated examples.
- Check `README.md` for installation and high-level usage.
- Review the API docs in `docs/api-reference.md` for available assertions, fixtures, and configuration options.
- If you hit an issue, open an issue in the repository with repro steps and expected behavior.

---

## Command-Line Usage

### Run all accessibility tests

```bash
pytest --a11y
```

### Run with a specific standard

See the full list of supported standards and aliases in the configuration documentation.

```bash
pytest --a11y --a11y-standard wcag2aaa
```

### Run with axe-core tags

You can also pass [raw axe tags](https://github.com/dequelabs/axe-core/blob/develop/doc/API.md#axe-core-tags) via `--a11y-tags`

```bash
pytest --a11y --a11y-tags wcag2aa,best-practice,cat.forms
```

### Run with wcag level

Map to corresponding WCAG level tags: A, AA, AAA.

```bash
pytest --a11y --wcag-level AAA
```
