# 0015 – Export dei carichi in NetCDF UGRID

- Data: 2026-11-03
- Stato: accettata

## Contesto

M1a chiede i carichi in NetCDF UGRID, con una variabile per layer, leggibili dai mesh layer di QGIS con dimensione temporale (sez. 17 e 24). Ogni export deve registrare il `run_id` da cui deriva.

## Decisione

- **Fonte.** Il file binario della griglia del run (`gwf.dis.grb`), il file dei carichi (`gwf.hds`) e il manifest. L'export descrive il run anche se il progetto è cambiato dopo.
- **Mesh.** Una faccia per colonna della griglia, nodi agli spigoli in senso antiorario, con le convenzioni DIS di MF6 (origine, rotazione). Coordinate dei nodi e dei centri faccia in metri nel CRS del progetto.
- **Variabili sulle facce.**
  - `head_l<k>` (tempo, faccia): carico del layer k; mancante nelle celle inattive, a passaggio verticale o asciutte (cella convertibile con carico sotto la base).
  - `head_upper` (tempo, faccia): carico della prima cella attiva satura dall'alto, cioè la superficie freatica dove la colonna è libera e il carico piezometrico dove è confinata.
  - `top`, `bottom_l<k>`, `idomain_l<k>`: geometria dei layer.
- **Tempo.** Giorni dalla data di inizio del modello, calendario standard. Lo stato stazionario iniziale sta a 0, gli altri valori alla fine del loro passo.
- **CRS.** Variabile `projected_coordinate_system` con i parametri CF, il WKT e gli attributi `epsg` ed `EPSG_code` cercati da MDAL, la libreria dei mesh di QGIS.
- **Metadati.** `run_id`, nome e hash di contenuto del progetto, versioni di phrear e MF6, convenzioni CF-1.8 UGRID-1.0.
- **File.** `runs/<run_id>/heads.nc`, compresso. Si scrive in un file temporaneo e lo si sostituisce solo a scrittura completata; se il file è aperto in un altro programma (lock di Windows), l'errore lo dice. `phrear run` lo scrive alla fine di ogni run riuscito, `phrear export` lo rigenera per un run scelto o per l'ultimo completato.

## Alternative scartate

- **Una variabile (tempo, layer, faccia).** MDAL non la presenta come dataset per layer; la SPEC chiede una variabile per layer.
- **Carichi delle celle asciutte.** Con Newton MF6 calcola un carico anche sotto la base; mostrarlo in mappa farebbe credere a una falda che non c'è.
- **Griglia ricostruita dal progetto.** Se il progetto cambia dopo il run, l'export non corrisponderebbe ai risultati.

## Conseguenze

- Il caricamento come mesh layer va verificato in QGIS 4; se MDAL non riconosce il CRS, si imposta a mano finché non si corregge l'attributo.
- Il viewer 3D potrà ricostruire i volumi da `top`, `bottom_l<k>` e `idomain_l<k>`.
