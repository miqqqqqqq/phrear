# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Repository skeleton: pixi environment locked for Windows (MODFLOW 6.8.1 from conda-forge), package `phrear` with a minimal CLI, EUPL-1.2 license.
- Quality tooling: ruff, mypy (strict), pytest, pre-commit hooks, GitHub Actions CI on Windows.
- Test that the core does not import QGIS or Qt; test that the `mf6` executable matches the version pinned in `pixi.toml`.
- Architecture decision records 0001–0004 in `docs/adr/`.
- `phrear.units`: physical quantities with one internal unit each (m, d), conversion of user units including Italian notations (`m³/anno`, `mm/giorno`); Julian year (ADR 0005).
- `phrear.errors`: error catalogue with stable codes, messages and hints in Italian and English, object references.
- `phrear.events`: event protocol version 1, JSON Lines UTF-8 on a binary stream, JSON Schema export (ADR 0006).
- CLI: `--json` and `--lang` options, usage and runtime errors reported as events, exit codes 0–3, subcommand registry.
