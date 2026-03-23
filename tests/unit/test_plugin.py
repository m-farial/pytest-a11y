from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest_a11y.plugin as plugin


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

    def test_resolve_a11y_dir_uses_cli_when_programmatic_not_set(self) -> None:
        """Use the CLI directory when it is non-default."""
        config = MagicMock()
        config.option = SimpleNamespace(a11y_reports=None)
        config.getoption.return_value = "cli_dir"
        config.getini.return_value = "ini_dir"

        result = plugin._resolve_a11y_dir(config)

        assert result == Path("cli_dir")

    def test_resolve_a11y_dir_uses_ini_when_cli_is_default(self) -> None:
        """Use the ini value when the CLI value remains at the default."""
        config = MagicMock()
        config.option = SimpleNamespace(a11y_reports=None)
        config.getoption.return_value = ".a11y_reports"
        config.getini.return_value = "ini_dir"

        result = plugin._resolve_a11y_dir(config)

        assert result == Path("ini_dir")

    @patch.dict("os.environ", {"A11Y_DIR": "env_dir"})
    def test_resolve_a11y_dir_uses_environment_when_cli_and_ini_are_default(
        self,
    ) -> None:
        """Use the environment variable when higher-priority values are absent."""
        config = MagicMock()
        config.option = SimpleNamespace(a11y_reports=None)
        config.getoption.return_value = ".a11y_reports"
        config.getini.return_value = ".a11y_reports"

        result = plugin._resolve_a11y_dir(config)

        assert result == Path("env_dir")

    @patch.dict("os.environ", {}, clear=True)
    def test_resolve_a11y_dir_falls_back_to_default(self) -> None:
        """Return the default directory when no overrides are present."""
        config = MagicMock()
        config.option = SimpleNamespace(a11y_reports=None)
        config.getoption.return_value = ".a11y_reports"
        config.getini.return_value = ".a11y_reports"

        result = plugin._resolve_a11y_dir(config)

        assert result == Path(".a11y_reports")

    def test_resolve_a11y_dir_handles_missing_programmatic_attribute(self) -> None:
        """Handle config.option objects that do not define a11y_reports."""
        config = MagicMock()
        config.option = SimpleNamespace()
        config.getoption.return_value = "cli_dir"
        config.getini.return_value = "ini_dir"

        result = plugin._resolve_a11y_dir(config)

        assert result == Path("cli_dir")


class TestPytestConfigure:
    """Tests for plugin configuration and session directory setup."""

    @patch("pytest_a11y.plugin.datetime")
    @patch("pytest_a11y.plugin._resolve_a11y_dir")
    def test_pytest_configure_sets_attributes_and_creates_directory_when_enabled(
        self,
        mock_resolve_a11y_dir: MagicMock,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Create the timestamped session directory when a11y is enabled."""
        config = MagicMock()
        config.getoption.return_value = True
        mock_resolve_a11y_dir.return_value = tmp_path / "reports"
        mock_datetime.now.return_value.strftime.return_value = "20260320_101500"

        plugin.pytest_configure(config)

        expected_root = (tmp_path / "reports").expanduser().resolve()
        expected_session_dir = expected_root / "run_20260320_101500"

        assert config.a11y_enabled is True
        assert config.a11y_dir == expected_root
        assert config.a11y_session_dir == expected_session_dir
        assert expected_session_dir.exists()

    @patch("pytest_a11y.plugin.datetime")
    @patch("pytest_a11y.plugin._resolve_a11y_dir")
    def test_pytest_configure_sets_attributes_without_creating_directory_when_disabled(
        self,
        mock_resolve_a11y_dir: MagicMock,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Skip directory creation when a11y checks are disabled."""
        config = MagicMock()
        config.getoption.return_value = False
        mock_resolve_a11y_dir.return_value = tmp_path / "reports"
        mock_datetime.now.return_value.strftime.return_value = "20260320_101500"

        plugin.pytest_configure(config)

        expected_root = (tmp_path / "reports").expanduser().resolve()
        expected_session_dir = expected_root / "run_20260320_101500"

        assert config.a11y_enabled is False
        assert config.a11y_dir == expected_root
        assert config.a11y_session_dir == expected_session_dir

    @patch("pytest_a11y.plugin.datetime")
    @patch("pytest_a11y.plugin._resolve_a11y_dir")
    def test_pytest_configure_uses_existing_session_dir_when_present(
        self,
        mock_resolve_a11y_dir: MagicMock,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Honor config.a11y_session_dir if set before pytest_configure."""
        config = MagicMock()
        config.getoption.return_value = True
        config.a11y_session_dir = tmp_path / "explicit_dir"

        plugin.pytest_configure(config)

        expected_session_dir = (tmp_path / "explicit_dir").expanduser().resolve()

        assert config.a11y_enabled is True
        assert config.a11y_session_dir == expected_session_dir
        assert config.a11y_dir == expected_session_dir.parent
        assert expected_session_dir.exists()

    @patch("pytest_a11y.plugin.datetime")
    @patch("pytest_a11y.plugin._resolve_a11y_dir")
    def test_pytest_configure_with_existing_session_dir_does_not_create_when_disabled(
        self,
        mock_resolve_a11y_dir: MagicMock,
        mock_datetime: MagicMock,
        tmp_path: Path,
    ) -> None:
        """If a11y disabled, existing session_dir is preserved but not created."""
        config = MagicMock()
        config.getoption.return_value = False
        config.a11y_session_dir = tmp_path / "explicit_dir"

        plugin.pytest_configure(config)

        expected_session_dir = (tmp_path / "explicit_dir").expanduser().resolve()

        assert config.a11y_enabled is False
        assert config.a11y_session_dir == expected_session_dir
        assert config.a11y_dir == expected_session_dir.parent
        assert not expected_session_dir.exists()
        assert not expected_session_dir.exists()


class TestPluginExports:
    """Tests for public module exports."""

    def test_all_exports_expected_hook_functions(self) -> None:
        """Expose only the intended public pytest hook functions."""
        assert plugin.__all__ == [
            "pytest_addoption",
            "pytest_configure",
        ]
