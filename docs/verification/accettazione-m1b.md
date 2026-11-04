# Accettazione di M1b: plugin e riga di comando

Criterio della sezione 24 della SPEC: il progetto di esempio di M1a eseguito dal plugin dà risultati identici a quelli da CLI.

phrear 0.1.0.dev0, MODFLOW 6 6.8.1, QGIS 4.2.3, 2026-11-04.

## Metodo

Sullo stesso progetto di esempio (`phrear example`) si eseguono due run, uno dal plugin e uno dalla riga di comando, e si confrontano con `pixi run compare-runs <run A> <run B>`:

- `gwf.hds`, i carichi binari scritti da MODFLOW 6, byte per byte;
- ogni variabile di `heads.nc`, valore per valore, con i valori mancanti che devono coincidere;
- i file di input di MODFLOW 6 riga per riga, tranne il commento iniziale in cui FloPy scrive l'ora.

Listing, manifest e attributi di `heads.nc` contengono date, nomi e percorsi del run e non entrano nel confronto. Il confronto non è cieco: sullo stesso progetto con una portata diversa rileva le differenze in `heads.nc` e in `gwf.wel`.

## Esiti

| Prova | Dove | Esito |
|---|---|---|
| Comando costruito dal plugin (`core_command`), tramite pixi, con l'ambiente ripulito dalle variabili di QGIS, contro `phrear run` | CI su Windows, test `tests/plugin/test_acceptance.py` a ogni push | identici |
| Pulsante Esegui del pannello Phrear in QGIS 4.2.3 senza finestre, contro `pixi run phrear run` | Linux, sessione di sviluppo | identici: 421 800 valori di carico in 16 variabili, `gwf.hds` byte per byte, 14 file di input |
| Pulsante Esegui del pannello in QGIS 4 su Windows, contro `pixi run phrear run` | macchina dell'utente | da eseguire (sotto) |

## Prova su Windows

1. In QGIS 4: Plugin → Phrear → Crea il progetto di esempio…, in una cartella nuova.
2. Nel pannello Phrear scrivi `plugin` come nome del run e premi **Esegui**.
3. In PowerShell, dalla cartella del repository:

   ```powershell
   pixi run phrear run "<cartella dell'esempio>" --run-id cli
   pixi run compare-runs "<cartella dell'esempio>\runs\plugin" "<cartella dell'esempio>\runs\cli"
   ```

4. L'esito atteso è `Identical: …`, con codice di uscita 0.
