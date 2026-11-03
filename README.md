# Phrear

Groundwater modelling platform for QGIS built on MODFLOW 6. Successor in spirit to FREEWAT: flow first, then calibration and solute transport.

Piattaforma di modellazione delle acque sotterranee per QGIS basata su MODFLOW 6: prima il flusso, poi calibrazione e trasporto.

**Status:** pre-alpha, milestone M1a in progress. The project specification is [docs/SPEC.md](docs/SPEC.md) (Italian).

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
