import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

# ============================================================================
# Normalization patterns — edit these if dynamic content changes
# ============================================================================

# Timestamps: ISO format e.g. "2026-01-24T16:41:21" or with ms/tz "2026-01-24T16:41:21.123Z"
_RE_TIMESTAMP_ISO = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)

# Timestamps: human-readable e.g. "2026-01-24 16:41:21"
_RE_TIMESTAMP_HUMAN = re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}")

# CI run folder timestamps e.g. "run_20260124_164121"
_RE_TIMESTAMP_RUN = re.compile(r"run_\d{8}_\d{6}")

# Windows absolute paths e.g. "C:\Users\foo\..." or "C:/Users/foo/..."
_RE_PATH_WINDOWS = re.compile(r'[a-zA-Z]:[\\\/][^\\"]*')

# Windows UNC paths e.g. "\\server\share\folder\file.json"
_RE_PATH_WINDOWS_UNC = re.compile(
    r'(?<!\w)\\\\[^\\/\s"<]+\\[^\\/\s"<]+(?:\\[^\\/\s"<]+)*'
)

# Unix absolute filesystem paths under known runtime/build roots only.
# Intentionally restricted to an allowlist to avoid false positives for
# legitimate slash-prefixed web paths in HTML/JSON such as "/privacy",
# "/terms", or "/help/color-contrast".
_RE_PATH_UNIX = re.compile(
    r'(?<![:\w])/(?:home|Users|tmp|var|workspace|opt|root)(?:/[^/\s"<]+){1,}'
)
# Generated git hash filenames e.g. "__master__abc123def456"
_RE_GIT_HASH = re.compile(r"__master__[a-f0-9]{10,}")

# JSON keys to skip entirely during normalization (machine/run specific)
_SKIP_JSON_KEYS: frozenset[str] = frozenset({"screenshot_path"})

_STRING_NORMALIZERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_RE_TIMESTAMP_ISO, "TIMESTAMP"),
    (_RE_TIMESTAMP_HUMAN, "TIMESTAMP"),
    (_RE_TIMESTAMP_RUN, "run_TIMESTAMP"),
    (_RE_PATH_WINDOWS, "FILEPATH"),
    (_RE_PATH_WINDOWS_UNC, "FILEPATH"),
    (_RE_PATH_UNIX, "FILEPATH"),
    (_RE_GIT_HASH, "__master__HASH"),
)


def _normalize_dynamic_text(value: str) -> str:
    """Replace dynamic machine- and run-specific text with stable placeholders."""
    normalized = value
    for pattern, replacement in _STRING_NORMALIZERS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def normalize_html_content(html_content: str) -> str:
    """
    Normalize HTML for comparison by removing dynamic content.

    Patterns removed (see module-level constants for regex details):
    - ISO and human-readable timestamps
    - Windows and Unix absolute file paths
    - CI run folder timestamps
    - Generated git hash strings in filenames
    - Whitespace variations
    """
    html_content = _normalize_dynamic_text(html_content)

    # Normalize whitespace
    html_content = re.sub(r"\s+", " ", html_content)
    html_content = re.sub(r">\s+<", "><", html_content)

    return html_content.strip()


def normalize_json_content(json_content: str) -> str:
    """
    Normalize JSON for comparison by removing dynamic content.

    Patterns removed (see module-level constants for regex details):
    - ISO and human-readable timestamps
    - Windows and Unix absolute file paths
    - CI run folder timestamps
    - Keys listed in _SKIP_JSON_KEYS (e.g. screenshot_path)
    """
    try:
        data = json.loads(json_content)

        def clean_value(obj: Any) -> Any:
            """Recursively normalize JSON-safe values."""
            if isinstance(obj, dict):
                return {
                    key: clean_value(value)
                    for key, value in obj.items()
                    if key not in _SKIP_JSON_KEYS
                }
            if isinstance(obj, list):
                return [clean_value(item) for item in obj]
            if isinstance(obj, str):
                return _normalize_dynamic_text(obj)
            return obj

        cleaned_data = clean_value(data)
        return json.dumps(cleaned_data, sort_keys=True, separators=(",", ":"))
    except json.JSONDecodeError:
        return json_content


class BaselineManager:
    """Manage baseline artifacts and hash verification.

    Supports multiple comparison strategies:
    - Hash-based: Exact match (default, fast, deterministic)
    - Tolerance-based: For images, allows minor pixel variations
    """

    def __init__(self, baseline_dir: Path | str, image_tolerance: int = 0) -> None:
        """
        Initialize baseline manager.

        Args:
            baseline_dir: Directory to store baselines
            image_tolerance: Pixel difference tolerance for images (0-255)
                           0 = exact match (hash-based)
                           1-10 = minor variations allowed (anti-aliasing, etc.)
        """
        self.baseline_dir = Path(baseline_dir)
        self.hashes_file = self.baseline_dir / "baseline_hashes.json"
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.image_tolerance = image_tolerance
        self.hashes = self._load_hashes()

    def _load_hashes(self) -> dict[str, Any]:
        """Load stored baseline hashes from JSON file."""
        if self.hashes_file.exists():
            with open(self.hashes_file) as f:
                data: dict[str, Any] = json.load(f)
                return data
        return {}

    def _save_hashes(self) -> None:
        """Save baseline hashes to JSON file."""
        with open(self.hashes_file, "w") as f:
            json.dump(self.hashes, f, indent=2)

    def _compute_file_hash(self, file_path: Path, normalize: bool = False) -> str:
        """
        Compute SHA256 hash of a file.

        Args:
            file_path: Path to file
            normalize: If True, normalize content before hashing (for HTML/JSON)
        """
        suffix = file_path.suffix.lower()

        if normalize and suffix == ".html":
            with open(file_path, encoding="utf-8") as f:
                html_content = f.read()
            normalized = normalize_html_content(html_content)
            return hashlib.sha256(normalized.encode()).hexdigest()

        if normalize and suffix == ".json":
            with open(file_path, encoding="utf-8") as f:
                json_content = f.read()
            normalized = normalize_json_content(json_content)
            return hashlib.sha256(normalized.encode()).hexdigest()

        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _images_match_with_tolerance(
        self, baseline_path: Path, current_path: Path
    ) -> tuple[bool, int, int]:
        """
        Compare two images with pixel tolerance.

        Args:
            baseline_path: Path to baseline image
            current_path: Path to current image

        Returns:
            Tuple of (match: bool, diff_pixels: int, total_pixels: int)
        """
        try:
            baseline_img = Image.open(baseline_path).convert("RGB")
            current_img = Image.open(current_path).convert("RGB")

            if baseline_img.size != current_img.size:
                current_img = current_img.resize(
                    baseline_img.size, Image.Resampling.LANCZOS
                )

            diff = ImageChops.difference(baseline_img, current_img)
            diff_data = list(diff.get_flattened_data())

            diff_pixels = sum(
                1
                for pixel in diff_data
                if isinstance(pixel, tuple) and max(pixel) > self.image_tolerance
            )
            total_pixels = len(diff_data)

            threshold = total_pixels * 0.01
            match = diff_pixels < threshold

            return match, diff_pixels, total_pixels
        except Exception:
            return False, -1, -1

    def delete_baseline(self, artifact_name: str) -> None:
        """
        Delete baseline artifact and its hash entry.

        Args:
            artifact_name: Name/path for artifact
        """
        baseline_path = self.baseline_dir / artifact_name
        if baseline_path.exists():
            baseline_path.unlink()

        if artifact_name in self.hashes:
            del self.hashes[artifact_name]
            self._save_hashes()

    def save_baseline(
        self,
        artifact_name: str,
        artifact_path: Path | str,
        artifact_type: str | None = None,
    ) -> None:
        """
        Save artifact to baseline and compute hash.

        Args:
            artifact_name: Name/path for artifact (e.g., "report.html", "screenshots/1.png")
            artifact_path: Path to source file
            artifact_type: Type of artifact ("image", "html", "json", "text")
        """
        artifact_path = Path(artifact_path)
        suffix = artifact_path.suffix.lower()

        # If no explicit type was provided, default to image.
        if artifact_type is None:
            artifact_type = "image"

        # If caller explicitly asked for image but extension indicates text-ish,
        # infer a better type.
        if artifact_type == "image":
            extension_map = {
                ".html": "html",
                ".json": "json",
                ".txt": "text",
            }
            artifact_type = extension_map.get(suffix, artifact_type)

        baseline_path = self.baseline_dir / artifact_name
        baseline_path.parent.mkdir(parents=True, exist_ok=True)

        should_normalize = artifact_type in ("html", "json")
        hash_value = self._compute_file_hash(artifact_path, normalize=should_normalize)

        self.hashes[artifact_name] = {
            "hash": hash_value,
            "type": artifact_type,
            "created": datetime.now().isoformat(),
        }
        self._save_hashes()

        shutil.copy2(artifact_path, baseline_path)

    def compare_artifact(
        self, artifact_name: str, artifact_path: Path | str
    ) -> dict[str, Any]:
        """
        Compare artifact against baseline hash.

        For images with tolerance > 0, uses pixel-based comparison.
        For other types, uses hash-based comparison.

        Args:
            artifact_name: Name/path for artifact
            artifact_path: Path to current artifact file

        Returns:
            Dict with comparison results
        """
        artifact_path = Path(artifact_path)
        baseline_entry = self.hashes.get(artifact_name, {})
        artifact_type = (
            baseline_entry.get("type", "image")
            if isinstance(baseline_entry, dict)
            else "image"
        )
        baseline_path = self.baseline_dir / artifact_name

        if (
            artifact_type == "image"
            and self.image_tolerance > 0
            and baseline_path.exists()
        ):
            match, diff_pixels, total_pixels = self._images_match_with_tolerance(
                baseline_path, artifact_path
            )
            return {
                "artifact": artifact_name,
                "match": match,
                "comparison_method": "pixel_tolerance",
                "tolerance": self.image_tolerance,
                "diff_pixels": diff_pixels,
                "total_pixels": total_pixels,
                "baseline_path": baseline_path,
                "message": (
                    f"✓ {artifact_name} matches baseline (within tolerance)"
                    if match
                    else f"✗ {artifact_name} differs from baseline ({diff_pixels}/{total_pixels} pixels)"
                ),
            }

        should_normalize = artifact_type in ("html", "json")
        current_hash = self._compute_file_hash(
            artifact_path, normalize=should_normalize
        )
        baseline_hash = (
            baseline_entry.get("hash")
            if isinstance(baseline_entry, dict)
            else baseline_entry
        )

        hash_match: bool | None = (
            current_hash == baseline_hash if baseline_hash else None
        )

        return {
            "artifact": artifact_name,
            "match": hash_match,
            "comparison_method": "hash",
            "current_hash": current_hash,
            "baseline_hash": baseline_hash,
            "baseline_path": baseline_path,
            "message": (
                f"✓ {artifact_name} matches baseline"
                if hash_match
                else f"✗ {artifact_name} does not match baseline"
                if hash_match is False
                else f"⚠ No baseline for {artifact_name} (first run)"
            ),
        }

    def create_baseline(
        self,
        artifact_name: str,
        artifact_path: Path | str,
        artifact_type: str = "image",
    ) -> dict[str, Any]:
        """Create initial baseline for an artifact."""
        artifact_path = Path(artifact_path)

        if artifact_name in self.hashes:
            return {
                "artifact": artifact_name,
                "created": False,
                "message": f"Baseline already exists for {artifact_name}",
            }

        self.save_baseline(artifact_name, artifact_path, artifact_type)

        return {
            "artifact": artifact_name,
            "created": True,
            "hash": self.hashes[artifact_name]["hash"],
            "message": f"Baseline created for {artifact_name}",
        }

    def update_baseline(
        self, artifact_name: str, artifact_path: Path | str
    ) -> dict[str, Any]:
        """Update existing baseline."""
        artifact_path = Path(artifact_path)
        old_hash = self.hashes.get(artifact_name, {}).get("hash")

        artifact_type = self.hashes.get(artifact_name, {}).get("type", "image")
        self.delete_baseline(artifact_name)
        self.save_baseline(artifact_name, artifact_path, artifact_type)
        new_hash = self.hashes[artifact_name]["hash"]

        return {
            "artifact": artifact_name,
            "updated": True,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "changed": old_hash != new_hash,
            "message": f"Baseline updated for {artifact_name}",
        }
