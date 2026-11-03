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
- Project format (schema 1): `project.toml` validated with pydantic and written with tomlkit keeping comments (ADR 0007); GeoPackage with the M1a tables, unique indexes, timestamp triggers and the ST_* functions needed by the R-tree triggers (ADR 0008).
- Content hashes of settings, GeoPackage tables and rasters; migration framework with backup.
- Commands `new`, `info`, `schema` (data schema and event protocol as JSON) and `migrate`; `result` event.
- Time discretisation (ADR 0009): time series with exact values and averages, stress periods at regime changes, merge of short periods, automatic time steps, steady-state values, MF6 time series records; `[time]` settings; command `calendar`.
- Engine test: MF6 well volumes equal the exact integral of stepwise and linear series.
- Geometry and grid (ADR 0010): rotated DIS grid with MF6 conventions, active cells by centroid or area fraction, contact surfaces sampled as cell means of the bilinear interpolant, checks on crossing surfaces, coverage, raster CRS, DEM, thin units and isolated cells, layering with sublayers and vertical pass-through cells; command `grid` with GeoPackage export of the cells.
- Parameters and initial heads (ADR 0011): uniform values per unit read from `param_values` with unit conversion and provenance, required parameters, errors and plausibility warnings, arrays per layer for NPF and STO; initial heads constant or sampled from a raster, warning on columns dry below the lowest active cell; command `params`.
- Boundary conditions (ADR 0012): registry of boundary types with package-neutral assignments (cell, forcing, multiplier, boundname); intersection of points, lines and polygons with the rotated grid; wells (WEL) shared among screened layers by transmissivity; fixed heads (CHD) from stations along lines, interpolated by chainage with exactly combined series, and over areas; recharge (RCH) on the uppermost active cell with the covered fraction; checks against MF6 constraints (fixed heads below the cell bottom, duplicate fixed heads); stress period records and time series records; command `bc` with GeoPackage export of the assigned cells.
- Pre-run checks (ADR 0013): inspection of the project in stages with dependencies, error collector gathering one error per parameter row, unit and boundary feature, registry of model checks (steady period without fixed heads, wells in fixed head cells, magnitude of rates and recharge, Newton off with convertible units); command `check` listing every error and warning, exit code 1 on errors.
- Build and run (ADR 0014): `phrear.modflow` writes the MF6 simulation with FloPy (TDIS, IMS presets, GWF with DIS, IC, NPF, STO, WEL, CHD, RCH, OC) at 15 significant digits, period blocks only on change, TS files grouped by shared dates; `manifest.json` with versions, content hashes, settings and outcome; execution with the `mf6` executable, progress events, listing and budget checks; commands `build` and `run`. Engine test: fixed heads, well rates and recharge reproduced exactly by MF6.
