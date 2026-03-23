from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

baseline_module = importlib.import_module(
    "pytest_a11y._internal.comparison.baseline_manager"
)

BaselineManager = baseline_module.BaselineManager


def test_comparison_package_exports_baseline_manager() -> None:
    """Ensure the comparison package re-exports BaselineManager."""

    pkg = importlib.import_module("pytest_a11y._internal.comparison")
    pkg = importlib.reload(pkg)

    assert pkg.BaselineManager is BaselineManager
    assert pkg.__all__ == ["BaselineManager"]


class TestBaselineManagerModuleImport:
    """Tests for import-time execution in the baseline manager module."""

    def test_module_can_be_reloaded(self) -> None:
        """Reload the module so import-time lines execute under coverage."""
        reloaded = importlib.reload(baseline_module)

        assert reloaded is baseline_module
        assert reloaded.__name__ == "pytest_a11y._internal.comparison.baseline_manager"


class TestNormalizationHelpers:
    """Tests for content normalization helpers."""

    @pytest.mark.parametrize(
        "raw",
        [
            "2026-03-20T12:00:00",
            "2026-03-20 12:00:00",
            "run_20260320_120000",
            r"C:\Users\me\project\file.json",
            r"\\server\share\project\file.json",
            "/workspace/project/file.json",
            "/opt/build/output/file.json",
            "__master__abc123def456",
        ],
    )
    def test_normalize_dynamic_text_replaces_supported_patterns(
        self,
        raw: str,
    ) -> None:
        """Replace dynamic strings with stable placeholders."""
        normalized = baseline_module._normalize_dynamic_text(raw)

        assert raw not in normalized

    def test_normalize_html_content_replaces_dynamic_values(self) -> None:
        """Normalize timestamps and supported filesystem paths in HTML content."""
        html = (
            "<div>"
            "Generated 2026-03-20T12:00:00 "
            "C:\\Users\\me\\project\\file.html "
            "\\\\server\\share\\project\\file.html "
            "/workspace/project/file.html "
            "/opt/build/output/file.html "
            "run_20260320_120000 "
            "__master__abc123def456"
            "</div>"
        )

        normalized = baseline_module.normalize_html_content(html)

        assert "2026-03-20T12:00:00" not in normalized
        assert "C:\\Users\\me\\project\\file.html" not in normalized
        assert "\\\\server\\share\\project\\file.html" not in normalized
        assert "/workspace/project/file.html" not in normalized
        assert "/opt/build/output/file.html" not in normalized
        assert "run_20260320_120000" not in normalized
        assert "__master__abc123def456" not in normalized

    def test_normalize_html_content_does_not_replace_url_paths(self) -> None:
        """Do not normalize legitimate slash-prefixed web paths in HTML."""
        html = (
            "<div>"
            '<a href="/privacy">Privacy</a>'
            '<a href="/terms">Terms</a>'
            '<a href="/help/color-contrast">Help</a>'
            '<img src="/static/app.css">'
            "</div>"
        )

        normalized = baseline_module.normalize_html_content(html)

        assert 'href="/privacy"' in normalized
        assert 'href="/terms"' in normalized
        assert 'href="/help/color-contrast"' in normalized
        assert 'src="/static/app.css"' in normalized
        assert "FILEPATH" not in normalized

    def test_normalize_json_content_replaces_dynamic_values(self) -> None:
        """Normalize timestamps and filesystem paths in JSON content."""
        raw = json.dumps(
            {
                "timestamp": "2026-03-20T12:00:00",
                "human": "2026-03-20 12:00:00",
                "run": "run_20260320_120000",
                "windows_path": r"C:\Users\me\project\file.json",
                "unc_path": r"\\server\share\project\file.json",
                "unix_path": "/workspace/project/file.json",
                "opt_path": "/opt/build/output/file.json",
                "git_hash": "__master__abc123def456",
                "nested": [{"ts": "2026-03-20T12:00:00"}],
            }
        )

        normalized = baseline_module.normalize_json_content(raw)

        assert "2026-03-20T12:00:00" not in normalized
        assert "2026-03-20 12:00:00" not in normalized
        assert "run_20260320_120000" not in normalized
        assert r"C:\Users\me\project\file.json" not in normalized
        assert r"\\server\share\project\file.json" not in normalized
        assert "/workspace/project/file.json" not in normalized
        assert "/opt/build/output/file.json" not in normalized
        assert "__master__abc123def456" not in normalized

    def test_normalize_json_content_does_not_replace_url_paths(self) -> None:
        """Do not normalize legitimate slash-prefixed web paths in JSON."""
        raw = json.dumps(
            {
                "help_path": "/help/color-contrast",
                "privacy_path": "/privacy",
                "terms_path": "/terms",
                "asset_path": "/static/app.css",
            }
        )

        normalized = baseline_module.normalize_json_content(raw)

        assert '"help_path":"/help/color-contrast"' in normalized
        assert '"privacy_path":"/privacy"' in normalized
        assert '"terms_path":"/terms"' in normalized
        assert '"asset_path":"/static/app.css"' in normalized
        assert "FILEPATH" not in normalized

    def test_normalize_json_content_preserves_nested_non_string_values(self) -> None:
        """Leave nested non-string JSON values unchanged while normalizing strings."""
        raw = json.dumps(
            {
                "outer": {
                    "count": 123,
                    "enabled": True,
                    "missing": None,
                    "items": [1, False, None, "2026-03-20T12:00:00"],
                }
            }
        )

        normalized = baseline_module.normalize_json_content(raw)

        assert '"count":123' in normalized
        assert '"enabled":true' in normalized
        assert '"missing":null' in normalized
        assert '"items":[1,false,null,"TIMESTAMP"]' in normalized


class TestInitializationAndHashStorage:
    """Tests for initialization and hash file persistence."""

    def test_init_creates_directory_and_loads_empty_hashes(
        self, tmp_path: Path
    ) -> None:
        """Create the baseline directory and initialize empty hashes."""
        manager = BaselineManager(tmp_path / "baselines")

        assert manager.baseline_dir.exists()
        assert manager.hashes == {}
        assert manager.hashes_file == manager.baseline_dir / "baseline_hashes.json"

    def test_load_hashes_reads_existing_file(self, tmp_path: Path) -> None:
        """Load existing baseline hashes from disk."""
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        hashes_file = baseline_dir / "baseline_hashes.json"
        hashes_file.write_text(
            json.dumps({"artifact.png": {"hash": "abc", "type": "image"}}),
            encoding="utf-8",
        )

        manager = BaselineManager(baseline_dir)

        assert manager.hashes == {"artifact.png": {"hash": "abc", "type": "image"}}

    def test_save_hashes_writes_json_file(self, tmp_path: Path) -> None:
        """Persist hashes to the baseline hashes file."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes = {"artifact.txt": {"hash": "123", "type": "text"}}

        manager._save_hashes()

        payload = json.loads(manager.hashes_file.read_text(encoding="utf-8"))
        assert payload == {"artifact.txt": {"hash": "123", "type": "text"}}


class TestComputeFileHash:
    """Tests for file hashing behavior."""

    def test_compute_file_hash_for_plain_file(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Compute a stable hash for a normal file."""
        manager = BaselineManager(tmp_path / "baselines")

        first = manager._compute_file_hash(sample_text_file)
        second = manager._compute_file_hash(sample_text_file)

        assert first == second
        assert isinstance(first, str)
        assert len(first) == 64

    def test_compute_file_hash_normalizes_html(
        self,
        tmp_path: Path,
        sample_html_file: Path,
    ) -> None:
        """Hash normalized HTML content when requested."""
        manager = BaselineManager(tmp_path / "baselines")

        with patch.object(
            baseline_module,
            "normalize_html_content",
            return_value="normalized-html",
        ) as mock_normalize:
            result = manager._compute_file_hash(sample_html_file, normalize=True)

        mock_normalize.assert_called_once()
        assert isinstance(result, str)
        assert len(result) == 64

    def test_compute_file_hash_normalizes_json(
        self,
        tmp_path: Path,
        sample_json_file: Path,
    ) -> None:
        """Hash normalized JSON content when requested."""
        manager = BaselineManager(tmp_path / "baselines")

        with patch.object(
            baseline_module,
            "normalize_json_content",
            return_value='{"normalized":true}',
        ) as mock_normalize:
            result = manager._compute_file_hash(sample_json_file, normalize=True)

        mock_normalize.assert_called_once()
        assert isinstance(result, str)
        assert len(result) == 64


class TestImageComparison:
    """Tests for pixel-tolerance image comparison."""

    def test_images_match_with_tolerance_for_identical_images(
        self,
        tmp_path: Path,
        red_png: Path,
    ) -> None:
        """Treat identical images as matching."""
        manager = BaselineManager(tmp_path / "baselines", image_tolerance=0)

        match, diff_pixels, total_pixels = manager._images_match_with_tolerance(
            red_png,
            red_png,
        )

        assert match is True
        assert diff_pixels == 0
        assert total_pixels > 0

    def test_images_match_with_tolerance_resizes_current_image(
        self,
        tmp_path: Path,
        red_png: Path,
    ) -> None:
        """Resize the current image to match the baseline before comparison."""
        current = tmp_path / "bigger.png"
        baseline_module.Image.new("RGB", (8, 8), (255, 0, 0)).save(current)

        manager = BaselineManager(tmp_path / "baselines", image_tolerance=0)

        match, diff_pixels, total_pixels = manager._images_match_with_tolerance(
            red_png,
            current,
        )

        assert match is True
        assert diff_pixels == 0
        assert total_pixels > 0

    def test_images_match_with_tolerance_returns_fallback_on_exception(
        self,
        tmp_path: Path,
        red_png: Path,
    ) -> None:
        """Return the hash-fallback sentinel values when image comparison fails."""
        manager = BaselineManager(tmp_path / "baselines", image_tolerance=5)

        with patch.object(
            baseline_module.Image, "open", side_effect=RuntimeError("boom")
        ):
            result = manager._images_match_with_tolerance(red_png, red_png)

        assert result == (False, -1, -1)


class TestDeleteAndSaveBaseline:
    """Tests for baseline file deletion and saving."""

    def test_delete_baseline_removes_file_and_hash_entry(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Delete the stored file and its hash metadata."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.save_baseline("artifact.txt", sample_text_file, "text")

        assert "artifact.txt" in manager.hashes
        assert (manager.baseline_dir / "artifact.txt").exists()

        manager.delete_baseline("artifact.txt")

        assert "artifact.txt" not in manager.hashes
        assert not (manager.baseline_dir / "artifact.txt").exists()

    def test_delete_baseline_removes_hash_when_file_is_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Delete only hash metadata when the baseline file is absent."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes["artifact.txt"] = {"hash": "abc", "type": "text"}

        manager.delete_baseline("artifact.txt")

        assert "artifact.txt" not in manager.hashes

    def test_delete_baseline_removes_file_when_hash_entry_is_missing(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Delete only the file when no hash metadata exists."""
        manager = BaselineManager(tmp_path / "baselines")
        baseline_path = manager.baseline_dir / "artifact.txt"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_bytes(sample_text_file.read_bytes())

        manager.delete_baseline("artifact.txt")

        assert not baseline_path.exists()

    def test_save_baseline_computes_hash_with_normalization_for_html(
        self,
        tmp_path: Path,
        sample_html_file: Path,
    ) -> None:
        """Normalize HTML and store hash metadata before copying the file."""
        manager = BaselineManager(tmp_path / "baselines")

        with patch.object(
            manager,
            "_compute_file_hash",
            wraps=manager._compute_file_hash,
        ) as mock_hash:
            manager.save_baseline("report.html", sample_html_file, "html")

        assert manager.hashes["report.html"]["type"] == "html"
        assert mock_hash.call_args.kwargs["normalize"] is True

    def test_save_baseline_computes_hash_with_normalization_for_json(
        self,
        tmp_path: Path,
        sample_json_file: Path,
    ) -> None:
        """Normalize JSON and store hash metadata before copying the file."""
        manager = BaselineManager(tmp_path / "baselines")

        with patch.object(
            manager,
            "_compute_file_hash",
            wraps=manager._compute_file_hash,
        ) as mock_hash:
            manager.save_baseline("report.json", sample_json_file, "json")

        assert manager.hashes["report.json"]["type"] == "json"
        assert mock_hash.call_args.kwargs["normalize"] is True

    @pytest.mark.parametrize(
        ("artifact_name", "artifact_type", "expected_type"),
        [
            ("report.html", "image", "html"),
            ("report.json", "image", "json"),
            ("image.png", "image", "image"),
            ("image.jpg", "image", "image"),
            ("report.txt", "image", "text"),
        ],
    )
    def test_save_baseline_infers_or_preserves_type_from_inputs(
        self,
        tmp_path: Path,
        artifact_name: str,
        artifact_type: str,
        expected_type: str,
    ) -> None:
        """Infer type only for image defaults and preserve explicit non-image types."""
        manager = BaselineManager(tmp_path / "baselines")
        source = tmp_path / artifact_name
        source.write_text("content", encoding="utf-8")

        manager.save_baseline(artifact_name, source, artifact_type)

        assert manager.hashes[artifact_name]["type"] == expected_type
        assert (manager.baseline_dir / artifact_name).exists()

    @pytest.mark.parametrize(
        ("artifact_name", "expected_type"),
        [
            ("report.html", "html"),
            ("report.json", "json"),
            ("image.png", "image"),
            ("image.jpg", "image"),
            ("report.txt", "text"),
        ],
    )
    def test_save_baseline_infers_type_from_extension_when_type_not_given(
        self,
        tmp_path: Path,
        artifact_name: str,
        expected_type: str,
    ) -> None:
        """Infer type from extension when artifact_type is omitted (None)."""
        manager = BaselineManager(tmp_path / "baselines")
        source = tmp_path / artifact_name
        source.write_text("content", encoding="utf-8")

        manager.save_baseline(artifact_name, source)

        assert manager.hashes[artifact_name]["type"] == expected_type
        assert (manager.baseline_dir / artifact_name).exists()

    def test_save_baseline_infers_text_type_and_uses_expected_baseline_path(
        self,
        tmp_path: Path,
    ) -> None:
        """Infer text type for .txt input passed as image and copy to the computed baseline path."""
        manager = BaselineManager(tmp_path / "baselines")
        source = tmp_path / "report.txt"
        source.write_text("content", encoding="utf-8")
        expected_baseline_path = manager.baseline_dir / "report.txt"

        with (
            patch.object(
                manager, "_compute_file_hash", return_value="hash123"
            ) as mock_hash,
            patch.object(baseline_module.shutil, "copy2") as mock_copy,
        ):
            manager.save_baseline("report.txt", source, "image")

        mock_hash.assert_called_once_with(source, normalize=False)
        mock_copy.assert_called_once_with(source, expected_baseline_path)
        assert manager.hashes["report.txt"]["type"] == "text"

    def test_save_baseline_does_not_change_type_for_unrecognized_suffix(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify the save_baseline suffix branch is exercised when the suffix is not recognized."""
        manager = BaselineManager(tmp_path / "baselines")
        source = tmp_path / "style.css"
        source.write_text("body {}", encoding="utf-8")

        manager.save_baseline("style.css", source, "image")

        # The suffix is unrecognized, so artifact_type should not be rewritten
        assert manager.hashes["style.css"]["type"] == "image"
        assert (manager.baseline_dir / "style.css").exists()

    @pytest.mark.parametrize(
        ("artifact_name", "content"),
        [
            ("report.html", "<html></html>"),
            ("report.json", "{}"),
            ("report.txt", "content"),
        ],
    )
    def test_save_baseline_preserves_explicit_non_image_type_for_text_like_suffixes(
        self,
        tmp_path: Path,
        artifact_name: str,
        content: str,
    ) -> None:
        """Do not override an explicit non-image type based on .html/.json/.txt suffix."""
        manager = BaselineManager(tmp_path / "baselines")
        source = tmp_path / artifact_name
        source.write_text(content, encoding="utf-8")

        manager.save_baseline(artifact_name, source, "text")

        assert manager.hashes[artifact_name]["type"] == "text"

    def test_init_uses_loaded_hashes_and_stores_image_tolerance(
        self,
        tmp_path: Path,
    ) -> None:
        """Use _load_hashes() during initialization and store config values."""
        expected_hashes = {"artifact.txt": {"hash": "abc", "type": "text"}}

        with patch.object(
            BaselineManager,
            "_load_hashes",
            return_value=expected_hashes,
        ) as mock_load:
            manager = BaselineManager(tmp_path / "baselines", image_tolerance=7)

        mock_load.assert_called_once()
        assert manager.baseline_dir == tmp_path / "baselines"
        assert manager.hashes_file == (tmp_path / "baselines" / "baseline_hashes.json")
        assert manager.baseline_dir.exists()
        assert manager.image_tolerance == 7
        assert manager.hashes == expected_hashes

    def test_save_baseline_preserves_explicit_non_image_type_for_txt_suffix(
        self,
        tmp_path: Path,
    ) -> None:
        """Do not override an explicit non-image type based on .txt suffix."""
        manager = BaselineManager(tmp_path / "baselines")
        source = tmp_path / "report.txt"
        source.write_text("content", encoding="utf-8")

        manager.save_baseline("report.txt", source, "text")

        assert manager.hashes["report.txt"]["type"] == "text"
        assert (manager.baseline_dir / "report.txt").exists()


class TestCompareArtifact:
    """Tests for artifact comparison behavior."""

    def test_compare_artifact_uses_pixel_tolerance_for_images(
        self,
        tmp_path: Path,
        red_png: Path,
    ) -> None:
        """Use pixel-tolerance comparison for existing image baselines when enabled."""
        manager = BaselineManager(tmp_path / "baselines", image_tolerance=5)
        manager.hashes["img.png"] = {"hash": "abc", "type": "image"}
        baseline_path = manager.baseline_dir / "img.png"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_bytes(red_png.read_bytes())

        with patch.object(
            manager,
            "_images_match_with_tolerance",
            return_value=(True, 0, 16),
        ) as mock_compare:
            result = manager.compare_artifact("img.png", red_png)

        mock_compare.assert_called_once()
        assert result["comparison_method"] == "pixel_tolerance"
        assert result["match"] is True
        assert "within tolerance" in result["message"]

    def test_compare_artifact_uses_hash_fallback_for_non_images(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Use hash-based comparison for non-image artifacts."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes["artifact.txt"] = {"hash": "expected", "type": "text"}

        with patch.object(
            manager, "_compute_file_hash", return_value="expected"
        ) as mock_hash:
            result = manager.compare_artifact("artifact.txt", sample_text_file)

        mock_hash.assert_called_once_with(sample_text_file, normalize=False)
        assert result["comparison_method"] == "hash"
        assert result["match"] is True
        assert "matches baseline" in result["message"]

    def test_compare_artifact_handles_missing_baseline_hash(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Return a first-run warning when no baseline hash exists."""
        manager = BaselineManager(tmp_path / "baselines")

        with patch.object(
            manager, "_compute_file_hash", return_value="current"
        ) as mock_hash:
            result = manager.compare_artifact("artifact.txt", sample_text_file)

        mock_hash.assert_called_once_with(sample_text_file, normalize=False)
        assert result["match"] is None
        assert "first run" in result["message"]

    def test_compare_artifact_uses_normalization_for_html_and_json(
        self,
        tmp_path: Path,
        sample_html_file: Path,
        sample_json_file: Path,
    ) -> None:
        """Normalize HTML and JSON when comparing by hash."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes["report.html"] = {"hash": "x", "type": "html"}
        manager.hashes["report.json"] = {"hash": "y", "type": "json"}

        with patch.object(manager, "_compute_file_hash", return_value="x") as mock_hash:
            manager.compare_artifact("report.html", sample_html_file)
        assert mock_hash.call_args.kwargs["normalize"] is True

        with patch.object(manager, "_compute_file_hash", return_value="y") as mock_hash:
            manager.compare_artifact("report.json", sample_json_file)
        assert mock_hash.call_args.kwargs["normalize"] is True

    def test_compare_artifact_supports_legacy_string_hash_entry(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Handle legacy hash entries stored as plain strings."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes["artifact.txt"] = "expected"

        with patch.object(manager, "_compute_file_hash", return_value="different"):
            result = manager.compare_artifact("artifact.txt", sample_text_file)

        assert result["baseline_hash"] == "expected"
        assert result["match"] is False
        assert "does not match baseline" in result["message"]


class TestCreateAndUpdateBaseline:
    """Tests for first-time creation and update behavior."""

    def test_create_baseline_returns_existing_when_already_present(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Avoid recreating an already-known baseline."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes["artifact.txt"] = {"hash": "abc", "type": "text"}

        result = manager.create_baseline("artifact.txt", sample_text_file, "text")

        assert result == {
            "artifact": "artifact.txt",
            "created": False,
            "message": "Baseline already exists for artifact.txt",
        }

    def test_create_baseline_saves_and_returns_hash(
        self,
        tmp_path: Path,
        sample_text_file: Path,
    ) -> None:
        """Create a new baseline and return the stored hash."""
        manager = BaselineManager(tmp_path / "baselines")

        result = manager.create_baseline("artifact.txt", sample_text_file, "text")

        assert result["artifact"] == "artifact.txt"
        assert result["created"] is True
        assert result["hash"] == manager.hashes["artifact.txt"]["hash"]
        assert "Baseline created" in result["message"]

    def test_update_baseline_replaces_old_file_and_reports_change(
        self,
        tmp_path: Path,
    ) -> None:
        """Delete the old baseline, save the new one, and report changed hashes."""
        manager = BaselineManager(tmp_path / "baselines")
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("old", encoding="utf-8")
        new.write_text("new", encoding="utf-8")

        manager.save_baseline("artifact.txt", old, "text")
        old_hash = manager.hashes["artifact.txt"]["hash"]

        result = manager.update_baseline("artifact.txt", new)

        assert result["artifact"] == "artifact.txt"
        assert result["updated"] is True
        assert result["old_hash"] == old_hash
        assert result["new_hash"] == manager.hashes["artifact.txt"]["hash"]
        assert result["changed"] is True
        assert "Baseline updated" in result["message"]

    def test_update_baseline_preserves_existing_type(
        self,
        tmp_path: Path,
        red_png: Path,
    ) -> None:
        """Reuse the stored artifact type when updating an existing baseline."""
        manager = BaselineManager(tmp_path / "baselines")
        manager.hashes["img.png"] = {"hash": "old", "type": "image"}

        def save_side_effect(
            artifact_name: str,
            artifact_path: Path,
            artifact_type: str,
        ) -> None:
            """Simulate saving a new baseline and updating stored metadata."""
            manager.hashes[artifact_name] = {"hash": "new", "type": artifact_type}

        with (
            patch.object(manager, "delete_baseline") as mock_delete,
            patch.object(
                manager,
                "save_baseline",
                side_effect=save_side_effect,
            ) as mock_save,
        ):
            result = manager.update_baseline("img.png", red_png)

        mock_delete.assert_called_once_with("img.png")
        mock_save.assert_called_once_with("img.png", red_png, "image")
        assert result["old_hash"] == "old"
        assert result["new_hash"] == "new"
        assert result["changed"] is True
