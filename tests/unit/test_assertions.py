from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import pytest_a11y.assertions as assertions_module
from pytest_a11y.assertions import (
    _generate_reports,
    _nodeid_hash,
    _safe_slug,
    _should_generate_reports,
    assert_no_axe_violations,
    assert_no_critical_violations,
    assert_results_no_critical,
    assert_results_no_violations,
)
from pytest_a11y.types import Results


class TestAssertionsModuleImport:
    """Tests for import-time execution."""

    def test_assertions_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(assertions_module)

        assert reloaded is assertions_module
        assert reloaded.__name__ == "pytest_a11y.assertions"


class TestHelpers:
    """Tests for pure helper functions."""

    @pytest.mark.parametrize(
        ("text", "max_len", "expected"),
        [
            ("simple", 10, "simple"),
            ("a/b:c", 10, "a_b_c"),
            ("!@#$%^&*()_+", 5, "a11y"),
            ("!!!", 10, "a11y"),
            ("very_long_name", 4, "very"),
        ],
    )
    def test_safe_slug(self, text: str, max_len: int, expected: str) -> None:
        """Convert text into a filesystem-safe slug."""
        assert _safe_slug(text, max_len=max_len) == expected

    def test_nodeid_hash_is_stable_and_respects_length(self) -> None:
        """Generate a stable nodeid hash with the requested length."""
        nodeid = "tests/unit/test_example.py::test_fn[1]"

        first = _nodeid_hash(nodeid, length=8)
        second = _nodeid_hash(nodeid, length=8)

        assert first == second
        assert len(first) == 8
        assert _nodeid_hash(nodeid + "x", length=8) != first

    def test_nodeid_hash_enforces_minimum_digest_size(self) -> None:
        """Handle short requested lengths safely."""
        result = _nodeid_hash("nodeid", length=1)

        assert len(result) == 1


class TestShouldGenerateReports:
    """Tests for report generation enablement logic."""

    def test_should_generate_reports_uses_current_request_when_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Prefer pytest.current_request when present."""
        request = SimpleNamespace(config=SimpleNamespace(getoption=lambda name: True))
        monkeypatch.setattr(
            assertions_module.pytest, "current_request", request, raising=False
        )

        assert _should_generate_reports() is True

    def test_should_generate_reports_returns_false_from_current_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Return False when current request reports a disabled flag."""
        request = SimpleNamespace(config=SimpleNamespace(getoption=lambda name: False))
        monkeypatch.setattr(
            assertions_module.pytest, "current_request", request, raising=False
        )

        assert _should_generate_reports() is False

    def test_should_generate_reports_falls_back_to_pytest_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Use pytest.config when current_request is unavailable."""
        monkeypatch.delattr(assertions_module.pytest, "current_request", raising=False)
        monkeypatch.setattr(
            assertions_module.pytest,
            "config",
            SimpleNamespace(getoption=lambda name: True),
            raising=False,
        )

        assert _should_generate_reports() is True

    def test_should_generate_reports_returns_false_when_no_request_or_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Return False when neither request nor config is available."""
        monkeypatch.delattr(assertions_module.pytest, "current_request", raising=False)
        monkeypatch.delattr(assertions_module.pytest, "config", raising=False)

        assert _should_generate_reports() is False

    def test_should_generate_reports_logs_warning_when_request_access_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Log and continue when current_request access raises."""

        class RaisingPytest:
            """Pytest-like object that raises for current_request."""

            config = SimpleNamespace(getoption=lambda name: False)

            def __getattr__(self, name: str) -> Any:
                if name == "current_request":
                    raise RuntimeError("boom")
                raise AttributeError(name)

        with patch.object(assertions_module, "pytest", RaisingPytest()):
            with patch.object(assertions_module.logger, "warning") as mock_warning:
                assert _should_generate_reports() is False
                mock_warning.assert_any_call(
                    "Warning: Could not access pytest request to check --a11y flag."
                )

    def test_should_generate_reports_logs_warning_when_config_access_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Log and continue when config access raises."""
        monkeypatch.delattr(assertions_module.pytest, "current_request", raising=False)

        class RaisingPytest:
            """Pytest-like object that raises for config."""

            def __getattr__(self, name: str) -> Any:
                if name == "config":
                    raise RuntimeError("boom")
                raise AttributeError(name)

        with patch.object(assertions_module, "pytest", RaisingPytest()):
            with patch.object(assertions_module.logger, "warning") as mock_warning:
                assert _should_generate_reports() is False
                mock_warning.assert_any_call(
                    "Warning: Could not access pytest config to check --a11y flag."
                )

    def test_should_generate_reports_falls_back_when_current_request_is_falsy(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fall back to pytest.config when current_request is present but falsy."""
        monkeypatch.setattr(
            assertions_module.pytest, "current_request", None, raising=False
        )
        monkeypatch.setattr(
            assertions_module.pytest,
            "config",
            SimpleNamespace(getoption=lambda name: True),
            raising=False,
        )

        assert _should_generate_reports() is True


class TestGenerateReports:
    """Tests for report and screenshot generation."""

    def test_generate_reports_returns_for_none_results(self, dummy_driver: Any) -> None:
        """Return immediately when axe_results is None."""
        assert _generate_reports(None, dummy_driver) is None

    def test_generate_reports_returns_when_request_disables_a11y(
        self,
        tmp_path: Path,
        dummy_driver: Any,
    ) -> None:
        """Return early when explicit request has --a11y disabled."""
        request = SimpleNamespace(
            config=SimpleNamespace(
                getoption=lambda name: False, a11y_session_dir=tmp_path
            ),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case", name="test_case"
            ),
        )

        assert (
            _generate_reports({"violations": []}, dummy_driver, request=request) is None
        )

    def test_generate_reports_returns_when_request_option_lookup_raises(
        self,
        tmp_path: Path,
        dummy_driver: Any,
    ) -> None:
        """Return early when explicit request config access fails."""
        request = SimpleNamespace(
            config=SimpleNamespace(
                getoption=lambda name: (_ for _ in ()).throw(RuntimeError("boom"))
            ),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case", name="test_case"
            ),
        )

        assert (
            _generate_reports({"violations": []}, dummy_driver, request=request) is None
        )

    def test_generate_reports_returns_when_global_reporting_disabled(
        self,
        dummy_driver: Any,
    ) -> None:
        """Return early when global report generation is disabled."""
        with patch.object(
            assertions_module, "_should_generate_reports", return_value=False
        ):
            assert (
                _generate_reports({"violations": []}, dummy_driver, request=None)
                is None
            )

    def test_generate_reports_logs_warning_on_import_error(
        self,
        tmp_path: Path,
        dummy_driver: Any,
    ) -> None:
        """Log a warning and return when reporting modules cannot be imported."""
        request = SimpleNamespace(
            config=SimpleNamespace(
                getoption=lambda name: True, a11y_session_dir=tmp_path
            ),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case", name="test_case"
            ),
        )

        original_import = __import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if (
                name.startswith("pytest_a11y._internal.reporting")
                or name == "pytest_a11y._internal.screenshots"
            ):
                raise ImportError("missing reporting deps")
            return original_import(name, *args, **kwargs)

        with patch.object(assertions_module.logger, "warning") as mock_warning:
            with patch("builtins.__import__", side_effect=fake_import):
                _generate_reports({"violations": []}, dummy_driver, request=request)

        assert mock_warning.called

    def test_generate_reports_returns_when_config_missing_session_dir(
        self,
        dummy_driver: Any,
    ) -> None:
        """Return when config is missing a11y_session_dir."""
        request = SimpleNamespace(
            config=SimpleNamespace(getoption=lambda name: True),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case", name="test_case"
            ),
        )

        fake_html_module = ModuleType("fake_html")
        fake_html_module.generate_a11y_report = MagicMock()

        fake_json_module = ModuleType("fake_json")
        fake_json_module.write_a11y_json_report = MagicMock()

        fake_screenshots_module = ModuleType("fake_screenshots")
        fake_screenshots_module.capture_violation_screenshots = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "pytest_a11y._internal.reporting.html_report": fake_html_module,
                "pytest_a11y._internal.reporting.json_report": fake_json_module,
                "pytest_a11y._internal.screenshots": fake_screenshots_module,
            },
        ):
            assert (
                _generate_reports({"violations": []}, dummy_driver, request=request)
                is None
            )

    def test_generate_reports_writes_html_json_and_screenshots(
        self,
        tmp_path: Path,
        dummy_driver: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Generate all artifacts when config and violations are present."""
        session_dir = tmp_path / "run_123"
        session_dir.mkdir()

        request = SimpleNamespace(
            config=SimpleNamespace(
                getoption=lambda name: True, a11y_session_dir=session_dir
            ),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case[param]", name="test_case[param]"
            ),
        )
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")

        html_writer = MagicMock()
        json_writer = MagicMock()
        screenshot_writer = MagicMock()

        fake_html_module = ModuleType("fake_html")
        fake_html_module.generate_a11y_report = html_writer

        fake_json_module = ModuleType("fake_json")
        fake_json_module.write_a11y_json_report = json_writer

        fake_screenshots_module = ModuleType("fake_screenshots")
        fake_screenshots_module.capture_violation_screenshots = screenshot_writer

        axe_results = {"violations": [{"id": "rule1"}]}

        with patch.dict(
            "sys.modules",
            {
                "pytest_a11y._internal.reporting.html_report": fake_html_module,
                "pytest_a11y._internal.reporting.json_report": fake_json_module,
                "pytest_a11y._internal.screenshots": fake_screenshots_module,
            },
        ):
            _generate_reports(axe_results, dummy_driver, request=request)

        screenshot_writer.assert_called_once()
        html_writer.assert_called_once()
        json_writer.assert_called_once()

        html_path = html_writer.call_args.kwargs["output_path"]
        json_path = json_writer.call_args.kwargs["output_path"]
        screenshot_dir = html_writer.call_args.kwargs["screenshot_dir"]

        assert html_path.parent == session_dir
        assert json_path.parent == session_dir
        assert screenshot_dir == session_dir / "violation_screenshots"
        assert "__gw1__" in html_path.name

    def test_generate_reports_skips_screenshots_when_no_violations(
        self,
        tmp_path: Path,
        dummy_driver: Any,
    ) -> None:
        """Skip screenshot capture when there are no violations."""
        session_dir = tmp_path / "run_123"
        session_dir.mkdir()

        request = SimpleNamespace(
            config=SimpleNamespace(
                getoption=lambda name: True, a11y_session_dir=session_dir
            ),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case", name="test_case"
            ),
        )

        html_writer = MagicMock()
        json_writer = MagicMock()
        screenshot_writer = MagicMock()

        fake_html_module = ModuleType("fake_html")
        fake_html_module.generate_a11y_report = html_writer

        fake_json_module = ModuleType("fake_json")
        fake_json_module.write_a11y_json_report = json_writer

        fake_screenshots_module = ModuleType("fake_screenshots")
        fake_screenshots_module.capture_violation_screenshots = screenshot_writer

        with patch.dict(
            "sys.modules",
            {
                "pytest_a11y._internal.reporting.html_report": fake_html_module,
                "pytest_a11y._internal.reporting.json_report": fake_json_module,
                "pytest_a11y._internal.screenshots": fake_screenshots_module,
            },
        ):
            _generate_reports({"violations": []}, dummy_driver, request=request)

        screenshot_writer.assert_not_called()
        html_writer.assert_called_once()
        json_writer.assert_called_once()

    def test_generate_reports_uses_global_pytest_config_when_request_missing(
        self,
        tmp_path: Path,
        dummy_driver: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Use pytest.config when no explicit request is supplied."""
        session_dir = tmp_path / "run_123"
        session_dir.mkdir()

        monkeypatch.setattr(
            assertions_module.pytest,
            "config",
            SimpleNamespace(a11y_session_dir=session_dir),
            raising=False,
        )

        html_writer = MagicMock()
        json_writer = MagicMock()
        screenshot_writer = MagicMock()

        fake_html_module = ModuleType("fake_html")
        fake_html_module.generate_a11y_report = html_writer

        fake_json_module = ModuleType("fake_json")
        fake_json_module.write_a11y_json_report = json_writer

        fake_screenshots_module = ModuleType("fake_screenshots")
        fake_screenshots_module.capture_violation_screenshots = screenshot_writer

        with patch.object(
            assertions_module, "_should_generate_reports", return_value=True
        ):
            with patch.dict(
                "sys.modules",
                {
                    "pytest_a11y._internal.reporting.html_report": fake_html_module,
                    "pytest_a11y._internal.reporting.json_report": fake_json_module,
                    "pytest_a11y._internal.screenshots": fake_screenshots_module,
                },
            ):
                _generate_reports({"violations": []}, dummy_driver, request=None)

        html_writer.assert_called_once()
        json_writer.assert_called_once()

    def test_generate_reports_logs_warning_on_runtime_exception(
        self,
        tmp_path: Path,
        dummy_driver: Any,
    ) -> None:
        """Log a warning and return when report generation raises unexpectedly."""
        session_dir = tmp_path / "run_123"
        session_dir.mkdir()

        request = SimpleNamespace(
            config=SimpleNamespace(
                getoption=lambda name: True, a11y_session_dir=session_dir
            ),
            node=SimpleNamespace(
                nodeid="tests/test_file.py::test_case", name="test_case"
            ),
        )

        html_writer = MagicMock(side_effect=RuntimeError("boom"))
        json_writer = MagicMock()
        screenshot_writer = MagicMock()

        fake_html_module = ModuleType("fake_html")
        fake_html_module.generate_a11y_report = html_writer

        fake_json_module = ModuleType("fake_json")
        fake_json_module.write_a11y_json_report = json_writer

        fake_screenshots_module = ModuleType("fake_screenshots")
        fake_screenshots_module.capture_violation_screenshots = screenshot_writer

        with patch.object(assertions_module.logger, "warning") as mock_warning:
            with patch.dict(
                "sys.modules",
                {
                    "pytest_a11y._internal.reporting.html_report": fake_html_module,
                    "pytest_a11y._internal.reporting.json_report": fake_json_module,
                    "pytest_a11y._internal.screenshots": fake_screenshots_module,
                },
            ):
                _generate_reports({"violations": []}, dummy_driver, request=request)

        mock_warning.assert_called_once()


class TestRawAssertions:
    """Tests for raw AxeResults assertions."""

    def test_assert_no_axe_violations_passes_with_no_violations_and_driver(
        self,
        monkeypatch: pytest.MonkeyPatch,
        dummy_driver: Any,
    ) -> None:
        """Generate reports and pass when no violations exist."""
        request = SimpleNamespace(getfixturevalue=lambda name: dummy_driver)

        monkeypatch.setattr(
            assertions_module.pytest, "current_request", request, raising=False
        )

        with patch.object(assertions_module, "_generate_reports") as mock_generate:
            assert_no_axe_violations({"violations": []})

        mock_generate.assert_called_once()

    def test_assert_no_axe_violations_passes_when_driver_lookup_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Skip report generation when the driver fixture cannot be resolved."""

        class RequestWithoutDriver:
            """Request double that raises on fixture lookup."""

            def getfixturevalue(self, name: str) -> Any:
                raise pytest.FixtureLookupError(name, None)

        monkeypatch.setattr(
            assertions_module.pytest,
            "current_request",
            RequestWithoutDriver(),
            raising=False,
        )

        with patch.object(assertions_module, "_generate_reports") as mock_generate:
            assert_no_axe_violations({"violations": []})

        mock_generate.assert_not_called()

    def test_assert_no_axe_violations_raises_with_formatted_message(self) -> None:
        """Raise with formatted violation ids and node counts."""
        with pytest.raises(AssertionError, match=r"rule1 \(2 nodes\)"):
            assert_no_axe_violations(
                {"violations": [{"id": "rule1", "nodes": [{}, {}]}]}
            )

    def test_assert_no_critical_violations_passes_when_none_critical(
        self,
        monkeypatch: pytest.MonkeyPatch,
        dummy_driver: Any,
    ) -> None:
        """Pass when only non-critical violations exist."""
        request = SimpleNamespace(getfixturevalue=lambda name: dummy_driver)
        monkeypatch.setattr(
            assertions_module.pytest, "current_request", request, raising=False
        )

        with patch.object(assertions_module, "_generate_reports") as mock_generate:
            assert_no_critical_violations(
                {"violations": [{"id": "rule1", "impact": "serious", "nodes": [{}]}]}
            )

        mock_generate.assert_called_once()

    def test_assert_no_critical_violations_skips_report_generation_when_driver_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Skip report generation when the driver fixture cannot be resolved."""

        class RequestWithoutDriver:
            """Request double that raises on fixture lookup."""

            def getfixturevalue(self, name: str) -> Any:
                raise pytest.FixtureLookupError(name, None)

        monkeypatch.setattr(
            assertions_module.pytest,
            "current_request",
            RequestWithoutDriver(),
            raising=False,
        )

        with patch.object(assertions_module, "_generate_reports") as mock_generate:
            assert_no_critical_violations({"violations": []})

        mock_generate.assert_not_called()

    def test_assert_no_critical_violations_raises_on_critical(self) -> None:
        """Raise only for critical violations."""
        with pytest.raises(AssertionError, match=r"b \(2 nodes\)"):
            assert_no_critical_violations(
                {
                    "violations": [
                        {"id": "a", "impact": "serious", "nodes": []},
                        {"id": "b", "impact": "critical", "nodes": [{}, {}]},
                    ]
                }
            )


class TestProcessedAssertions:
    """Tests for processed Results assertions."""

    def test_assert_results_no_violations_passes(
        self,
        processed_results_no_violations: Results,
    ) -> None:
        """Pass when processed results contain no violations."""
        assert assert_results_no_violations(processed_results_no_violations) is None

    def test_assert_results_no_violations_raises(
        self,
        processed_results_with_minor: Results,
    ) -> None:
        """Raise with violation summaries when violations exist."""
        with pytest.raises(AssertionError, match="violations found"):
            assert_results_no_violations(processed_results_with_minor)

    def test_assert_results_no_critical_passes_for_non_critical(
        self,
        processed_results_with_minor: Results,
    ) -> None:
        """Pass when no critical processed violations exist."""
        assert assert_results_no_critical(processed_results_with_minor) is None

    def test_assert_results_no_critical_raises(
        self,
        processed_results_with_critical: Results,
    ) -> None:
        """Raise when critical processed violations exist."""
        with pytest.raises(AssertionError, match="critical violations found"):
            assert_results_no_critical(processed_results_with_critical)
