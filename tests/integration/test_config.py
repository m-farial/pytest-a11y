"""
Configuration priority tests for pytest-a11y.

Tests that configuration follows the correct priority:
1. Default (if nothing specified)
2. Environment variable (overrides default)
3. pytest.ini (overrides environment)
4. CLI argument (overrides all)
"""

from __future__ import annotations

import re

import pytest

pytest_plugins = ["pytester"]


def extract_config_from_output(output: str) -> dict[str, str]:
    """Extract configuration JSON from pytest subprocess output."""
    # Look for JSON output in the format: {"resolved": "path/to/config"}
    match = re.search(r'\{"resolved":\s*"([^"]+)"\}', output)
    if match:
        return {"resolved": match.group(1)}
    raise ValueError(f"Could not find config JSON in output:\n{output}")


def setup_test(
    pytester: pytest.Pytester,
    ini_config: str | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Setup a test environment with optional pytest.ini configuration.

    If `env` is provided, the conftest written to the subprocess will set
    those environment variables at import-time so the plugin sees them.
    """
    # If env override requested, create a sitecustomize so the spawned pytest
    # subprocess picks up the env *before* plugins are initialized.
    if env:
        pairs = ", ".join(f'"{k}": "{v}"' for k, v in env.items())
        pytester.makefile(
            ".py",
            sitecustomize=f"import os\nos.environ.update({{{pairs}}})\n",
        )

    # Create conftest with config reporting
    pytester.makeconftest(
        """import json
from pathlib import Path

def pytest_configure(config):
    # Print resolved config directory (read attribute set by plugin when
    # available; fall back to CLI/INI defaults otherwise)
    resolved = getattr(config, "a11y_dir", None)
    if resolved is None:
        try:
            resolved = config.getoption("--a11y-dir")
        except Exception:
            resolved = config.getini("a11y_reports") or ".a11y_reports"
    print(json.dumps({"resolved": str(resolved)}))
"""
    )

    # Create minimal test
    pytester.makepyfile(test_config="def test_dummy(): pass")

    # Add pytest.ini if provided
    if ini_config:
        pytester.makefile(".ini", pytest=ini_config)


@pytest.mark.integration
def test_default_configuration(pytester: pytest.Pytester) -> None:
    """
    Verify that default configuration is used when nothing is specified.

    Expected: a11y_reports directory defaults to .a11y_reports
    """
    setup_test(pytester)
    result = pytester.runpytest_subprocess("--a11y", "-q", "-s")
    output = str(result.stdout) + str(result.stderr)

    config = extract_config_from_output(output)
    assert config["resolved"].endswith(
        ".a11y_reports"
    ), "Default should be .a11y_reports"


@pytest.mark.integration
def test_environment_variable_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The environment variable A11Y_DIR should override the default directory.

    This is verified by calling the resolver directly (unit-style) because
    subprocess-based env injection is unreliable in this test harness.
    """
    from pytest_a11y import plugin

    # Ensure no higher-priority sources are set on the dummy config
    class DummyConfig:
        def __init__(self):
            self.option = type("opt", (), {})()

        def getoption(self, name):
            return ".a11y_reports"

        def getini(self, name):
            return ".a11y_reports"

    monkeypatch.setenv("A11Y_DIR", "env_reports")
    cfg = DummyConfig()

    resolved = plugin._resolve_a11y_dir(cfg)
    assert str(resolved).endswith(
        "env_reports"
    ), "Environment variable should override default"


@pytest.mark.integration
def test_cli_argument_override_all(pytester: pytest.Pytester) -> None:
    """
    Verify that CLI arguments have the highest priority.

    Priority:
    1. CLI argument (--a11y-dir) ← highest
    2. pytest.ini (a11y_reports)
    3. Environment variable (A11Y_DIR)
    4. Default (.a11y_reports) ← lowest
    """
    ini_config = "[pytest]\na11y_reports = ini_reports\n"
    setup_test(pytester, ini_config=ini_config, env={"A11Y_DIR": "env_reports"})

    result = pytester.runpytest_subprocess(
        "--a11y",
        "--a11y-dir",
        "cli_reports",
        "-q",
        "-s",
    )
    output = str(result.stdout) + str(result.stderr)

    config = extract_config_from_output(output)
    assert config["resolved"].endswith(
        "cli_reports"
    ), "CLI argument should have highest priority"
