# 0017 – Progetto di esempio, registro degli exporter, chiusura di M1a

- Data: 2026-11-03
- Stato: accettata

## Contesto

Per chiudere M1a la sezione 24 chiede un progetto di esempio completo eseguibile da CLI, una guida rapida per la CLI e una guida per gli sviluppatori. L'ambito comprende anche il registro `Exporter`, non ancora presente dopo l'incremento 10.

## Decisione

- **Esempio generato dal codice.** `phrear example <cartella>` crea il progetto con `phrear.project.editing`, che scrive feature, righe e raster come farebbe l'utente in QGIS. Il repository non contiene binari (GeoPackage, GeoTIFF) che cambierebbero hash a ogni rigenerazione, e l'esempio segue sempre lo schema corrente.
- **Contenuto dell'esempio.** Piana alluvionale sintetica di 3 × 2 km in EPSG:7791 (sito inventato) con:
  - limi di copertura convertibili, che si chiudono a ovest, su ghiaie e sabbie in due sotto-layer;
  - limite a monte a 47 m posto mezza cella dentro il dominio;
  - fiume con livelli mensili a due stazioni;
  - pozzo idropotabile a 15 l/s e pozzo irriguo stagionale (10 l/s da aprile, 20 l/s da giugno, fermo da settembre);
  - ricarica di 250 e 80 mm/anno su zone che non si sovrappongono;
  - il 2024 dopo uno stato stazionario.

  Ogni elemento di M1a è presente; `check` dà un solo avviso, quello voluto sulla copertura che si chiude.
- **Regressione.** Un test esegue l'esempio e confronta i carichi di tre colonne, nello stato stazionario e a fine 2024, con valori di riferimento entro 10⁻³ m. Una modifica che li cambia va giustificata (sezione 20).
- **Registro `Exporter`.** Nome, etichette, formato, file prodotto e funzione `write(cartella del run, manifest, data)`. Il primo exporter è `heads` (NetCDF UGRID, ADR 0015). `phrear export --format` sceglie tra gli exporter registrati, e `run` usa `heads`.
- **Guide.** `docs/guida-rapida-cli.md` va dall'installazione ai carichi in QGIS; `docs/guida-sviluppatori.md` copre struttura, flusso dei dati, convenzioni ed estensione dei registri.

## Alternative scartate

- **Esempio salvato come file nel repository.** Binari da aggiornare a ogni cambio di schema, con hash instabili.
- **Esempio su un sito reale.** Richiede dati con licenza chiara; il caso reale è previsto tra M3 e M4.

## Conseguenze

- I criteri di accettazione di M1a sono soddisfatti:
  - verifica Thiem, Theis e Dupuit (ADR 0016);
  - progetto di esempio eseguibile da CLI;
  - nessun import di QGIS nel core (test dedicato);
  - guide.
- Il passo successivo è M1b, il plugin minimo, che crea il progetto, esegue tramite la CLI e carica `heads.nc` come mesh layer.
