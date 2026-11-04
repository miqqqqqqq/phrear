# 0021 – Plugin QGIS: pannello di controllo ed esecuzione

- Data: 2026-11-04
- Stato: accettata

## Contesto

L'incremento 4 di M1b porta nel plugin il controllo e l'esecuzione del progetto (sez. 18, pannello di esecuzione; sez. 9, punti 8 e 9). Gli errori devono essere «collegati alla feature o alla cella interessata». L'ADR 0020 lasciava aperto un errore di GDAL sull'estensione dei layer dopo un salvataggio in QGIS.

## Decisione

- **Pannello Phrear.** Pannello agganciabile (`QgsDockWidget`) aperto dal menu, dalla barra e da solo all'apertura di un progetto. Contiene:
  - il progetto associato al progetto QGIS;
  - il nome del run, facoltativo;
  - i pulsanti Controlla (`phrear check`), Esegui (`phrear run`) e Annulla;
  - lo stato e una barra di avanzamento che segue gli eventi `progress`;
  - la scheda Problemi, con l'esito di ogni fase del controllo ed errori e avvisi;
  - la scheda Log, con l'ora locale di ogni evento.

  Prima di ogni comando il plugin chiede di salvare le modifiche in sospeso (ADR 0019). Durante il comando i pulsanti sono disattivati e la barra dei messaggi non mostra il suo indicatore.
- **Problemi.** Ogni problema mostra il messaggio del core, il luogo (layer e campo con le etichette dello schema, `fid`, cella contata da 1, file), il codice e il suggerimento. Se il riferimento indica un layer e un `fid`, due collegamenti:
  - «Mostra la feature» seleziona la feature, la centra e la evidenzia; per una tabella apre la tabella degli attributi filtrata su quella riga;
  - «Apri il form» apre il form della feature.

  L'esito riassuntivo del controllo (`check.failed`) va nello stato e non diventa una riga. Gli altri esiti negativi del comando, come un run già esistente o un nome non valido, compaiono come errori. Le regole sul nome del run restano nel core: il plugin passa il nome e mostra l'errore del core.
- **Etichette delle fasi.** Il risultato di `check` riporta per ogni fase anche l'etichetta in italiano e in inglese, così il plugin non ripete l'elenco delle fasi.
- **Logica senza Qt.** `client/runs.py` costruisce argomenti, righe dei problemi, fasi, voci di log e riepilogo del run. È testato in CI con eventi reali del core su un progetto di esempio con un errore.
- **Estensione dei layer.** La causa dell'errore lasciato aperto dall'ADR 0020 è la modalità «nolock» di SQLite. QGIS apre in quella modalità i layer GeoPackage in sola lettura; quando una sessione di modifica passa il file al journal WAL, quelle connessioni non riescono più a leggere e l'estensione dei layer non si calcola. Il problema non dipende dal core: si riproduce con un GeoPackage creato da GDAL. Il plugin apre ora i layer del progetto con l'opzione `NOLOCK=NO`, e aggiorna la sorgente dei layer salvati senza opzione quando un progetto QGIS viene riaperto. Nelle prove il problema non si presenta più, con il core eseguito tra un salvataggio e l'altro. La correzione dell'estensione nel core prevista dall'ADR 0020 non serve.

## Alternative scartate

- **Errori nella barra dei messaggi o in una finestra.** Spariscono o bloccano QGIS, e non restano accanto alla mappa mentre si correggono i dati.
- **Elenco dei problemi in una vista ad albero.** In un pannello stretto tronca i messaggi lunghi; il testo con collegamenti va a capo.
- **Controllo del nome del run nel plugin.** Duplicherebbe la regola del core.
- **Estensione aggiornata dal core.** Avrebbe evitato l'errore solo per i layer con feature, mentre i layer vuoti continuavano a darlo.

## Conseguenze

- I layer del progetto possono tenere brevi blocchi di lettura sul GeoPackage. Quando il core scriverà su `model.gpkg` con QGIS aperto (migrazioni, import) andrà verificato che l'attesa di SQLite basti.
- I risultati del run (carichi come mesh layer, elenco dei run) arrivano nell'incremento 5. Per ora il log indica la cartella del run.
- Un run annullato dopo la scrittura dei file lascia la sua cartella in `runs/`, con il manifest che non lo dà come completato; l'elenco dei run dell'incremento 5 dovrà mostrarlo come tale.
