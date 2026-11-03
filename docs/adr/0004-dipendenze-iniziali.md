# 0004 – Dipendenze iniziali e loro licenze

- Data: 2026-11-03
- Stato: accettata

## Contesto

La sezione 6 della spec vieta nuove dipendenze senza motivo, alternative e licenza registrati. Il core è distribuito con licenza EUPL-1.2, quindi ogni dipendenza deve avere una licenza permissiva o copyleft debole a collegamento dinamico.

## Decisione

Dipendenze dell'ambiente di M1a, con versione risolta nel lockfile al 2026-11-03 e licenza dichiarata dal pacchetto conda-forge.

| Pacchetto | Versione | Licenza | Uso |
|---|---|---|---|
| python | 3.12.16 | Python-2.0 | interprete |
| modflow6 | 6.8.1 | CC0-1.0 | motore di calcolo (ADR 0001) |
| flopy | 3.12.0 | CC0-1.0 | scrittura e lettura dei file MF6, intersezioni con la griglia |
| numpy | 2.5.4 | BSD-3-Clause | array |
| pandas | 3.1.0 | BSD-3-Clause | tabelle e serie temporali |
| xarray | 2026.9.0 | Apache-2.0 | array etichettati, NetCDF |
| netcdf4 | 1.7.4 | MIT | scrittura NetCDF |
| geopandas | 1.2.0 | BSD-3-Clause | feature vettoriali |
| shapely | 2.2.0 | BSD-3-Clause | geometria (GEOS) |
| pyogrio | 0.13.0 | MIT | lettura e scrittura del GeoPackage |
| rasterio | 1.5.2 | BSD-3-Clause | raster di superfici e parametri |
| pyproj | 3.8.0 | MIT | sistemi di riferimento |
| xugrid | 0.15.3 | MIT | NetCDF UGRID per i mesh layer di QGIS |
| pint | 0.26.2 | BSD-3-Clause | unità di misura |
| pydantic | 2.14.2 | MIT | validazione di `project.toml` |
| matplotlib-base | 3.11.2 | PSF-2.0 | grafici dei report di verifica |

Librerie native principali: GDAL 3.13.3 (MIT), GEOS 3.14.1 (LGPL-2.1-only, collegata dinamicamente), PROJ 9.9.0 (MIT), HDF5 2.2.0 (BSD-3-Clause), netCDF-C 4.10.1 (MIT).

Strumenti di sviluppo, non distribuiti: pytest 9.2.0, ruff 0.17.3, mypy 2.4.1, pre-commit 4.7.0, tutti MIT.

`modflowapi`, `gstools`, PyVista e PEST++ previsti nella sezione 6 entrano con le milestone che li usano, ciascuno con la propria voce.

## Alternative scartate

Le alternative per ambito sono quelle della sezione 6 della spec. Nessuna dipendenza con licenza incompatibile con EUPL-1.2.

## Conseguenze

Ogni aggiornamento del lockfile che cambia una licenza va riportato in questo registro.
