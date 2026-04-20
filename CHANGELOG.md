# Changelog

All notable changes to this project will be documented in this file.

This project follows **Semantic Versioning**.

https://semver.org/

---

## [1.0.0] - 2026-04-08

### Added

* Initial public release of `pytest-a11y`
* pytest plugin for automated accessibility testing using axe-core
* Interactive HTML reports with violation cards, WCAG references, and pass/fail breakdown
* JSON report output for CI/CD integration
* Per-violation screenshot capture with visual overlays
* WCAG standard configuration via `--a11y-standard` (`wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa`, `section508` and dot-notation aliases)
* Custom axe tag filtering via `--a11y-tags`
* Structured Results API with full type hints (`Results`, `AxeResults`, `AxeRunnerProtocol`)
* `--a11y` flag to enable report generation — tests run as plain assertions without it
* Configurable report output directory via CLI, `pytest.ini`, environment variable, or `conftest.py`
* pytest-xdist parallel execution support
* GitHub Actions and GitLab CI compatibility

---

## [0.1.0] - Initial Development

Initial internal development version.
