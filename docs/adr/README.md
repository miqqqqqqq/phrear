# Registro delle decisioni architetturali (ADR)

Ogni decisione presa durante lo sviluppo ha un file numerato in questa cartella e una riga nella sezione 27 di [SPEC.md](../SPEC.md). Le decisioni 1–26 della sezione 27 precedono l'avvio dello sviluppo e non hanno un file dedicato.

| ADR | Titolo | Stato | Sez. 27 |
|---|---|---|---|
| [0001](0001-ambiente-pixi.md) | Ambiente pixi, Python 3.12, MODFLOW 6.8.1 da conda-forge | accettata | 29 |
| [0002](0002-cli-argparse.md) | CLI con argparse | accettata | 30 |
| [0003](0003-windows-github.md) | Piattaforma Windows, hosting e CI su GitHub | accettata | 27, 28 |
| [0004](0004-dipendenze-iniziali.md) | Dipendenze iniziali e loro licenze | accettata | – |
| [0005](0005-unita-interne.md) | Unità interne e convenzioni sulle unità | accettata | 31 |
| [0006](0006-protocollo-eventi.md) | Protocollo degli eventi, errori e codici di uscita | accettata | 32 |
| [0007](0007-project-toml.md) | project.toml: pydantic e tomlkit | accettata | 33 |
| [0008](0008-schema-geopackage-v1.md) | Schema GeoPackage versione 1 | accettata | 34 |
| [0009](0009-discretizzazione-temporale.md) | Discretizzazione temporale | accettata | 35 |
| [0010](0010-geometria-e-griglia.md) | Geometria e griglia DIS | accettata | 36 |
| [0011](0011-parametri-e-carichi-iniziali.md) | Parametri uniformi per unità e carichi iniziali | accettata | 37 |
| [0012](0012-condizioni-al-contorno-m1a.md) | Condizioni al contorno di M1a: pozzi, carichi imposti, ricarica | accettata | 38 |
| [0013](0013-controlli-pre-run.md) | Controlli pre-run e comando `check` | accettata | 39 |
| [0014](0014-build-e-run-mf6.md) | Build e run di MODFLOW 6 in M1a | accettata | 40 |
| [0015](0015-export-carichi-netcdf-ugrid.md) | Export dei carichi in NetCDF UGRID | accettata | 41 |
| [0016](0016-verifica-analitica.md) | Verifica con soluzioni analitiche e comando `verify` | accettata | 42 |
| [0017](0017-esempio-e-chiusura-m1a.md) | Progetto di esempio, registro degli exporter, chiusura di M1a | accettata | 43 |
| [0018](0018-plugin-qgis-architettura.md) | Plugin QGIS: collegamento al core, processi, traduzioni, pacchetto | accettata | 44 |
| [0019](0019-plugin-progetti.md) | Plugin QGIS: progetti, layer e modifiche in sospeso | accettata | 45 |
| [0020](0020-plugin-form-relazioni-stili.md) | Plugin QGIS: form, relazioni e stili dallo schema | accettata | 46 |
| [0021](0021-plugin-pannello-controllo-esecuzione.md) | Plugin QGIS: pannello di controllo ed esecuzione | accettata | 47 |
| [0022](0022-plugin-risultati.md) | Plugin QGIS: risultati, elenco dei run, griglia e celle | accettata | 48 |
| [0023](0023-accettazione-e-chiusura-m1b.md) | Accettazione e chiusura di M1b | accettata | 49 |
| [0024](0024-m2-schema-2-e-regole-dei-parametri.md) | M2: schema 2, migrazione e regole di assegnazione dei parametri | accettata | 50 |
| [0025](0025-parametri-per-cella-uniformi-e-zone.md) | Parametri per cella: valori uniformi e zone | accettata | 51 |

## Modello

```markdown
# NNNN – Titolo

- Data: AAAA-MM-GG
- Stato: proposta | accettata | sostituita da NNNN

## Contesto
## Decisione
## Alternative scartate
## Conseguenze
```
