from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

runner_module = importlib.import_module("pytest_a11y.axe._runner")

AxeRunner = runner_module.AxeRunner
PageReadiness = runner_module.PageReadiness


class TestRunnerModuleImport:
    """Tests for module import coverage."""

    def test_runner_module_can_be_reloaded(self) -> None:
        """Reload module so import-time lines execute under coverage."""
        reloaded = importlib.reload(runner_module)

        assert reloaded is runner_module
        assert reloaded.__name__ == "pytest_a11y.axe._runner"


class TestPageReadiness:
    """Tests for PageReadiness dataclass."""

    def test_fields_are_stored(self) -> None:
        """Store ok flag and reason."""
        r = PageReadiness(ok=True, reason="OK")

        assert r.ok is True
        assert r.reason == "OK"


class TestAxeRunnerInitialization:
    """Tests for AxeRunner initialization."""

    @patch.object(runner_module, "Axe")
    def test_init_sets_fields(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """Initialize runner with driver and request."""
        axe_instance = MagicMock()
        mock_axe.return_value = axe_instance

        runner = AxeRunner(mock_driver, request=mock_request)

        assert runner._driver is mock_driver
        assert runner._request is mock_request
        assert runner._axe is axe_instance


class TestInject:
    """Tests for inject()."""

    @patch.object(runner_module, "Axe")
    def test_inject_calls_axe_inject(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """Call Axe.inject()."""
        axe_instance = MagicMock()
        mock_axe.return_value = axe_instance

        runner = AxeRunner(mock_driver, request=mock_request)

        runner.inject()

        axe_instance.inject.assert_called_once()


class TestCheckPageAnalyzable:
    """Tests for page readiness checks."""

    @patch.object(runner_module, "Axe")
    def test_browser_error_page(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return not OK for browser error page."""
        mock_axe.return_value = MagicMock()
        mock_driver.current_url = "chrome-error://chromewebdata/"

        runner = AxeRunner(mock_driver)

        result = runner.check_page_analyzable()

        assert result.ok is False
        assert (
            result.reason
            == "Browser error page detected: chrome-error://chromewebdata/"
        )

    @patch.object(runner_module, "Axe")
    def test_document_not_ready(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return not OK if readyState != complete."""
        mock_axe.return_value = MagicMock()
        mock_driver.current_url = "https://example.com"
        mock_driver.execute_script.return_value = "loading"

        runner = AxeRunner(mock_driver)

        result = runner.check_page_analyzable()

        assert result.ok is False

    @patch.object(runner_module, "Axe")
    def test_ready_page(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return OK when page is ready."""
        mock_axe.return_value = MagicMock()
        mock_driver.current_url = "https://example.com"
        mock_driver.execute_script.side_effect = ["complete", True]

        runner = AxeRunner(mock_driver)

        result = runner.check_page_analyzable()

        assert result.ok is True
        assert result.reason == "OK"

    @patch.object(runner_module, "Axe")
    def test_missing_dom(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return not OK when documentElement is missing."""
        mock_axe.return_value = MagicMock()
        mock_driver.current_url = "https://example.com"
        mock_driver.execute_script.side_effect = ["complete", False]

        runner = AxeRunner(mock_driver)

        result = runner.check_page_analyzable()

        assert result.ok is False
        assert result.reason == "DOM not available (documentElement missing)"

    @patch.object(runner_module, "Axe")
    def test_javascript_execution_failure(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return not OK when JavaScript execution raises an exception."""
        mock_axe.return_value = MagicMock()
        mock_driver.current_url = "https://example.com"
        mock_driver.execute_script.side_effect = RuntimeError("boom")

        runner = AxeRunner(mock_driver)

        result = runner.check_page_analyzable()

        assert result.ok is False
        assert result.reason == "JavaScript execution failed: RuntimeError"

    @patch.object(runner_module, "Axe")
    @pytest.mark.parametrize(
        ("current_url", "expected_reason"),
        [
            ("", "Blank page detected: about:blank"),
            ("about:blank", "Blank page detected: about:blank"),
            ("about:blank#blocked", "Blank page detected: about:blank#blocked"),
        ],
    )
    def test_blank_page_returns_not_ready(
        self,
        mock_axe: MagicMock,
        current_url: str,
        expected_reason: str,
        mock_driver: MagicMock,
    ) -> None:
        """Return not OK for blank-page URLs."""
        mock_axe.return_value = MagicMock()
        mock_driver.current_url = current_url

        runner = runner_module.AxeRunner(mock_driver)

        result = runner.check_page_analyzable()

        assert result.ok is False
        assert result.reason == expected_reason
        mock_driver.execute_script.assert_not_called()


class TestRun:
    """Tests for run()."""

    @patch.object(runner_module, "_generate_reports")
    @patch.object(runner_module, "Axe")
    def test_run_executes_axe_and_generates_reports(
        self,
        mock_axe: MagicMock,
        mock_reports: MagicMock,
        mock_driver: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """Execute axe.run() and generate reports."""
        axe_instance = MagicMock()
        axe_results = {"violations": []}
        axe_instance.run.return_value = axe_results
        mock_axe.return_value = axe_instance

        runner = AxeRunner(mock_driver, request=mock_request)

        result = runner.run()

        assert result == axe_results
        axe_instance.inject.assert_called_once()
        axe_instance.run.assert_called_once()

        mock_reports.assert_called_once()

    @patch.object(runner_module, "_generate_reports")
    @patch.object(runner_module, "Axe")
    def test_run_passes_standard_option_to_axe(
        self,
        mock_axe: MagicMock,
        mock_reports: MagicMock,
        mock_driver: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """A standard should be passed through as axe options."""
        axe_instance = MagicMock()
        axe_results = {"violations": []}
        axe_instance.run.return_value = axe_results
        mock_axe.return_value = axe_instance

        runner = AxeRunner(mock_driver, request=mock_request, standard="wcag2aaa")

        runner.run()

        axe_instance.run.assert_called_once_with(
            options={"runOnly": {"type": "tag", "values": ["wcag2aaa"]}}
        )


class TestCounts:
    """Tests for count helper methods."""

    @patch.object(runner_module, "Axe")
    def test_count_methods(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return correct counts."""
        mock_axe.return_value = MagicMock()

        runner = AxeRunner(mock_driver)

        results = {
            "violations": [{"id": "v1"}],
            "passes": [{"id": "p1"}, {"id": "p2"}],
            "incomplete": [{"id": "i1"}],
        }

        assert runner.violation_count(results) == 1
        assert runner.pass_count(results) == 2
        assert runner.incomplete_count(results) == 1


class TestHasViolations:
    """Tests for has_violations()."""

    @patch.object(runner_module, "Axe")
    def test_has_violations(
        self,
        mock_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Return True when violations exist."""
        mock_axe.return_value = MagicMock()

        runner = AxeRunner(mock_driver)

        results = {"violations": [{"id": "v1"}]}

        assert runner.has_violations(results) is True


class TestProcessResults:
    """Tests for process_results()."""

    @patch.object(runner_module.Results, "from_axe")
    @patch.object(runner_module, "Axe")
    def test_process_results_delegates_to_results(
        self,
        mock_axe: MagicMock,
        mock_from_axe: MagicMock,
        mock_driver: MagicMock,
    ) -> None:
        """Call Results.from_axe()."""
        mock_axe.return_value = MagicMock()

        runner = AxeRunner(mock_driver)

        raw = {"violations": []}

        runner.process_results(raw)

        mock_from_axe.assert_called_once_with(raw)
