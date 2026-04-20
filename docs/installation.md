# Installation Guide

## Prerequisites

Before installing pytest-a11y, ensure you have:

- **Python 3.10 or later** - Check with `python --version`
- **pip or Poetry** - Package manager for Python
- **pytest ≥ 8.0** - Testing framework
- **Selenium ≥ 4.10** - WebDriver bindings

## Installation Methods

### Option 1: Install from PyPI (Recommended)

The simplest way to install pytest-a11y:

```bash
pip install pytest-a11y
```

This installs pytest-a11y and all required dependencies.

### Option 2: Install with Development Dependencies

If you're contributing or want development tools (ruff, mypy, etc.):

```bash
pip install "pytest-a11y[dev]"
```

### Option 3: Install from Git (Development)

To use the latest development version:

```bash
git clone https://github.com/m-farial/pytest-a11y.git
cd pytest-a11y
pip install -e "."
```

With development tools:

```bash
pip install -e ".[dev]"
```

### Option 4: Install with Poetry

In your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
python = "^3.10"
pytest-a11y = "^1.0.0"
```

Then:

```bash
poetry install
```

Or add directly:

```bash
poetry add pytest-a11y
```

## Setting Up Your WebDriver

pytest-a11y works with any Selenium WebDriver. You'll need to provide a `driver` fixture in your test configuration.

### WebDriver Options

#### Option 1: Using webdriver-manager (Recommended)

webdriver-manager automatically downloads and manages drivers:

```bash
pip install webdriver-manager
```

In your test `conftest.py`:

```python
import pytest
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

@pytest.fixture
def driver() -> WebDriver:
    """Provide a Chrome WebDriver for tests."""
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    yield driver
    driver.quit()
```

#### Option 2: Manual Driver Management

If you prefer to manage drivers yourself:

```python
import pytest
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

@pytest.fixture
def driver() -> WebDriver:
    """Provide a Chrome WebDriver for tests."""
    driver = webdriver.Chrome()  # Requires ChromeDriver in PATH
    yield driver
    driver.quit()
```

#### Option 3: Remote WebDriver

For Selenium Grid or cloud providers:

```python
import pytest
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

@pytest.fixture
def driver() -> WebDriver:
    """Provide a remote WebDriver."""
    driver = webdriver.Remote(
        command_executor="http://localhost:4444",
        options=webdriver.ChromeOptions()
    )
    yield driver
    driver.quit()
```

### WebDriver Support

pytest-a11y supports all Selenium WebDriver implementations:
- Chrome/Chromium
- Firefox
- Safari
- Edge
- Internet Explorer (legacy)
- Any Selenium Grid setup

For driver-specific setup instructions, see the [Selenium documentation](https://www.selenium.dev/documentation/).

## Verify Installation

Check that pytest-a11y is installed correctly:

```bash
pytest --version
pytest --fixtures | findstr a11y
```

You should see output mentioning pytest-a11y fixtures and the `axe` fixture.

Or test with a simple script:

```python
# test_installation.py
from pytest_a11y import assert_no_axe_violations

def test_import() -> None:
    """Verify pytest-a11y is installed correctly."""
    assert callable(assert_no_axe_violations)
    print("✅ pytest-a11y installed successfully!")
```

Run it:

```bash
pytest test_installation.py -v
```

## Configure pytest

After installation, set up your project for testing:

### Create conftest.py

Place this in your `tests/` directory:

```python
# tests/conftest.py
import pytest
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

@pytest.fixture
def driver() -> WebDriver:
    """Provide a Chrome WebDriver for tests."""
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    yield driver
    driver.quit()
```

### Configure pytest.ini or pyproject.toml

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
addopts = -v --tb=short
```

Or in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

## Configuration Reference

For accessibility testing configuration (report directory, standards, etc.), see the [README Configuration Section](../README.md#configuration).

Common options:
- `--a11y` - Enable accessibility reports
- `--a11y-dir ./my_reports` - Custom report directory

## Next Steps

1. Create your first test file (see [Quick Start Guide](quickstart.md))
2. Write a simple accessibility test
3. Run with `pytest --a11y`
4. Check the reports in `.a11y_reports/`
5. Review the [README](../README.md) for detailed usage patterns

## Troubleshooting

### ImportError: No module named 'pytest_a11y'

**Solution:** Verify installation:

```bash
pip list | grep pytest-a11y
pip show pytest-a11y
```

If not found, reinstall:

```bash
pip uninstall pytest-a11y
pip install pytest-a11y
```

### "axe fixture not found"

**Solution:** Make sure you have a `driver` fixture in your `conftest.py`. The `axe` fixture requires the `driver` fixture to be available.

### WebDriver issues

**Solution:** Ensure WebDriver matches your browser version. Using `webdriver-manager` handles this automatically. Otherwise, download the correct driver version from:
- [ChromeDriver](https://chromedriver.chromium.org/)
- [GeckoDriver](https://github.com/mozilla/geckodriver)
- [EdgeDriver](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/)

### Environment-specific issues

For Docker or CI environments, ensure:
- Python 3.10+ is available
- Browser binaries are installed (Chrome, Firefox, etc.)
- Display environment is configured for headless testing

See [CI/CD Integration](../README.md#cicd-integration) section in README for Docker and GitHub Actions examples.

## Getting Help

- Review the [Quick Start Guide](quickstart.md) for usage examples
- Check the [README](../README.md) for API reference and patterns
- See [API Reference](api-reference.md) for complete API documentation
- Open an issue on [GitHub](https://github.com/m-farial/pytest-a11y/issues)

---

Next: [Quick Start Guide](quickstart.md)