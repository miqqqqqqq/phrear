# 0020 – Plugin QGIS: form, relazioni e stili dallo schema

- Data: 2026-11-04
- Stato: accettata

## Contesto

L'incremento 3 di M1b porta i form delle feature «con unità, default, intervalli e descrizioni, generati dallo schema JSON» (sez. 18), senza una copia dello schema nel plugin (sez. 5, ADR 0008). Lo schema descriveva campi e tabelle ma non i legami tra tabelle: per mostrare i parametri nel form di un'unità, i valori nel form di una serie e le stazioni nel form di una linea servono relazioni dichiarate nel core.

## Decisione

- **Schema del core.** `project/schema.py` dichiara, e `phrear schema` esporta:
  - **relazioni** (`RELATIONS`):
    - parametri dell'unità, `param_values.object_id` → `hydro_units.fid` con `object_type = unit`;
    - valori della serie, `timeseries_values.series_id` → `timeseries_meta.series_id`;
    - stazioni, `line_stations.feature_id` → `fid` di `fixed_head_lines` o `fixed_head_areas` secondo `feature_layer` (relazione polimorfica);
  - **liste di valori** (`Lookup`: tabella, chiave, campo mostrato, filtro):
    - `series_id` di pozzi, stazioni e zone di ricarica limitato alle serie di portata, livello e velocità;
    - `scenario_id` dalla tabella degli scenari;
    - `top_unit` e `bottom_unit` per posizione, con il nome dell'unità;
  - **stile** di ogni layer geometrico (`LayerStyle`): tipo di simbolo, colore, contorno, dimensioni, opacità.

  Due test verificano che ogni relazione e ogni lista punti a tabelle e campi esistenti e che ogni layer geometrico abbia uno stile del suo tipo. `object_type` di `param_values` ha ora il default `unit`, e un valore vuoto vale `unit` anche in lettura.
- **Piano senza Qt.** `client/forms.py` ricava dallo schema alias, widget, vincoli, default, relazioni, espressioni di visualizzazione e simboli; è testato in CI. `forms.py` li applica ai layer appena caricati.
- **Campi.**
  - Alias con l'unità: «Inizio filtro [m]».
  - Widget:
    - scelte → elenco (value map);
    - liste di valori → value relation filtrata;
    - booleani → casella;
    - interi → spin box con minimo e massimo;
    - date → calendario;
    - reali → casella di testo, perché lo spin box di QGIS arrotonda alla precisione del campo, che nel GeoPackage è 0;
    - note → testo su più righe.
  - Ogni widget accetta il valore vuoto, anche per i campi obbligatori. Un elenco o una data che non possono restare vuoti riempirebbero il campo con la prima voce o con la data di oggi senza che l'utente se ne accorga.
- **Vincoli.**
  - Obbligatorio e unico su un solo campo: vincolo rigido, la feature non si salva.
  - Fuori intervallo: vincolo debole, avviso nel form.

  Il core li ricontrolla tutti con `check`.
- **Default e ordine.** I default sono quelli dello schema, come espressioni di QGIS. Ordine nel form:
  - `fid`;
  - campi modificabili nell'ordine dello schema;
  - note;
  - campi di sistema (`created_at`, `modified_at`, mantenuti dai trigger), in sola lettura.

  Seguono gli editor delle relazioni e un riquadro chiuso «Guida» con la descrizione della tabella e dei campi.
- **Relazioni.**
  - Composizione: eliminare in QGIS un'unità, una serie o una linea ne elimina parametri, valori o stazioni, dopo la conferma che QGIS chiede.
  - Una relazione con filtro sul figlio (parametri delle unità) diventa una relazione polimorfica con un solo padre. QGIS mostra così solo i figli con `object_type = unit` e assegna il valore ai figli aggiunti dal form.
  - Per le stazioni ogni layer porta la variabile `phrear_table` con il nome della tabella, che è il valore di `feature_layer`.
  - Gli id delle relazioni contengono un hash della cartella del progetto, così due progetti aperti insieme non si scontrano.
- **Stili.** Simbolo unico dallo schema. Il dominio ha solo il contorno; aree e zone hanno un riempimento trasparente.
- **Date e ore.** Durante le prove è emerso che QGIS scrive nel GeoPackage una data in ora locale senza fuso (calcolatore di campi, Python, copia e incolla) convertendola in UTC. Il 15 luglio alle 00:00 diventava il 14 luglio alle 22:00Z, e il core, che legge l'ora civile e ignora il fuso (ADR 0007), l'avrebbe spostata di due ore. Il calendario del form scrive invece la data con il suo scarto (`2024-07-15T00:00:00+02:00`), che conserva l'ora. Prima di ogni salvataggio il plugin dà il fuso del sistema alle date senza fuso, così vengono scritte allo stesso modo.
- **Persistenza.** Form, relazioni, stili e variabili si salvano nel progetto QGIS. Le date sono protette anche nei layer riaperti da un progetto QGIS salvato.

## Alternative scartate

- **Form `.ui` o codice per ogni layer.** Duplicano lo schema e si disallineano alle migrazioni.
- **Intervalli come vincolo rigido.** Bloccherebbero il salvataggio di un dato da correggere dopo; `check` li riporta comunque come errori.
- **Relazioni di associazione.** Lascerebbero parametri, valori e stazioni senza padre.
- **Relazione semplice per i parametri delle unità.** Mostrerebbe anche i parametri delle zone con lo stesso `object_id`, dalla M2.
- **Conversione delle date nel core con il fuso della macchina.** I risultati dipenderebbero dalla macchina su cui gira il core.
- **Date salvate come testo nel GeoPackage.** Eviterebbero la conversione, ma richiedono una migrazione dei progetti esistenti.

## Conseguenze

- Un campo nuovo dello schema ha il suo form senza codice del plugin; una relazione o una lista nuova si dichiarano solo in `schema.py`.
- Nel GeoPackage le date possono avere uno scarto di fuso (`+01:00`, `+02:00`), che il core ignora.
- **Problema aperto, poi risolto.** Dopo un salvataggio in QGIS, GDAL non riusciva più a calcolare l'estensione degli altri layer dello stesso GeoPackage («unable to open database file»). La causa è la modalità «nolock» con cui QGIS apre i layer in sola lettura, e la correzione è nel plugin (ADR 0021).
