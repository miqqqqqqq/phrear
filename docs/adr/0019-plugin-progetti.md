# 0019 – Plugin QGIS: progetti, layer e modifiche in sospeso

- Data: 2026-11-04
- Stato: accettata

## Contesto

L'incremento 2 di M1b porta nel plugin la creazione, l'apertura e il riepilogo dei progetti (sez. 18 e 24). La sezione 5 chiede che il plugin non contenga logica del modello e che le modifiche aperte non vengano ignorate dai comandi del core. Nel collaudo dell'incremento 1 è emerso che il clic su un comando non dava alcun segnale durante i secondi di avvio di pixi.

## Decisione

- **Nuovo progetto ed esempio.** Dialoghi del plugin che validano nome, cartella nuova o vuota, codice EPSG e date, e poi eseguono `phrear new` o `phrear example`. La cartella del progetto viene proposta dal nome (lettere ASCII, cifre, `_` e `-`) e resta modificabile. L'ultima cartella usata è ricordata.
- **Apertura.** `phrear info` dà nome, CRS e conteggi, `phrear schema` (letto una volta per sessione) dà tabelle, geometrie ed etichette IT/EN. Il plugin carica ogni tabella di `model.gpkg` come layer OGR in un gruppo «Phrear – <nome>» in cima all'albero:
  - sottogruppo «Modello concettuale» con i layer geometrici, punti, poi linee, poi poligoni;
  - sottogruppo «Tabelle», chiuso.

  Nomi e ordine vengono dallo schema del core, non da una copia nel plugin. Ogni layer porta la proprietà `phrear/table`, il gruppo la proprietà `phrear/project`.
- **Progetto QGIS.** Il percorso del progetto Phrear è salvato nel progetto QGIS (voce `Phrear/project`), così i comandi successivi sanno su quale progetto lavorare. Se il progetto QGIS è vuoto ne prende il CRS. La mappa si centra sul dominio. Un progetto già aperto non viene caricato una seconda volta.
- **Modifiche in sospeso.** Prima di un comando sul progetto, se un layer che legge `model.gpkg` ha modifiche non salvate, il plugin chiede di salvare, scartare o annullare. Un salvataggio non riuscito ferma il comando e mostra gli errori di QGIS.
- **Indicatore.** Ogni comando mostra nella barra dei messaggi «<azione> in corso…» con una barra animata, che segue gli eventi `progress` quando ci sono, e un pulsante Annulla. L'indicatore sparisce alla risposta del core.

## Alternative scartate

- **Elenco dei layer scritto nel plugin.** Si disallineerebbe dallo schema a ogni migrazione.
- **Un layer QGIS per tutto il GeoPackage**, cioè il raggruppamento automatico di QGIS: niente nomi in italiano, niente ordine per geometria, niente distinzione tra layer e tabelle.
- **Salvataggio automatico delle modifiche senza chiedere.** Le modifiche dell'utente vanno confermate.

## Conseguenze

- I comandi di controllo ed esecuzione (incremento 4) useranno il progetto associato e la stessa verifica delle modifiche.
- I form generati dallo schema (incremento 3) si applicheranno ai layer riconosciuti dalla proprietà `phrear/table`.
