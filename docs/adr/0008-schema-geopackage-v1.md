# 0008 – Schema GeoPackage versione 1

- Data: 2026-11-03
- Stato: accettata

## Contesto

La sezione 8.2 della spec elenca layer e tabelle del modello concettuale. M1a richiede la prima versione dello schema e i meccanismi che lo rendono tracciabile e aggiornabile: hash di contenuto, stato "modificato" e migrazioni con backup.

## Decisione

- **Fonte unica.** `phrear/project/schema.py` è la fonte unica. Creazione, validazione e documento JSON per il plugin (`phrear schema`) derivano da lì. Per ogni campo lo schema dichiara tipo, unità o grandezza, default, scelte ammesse, intervallo ed etichette in italiano e inglese.
- **Tabelle della versione 1.** `domain`, `hydro_units`, `surfaces`, `param_values`, `wells`, `fixed_head_lines`, `fixed_head_areas`, `line_stations`, `recharge_zones`, `timeseries_meta`, `timeseries_values`, `scenarios`, `scenario_changes`, `change_log`. Le altre tabelle della sezione 8.2 arrivano con le milestone che le usano, tramite migrazioni numerate.
- **Un layer per tipo di geometria.** Le feature "linea o poligono" della spec diventano due layer (`fixed_head_lines`, `fixed_head_areas`), perché QGIS digitalizza un solo tipo per layer. Si usano i tipi Multi, così gli shapefile importati con parti multiple non vanno convertiti.
- **Nomi senza parole riservate.** `order` diventa `position`, `index` diventa `surface_index`. In `scenario_changes`, `layer` e `fid` diventano `target_layer` e `target_fid`, perché `fid` è la chiave primaria di ogni tabella GeoPackage.
- **Default nello schema.** I default stanno nello schema e non nelle colonne SQL. Li applicano il core in lettura e i form del plugin. GDAL non espone i default di colonna, e SQLite non li modifica senza ricreare la tabella.
- **Timestamp.** `created_at` e `modified_at` sono mantenuti da trigger SQLite, in UTC con formato GeoPackage `AAAA-MM-GGTHH:MM:SS.sssZ`.
- **Funzioni ST\_.** I trigger R-tree di GDAL chiamano ST_IsEmpty, ST_MinX, ST_MinY, ST_MaxX e ST_MaxY. Il core le registra su ogni connessione SQLite (`gpkg.connect`), altrimenti nessuna scrittura diretta su un layer è possibile.
- **Hash di contenuto.**
  - **Tabelle dello schema.** Righe ordinate per `fid`, tutte le colonne tranne i timestamp, float in esadecimale esatto, geometrie in WKB canonico little-endian senza header GeoPackage.
  - **Impostazioni.** project.toml validato, senza le versioni del software.
  - **Raster.** I byte di ogni file in `rasters/`.
  - **Tabelle escluse.** `layer_styles` di QGIS e le tabelle interne.
- **Migrazioni.** `MIGRATIONS[n]` porta lo schema da n a n+1. Prima del primo passo il core copia project.toml e model.gpkg in `backups/<data>_schema<n>/`. Ogni passo viene registrato in `change_log`.
- **Tipi per mypy.** Per geopandas, pyogrio, shapely e le altre librerie senza informazioni di tipo, mypy le tratta come `Any`. pandas usa `pandas-stubs` 2.x (BSD-3-Clause), solo in sviluppo.

## Alternative scartate

- Un solo layer di tipo `Geometry` per linee e poligoni, che QGIS gestisce male in digitalizzazione.
- Tutte le tabelle della sez. 8.2 subito nello schema v1, cioè anticipare funzioni di milestone successive.
- Hash del file model.gpkg, che cambia anche senza modifiche al modello.
- Scritture solo tramite GDAL, che rendono più lente e meno controllabili operazioni come le migrazioni.

## Conseguenze

- Le prossime migrazioni (M2: `param_zones`, `field_tests`; M3: condizioni al contorno; …) vanno testate su un progetto di schema 1.
- La sezione 8.2 della spec riporta una sintesi dei campi. In caso di differenza prevale lo schema.
