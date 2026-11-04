# 0023 – Accettazione e chiusura di M1b

- Data: 2026-11-04
- Stato: accettata

## Contesto

La sezione 24 chiede per M1b che il progetto di esempio eseguito dal plugin dia risultati identici a quelli da CLI, e una guida rapida per l'utente del plugin. Con gli incrementi 1–5 il plugin crea e apre i progetti, genera form e relazioni dallo schema, controlla ed esegue il modello e carica i risultati (ADR 0018–0022).

## Decisione

- **Confronto dei run.** `scripts/compare_runs.py` (`pixi run compare-runs <run A> <run B>`) confronta due run senza tolleranza:
  - `gwf.hds` byte per byte;
  - ogni variabile di `heads.nc` valore per valore, con i valori mancanti che devono coincidere;
  - i file di input di MODFLOW 6 riga per riga.

  Sono esclusi il commento iniziale con l'ora di FloPy e i file che contengono date, nomi o percorsi del run (listing, manifest, attributi di `heads.nc`).
- **Identici, non vicini.** Plugin e CLI eseguono lo stesso core con lo stesso lockfile, quindi lo stesso MODFLOW 6 sugli stessi file. Qualunque differenza indicherebbe dati o ambiente diversi; una tolleranza la nasconderebbe.
- **Due prove di accettazione.**
  - In CI, a ogni push su Windows: il test `tests/plugin/test_acceptance.py` esegue un run con il comando costruito dal plugin (`core_command`), tramite pixi e con l'ambiente ripulito dalle variabili di QGIS, e un run con `phrear run`, poi li confronta. Il test verifica anche che il confronto rilevi un progetto con una portata diversa.
  - In QGIS 4.2.3 senza finestre: run dal pulsante Esegui del pannello contro run da riga di comando, con esito identico.

  Gli esiti sono in `docs/verification/accettazione-m1b.md`, con la stessa prova da ripetere su Windows.
- **Carichi con il driver indicato.** Il plugin apre `heads.nc` come `Ugrid:"<file>"`. Senza driver MDAL prova prima gli altri formati, e le librerie HDF5 riempiono l'output di QGIS di diagnostica.
- **Guida del plugin.** `docs/guida-plugin.md` ha ora un percorso guidato di dieci passi sul progetto di esempio, dalla creazione ai carichi nel tempo, e i passi per un modello nuovo. I passi seguono l'ordine in cui `check` chiede i dati mancanti, verificato su un progetto costruito passo per passo. Le impostazioni di `project.toml` si modificano per ora con un editor di testo.
- **Chiusura.** M1b è chiusa con la prova su Windows dell'utente: checklist degli incrementi 3–5 e confronto del documento di accettazione.

## Alternative scartate

- **Confronto con tolleranza.** Accetterebbe differenze che non devono esistere.
- **Confronto di tutti i file del run.** Listing e manifest contengono ore e percorsi e differiscono sempre.
- **QGIS nella CI.** Come per l'ADR 0018: il percorso di calcolo del plugin è provato in CI senza QGIS, il pannello nella sessione di sviluppo e dall'utente.

## Conseguenze

- I criteri di accettazione di M1b sono soddisfatti in CI e in QGIS 4.2.3 su Linux; resta la conferma su Windows.
- Restano per le milestone successive:
  - un editor delle impostazioni di `project.toml` nel plugin;
  - le procedure guidate (sez. 18);
  - gli algoritmi Processing;
  - il grafico della convergenza.
- Il passo successivo è M2, parametri completi.
