from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

overlay_module = importlib.import_module("pytest_a11y._internal.visual.axe_overlay")

ViolationScreenshot = overlay_module.ViolationScreenshot


class TestAxeOverlayModuleImport:
    """Tests for import-time execution."""

    def test_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(overlay_module)

        assert reloaded is overlay_module
        assert reloaded.__name__ == "pytest_a11y._internal.visual.axe_overlay"


class TestViolationScreenshot:
    """Tests for the ViolationScreenshot dataclass."""

    def test_fields_are_stored(self, tmp_path: Path) -> None:
        """Store the expected screenshot metadata fields."""
        screenshot = ViolationScreenshot(
            violation_id="color-contrast",
            violation_index=1,
            screenshot_path=tmp_path / "shot.png",
            marked_count=2,
        )

        assert screenshot.violation_id == "color-contrast"
        assert screenshot.violation_index == 1
        assert screenshot.screenshot_path == tmp_path / "shot.png"
        assert screenshot.marked_count == 2


class TestSelectorHelpers:
    """Tests for selector filtering helpers."""

    @pytest.mark.parametrize(
        ("selector", "expected"),
        [
            ("html", True),
            (" body ", True),
            ("*", True),
            ("#main", False),
        ],
    )
    def test_is_global_selector(self, selector: str, expected: bool) -> None:
        """Identify global selectors correctly."""
        assert overlay_module._is_global_selector(selector) is expected

    def test_iter_violation_selectors_filters_invalid_and_global(self) -> None:
        """Yield only non-global, non-empty string selectors."""
        violation = {
            "nodes": [
                {"target": ["html", "#main", " ", "body"]},
                {"target": ["#login", "*"]},
                {"target": "not-a-list"},
                {},
            ]
        }

        selectors = list(overlay_module._iter_violation_selectors(violation))

        assert selectors == ["#main", "#login"]

    def test_iter_violation_selectors_respects_max_nodes(self) -> None:
        """Limit yielded selectors to the requested node count."""
        violation = {
            "nodes": [
                {"target": ["#one"]},
                {"target": ["#two"]},
                {"target": ["#three"]},
            ]
        }

        selectors = list(
            overlay_module._iter_violation_selectors(violation, max_nodes=2)
        )

        assert selectors == ["#one", "#two"]

    @pytest.mark.parametrize(
        ("violation", "expected"),
        [
            ({"nodes": []}, True),
            ({"nodes": [{"target": ["html", "body"]}]}, True),
            ({"nodes": [{"target": ["#main"]}]}, False),
            ({"nodes": [{"target": "not-a-list"}, {"target": ["html"]}]}, True),
        ],
    )
    def test_has_global_selector_only(
        self,
        violation: dict[str, object],
        expected: bool,
    ) -> None:
        """Detect whether only global selectors are present."""
        assert overlay_module._has_global_selector_only(violation) is expected


class TestDisplayHelpers:
    """Tests for display and JavaScript helper functions."""

    @pytest.mark.parametrize(
        ("impact", "expected"),
        [
            ("critical", "#b00020"),
            ("serious", "#e65100"),
            ("moderate", "#f9a825"),
            ("minor", "#1565c0"),
            ("unknown", "#616161"),
            ("weird", "#616161"),
            (None, "#616161"),
        ],
    )
    def test_severity_color(self, impact: str | None, expected: str) -> None:
        """Map impact values to stable hex colors."""
        assert overlay_module._severity_color(impact) == expected

    def test_mark_selector_on_page_returns_bool(self, mock_driver: MagicMock) -> None:
        """Return a boolean result from execute_script."""
        mock_driver.execute_script.return_value = True

        result = overlay_module._mark_selector_on_page(
            mock_driver,
            "#main",
            "1: color-contrast",
            "#e65100",
            14,
        )

        assert result is True
        mock_driver.execute_script.assert_called_once()

    def test_add_page_level_banner_executes_script(
        self,
        mock_driver: MagicMock,
    ) -> None:
        """Execute JavaScript to add a page-level banner."""
        overlay_module._add_page_level_banner(
            mock_driver,
            "landmark-one-main",
            "moderate",
            "#f9a825",
        )

        mock_driver.execute_script.assert_called_once()

    def test_cleanup_violation_marks_executes_script(
        self,
        mock_driver: MagicMock,
    ) -> None:
        """Execute JavaScript to remove violation markers."""
        overlay_module._cleanup_violation_marks(mock_driver)

        mock_driver.execute_script.assert_called_once()


class TestCaptureViolationScreenshots:
    """Tests for per-violation screenshot capture."""

    def test_capture_creates_output_dir_and_returns_empty_for_no_violations(
        self,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Create the output directory and return no screenshots for empty violations."""
        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            {"violations": []},
            tmp_path / "screens",
        )

        assert result == {}
        assert (tmp_path / "screens").exists()

    def test_capture_skips_violation_with_no_nodes_or_unknown_impact(
        self,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Skip violations that cannot be meaningfully captured."""
        axe_results = {
            "violations": [
                {"id": "rule1", "impact": "serious", "nodes": []},
                {"id": "rule2", "impact": "unknown", "nodes": [{"target": ["#a"]}]},
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
        )

        assert result == {}

    @patch.object(overlay_module, "_cleanup_violation_marks")
    @patch.object(overlay_module, "_mark_selector_on_page")
    def test_capture_marks_elements_and_saves_screenshot(
        self,
        mock_mark: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Mark selectors, save the screenshot, and store paths in-place."""
        mock_mark.return_value = True

        axe_results = {
            "violations": [
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "nodes": [{"target": ["#main"]}],
                }
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
        )

        expected_path = str(tmp_path / "serious_color-contrast_1.png")
        assert result == {"color-contrast": expected_path}
        assert axe_results["violations"][0]["screenshot_path"] == expected_path
        mock_driver.save_screenshot.assert_called_once_with(expected_path)
        mock_cleanup.assert_called_once_with(mock_driver)

    @patch.object(overlay_module, "_cleanup_violation_marks")
    @patch.object(overlay_module, "_mark_selector_on_page")
    def test_capture_appends_safe_filename_suffix(
        self,
        mock_mark: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Append a sanitized filename suffix to screenshot filenames."""
        mock_mark.return_value = True

        axe_results = {
            "violations": [
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "nodes": [{"target": ["#main"]}],
                }
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
            filename_suffix="danger/..suffix",
        )

        screenshot_path = result["color-contrast"]
        assert screenshot_path.endswith("_danger_suffix.png")
        assert ".." not in Path(screenshot_path).name
        assert "/" not in Path(screenshot_path).name
        mock_driver.save_screenshot.assert_called_once_with(screenshot_path)
        mock_cleanup.assert_called_once_with(mock_driver)

    @patch.object(overlay_module, "_add_page_level_banner")
    @patch.object(overlay_module, "_cleanup_violation_marks")
    @patch.object(overlay_module, "_mark_selector_on_page")
    def test_capture_adds_banner_when_only_global_selectors(
        self,
        mock_mark: MagicMock,
        mock_cleanup: MagicMock,
        mock_banner: MagicMock,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Add a banner when no specific element can be marked."""
        mock_mark.return_value = False

        axe_results = {
            "violations": [
                {
                    "id": "landmark-one-main",
                    "impact": "moderate",
                    "nodes": [{"target": ["html"]}],
                }
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
        )

        assert "landmark-one-main" in result
        mock_banner.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch.object(overlay_module.logger, "warning")
    @patch.object(overlay_module, "_mark_selector_on_page")
    def test_capture_logs_warning_when_marking_raises(
        self,
        mock_mark: MagicMock,
        mock_warning: MagicMock,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Log and continue when selector marking raises."""
        mock_mark.side_effect = RuntimeError("boom")

        axe_results = {
            "violations": [
                {
                    "id": "rule1",
                    "impact": "serious",
                    "nodes": [{"target": ["#main"]}],
                }
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
        )

        assert result == {}
        mock_warning.assert_called_once()

    @patch.object(overlay_module.logger, "warning")
    @patch.object(overlay_module, "_cleanup_violation_marks")
    @patch.object(overlay_module, "_mark_selector_on_page")
    def test_capture_logs_warning_when_save_screenshot_raises(
        self,
        mock_mark: MagicMock,
        mock_cleanup: MagicMock,
        mock_warning: MagicMock,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Log and continue when screenshot saving raises."""
        mock_mark.return_value = True
        mock_driver.save_screenshot.side_effect = RuntimeError("boom")

        axe_results = {
            "violations": [
                {
                    "id": "rule1",
                    "impact": "serious",
                    "nodes": [{"target": ["#main"]}],
                }
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
        )

        assert "rule1" in result
        mock_warning.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch.object(overlay_module, "_cleanup_violation_marks")
    @patch.object(overlay_module, "_mark_selector_on_page")
    def test_capture_skips_scroll_into_view_when_disabled(
        self,
        mock_mark: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
        mock_driver: MagicMock,
    ) -> None:
        """Skip scrolling into view when that option is disabled."""
        mock_mark.return_value = True

        axe_results = {
            "violations": [
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "nodes": [{"target": ["#main"]}],
                }
            ]
        }

        result = overlay_module.capture_violation_screenshots(
            mock_driver,
            axe_results,
            tmp_path,
            scroll_into_view=False,
        )

        expected_path = str(tmp_path / "serious_color-contrast_1.png")

        assert result == {"color-contrast": expected_path}
        assert axe_results["violations"][0]["screenshot_path"] == expected_path
        mock_mark.assert_called_once_with(
            mock_driver,
            "#main",
            "1: color-contrast",
            "#e65100",
            0,
        )
        mock_driver.save_screenshot.assert_called_once_with(expected_path)
        mock_cleanup.assert_called_once_with(mock_driver)

        assert mock_driver.execute_script.call_count == 1
        assert (
            mock_driver.execute_script.call_args.args[0]
            == "return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
        )


class TestRelativeScreenshotPath:
    """Tests for screenshot path normalization."""

    def test_returns_relative_path_when_possible(self, tmp_path: Path) -> None:
        """Return a forward-slash relative path when possible."""
        output_path = tmp_path / "reports" / "report.html"
        screenshot_path = tmp_path / "reports" / "shots" / "a.png"

        result = overlay_module.get_relative_screenshot_path(
            screenshot_path,
            output_path,
        )

        assert result == "shots/a.png"

    def test_falls_back_to_filename_by_default(self, tmp_path: Path) -> None:
        """Return only the filename when a relative path cannot be computed."""
        output_path = tmp_path / "reports" / "report.html"
        screenshot_path = Path("C:/other/place/a.png")

        result = overlay_module.get_relative_screenshot_path(
            screenshot_path,
            output_path,
        )

        assert result == "a.png"

    def test_falls_back_to_full_posix_path_when_filename_fallback_disabled(
        self,
        tmp_path: Path,
    ) -> None:
        """Return the full posix path when relative computation fails and filename fallback is disabled."""
        output_path = tmp_path / "reports" / "report.html"
        screenshot_path = Path("C:/other/place/a.png")

        result = overlay_module.get_relative_screenshot_path(
            screenshot_path,
            output_path,
            fallback_to_filename=False,
        )

        assert result == Path("C:/other/place/a.png").as_posix()
