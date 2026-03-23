from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import pytest_a11y.plugin as plugin


class BytesPathLike(os.PathLike):
    """os.PathLike returning bytes from __fspath__."""

    def __fspath__(self) -> bytes:
        return b"some_dir"


class TestPluginModuleImport:
    """Tests for import-time execution in the plugin module."""

    def test_plugin_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(plugin)

        assert reloaded is plugin
        assert reloaded.__name__ == "pytest_a11y.plugin"


class TestPytestAddoption:
    """Tests for pytest option registration."""

    def test_pytest_addoption_registers_cli_and_ini_options(self) -> None:
        """Register the expected CLI and ini configuration options."""
        parser = MagicMock()
        group = MagicMock()
        parser.getgroup.return_value = group

        plugin.pytest_addoption(parser)

        parser.getgroup.assert_called_once_with(
            "a11y",
            "Accessibility testing options",
        )

        assert group.addoption.call_count == 2
        group.addoption.assert_any_call(
            "--a11y",
            action="store_true",
            default=False,
            help="Enable accessibility checks and report generation.",
        )
        group.addoption.assert_any_call(
            "--a11y-dir",
            type=str,
            default=".a11y_reports",
            help="Directory to save a11y reports (default: .a11y_reports)",
        )

        parser.addini.assert_called_once_with(
            "a11y_reports",
            type="string",
            default=".a11y_reports",
            help="Directory to save a11y reports (can also use --a11y-dir CLI option)",
        )


class TestResolveA11yDir:
    """Tests for a11y directory resolution priority."""

    def test_resolve_a11y_dir_prefers_programmatic_option(self) -> None:
        """Use config.option.a11y_reports when it is set programmatically."""
        config = MagicMock()
        config.option = SimpleNamespace(a11y_reports="programmatic_dir")

        result = plugin._resolve_a11y_dir(config)

        assert result == Path("programmatic_dir")

    @pytest.mark.parametrize(
        "cli_value,ini_value,env_value,expected",
        [
            ("cli_dir", "ini_dir", None, Path("cli_dir")),
            (".a11y_reports", "ini_dir", None, Path("ini_dir")),
            (".a11y_reports", ".a11y_reports", "env_dir", Path("env_dir")),
            (".a11y_reports", ".a11y_reports", None, Path(".a11y_reports")),
        ],
    )
    def test_resolve_a11y_dir_priority(
        self,
        monkeypatch,
        cli_value,
        ini_value,
        env_value,
        expected,
    ) -> None:
        """Resolution priority from CLI, ini, env, and defaults."""
        config = MagicMock()
        config.option = SimpleNamespace(a11y_reports=None)
        config.getoption.return_value = cli_value
        config.getini.return_value = ini_value

        if env_value is not None:
            monkeypatch.setenv("A11Y_DIR", env_value)
        else:
            monkeypatch.delenv("A11Y_DIR", raising=False)

        result = plugin._resolve_a11y_dir(config)

        assert result == expected

    def test_resolve_a11y_dir_handles_missing_programmatic_attribute(self) -> None:
        """Handle config.option objects that do not define a11y_reports."""
        config = MagicMock()
        config.option = SimpleNamespace()
        config.getoption.return_value = "cli_dir"
        config.getini.return_value = "ini_dir"

        result = plugin._resolve_a11y_dir(config)

        assert result == Path("cli_dir")

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("some_dir", Path("some_dir")),
            (Path("some_dir"), Path("some_dir")),
            (os.fsencode("some_dir"), None),
            ("", None),
            (None, None),
        ],
    )
    def test_coerce_pathlike_variants(self, input_value, expected) -> None:
        """Validate _coerce_pathlike covers str, Path, empty and None paths."""
        result = plugin._coerce_pathlike(input_value)

        assert result == expected

    def test_coerce_pathlike_rejects_invalid_types(self) -> None:
        """Ensure non-pathlike runtimes are not converted into a Path."""
        assert plugin._coerce_pathlike(123) is None
        assert plugin._coerce_pathlike(object()) is None

    def test_coerce_pathlike_bytes_pathlike(self) -> None:
        """A real os.PathLike object returning bytes should return None."""
        assert plugin._coerce_pathlike(BytesPathLike()) is None


class TestPytestConfigure:
    """Tests for plugin configuration and session directory setup."""

    @pytest.mark.parametrize(
        "a11y_enabled,existing_session_dir,should_create",
        [
            (True, None, True),
            (False, None, False),
            (True, "explicit_dir", True),
            (False, "explicit_dir", False),
        ],
    )
    @patch("pytest_a11y.plugin.datetime")
    @patch("pytest_a11y.plugin._resolve_a11y_dir")
    def test_pytest_configure_sets_session_dir_and_creation_behavior(
        self,
        mock_resolve_a11y_dir: MagicMock,
        mock_datetime: MagicMock,
        a11y_enabled: bool,
        existing_session_dir: str | None,
        should_create: bool,
        tmp_path: Path,
    ) -> None:
        """Check session directory is configured and directory creation obeys --a11y."""
        config = MagicMock()
        config.getoption.return_value = a11y_enabled

        mock_datetime.now.return_value.strftime.return_value = "20260320_101500"

        if existing_session_dir is None:
            mock_resolve_a11y_dir.return_value = tmp_path / "reports"
        else:
            config.a11y_session_dir = tmp_path / existing_session_dir

        plugin.pytest_configure(config)

        if existing_session_dir is None:
            expected_root = (tmp_path / "reports").expanduser().resolve()
            expected_session_dir = expected_root / "run_20260320_101500"
        else:
            expected_session_dir = (
                (tmp_path / existing_session_dir).expanduser().resolve()
            )
            expected_root = expected_session_dir.parent

        assert config.a11y_enabled is a11y_enabled
        assert config.a11y_dir == expected_root
        assert config.a11y_session_dir == expected_session_dir

        assert expected_session_dir.exists() is should_create


class TestPluginExports:
    """Tests for public module exports."""

    def test_all_exports_expected_hook_functions(self) -> None:
        """Expose only the intended public pytest hook functions."""
        assert plugin.__all__ == [
            "pytest_addoption",
            "pytest_configure",
        ]
