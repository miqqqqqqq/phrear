# Guida per gli sviluppatori

La specifica è [SPEC.md](SPEC.md); le decisioni prese durante lo sviluppo sono negli [ADR](adr/README.md). Questa guida descrive come è organizzato il core e come si estende.

## Ambiente e comandi

```powershell
pixi install
pixi run check       # lint, type check e test, come la CI
pixi run test        # solo i test
pixi run format      # formattazione e correzioni automatiche di ruff
pixi run typecheck   # mypy in modalità strict
```

La CI (GitHub Actions su Windows) esegue lint, type check e test a ogni push su `main`. I test marcati `engine` eseguono MODFLOW 6 e girano anche in CI; da soli si lanciano con `pixi run pytest -m engine`. Linux è usato solo per lo sviluppo.

## Struttura del core

| Modulo | Contenuto |
|---|---|
| `cli.py`, `commands/` | riga di comando; ogni file registra i suoi comandi in `COMMANDS` |
| `errors.py` | catalogo dei codici di errore e avviso con testi IT/EN e suggerimenti; `ErrorCollector` |
| `events.py` | protocollo degli eventi JSON (ADR 0006) |
| `units.py` | grandezze fisiche e unità interne, m e d (ADR 0005) |
| `project/` | `project.toml`, schema unico del GeoPackage, hash, migrazioni, lettura e scrittura delle feature |
| `timeline/` | serie temporali, calendario degli stress period, record TS (ADR 0009) |
| `grid/`, `geology/` | griglia DIS, campionamento delle superfici, layer (ADR 0010) |
| `params/`, `conceptual/` | parametri per unità e per layer, carichi iniziali (ADR 0011) |
| `boundaries/` | registro delle condizioni al contorno e assegnazioni per cella (ADR 0012) |
| `checks/` | ispezione per fasi e registro dei controlli (ADR 0013) |
| `modflow/` | file MF6 con FloPy, manifest, esecuzione (ADR 0014) |
| `results/` | registro degli exporter, carichi in NetCDF UGRID (ADR 0015) |
| `verification/` | casi di verifica analitica e report (ADR 0016) |
| `examples/` | progetto di esempio |

Il core non importa QGIS né Qt, e un test lo verifica. Il plugin comunica con il core solo tramite CLI, eventi JSON e file del progetto.

## Flusso dei dati

```
project.toml + model.gpkg + rasters/
  → project_timeline        calendario e serie in unità interne
  → build_model_grid        griglia, quote, IDOMAIN
  → load_parameters         parametri per unità → layer_parameters
  → initial_heads
  → build_boundaries        assegnazioni (cella, forzante, moltiplicatore, boundname)
  → inspect_project         tutto quanto sopra, più i controlli registrati
  → build_run / execute     file MF6, manifest, run
  → EXPORTERS               prodotti del run (heads.nc)
```

`inspect_project` è il punto d'ingresso comune: `check` lo usa per elencare tutti i problemi, `build` e `run` per fermarsi se ce ne sono.

## Convenzioni

- **Codice e testi.** Codice, commenti e messaggi di commit in inglese. Testi per l'utente in italiano e inglese, nel catalogo di `errors.py`. Documentazione in italiano.
- **Unità.** Dentro il core tutto è in metri e giorni. La conversione avviene una sola volta, alla lettura, con `units.conversion_factor`; il valore originale e la sua unità restano accanto al valore interno.
- **Errori.** Mai un'eccezione generica per un problema dei dati. Si usa un codice del catalogo con un `ObjectRef` che indica layer, fid e campo. Un problema che non impedisce il calcolo diventa un avviso (`Problem.from_code`).
- **Nessuna correzione silenziosa.** Un dato incoerente produce un errore o un avviso e non viene modificato.
- **Schema unico.** Layer e campi del GeoPackage sono definiti solo in `project/schema.py`; creazione, export JSON e migrazioni derivano da lì.
- **Decisioni.** Ogni scelta che cambia comportamento o formato ha un ADR in `docs/adr/` e una riga nella sezione 27 della SPEC.

## Come si estende

- **Un comando.** Un `CommandSpec(name, help, configure, handler)` nella lista `COMMANDS` di un modulo di `commands/`, registrato in `commands/__init__.py`. Il handler riceve `Context` e usa `ctx.result`, `ctx.warn` ed eventuali eventi, così funziona sia in testo sia con `--json`.
- **Un tipo di condizione al contorno.** Un `BoundaryConditionType` con la funzione `build(ctx) -> PackageInput`, aggiunto con `boundaries.registry.register`. Gli errori per feature passano da `ctx.errors.fail(...)`, così `check` li raccoglie tutti. La scrittura del pacchetto MF6 va aggiunta in `modflow/simulation.py`.
- **Un controllo.** Un `Check` con severità, fasi richieste e funzione `run(ins) -> list[Problem]`, aggiunto con `checks.registry.register`; il codice e i testi vanno nel catalogo.
- **Un exporter.** Un `Exporter` con la funzione `write(folder, manifest, created) -> Path`, aggiunto con `results.exporters.register`; diventa una scelta di `phrear export --format`.
- **Un caso di verifica.** Un `Case` in `verification/cases.py`, con la costruzione del progetto (via `project.editing`), il confronto con la soluzione analitica e la tolleranza; compare in `verify` e nei test `engine`.

## Test

- `tests/unit/sites.py` costruisce un sito sintetico (dominio, due unità, superfici) condiviso dalla maggior parte dei test; `tests/unit/conftest.py` aggiunge parametri validi (`valid_site`) e un modello completo (`model_site`).
- I test sul motore confrontano i risultati di MF6 con valori attesi esatti: carichi CHD, portate, ricarica, soluzioni analitiche e valori di regressione del progetto di esempio.
- Una modifica che cambia i valori di regressione del progetto di esempio (`tests/unit/examples/`) va giustificata nel commit.
