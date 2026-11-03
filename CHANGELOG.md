# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Repository skeleton: pixi environment locked for Windows (MODFLOW 6.8.1 from conda-forge), package `phrear` with a minimal CLI, EUPL-1.2 license.
- Quality tooling: ruff, mypy (strict), pytest, pre-commit hooks, GitHub Actions CI on Windows.
- Test that the core does not import QGIS or Qt; test that the `mf6` executable matches the version pinned in `pixi.toml`.
- Architecture decision records 0001–0004 in `docs/adr/`.
