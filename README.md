# Phrear

Groundwater modelling platform for QGIS built on MODFLOW 6. Successor in spirit to FREEWAT: flow first, then calibration and solute transport.

Piattaforma di modellazione delle acque sotterranee per QGIS basata su MODFLOW 6: prima il flusso, poi calibrazione e trasporto.

**Status:** pre-alpha. Milestone M1a (core, CLI, numerical verification) is complete; M1b, the minimal QGIS plugin, is in progress. The project specification is [docs/SPEC.md](docs/SPEC.md) (Italian).

Documentation (Italian):

- [Guida rapida da riga di comando](docs/guida-rapida-cli.md)
- [Guida per gli sviluppatori](docs/guida-sviluppatori.md)
- [Plugin per QGIS 4](docs/guida-plugin.md)
- [Report di verifica](docs/verification/report.md): Thiem, Theis, Dupuit, flusso 1D
- [Decisioni architetturali](docs/adr/README.md)

## Quick start

```powershell
pixi install
pixi run phrear example C:\temp\esempio
pixi run phrear check C:\temp\esempio
pixi run phrear run C:\temp\esempio
```

The heads of the run are in `runs/<run_id>/heads.nc`, a NetCDF UGRID file that QGIS opens as a mesh layer.

## Development

Requirements: [pixi](https://pixi.sh). Supported platform: Windows.

```powershell
pixi install
pixi run check      # lint, type check, tests
pixi run phrear --version
```

## License

- Core (`src/phrear`): [EUPL-1.2](LICENSE)
- QGIS plugin (`qgis_plugin/`): GPL-2.0-or-later

Copyright © 2026 Michele.
