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
